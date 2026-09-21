"""Regression tests for the LunaKey review findings (2026-09-20).

These tests encode the CORRECT behaviour for the P1/P2 findings:

- P1: retry/reconcile must not (re)trigger a paid upstream call for an order
  that was refunded/cancelled/completed, and must not mutate a job that is
  currently in flight.
- P2: pause must block new checkout, idempotent replay must not depend on the
  lookup token, and unclear retries must respect a confirmed replay window.

Everything runs on a temporary SQLite DB with a mocked provider transport; no
real API call is made.
"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

import requests

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "lunakey-races-flask-secret-123456789"
os.environ["JWT_SECRET"] = "lunakey-races-jwt-secret-1234567890"
os.environ["REFRESH_TOKEN_PEPPER"] = "lunakey-races-pepper-1234567890"
os.environ["ADMIN_EMAIL"] = "races-admin@example.com"
os.environ["ADMIN_USERNAME"] = "races_admin"
os.environ["ADMIN_PASSWORD"] = "races-admin-password-12345"
os.environ["LUNAKEY_API_KEY"] = "lk-races-key-not-real"
os.environ["LUNAKEY_ENABLED"] = "1"
os.environ["LUNAKEY_WORKER_ENABLED"] = "0"
os.environ["TELEGRAM_NOTIFICATIONS_ENABLED"] = "0"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db, lunakey_service  # noqa: E402
from locket.providers import lunakey  # noqa: E402
from locket.provider_worker import ProviderWorker  # noqa: E402
from locket.token_auth import create_access_token, create_token_family  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._text = json.dumps(body) if isinstance(body, (dict, list)) else (body or "")

    @property
    def text(self):
        return self._text

    def json(self):
        return json.loads(self._text)


class FakeTransport:
    def __init__(self):
        self.responses = []
        self.calls = []

    def queue(self, status_code, body):
        self.responses.append(FakeResponse(status_code, body))
        return self

    def queue_error(self, exc):
        self.responses.append(exc)
        return self

    def __call__(self, method, url, *, headers, json_body, timeout):
        self.calls.append({"url": url, "json": json_body})
        if not self.responses:
            raise AssertionError("FakeTransport has no queued response")
        nxt = self.responses.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


def lookup_ok(username="locketuser", uid=None, has_gold=False):
    return {
        "success": True,
        "profile": {
            "username": username,
            "name": "Locket User",
            "avatar": "https://example.com/a.jpg",
            "uid": uid or f"uid-{uuid.uuid4().hex[:8]}",
            "has_gold": has_gold,
            "gold_expiry": None,
            "gold_days_left": 0,
        },
    }


def activate_ok(request_id):
    return {
        "success": True,
        "code": 200,
        "message": "ok",
        "order_code": f"LOK-{uuid.uuid4().hex[:6].upper()}",
        "request_id": request_id,
        "price_deducted": 39000,
        "remaining_balance": 100000,
        "profile": {"username": "locketuser", "name": "Locket User", "avatar": "https://example.com/a.jpg"},
    }


def _bootstrap():
    os.environ["LOCKET_DB"] = temp_db_path
    db.close_conn()
    app = create_app()
    app.config["TESTING"] = True
    conn = db.get_conn()
    now = time.time()
    for uid, name in ((601, "racer1"), (602, "racer2")):
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, 'user', ?)",
            (uid, f"{name}@test.com", name, name.title(), generate_password_hash("password12345"), now),
        )
    conn.commit()
    plan = db.create_plan(
        name="LunaKey Race Plan", slug="lunakey-race-1y", duration_days=365, price_vnd=50000,
        supported_platforms="ios", ios_fulfillment_mode="auto_activation",
        android_fulfillment_mode="disabled", activation_provider="lunakey",
        provider_category="yearly", warranty_months=0, allow_existing_gold=0, is_active=1,
    )
    lunakey_service.resume_provider()
    return app, plan


APP, PLAN = _bootstrap()


class BaseRaceTest(unittest.TestCase):
    app = APP
    plan = PLAN

    def setUp(self):
        lunakey_service.resume_provider()
        # Other tests in this module may hide the plan; keep it sellable by default.
        db.get_conn().execute("UPDATE plans SET is_active = 1 WHERE id = ?", (self.plan,))
        db.get_conn().commit()

    def _set_balance(self, user_id, coins):
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance_coin = excluded.balance_coin, updated_at = excluded.updated_at",
            (user_id, coins, time.time()),
        )
        conn.commit()

    def _create_paid_order(self, user_id=601, coins=100, uid=None):
        username = f"u_{uuid.uuid4().hex[:8]}"
        uid = uid or f"uid-{uuid.uuid4().hex[:10]}"
        self._set_balance(user_id, coins)
        status, res = db.purchase_plan_with_coin_atomic(
            user_id=user_id, plan_id=self.plan, platform="ios",
            fulfillment_mode="auto_activation", locket_username=username,
            idempotency_key=f"race-{uuid.uuid4().hex}",
            provider="lunakey", provider_category="yearly", warranty_months=0,
            provider_uid=uid, provider_username=username,
            provider_profile_json=json.dumps({"username": username, "uid": uid, "has_gold": False}),
        )
        self.assertEqual(status, "ok", res)
        job = lunakey_service.ensure_provider_job_for_order(res["order"]["id"])
        return res["order"]["id"], job

    def _worker(self, transport):
        return ProviderWorker(app=self.app, client_factory=lambda: lunakey.LunaKeyClient(transport=transport))

    def _lease_and_process(self, worker, job_id, owner, attempt_count=1):
        conn = db.get_conn()
        now = time.time()
        window = lunakey_service.idempotency_window_seconds()
        deadline = (now + window) if window > 0 else None
        conn.execute(
            "UPDATE provider_jobs SET status='leased', lease_owner=?, lease_expires_at=?, "
            "attempt_count=?, first_sent_at=COALESCE(first_sent_at, ?), "
            "replay_deadline=COALESCE(replay_deadline, ?), updated_at=? WHERE id=?",
            (owner, now + 60, attempt_count, now, deadline, now, job_id),
        )
        conn.commit()
        worker._process(db.get_provider_job_by_id(job_id), owner)

    def _park_other_jobs(self, job_id):
        """Cancel every other runnable job so claim results are deterministic.

        The DB is shared across the module, so a claim-based test must not
        depend on whatever jobs other tests left behind.
        """
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='cancelled' "
            "WHERE id != ? AND status IN ('pending','leased')",
            (job_id,),
        )
        db.get_conn().commit()

    def _claim_target(self, job_id, owner, window=0):
        """Claim one specific job through the REAL claim path."""
        self._park_other_jobs(job_id)
        claimed = db.claim_provider_job(owner, lease_seconds=60, replay_window_seconds=window)
        self.assertIsNotNone(claimed, "target job was not claimable")
        self.assertEqual(claimed["id"], job_id)
        return claimed

    def _claim_expect_none(self, job_id, owner, window=0):
        self._park_other_jobs(job_id)
        return db.claim_provider_job(owner, lease_seconds=60, replay_window_seconds=window)

    def _assert_no_http_for_order(self, order_id, job_id, request_id):
        """Prove the worker never sends THIS order, scoped by request_id so it
        does not depend on unrelated jobs in the shared DB."""
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='pending', next_attempt_at=NULL, lease_owner=NULL WHERE id=?",
            (job_id,),
        )
        db.get_conn().commit()
        ft = FakeTransport()
        self._worker(ft).tick("w-no-http")
        sent = [c for c in ft.calls if c["json"].get("request_id") == request_id]
        self.assertEqual(sent, [], "worker sent an HTTP call for the target order")
        after = db.get_provider_job_by_id(job_id)
        self.assertNotIn(after["status"], ("leased", "succeeded"))
        return after

    def _assert_no_http_possible(self, order_id, job):
        """A refunded/terminal order's job must never be claimed or sent."""
        self.assertIsNone(self._claim_expect_none(job["id"], "w-after-refund"))
        after = self._assert_no_http_for_order(order_id, job["id"], job["provider_request_id"])
        self.assertEqual(after["status"], "pending")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "refunded")

    def _headers(self, user_id=601):
        client = self.app.test_client()
        csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
        family_id, _, _ = create_token_family(user_id=user_id)
        return {
            "Authorization": f"Bearer {create_access_token(user_id, family_id)}",
            "X-CSRF-Token": csrf,
            "Content-Type": "application/json",
        }, client

    def _admin_headers(self):
        # user 1 is the seed admin provisioned from ADMIN_* env at app boot.
        return self._headers(1)


