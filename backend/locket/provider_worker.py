"""Durable LunaKey provider worker.

One or more daemon threads poll the ``provider_jobs`` outbox and call LunaKey.
Design notes:

- The worker is completely independent of the legacy Locket account rotator.
- It never holds a SQLite transaction while performing HTTP: the job is claimed
  and committed first, then the network call runs, then a single transaction
  finalizes the job and its order (with lease fencing).
- Retry policy lives here (not in the HTTP client) so idempotency stays under
  our control. Every retry reuses the immutable ``request_id`` and payload.
- Starting is explicit and safe for WSGI/Gunicorn: ``LUNAKEY_WORKER_ENABLED=0``
  disables it (useful for tests and for draining workers). The gunicorn config
  already runs a single process, so an in-process pool is sufficient — no
  Redis/Celery is introduced.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid

from . import db
from . import lunakey_service
from .providers import lunakey

logger = logging.getLogger(__name__)


def _env_flag(name, default="1"):
    return (os.getenv(name, default) or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default, minimum, maximum):
    raw = (os.getenv(name) or "").strip()
    try:
        value = int(raw) if raw else int(default)
    except (TypeError, ValueError):
        value = int(default)
    return max(int(minimum), min(int(maximum), value))


class ProviderWorker:
    def __init__(self, app=None, client_factory=None):
        self.app = app
        self._client_factory = client_factory or (lambda: lunakey.LunaKeyClient())
        self._stop = threading.Event()
        self._threads = []
        self._threads_count = _env_int("LUNAKEY_WORKER_THREADS", 1, 1, 8)
        self.lease_seconds = _env_int("LUNAKEY_LEASE_SECONDS", 120, 15, 900)
        self.poll_seconds = max(0.5, float(os.getenv("LUNAKEY_WORKER_POLL_SECONDS", "2") or 2))
        self._cleanup_interval = 30
        self._last_cleanup = 0.0

    # -- lifecycle ------------------------------------------------------

    @property
    def running(self):
        return any(t.is_alive() for t in self._threads)

    def start(self):
        if not _env_flag("LUNAKEY_WORKER_ENABLED", "1"):
            logger.info("LunaKey provider worker disabled by LUNAKEY_WORKER_ENABLED")
            return False
        if self.running:
            return True
        self._stop.clear()
        for index in range(self._threads_count):
            owner = f"lk-{os.getpid()}-{index}-{uuid.uuid4().hex[:6]}"
            thread = threading.Thread(
                target=self._loop,
                args=(owner,),
                daemon=True,
                name=f"lunakey-provider-{index}",
            )
            self._threads.append(thread)
            thread.start()
        logger.info("LunaKey provider worker started with %s thread(s)", self._threads_count)
        return True

    def stop(self, timeout=5):
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads = []
        return True

    # -- loop -----------------------------------------------------------

    def _loop(self, owner):
        while not self._stop.is_set():
            try:
                processed = self.tick(owner)
            except Exception as exc:  # never let the thread die
                logger.warning("LunaKey worker tick error (%s)", type(exc).__name__)
                processed = False
            if not processed:
                self._stop.wait(self.poll_seconds)

    def tick(self, owner):
        """Run one maintenance + claim + process cycle. Returns True if a job ran."""
        self._maintenance()
        if lunakey_service.is_provider_paused():
            return False
        job = db.claim_provider_job(
            owner,
            lease_seconds=self.lease_seconds,
            replay_window_seconds=lunakey_service.idempotency_window_seconds(),
        )
        if not job:
            return False
        self._process(job, owner)
        return True

    def _maintenance(self):
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        try:
            db.reclaim_expired_provider_leases()
            db.expire_exhausted_provider_jobs()
            db.expire_unreplayable_provider_jobs()
            db.cleanup_expired_provider_lookups()
            lunakey_service.recover_missing_provider_jobs()
        except Exception as exc:
            logger.warning("LunaKey worker maintenance error (%s)", type(exc).__name__)

    # -- processing -----------------------------------------------------

    def _process(self, job, owner):
        order_id = job["order_id"]
        request_id = job["provider_request_id"]
        attempt = job["attempt_count"]
        try:
            payload = json.loads(job["payload_json"])
        except (ValueError, TypeError):
            db.finalize_provider_job_tx(
                job["id"], owner,
                {"status": "failed", "last_error_code": "invalid_payload",
                 "last_error_msg": "Payload job không hợp lệ."},
            )
            return

        # Defensive: the payload hash must match the stored immutable payload.
        expected_hash = lunakey.payload_hash(payload.get("user", ""), payload.get("category", ""), request_id)
        if expected_hash != job["payload_hash"]:
            db.finalize_provider_job_tx(
                job["id"], owner,
                {"status": "failed", "last_error_code": "payload_hash_mismatch",
                 "last_error_msg": "Payload job đã bị thay đổi."},
            )
            return

        client = self._client_factory()
        try:
            result = client.activate(
                payload.get("user", ""), payload.get("category", ""), request_id, confirm=True
            )
        except lunakey.LunaKeyError as exc:
            self._handle_provider_error(job, owner, exc, order_id, attempt)
            return
        except Exception as exc:  # unknown programming/transport error
            logger.warning("LunaKey activate crashed for order %s (%s)", order_id, type(exc).__name__)
            self._schedule_retry_or_reconcile(job, owner, "unexpected_error",
                                              lunakey.public_message("unclear"), order_id, attempt)
            return

        self._finalize_success(job, owner, result, order_id)

    def _handle_provider_error(self, job, owner, exc, order_id, attempt):
        category = getattr(exc, "category", "unclear")
        code = getattr(exc, "code", "unclear")
        message = getattr(exc, "message", lunakey.public_message("unclear"))

        if category == "auth":
            # Pause new sends and require admin action. No loop retry. A 401 is
            # rejected before execution, so an admin retry is always safe.
            lunakey_service.pause_provider("auth")
            self._mark_reconciliation(job, owner, code, message, order_id, last_outcome="rejected")
            self._notify(order_id, "awaiting_reconciliation", message)
            return

        if category == "configuration":
            lunakey_service.pause_provider("configuration")
            self._mark_reconciliation(job, owner, code, message, order_id, last_outcome="rejected")
            self._notify(order_id, "awaiting_reconciliation", message)
            return

        if category == "insufficient_funds":
            # Customer already paid. Keep the order waiting for supply/admin and
            # never ask the customer to pay again. A 402 is a definite rejection
            # (nothing executed upstream), so a retry after top-up is safe.
            self._mark_reconciliation(job, owner, code, message, order_id, last_outcome="rejected")
            self._notify(order_id, "awaiting_reconciliation", message)
            return

        if category in ("invalid_request", "confirmation_required"):
            # Explicit rejection: no blind retry. Order is a confirmed failure so
            # the admin refund path is available.
            db.finalize_provider_job_tx(
                job["id"], owner,
                {"status": "failed", "last_error_code": code, "last_error_msg": message,
                 "last_outcome": "rejected", "lease_owner": None, "lease_expires_at": None},
                order_status="failed",
                order_updates={"provider_last_error_code": code, "provider_last_error_msg": message},
            )
            self._notify(order_id, "failed", message)
            return

        # unavailable / unclear / anything else: retry with backoff, same key,
        # but only within a confirmed idempotency window.
        self._schedule_retry_or_reconcile(job, owner, code, message, order_id, attempt)

    def _schedule_retry_or_reconcile(self, job, owner, code, message, order_id, attempt):
        max_attempts = job.get("max_attempts") or lunakey_service.DEFAULT_MAX_ATTEMPTS
        if attempt >= max_attempts:
            self._mark_reconciliation(job, owner, "retry_exhausted", message, order_id,
                                      last_outcome="sent_unclear")
            self._notify(order_id, "awaiting_reconciliation", message)
            return

        # An unclear outcome means the provider may or may not have executed the
        # request. Re-sending is only safe while a confirmed replay window is
        # open; otherwise it must wait for reconciliation.
        deadline = job.get("replay_deadline")
        now = time.time()
        if deadline is None or deadline <= now:
            self._mark_reconciliation(job, owner, "replay_window_expired", message, order_id,
                                      last_outcome="sent_unclear")
            self._notify(order_id, "awaiting_reconciliation", message)
            return

        next_at = lunakey_service.next_attempt_time(attempt)
        db.finalize_provider_job_tx(
            job["id"], owner,
            {"status": "pending", "last_error_code": code, "last_error_msg": message,
             "next_attempt_at": next_at, "last_outcome": "sent_unclear",
             "lease_owner": None, "lease_expires_at": None},
        )

    def _mark_reconciliation(self, job, owner, code, message, order_id, last_outcome="sent_unclear"):
        db.finalize_provider_job_tx(
            job["id"], owner,
            {"status": "awaiting_reconciliation", "last_error_code": code,
             "last_error_msg": message, "last_outcome": last_outcome,
             "lease_owner": None, "lease_expires_at": None},
            order_updates={"provider_last_error_code": code, "provider_last_error_msg": message},
        )

    def _finalize_success(self, job, owner, result, order_id):
        now = time.time()
        order = db.get_activation_order_by_id(order_id) or {}
        order_updates = {
            "provider_order_code": result.get("order_code"),
            "provider_price_deducted": result.get("price_deducted"),
            "provider_currency": result.get("currency"),
            "provider_balance_snapshot": result.get("remaining_balance"),
            "provider_balance_at": now if result.get("remaining_balance") is not None else None,
            "provider_completed_at": now,
            "provider_last_error_code": None,
            "provider_last_error_msg": None,
        }
        # Merge the activation response profile into the stored lookup profile
        # without losing the UID captured at lookup time.
        merged_profile = None
        try:
            existing_profile = json.loads(order.get("provider_profile_json") or "null")
        except (ValueError, TypeError):
            existing_profile = None
        if isinstance(existing_profile, dict) or isinstance(result.get("profile"), dict):
            merged_profile = dict(existing_profile or {})
            merged_profile.update(result.get("profile") or {})
            order_updates["provider_profile_json"] = json.dumps(merged_profile, ensure_ascii=False)

        # Warranty window is only derived when an explicit shop policy exists.
        warranty_start, warranty_end = lunakey_service.warranty_window(order, start_ts=now)
        if warranty_start is not None:
            order_updates["warranty_started_at"] = warranty_start
            order_updates["warranty_ends_at"] = warranty_end

        job_updates = {
            "status": "succeeded",
            "provider_order_code": result.get("order_code"),
            "last_outcome": "succeeded",
            "last_error_code": None,
            "last_error_msg": None,
            "result_json": json.dumps({
                "order_code": result.get("order_code"),
                "price_deducted": result.get("price_deducted"),
                "currency": result.get("currency"),
                "remaining_balance": result.get("remaining_balance"),
            }, ensure_ascii=False),
            "lease_owner": None,
            "lease_expires_at": None,
        }
        status, err = db.finalize_provider_job_tx(
            job["id"], owner, job_updates,
            order_status="completed", order_updates=order_updates,
        )
        if status != "ok":
            logger.warning("LunaKey finalize rejected for order %s: %s", order_id, status)
            if status == "order_conflict":
                # Upstream confirmed success but the order could not record it;
                # the job now waits for reconciliation. Never announce success.
                self._notify(order_id, "awaiting_reconciliation",
                            "Kích hoạt đã thành công nhưng đơn chưa cập nhật được, cần đối soát.")
            return

        # Optional follow-up lookup for Gold expiry. It must never turn a
        # confirmed success into a failure, so failures are swallowed.
        if _env_flag("LUNAKEY_LOOKUP_AFTER_ACTIVATION", "0"):
            try:
                self._refresh_gold_expiry(order_id, order)
            except Exception as exc:
                logger.info("LunaKey post-activation lookup skipped (%s)", type(exc).__name__)

        self._notify(order_id, "completed", result.get("message") or "Kích hoạt thành công.")

    def _refresh_gold_expiry(self, order_id, order):
        user = order.get("provider_username") or order.get("locket_username")
        if not user:
            return
        profile = self._client_factory().lookup(user)
        if not profile:
            return
        try:
            existing = json.loads(order.get("provider_profile_json") or "null")
        except (ValueError, TypeError):
            existing = None
        merged = dict(existing or {})
        merged.update(profile)
        db.get_conn().execute(
            "UPDATE activation_orders SET provider_profile_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(merged, ensure_ascii=False), time.time(), order_id),
        )
        db.get_conn().commit()

    def _notify(self, order_id, outcome, message):
        try:
            from .notifications import notify_provider_result

            notify_provider_result(order_id, outcome, message)
        except Exception:
            # Notification is strictly best-effort and never affects the job.
            pass