class RefundRetryRaceTests(BaseRaceTest):
    """P1-a: a refunded order must never be re-sent to the provider."""

    def _fail_then_refund(self, job, owner="w-reject", reason="hoan vi test"):
        """Drive a confirmed provider rejection, then refund the coin order.

        A refund is only permitted once the order is in a failed/queue state, so
        this reproduces the real chain: provider rejects -> order failed ->
        refund -> admin retry.
        """
        ft = FakeTransport().queue(400, {"success": False})
        self._lease_and_process(self._worker(ft), job["id"], owner, attempt_count=1)
        self.assertEqual(db.get_activation_order_by_id(job["order_id"])["status"], "failed")
        self.assertEqual(len(ft.calls), 1)

        refund_status, refund_res = db.refund_activation_order_coin(job["order_id"], reason=reason)
        self.assertEqual(refund_status, "ok", refund_res)
        self.assertEqual(db.get_activation_order_by_id(job["order_id"])["status"], "refunded")
        return ft

    def test_reset_after_refund_is_rejected_and_no_http(self):
        order_id, job = self._create_paid_order()
        self._fail_then_refund(job)

        # Admin retry must be refused for a refunded order.
        reset_status, reset_res = db.reset_provider_job_for_retry(order_id)
        self.assertNotEqual(reset_status, "ok", f"reset should be refused, got {reset_res}")
        self._assert_no_http_possible(order_id, job)

    def test_admin_retry_route_after_refund_is_rejected_and_no_http(self):
        order_id, job = self._create_paid_order()
        self._fail_then_refund(job, owner="w-reject-admin", reason="hoan vi qua admin")
        balance_after_refund = db.get_wallet_balance(601)

        headers, client = self._admin_headers()
        res = client.post(f"/api/admin/provider/jobs/{order_id}/retry", headers=headers, json={})
        self.assertNotEqual(res.status_code, 200, res.get_json())
        self.assertEqual(res.get_json().get("success"), False)

        self._assert_no_http_possible(order_id, job)
        self.assertEqual(db.get_wallet_balance(601), balance_after_refund)

    def test_claim_skips_refunded_order_even_if_pending(self):
        order_id, job = self._create_paid_order()
        self._fail_then_refund(job, owner="w-reject-claim", reason="hoan vi test 2")
        # Simulate a rogue pending job for a refunded order.
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='pending', next_attempt_at=NULL, lease_owner=NULL WHERE id=?",
            (job["id"],),
        )
        db.get_conn().commit()
        self.assertIsNone(self._claim_expect_none(job["id"], "w-claim-guard"))


class ReconcileRaceTests(BaseRaceTest):
    """P1-b: reconciliation must not touch an in-flight or succeeded job."""

    def test_reconcile_rejected_while_leased(self):
        order_id, job = self._create_paid_order()
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='leased', lease_owner='in-flight', lease_expires_at=? WHERE id=?",
            (time.time() + 60, job["id"]),
        )
        db.get_conn().commit()

        status, _ = db.mark_provider_job_reconciled(order_id, outcome="failed", note="manual during flight")
        self.assertNotEqual(status, "ok", "reconcile must be refused while the job is in flight")

        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "leased")
        self.assertEqual(after["lease_owner"], "in-flight")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "paid")

    def test_reconcile_cannot_downgrade_succeeded(self):
        order_id, job = self._create_paid_order()
        ft = FakeTransport().queue(200, activate_ok(job["provider_request_id"]))
        self._lease_and_process(self._worker(ft), job["id"], "w-ok", attempt_count=1)
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")

        status, _ = db.mark_provider_job_reconciled(order_id, outcome="failed", note="wrong conclusion")
        self.assertNotEqual(status, "ok", "reconcile must not downgrade a succeeded job")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "succeeded")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")

    def test_reconcile_refused_while_request_in_flight(self):
        """Block a real worker inside the transport (event, no sleep) and prove
        reconciliation is refused while the paid request is on the wire."""
        order_id, job = self._create_paid_order()
        entered = threading.Event()
        release = threading.Event()

        def transport(method, url, *, headers, json_body, timeout):
            entered.set()
            if not release.wait(timeout=5):
                raise AssertionError("test did not release the in-flight request")
            return FakeResponse(200, activate_ok(job["provider_request_id"]))

        worker = self._worker(transport)
        thread = threading.Thread(
            target=lambda: self._lease_and_process(worker, job["id"], "w-inflight", attempt_count=1)
        )
        thread.start()
        try:
            self.assertTrue(entered.wait(timeout=5), "request never entered the transport")
            status, _ = db.mark_provider_job_reconciled(
                order_id, outcome="failed", note="manual during flight"
            )
            self.assertNotEqual(status, "ok", "reconcile must be refused while the job is in flight")
            self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "leased")
            self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "paid")
        finally:
            release.set()
            thread.join(timeout=5)

        self.assertFalse(thread.is_alive(), "worker thread did not finish")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "succeeded")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")


class PauseGateTests(BaseRaceTest):
    """P2-a: pause must block new lookup/checkout before any money moves."""

    def test_pause_blocks_lookup_and_coin_checkout(self):
        headers, client = self._headers(601)
        self._set_balance(601, 100)
        lunakey_service.pause_provider("test")

        ft = FakeTransport().queue(200, lookup_ok())
        with patch("locket.providers.lunakey._default_transport", ft):
            look = client.post(
                "/api/lunakey/lookup", headers=headers,
                json={"plan_id": self.plan, "username": "pauseduser"},
            )
        self.assertEqual(look.status_code, 503, look.get_json())
        self.assertEqual(look.get_json()["error"], "provider_paused")

        # Even if a confirmation token existed, a new checkout must be blocked.
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO provider_lookups (token_hash, provider, user_id, plan_id, username, uid, profile_json, created_at, expires_at) "
            "VALUES ('pausedhash', 'lunakey', 601, ?, 'pauseduser', 'uid-paused', '{}', ?, ?)",
            (self.plan, time.time(), time.time() + 600),
        )
        conn.commit()
        res = client.post(
            "/api/orders/coin", headers=headers,
            json={"plan_id": self.plan, "platform": "ios", "username": "pauseduser",
                  "lookup_token": "pausedtoken", "idempotency_key": f"pause-{uuid.uuid4().hex}"},
        )
        # token hash mismatch means 409, but the pause gate must trigger first (503)
        self.assertEqual(res.status_code, 503, res.get_json())
        self.assertEqual(db.get_wallet_balance(601), 100)

    def test_pause_does_not_block_reading_existing_order(self):
        order_id, _job = self._create_paid_order()
        headers, client = self._headers(601)
        lunakey_service.pause_provider("test-read")
        res = client.get(f"/api/orders/{order_id}", headers=headers)
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(res.get_json()["order"]["id"], order_id)
        self.assertEqual(res.get_json()["order"]["provider_status"], "processing")


class ReplayIndependenceTests(BaseRaceTest):
    """P2-b: idempotent replay must not depend on token/plan/provider state."""

    def _make_coin_order(self, user_id=601):
        headers, client = self._headers(user_id)
        self._set_balance(user_id, 100)
        # Unique identity per order so repeated calls in one class never collide
        # with the duplicate-in-progress guard.
        username = f"replay_{uuid.uuid4().hex[:8]}"
        uid = f"uid-{uuid.uuid4().hex[:10]}"
        ft = FakeTransport().queue(200, lookup_ok(username=username, uid=uid))
        key = f"replay-{uuid.uuid4().hex}"
        with patch("locket.providers.lunakey._default_transport", ft):
            look = client.post(
                "/api/lunakey/lookup", headers=headers,
                json={"plan_id": self.plan, "username": username},
            ).get_json()
            first = client.post(
                "/api/orders/coin", headers=headers,
                json={"plan_id": self.plan, "platform": "ios", "username": username,
                      "lookup_token": look["lookup_token"], "idempotency_key": key},
            )
        self.assertEqual(first.status_code, 200, first.get_json())
        return client, headers, key, first.get_json()["activation_order_id"], username

    def test_coin_replay_after_token_expiry_returns_original(self):
        client, headers, key, order_id, username = self._make_coin_order()
        # Expire the lookup confirmation and pause the provider.
        db.get_conn().execute("UPDATE provider_lookups SET expires_at = ?", (time.time() - 10,))
        db.get_conn().commit()
        lunakey_service.pause_provider("test-replay")
        self._set_balance(601, 100)

        replay = client.post(
            "/api/orders/coin", headers=headers,
            json={"plan_id": self.plan, "platform": "ios", "username": username,
                  "lookup_token": "expired-token", "idempotency_key": key},
        )
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertEqual(replay.get_json()["activation_order_id"], order_id)
        self.assertTrue(replay.get_json().get("idempotent"))
        self.assertEqual(db.get_wallet_balance(601), 100)

    def test_coin_replay_after_plan_hidden_returns_original(self):
        client, headers, key, order_id, username = self._make_coin_order()
        db.get_conn().execute("UPDATE plans SET is_active = 0 WHERE id = ?", (self.plan,))
        db.get_conn().commit()
        self._set_balance(601, 100)

        replay = client.post(
            "/api/orders/coin", headers=headers,
            json={"plan_id": self.plan, "platform": "ios", "username": username,
                  "lookup_token": "whatever", "idempotency_key": key},
        )
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertEqual(replay.get_json()["activation_order_id"], order_id)
        self.assertEqual(db.get_wallet_balance(601), 100)
        db.get_conn().execute("UPDATE plans SET is_active = 1 WHERE id = ?", (self.plan,))
        db.get_conn().commit()

    def test_replay_with_different_plan_conflicts(self):
        client, headers, key, _order_id, username = self._make_coin_order()
        other_plan = db.create_plan(
            name="Other", slug="lunakey-race-other", duration_days=30, price_vnd=10000,
            supported_platforms="ios", ios_fulfillment_mode="auto_activation",
            android_fulfillment_mode="disabled", activation_provider="lunakey",
            provider_category="yearly", warranty_months=0, is_active=1,
        )
        replay = client.post(
            "/api/orders/coin", headers=headers,
            json={"plan_id": other_plan, "platform": "ios", "username": username,
                  "lookup_token": "whatever", "idempotency_key": key},
        )
        self.assertEqual(replay.status_code, 409, replay.get_json())
        self.assertEqual(replay.get_json()["error"], "idempotency_conflict")

    def test_qr_replay_after_token_expiry_and_pause_returns_original(self):
        headers, client = self._headers(601)
        username = f"qr_{uuid.uuid4().hex[:8]}"
        uid = f"uid-{uuid.uuid4().hex[:10]}"
        ft = FakeTransport().queue(200, lookup_ok(username=username, uid=uid))
        key = f"qr-replay-{uuid.uuid4().hex}"
        with patch("locket.providers.lunakey._default_transport", ft):
            look = client.post(
                "/api/lunakey/lookup", headers=headers,
                json={"plan_id": self.plan, "username": username},
            ).get_json()
            first = client.post(
                "/api/payments/plan", headers=headers,
                json={"plan_id": self.plan, "platform": "ios", "username": username,
                      "lookup_token": look["lookup_token"], "idempotency_key": key},
            )
        self.assertEqual(first.status_code, 200, first.get_json())
        order_id = first.get_json()["activation_order_id"]

        # Expire the lookup token and pause the provider: the stored QR request
        # must still be replayed instead of forcing a new lookup.
        db.get_conn().execute("UPDATE provider_lookups SET expires_at = ?", (time.time() - 10,))
        db.get_conn().commit()
        lunakey_service.pause_provider("test-qr-replay")
        replay = client.post(
            "/api/payments/plan", headers=headers,
            json={"plan_id": self.plan, "platform": "ios", "username": username,
                  "lookup_token": "expired-token", "idempotency_key": key},
        )
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertEqual(replay.get_json()["activation_order_id"], order_id)
        count = db.get_conn().execute(
            "SELECT COUNT(*) AS c FROM activation_orders WHERE user_id=601 AND locket_username=?",
            (username,),
        ).fetchone()["c"]
        self.assertEqual(count, 1, "QR replay created a second activation order")


class ReplayWindowTests(BaseRaceTest):
    """P2-c: unclear retries must respect a confirmed replay window."""

    def test_unclear_without_window_goes_to_reconciliation(self):
        order_id, job = self._create_paid_order()
        ft = FakeTransport().queue_error(requests.exceptions.Timeout("slow"))
        with patch.dict(os.environ, {"LUNAKEY_IDEMPOTENCY_WINDOW_SECONDS": ""}):
            self._lease_and_process(self._worker(ft), job["id"], "w-nowindow", attempt_count=1)
        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "awaiting_reconciliation")
        self.assertIsNotNone(after.get("first_sent_at"))
        self.assertEqual(len(ft.calls), 1)

    def test_unclear_within_window_retries_and_records_deadline(self):
        order_id, job = self._create_paid_order()
        ft = FakeTransport().queue_error(requests.exceptions.Timeout("slow"))
        with patch.dict(os.environ, {"LUNAKEY_IDEMPOTENCY_WINDOW_SECONDS": "3600"}):
            self._lease_and_process(self._worker(ft), job["id"], "w-window", attempt_count=1)
        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "pending")
        self.assertIsNotNone(after.get("first_sent_at"))
        self.assertIsNotNone(after.get("replay_deadline"))

    def test_expired_replay_window_blocks_retry_and_admin_reset(self):
        order_id, job = self._create_paid_order()
        ft = FakeTransport().queue_error(requests.exceptions.Timeout("slow"))
        with patch.dict(os.environ, {"LUNAKEY_IDEMPOTENCY_WINDOW_SECONDS": "3600"}):
            self._lease_and_process(self._worker(ft), job["id"], "w-exp", attempt_count=1)
        # Simulate the deadline having passed.
        db.get_conn().execute(
            "UPDATE provider_jobs SET replay_deadline = ?, next_attempt_at = NULL WHERE id = ?",
            (time.time() - 10, job["id"]),
        )
        db.get_conn().commit()
        db.expire_unreplayable_provider_jobs()
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")

        status, _ = db.reset_provider_job_for_retry(order_id)
        self.assertNotEqual(status, "ok", "reset must respect the expired replay window")

    def test_reset_attempts_cannot_bypass_expired_replay_window(self):
        order_id, job = self._create_paid_order()
        ft = FakeTransport().queue_error(requests.exceptions.Timeout("slow"))
        with patch.dict(os.environ, {"LUNAKEY_IDEMPOTENCY_WINDOW_SECONDS": "3600"}):
            self._lease_and_process(self._worker(ft), job["id"], "w-exp-att", attempt_count=1)
        db.get_conn().execute(
            "UPDATE provider_jobs SET replay_deadline = ? WHERE id = ?",
            (time.time() - 10, job["id"]),
        )
        db.get_conn().commit()

        status, _ = db.reset_provider_job_for_retry(order_id, reset_attempts=True)
        self.assertNotEqual(status, "ok", "reset_attempts must not bypass the replay window guard")

        headers, client = self._admin_headers()
        route = client.post(
            f"/api/admin/provider/jobs/{order_id}/retry",
            headers=headers, json={"reset_attempts": True},
        )
        self.assertNotEqual(route.status_code, 200, route.get_json())
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "pending")


class RetryConsistencyTests(BaseRaceTest):
    """P1-A regression: a retry that succeeds must complete the order and never
    be refundable, and an unclear retry must not fall back to the old failed
    state to allow a refund. Drives the real claim path and the admin route.
    """

    def _reject_once(self, job, owner="w-reject", code=400):
        ft = FakeTransport().queue(code, {"success": False})
        self._lease_and_process(self._worker(ft), job["id"], owner, attempt_count=1)
        self.assertEqual(db.get_activation_order_by_id(job["order_id"])["status"], "failed")
        self.assertEqual(len(ft.calls), 1)
        return ft

    def _ledger_count(self, order_id):
        return db.get_conn().execute(
            "SELECT COUNT(*) AS c FROM wallet_transactions "
            "WHERE reference_type='activation_order' AND reference_id=?",
            (str(order_id),),
        ).fetchone()["c"]

    def test_retry_success_completes_order_and_blocks_refund(self):
        order_id, job = self._create_paid_order()
        self._reject_once(job)
        headers, client = self._admin_headers()
        res = client.post(f"/api/admin/provider/jobs/{order_id}/retry", headers=headers, json={})
        self.assertEqual(res.status_code, 200, res.get_json())
        # Retry re-opens the order out of the refundable failed state.
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "paid")

        balance = db.get_wallet_balance(601)
        ledger_before = self._ledger_count(order_id)
        claimed = self._claim_target(job["id"], "retry-success")
        ft2 = FakeTransport().queue(200, activate_ok(claimed["provider_request_id"]))
        self._worker(ft2)._process(claimed, "retry-success")

        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "succeeded")
        status, _ = db.refund_activation_order_coin(order_id, reason="must be refused")
        self.assertNotEqual(status, "ok")
        self.assertEqual(db.get_wallet_balance(601), balance)
        self.assertEqual(self._ledger_count(order_id), ledger_before)

    def test_retry_timeout_waits_for_reconciliation_and_blocks_refund(self):
        order_id, job = self._create_paid_order()
        self._reject_once(job)
        db.reset_provider_job_for_retry(order_id)
        claimed = self._claim_target(job["id"], "retry-timeout")
        ft = FakeTransport().queue_error(requests.exceptions.Timeout("slow"))
        self._worker(ft)._process(claimed, "retry-timeout")

        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "paid")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")
        status, _ = db.refund_activation_order_coin(order_id, reason="unclear result")
        self.assertNotEqual(status, "ok")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "paid")

    def test_retry_reject_again_allows_exactly_one_refund(self):
        order_id, job = self._create_paid_order()
        self._reject_once(job)
        db.reset_provider_job_for_retry(order_id)
        claimed = self._claim_target(job["id"], "retry-reject")
        ft = FakeTransport().queue(400, {"success": False})
        self._worker(ft)._process(claimed, "retry-reject")

        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "failed")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "failed")
        first, _ = db.refund_activation_order_coin(order_id, reason="confirmed reject")
        self.assertEqual(first, "ok")
        second, _ = db.refund_activation_order_coin(order_id, reason="again")
        self.assertNotEqual(second, "ok")

    def test_refund_and_retry_race_only_one_wins(self):
        order_id, job = self._create_paid_order()
        self._reject_once(job)
        results = {}
        barrier = threading.Barrier(2)

        def do_refund():
            barrier.wait()
            results["refund"] = db.refund_activation_order_coin(order_id, reason="race")[0]

        def do_reset():
            barrier.wait()
            results["reset"] = db.reset_provider_job_for_retry(order_id)[0]

        threads = [threading.Thread(target=do_refund), threading.Thread(target=do_reset)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(10)
        self.assertFalse(
            results.get("refund") == "ok" and results.get("reset") == "ok",
            f"both refund and retry succeeded: {results}",
        )
        self.assertTrue(results.get("refund") == "ok" or results.get("reset") == "ok", results)
        if results.get("refund") == "ok":
            self._assert_no_http_possible(order_id, job)
        else:
            self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "paid")
            self.assertNotEqual(
                db.refund_activation_order_coin(order_id, reason="after reset")[0], "ok"
            )

    def test_finalizer_conflict_preserves_evidence_without_fake_success(self):
        order_id, job = self._create_paid_order()
        # Terminal order the confirmed success cannot be written to.
        db.get_conn().execute("UPDATE activation_orders SET status='refunded' WHERE id=?", (order_id,))
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='leased', lease_owner='w-conflict', "
            "lease_expires_at=?, attempt_count=1, first_sent_at=? WHERE id=?",
            (time.time() + 60, time.time(), job["id"]),
        )
        db.get_conn().commit()

        ft = FakeTransport().queue(200, activate_ok(job["provider_request_id"]))
        self._worker(ft)._process(db.get_provider_job_by_id(job["id"]), "w-conflict")

        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "awaiting_reconciliation")
        self.assertEqual(after["last_outcome"], "succeeded")
        self.assertIn("order_code", after["result_json"] or "")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "refunded")
        self.assertNotEqual(
            db.refund_activation_order_coin(order_id, reason="already refunded")[0], "ok"
        )

    def test_confirmed_success_on_failed_order_recovers_via_reconciliation(self):
        order_id, job = self._create_paid_order()
        db.get_conn().execute("UPDATE activation_orders SET status='failed' WHERE id=?", (order_id,))
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='awaiting_reconciliation', last_outcome='succeeded', "
            "lease_owner=NULL, lease_expires_at=NULL WHERE id=?",
            (job["id"],),
        )
        db.get_conn().commit()

        status, _ = db.mark_provider_job_reconciled(
            order_id, outcome="completed", note="upstream confirmed"
        )
        self.assertEqual(status, "ok")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")
        recovered = db.get_provider_job_by_id(job["id"])
        self.assertEqual(recovered["status"], "succeeded")
        self.assertEqual(recovered["last_outcome"], "succeeded")
        self.assertNotEqual(
            db.refund_activation_order_coin(order_id, reason="after recovery")[0], "ok"
        )


class ReplayGuardAfterCrashTests(BaseRaceTest):
    """P1-B regression: a new send that crashes must not inherit the previous
    attempt's `rejected` outcome to bypass the replay guard. Uses the real
    claim path (never sets leased directly)."""

    def _reject_then_retry_then_crash(self, code, window):
        order_id, job = self._create_paid_order()
        ft = FakeTransport().queue(code, {"success": False})
        self._lease_and_process(self._worker(ft), job["id"], "first", attempt_count=1)
        self.assertEqual(db.get_provider_job_by_id(job["id"])["last_outcome"], "rejected")

        db.reset_provider_job_for_retry(order_id)
        self._claim_target(job["id"], "second", window=window)
        # The new attempt must not carry the old rejected outcome.
        self.assertNotEqual(db.get_provider_job_by_id(job["id"])["last_outcome"], "rejected")

        # Crash after the send may have happened: lease expires, no finalize.
        db.get_conn().execute(
            "UPDATE provider_jobs SET lease_expires_at=? WHERE id=?",
            (time.time() - 1, job["id"]),
        )
        db.get_conn().commit()
        db.reclaim_expired_provider_leases()
        db.expire_unreplayable_provider_jobs()
        return order_id, job

    def test_402_then_retry_crash_without_window_waits_for_reconciliation(self):
        order_id, job = self._reject_then_retry_then_crash(402, 0)
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")
        self.assertIsNone(self._claim_expect_none(job["id"], "third", window=0))
        self._assert_no_http_for_order(order_id, job["id"], job["provider_request_id"])

    def test_400_then_retry_crash_without_window_waits_for_reconciliation(self):
        order_id, job = self._reject_then_retry_then_crash(400, 0)
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")
        self.assertIsNone(self._claim_expect_none(job["id"], "third", window=0))

    def test_retry_crash_with_expired_window_waits(self):
        order_id, job = self._reject_then_retry_then_crash(402, 3600)
        db.get_conn().execute(
            "UPDATE provider_jobs SET replay_deadline=?, next_attempt_at=NULL WHERE id=?",
            (time.time() - 10, job["id"]),
        )
        db.get_conn().commit()
        db.expire_unreplayable_provider_jobs()
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")
        self.assertIsNone(self._claim_expect_none(job["id"], "third", window=3600))

    def test_retry_crash_with_valid_window_replays_same_key(self):
        order_id, job = self._create_paid_order()
        ft = FakeTransport().queue(402, {"success": False})
        self._lease_and_process(self._worker(ft), job["id"], "first", attempt_count=1)
        db.reset_provider_job_for_retry(order_id)
        claimed2 = self._claim_target(job["id"], "second", window=3600)

        db.get_conn().execute(
            "UPDATE provider_jobs SET lease_expires_at=? WHERE id=?",
            (time.time() - 1, job["id"]),
        )
        db.get_conn().commit()
        db.reclaim_expired_provider_leases()
        db.expire_unreplayable_provider_jobs()
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "pending")

        claimed3 = self._claim_target(job["id"], "third", window=3600)
        self.assertEqual(claimed3["provider_request_id"], claimed2["provider_request_id"])
        ft2 = FakeTransport().queue(200, activate_ok(claimed3["provider_request_id"]))
        self._worker(ft2)._process(claimed3, "third")

        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")
        sent = [c["json"]["request_id"] for c in (ft.calls + ft2.calls)]
        self.assertTrue(sent and all(r == job["provider_request_id"] for r in sent), sent)
        purchases = db.get_conn().execute(
            "SELECT COUNT(*) AS c FROM wallet_transactions "
            "WHERE reference_type='activation_order' AND reference_id=? AND type='purchase'",
            (str(order_id),),
        ).fetchone()["c"]
        self.assertEqual(purchases, 1)

    def test_reset_keeps_first_sent_and_deadline(self):
        order_id, job = self._create_paid_order()
        ft = FakeTransport().queue(402, {"success": False})
        with patch.dict(os.environ, {"LUNAKEY_IDEMPOTENCY_WINDOW_SECONDS": "3600"}):
            self._lease_and_process(self._worker(ft), job["id"], "first", attempt_count=1)
        before = db.get_provider_job_by_id(job["id"])
        status, _ = db.reset_provider_job_for_retry(order_id, reset_attempts=True)
        self.assertEqual(status, "ok")
        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["first_sent_at"], before["first_sent_at"])
        self.assertEqual(after["replay_deadline"], before["replay_deadline"])


class ConfirmedSuccessEvidenceTests(BaseRaceTest):
    """Follow-up P1: a job that already carries confirmed upstream success must
    not be downgraded to failed (which would re-open the refund path), and must
    not be re-sent. Reconciliation to completed must still work."""

    def _seed_confirmed_success(self, order_status="failed"):
        order_id, job = self._create_paid_order()
        db.get_conn().execute(
            "UPDATE activation_orders SET status=? WHERE id=?", (order_status, order_id)
        )
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='awaiting_reconciliation', last_outcome='succeeded', "
            "result_json=?, lease_owner=NULL, lease_expires_at=NULL WHERE id=?",
            ('{"order_code":"LOK-CONFIRMED"}', job["id"]),
        )
        db.get_conn().commit()
        return order_id, job

    def _ledger_count(self, order_id):
        return db.get_conn().execute(
            "SELECT COUNT(*) AS c FROM wallet_transactions "
            "WHERE reference_type='activation_order' AND reference_id=?",
            (str(order_id),),
        ).fetchone()["c"]

    def test_reconcile_failed_cannot_downgrade_confirmed_success(self):
        order_id, job = self._seed_confirmed_success()
        balance = db.get_wallet_balance(601)
        ledger = self._ledger_count(order_id)

        status, _ = db.mark_provider_job_reconciled(
            order_id, outcome="failed", note="must be refused"
        )
        self.assertNotEqual(status, "ok", "reconcile must not downgrade succeeded evidence")

        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "awaiting_reconciliation")
        self.assertEqual(after["last_outcome"], "succeeded")
        self.assertIn("LOK-CONFIRMED", after["result_json"] or "")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "failed")

        # Refund is still refused and no money moves.
        self.assertNotEqual(
            db.refund_activation_order_coin(order_id, reason="after downgrade attempt")[0], "ok"
        )
        self.assertEqual(db.get_wallet_balance(601), balance)
        self.assertEqual(self._ledger_count(order_id), ledger)

    def test_reconcile_failed_route_returns_conflict_and_keeps_evidence(self):
        order_id, job = self._seed_confirmed_success()
        headers, client = self._admin_headers()
        res = client.post(
            f"/api/admin/provider/jobs/{order_id}/reconcile",
            headers=headers, json={"outcome": "failed", "note": "review conclusion"},
        )
        self.assertEqual(res.status_code, 409, res.get_json())
        self.assertEqual(res.get_json()["error"], "succeeded_evidence_conflict")

        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "awaiting_reconciliation")
        self.assertEqual(after["last_outcome"], "succeeded")
        self.assertIn("LOK-CONFIRMED", after["result_json"] or "")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "failed")
        self.assertNotEqual(
            db.refund_activation_order_coin(order_id, reason="route downgrade attempt")[0], "ok"
        )

    def test_reconcile_completed_route_recovers_confirmed_success(self):
        order_id, job = self._seed_confirmed_success()
        headers, client = self._admin_headers()
        res = client.post(
            f"/api/admin/provider/jobs/{order_id}/reconcile",
            headers=headers, json={"outcome": "completed", "note": "upstream confirmed"},
        )
        self.assertEqual(res.status_code, 200, res.get_json())

        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")
        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "succeeded")
        self.assertEqual(after["last_outcome"], "succeeded")
        self.assertNotEqual(
            db.refund_activation_order_coin(order_id, reason="after recovery")[0], "ok"
        )

    def test_retry_and_claim_refuse_succeeded_evidence(self):
        order_id, job = self._seed_confirmed_success()
        status, _ = db.reset_provider_job_for_retry(order_id)
        self.assertNotEqual(status, "ok", "retry must refuse a job with succeeded evidence")

        # Even a rogue pending state must not be claimable or sent.
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='pending', next_attempt_at=NULL, lease_owner=NULL WHERE id=?",
            (job["id"],),
        )
        db.get_conn().commit()
        self.assertIsNone(self._claim_expect_none(job["id"], "w-evidence"))
        after = self._assert_no_http_for_order(order_id, job["id"], job["provider_request_id"])
        self.assertEqual(after["last_outcome"], "succeeded")


def _cleanup_temp_db():
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(temp_db_path + suffix)
        except OSError:
            pass


import atexit  # noqa: E402

atexit.register(_cleanup_temp_db)


if __name__ == "__main__":
    unittest.main(verbosity=2)
