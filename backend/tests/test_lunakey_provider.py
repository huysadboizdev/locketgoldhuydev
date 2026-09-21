"""LunaKey provider integration tests.

All provider traffic is mocked through an injected transport; no real network
call is ever made and no real API key is required. Tests cover the client
contract, the durable job outbox (claim/lease/fencing/retry), the purchase
routes, admin operations and the schema migration.
"""

import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

import requests

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "lunakey-test-flask-secret-123456789"
os.environ["JWT_SECRET"] = "lunakey-test-jwt-secret-12345678901"
os.environ["REFRESH_TOKEN_PEPPER"] = "lunakey-test-pepper-1234567890"
os.environ["ADMIN_EMAIL"] = "lunakey-admin@example.com"
os.environ["ADMIN_USERNAME"] = "lunakey_admin"
os.environ["ADMIN_PASSWORD"] = "lunakey-admin-password-12345"
os.environ["LUNAKEY_API_KEY"] = "lk-test-key-must-never-leak-0001"
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

TEST_KEY = os.environ["LUNAKEY_API_KEY"]


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        if isinstance(body, (dict, list)):
            self._text = json.dumps(body)
        elif body is None:
            self._text = ""
        else:
            self._text = str(body)

    @property
    def text(self):
        return self._text

    def json(self):
        return json.loads(self._text)


class FakeTransport:
    """Records requests and replays queued responses (or raises queued errors)."""

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
        self.calls.append({
            "method": method,
            "url": url,
            "headers": dict(headers),
            "json": json_body,
            "timeout": timeout,
        })
        if not self.responses:
            raise AssertionError("FakeTransport has no queued response")
        nxt = self.responses.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


def lookup_ok(username="locketuser", uid="uid-123", has_gold=False, expiry=None):
    return {
        "success": True,
        "profile": {
            "username": username,
            "name": "Locket User",
            "avatar": "https://example.com/a.jpg",
            "uid": uid,
            "has_gold": has_gold,
            "gold_expiry": expiry,
            "gold_days_left": 10 if has_gold else 0,
        },
    }


def activate_ok(request_id, order_code="LOK-TEST-1", price=39000, balance=161000):
    return {
        "success": True,
        "code": 200,
        "message": "Kích hoạt Locket Gold thành công!",
        "order_code": order_code,
        "request_id": request_id,
        "price_deducted": price,
        "remaining_balance": balance,
        "profile": {"username": "locketuser", "name": "Locket User", "avatar": "https://example.com/a.jpg"},
    }


def _bootstrap():
    """Create the shared app/users/plans exactly once for this test module."""
    os.environ["LOCKET_DB"] = temp_db_path
    db.close_conn()
    app = create_app()
    app.config["TESTING"] = True

    conn = db.get_conn()
    now = time.time()
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, role, created_at) "
        "VALUES (501, 'buyer1@test.com', 'buyer1', 'Buyer One', ?, 1, 'user', ?)",
        (generate_password_hash("password12345"), now),
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, role, created_at) "
        "VALUES (502, 'buyer2@test.com', 'buyer2', 'Buyer Two', ?, 1, 'user', ?)",
        (generate_password_hash("password12345"), now),
    )
    conn.commit()

    lk_plan = db.create_plan(
        name="Locket Gold 1 năm (LunaKey)",
        slug="lunakey-1y",
        duration_days=365,
        price_vnd=50000,
        supported_platforms="ios",
        ios_fulfillment_mode="auto_activation",
        android_fulfillment_mode="disabled",
        activation_provider="lunakey",
        provider_category="yearly",
        warranty_months=0,
        warranty_policy=None,
        allow_existing_gold=0,
        is_active=1,
    )
    legacy_plan = db.create_plan(
        name="Legacy iOS",
        slug="lunakey-legacy-ios",
        duration_days=30,
        price_vnd=10000,
        supported_platforms="ios",
        ios_fulfillment_mode="auto_activation",
        android_fulfillment_mode="disabled",
    )
    lunakey_service.resume_provider()
    return app, lk_plan, legacy_plan


APP, LK_PLAN, LEGACY_PLAN = _bootstrap()


class BaseLunaKeyTest(unittest.TestCase):
    # Shared across every test class in this module.
    app = APP
    lk_plan = LK_PLAN
    legacy_plan = LEGACY_PLAN

    def setUp(self):
        lunakey_service.resume_provider()

    # -- helpers --

    def _headers(self, user_id=501):
        client = self.app.test_client()
        csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
        family_id, _, _ = create_token_family(user_id=user_id)
        return {
            "Authorization": f"Bearer {create_access_token(user_id, family_id)}",
            "X-CSRF-Token": csrf,
            "Content-Type": "application/json",
        }, client

    def _set_balance(self, user_id, coins):
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance_coin = excluded.balance_coin, updated_at = excluded.updated_at",
            (user_id, coins, time.time()),
        )
        conn.commit()

    def _create_paid_order(self, user_id=501, username=None, uid=None, coins=100):
        username = username or f"user_{uuid.uuid4().hex[:8]}"
        uid = uid or f"uid-{uuid.uuid4().hex[:10]}"
        self._set_balance(user_id, coins)
        status, res = db.purchase_plan_with_coin_atomic(
            user_id=user_id,
            plan_id=self.lk_plan,
            platform="ios",
            fulfillment_mode="auto_activation",
            locket_username=username,
            idempotency_key=f"test-{uuid.uuid4().hex}",
            provider="lunakey",
            provider_category="yearly",
            warranty_months=0,
            provider_uid=uid,
            provider_username=username,
            provider_profile_json=json.dumps({"username": username, "uid": uid, "has_gold": False}),
        )
        self.assertEqual(status, "ok", res)
        return res["order"]["id"], username, uid

    def _worker(self, transport):
        return ProviderWorker(
            app=self.app,
            client_factory=lambda: lunakey.LunaKeyClient(transport=transport),
        )

    def _lease_and_process(self, worker, job_id, owner, attempt_count=None):
        """Deterministically lease one job and run the worker's process step.

        Bypasses the shared claim queue so tests are independent of any jobs
        left behind by other tests in the same database. Mirrors the columns
        that ``claim_provider_job`` sets (first_sent_at / replay_deadline).
        """
        conn = db.get_conn()
        now = time.time()
        window = lunakey_service.idempotency_window_seconds()
        deadline = (now + window) if window > 0 else None
        if attempt_count is None:
            conn.execute(
                "UPDATE provider_jobs SET status='leased', lease_owner=?, lease_expires_at=?, "
                "attempt_count = attempt_count + 1, first_sent_at=COALESCE(first_sent_at, ?), "
                "replay_deadline=COALESCE(replay_deadline, ?), updated_at=? WHERE id=?",
                (owner, now + 60, now, deadline, now, job_id),
            )
        else:
            conn.execute(
                "UPDATE provider_jobs SET status='leased', lease_owner=?, lease_expires_at=?, "
                "attempt_count=?, first_sent_at=COALESCE(first_sent_at, ?), "
                "replay_deadline=COALESCE(replay_deadline, ?), updated_at=? WHERE id=?",
                (owner, now + 60, attempt_count, now, deadline, now, job_id),
            )
        conn.commit()
        leased = db.get_provider_job_by_id(job_id)
        worker._process(leased, owner)
        return leased

    def _park_other_jobs(self, job_id):
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='cancelled' "
            "WHERE id != ? AND status IN ('pending','leased')",
            (job_id,),
        )
        db.get_conn().commit()

    def _claim_target(self, job_id, owner, window=0):
        """Claim one specific job via the REAL claim path, independent of any
        jobs left behind by other tests in the shared DB."""
        self._park_other_jobs(job_id)
        claimed = db.claim_provider_job(owner, lease_seconds=60, replay_window_seconds=window)
        self.assertIsNotNone(claimed, "target job was not claimable")
        self.assertEqual(claimed["id"], job_id)
        return claimed

    def _claim_expect_none(self, job_id, owner, window=0):
        self._park_other_jobs(job_id)
        return db.claim_provider_job(owner, lease_seconds=60, replay_window_seconds=window)


class ProviderClientTests(BaseLunaKeyTest):
    def test_lookup_success_normalizes_profile(self):
        ft = FakeTransport().queue(200, lookup_ok(uid="u1"))
        client = lunakey.LunaKeyClient(transport=ft)
        profile = client.lookup("someone")
        self.assertEqual(profile["uid"], "u1")
        self.assertFalse(profile["has_gold"])
        # The key is sent only in the auth header; it never appears in the
        # normalized profile returned to callers.
        self.assertNotIn(TEST_KEY, json.dumps(profile))
        self.assertEqual(ft.calls[0]["headers"]["X-API-Key"], TEST_KEY)

    def test_lookup_not_found_is_invalid_request(self):
        ft = FakeTransport().queue(200, {"success": False, "message": "not found"})
        client = lunakey.LunaKeyClient(transport=ft)
        with self.assertRaises(lunakey.LunaKeyInvalidRequestError):
            client.lookup("nobody")

    def test_activate_success(self):
        ft = FakeTransport().queue(200, activate_ok("req-1"))
        client = lunakey.LunaKeyClient(transport=ft)
        res = client.activate("u", "yearly", "req-1")
        self.assertTrue(res["success"])
        self.assertEqual(res["order_code"], "LOK-TEST-1")
        self.assertEqual(res["currency"], "VND")
        # Both idempotency header and request_id are sent.
        self.assertEqual(ft.calls[0]["headers"]["Idempotency-Key"], "req-1")
        self.assertEqual(ft.calls[0]["json"]["request_id"], "req-1")

    def test_activate_success_false_is_unclear(self):
        ft = FakeTransport().queue(200, {"success": False, "request_id": "req-2"})
        with self.assertRaises(lunakey.LunaKeyUnclearError):
            lunakey.LunaKeyClient(transport=ft).activate("u", "yearly", "req-2")

    def test_activate_missing_order_code_is_unclear(self):
        body = activate_ok("req-3")
        body.pop("order_code")
        ft = FakeTransport().queue(200, body)
        with self.assertRaises(lunakey.LunaKeyUnclearError):
            lunakey.LunaKeyClient(transport=ft).activate("u", "yearly", "req-3")

    def test_activate_request_id_mismatch_is_unclear(self):
        ft = FakeTransport().queue(200, activate_ok("other-id"))
        with self.assertRaises(lunakey.LunaKeyUnclearError):
            lunakey.LunaKeyClient(transport=ft).activate("u", "yearly", "req-4")

    def test_http_status_mapping(self):
        cases = [
            (400, lunakey.LunaKeyInvalidRequestError),
            (401, lunakey.LunaKeyAuthError),
            (402, lunakey.LunaKeyInsufficientFundsError),
            (409, lunakey.LunaKeyConfirmationRequiredError),
            (502, lunakey.LunaKeyUnavailableError),
            (500, lunakey.LunaKeyUnavailableError),
        ]
        for status, exc_type in cases:
            with self.subTest(status=status):
                ft = FakeTransport().queue(status, {"success": False})
                with self.assertRaises(exc_type):
                    lunakey.LunaKeyClient(transport=ft).activate("u", "yearly", f"req-{status}")

    def test_timeout_and_bad_json_are_unclear(self):
        ft = FakeTransport().queue_error(requests.exceptions.Timeout("slow"))
        with self.assertRaises(lunakey.LunaKeyUnclearError):
            lunakey.LunaKeyClient(transport=ft).activate("u", "yearly", "req-t")

        ft2 = FakeTransport().queue(200, "<html>oops</html>")
        with self.assertRaises(lunakey.LunaKeyUnclearError):
            lunakey.LunaKeyClient(transport=ft2).activate("u", "yearly", "req-h")

    def test_redirect_is_not_followed_and_does_not_leak_key(self):
        ft = FakeTransport().queue(302, {"success": True})
        with self.assertRaises(lunakey.LunaKeyUnavailableError):
            lunakey.LunaKeyClient(transport=ft).activate("u", "yearly", "req-r")

    def test_unknown_category_is_rejected(self):
        ft = FakeTransport()
        with self.assertRaises(lunakey.LunaKeyConfigError):
            lunakey.LunaKeyClient(transport=ft).activate("u", "monthly", "req-c")
        self.assertEqual(ft.calls, [])

    def test_category_registry_only_confirms_documented_values(self):
        self.assertEqual(lunakey.resolve_provider_category("yearly"), "yearly")
        self.assertEqual(lunakey.resolve_provider_category(" YEARLY "), "yearly")
        # Never invent monthly/quarterly: unconfirmed values resolve to None.
        self.assertIsNone(lunakey.resolve_provider_category("month"))
        self.assertIsNone(lunakey.resolve_provider_category("monthly"))
        self.assertIsNone(lunakey.resolve_provider_category("1month"))
        self.assertIsNone(lunakey.resolve_provider_category(""))
        self.assertIsNone(lunakey.resolve_provider_category(None))

    def test_activate_maps_internal_category_to_provider_value(self):
        ft = FakeTransport().queue(200, activate_ok("req-map"))
        with patch.object(lunakey, "CATEGORY_ALIASES", {"yearly": "yearly", "gold_year": "yearly"}):
            lunakey.LunaKeyClient(transport=ft).activate("u", "gold_year", "req-map")
        self.assertEqual(ft.calls[0]["json"]["category"], "yearly")

    def test_missing_key_raises_config_error_without_key(self):
        with patch.dict(os.environ, {"LUNAKEY_API_KEY": ""}):
            with self.assertRaises(lunakey.LunaKeyConfigError) as ctx:
                lunakey.LunaKeyClient().lookup("u")
            self.assertNotIn("lk-test", str(ctx.exception))

    def test_key_never_appears_in_exception_message(self):
        ft = FakeTransport().queue_error(requests.exceptions.ConnectionError("boom"))
        try:
            lunakey.LunaKeyClient(transport=ft).lookup("u")
        except lunakey.LunaKeyError as exc:
            self.assertNotIn(TEST_KEY, str(exc))
            self.assertNotIn(TEST_KEY, json.dumps(exc.as_dict()))
        else:
            self.fail("expected error")

    def test_no_network_at_import(self):
        # Importing the module must not perform I/O; a client built without a
        # transport only touches the network when a method is called.
        client = lunakey.LunaKeyClient()
        self.assertIsNone(client._transport)


class ProviderPlanReadinessTests(BaseLunaKeyTest):
    def test_plan_readiness_reasons(self):
        base = {
            "id": 1, "activation_provider": "lunakey", "provider_category": "yearly",
            "warranty_months": 0, "warranty_policy": None,
        }
        self.assertEqual(lunakey_service.plan_readiness(base), [])

        missing_cat = dict(base, provider_category=None)
        self.assertIn("provider_category_missing", lunakey_service.plan_readiness(missing_cat))

        warranty = dict(base, warranty_months=6, warranty_policy=None)
        self.assertIn("warranty_policy_missing", lunakey_service.plan_readiness(warranty))

        with patch.dict(os.environ, {"LUNAKEY_API_KEY": ""}):
            self.assertIn("api_key_missing", lunakey_service.plan_readiness(base))

        with patch.dict(os.environ, {"LUNAKEY_ENABLED": "0"}):
            self.assertIn("provider_disabled", lunakey_service.plan_readiness(base))

    def test_legacy_plan_is_always_sellable(self):
        self.assertEqual(lunakey_service.plan_readiness({"activation_provider": "legacy_locket"}), [])

    def test_plan_readiness_flags_unsupported_category(self):
        base = {
            "id": 1, "activation_provider": "lunakey", "provider_category": "yearly",
            "warranty_months": 0, "warranty_policy": None,
        }
        self.assertEqual(lunakey_service.plan_readiness(base), [])
        self.assertIn(
            "provider_category_unsupported",
            lunakey_service.plan_readiness(dict(base, provider_category="month")),
        )
        self.assertIn(
            "provider_category_missing",
            lunakey_service.plan_readiness(dict(base, provider_category="")),
        )


class ProviderLookupConfirmationTests(BaseLunaKeyTest):
    def test_lookup_accepts_locket_link_and_at_prefix(self):
        plan = db.get_plan_by_id(self.lk_plan, public=False)
        cases = [
            ("someone", "someone"),
            ("@Someone", "Someone"),
            ("https://locket.cam/Someone", "Someone"),
            ("https://locket.cam/Someone?ref=1", "Someone"),
            ("https://locket.camera/links/Someone", "Someone"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                ft = FakeTransport().queue(200, lookup_ok(uid="uid-link"))
                token, _profile = lunakey_service.lookup_and_confirm(
                    501, plan, raw, client=lunakey.LunaKeyClient(transport=ft)
                )
                self.assertTrue(token)
                self.assertEqual(ft.calls[0]["json"]["user"], expected)

    def test_lookup_confirmation_roundtrip_and_reuse(self):
        ft = FakeTransport().queue(200, lookup_ok(uid="uid-conf"))
        plan = db.get_plan_by_id(self.lk_plan, public=False)
        token, profile = lunakey_service.lookup_and_confirm(501, plan, "someone", client=lunakey.LunaKeyClient(transport=ft))
        self.assertEqual(profile["uid"], "uid-conf")

        row = lunakey_service.consume_confirmation(501, self.lk_plan, token)
        self.assertIsNotNone(row)
        self.assertEqual(row["uid"], "uid-conf")
        # Reusable by owner until expiry (idempotent retry support).
        self.assertIsNotNone(lunakey_service.consume_confirmation(501, self.lk_plan, token))

    def test_lookup_confirmation_rejects_wrong_owner_or_plan(self):
        ft = FakeTransport().queue(200, lookup_ok(uid="uid-owner"))
        plan = db.get_plan_by_id(self.lk_plan, public=False)
        token, _ = lunakey_service.lookup_and_confirm(501, plan, "someone", client=lunakey.LunaKeyClient(transport=ft))
        self.assertIsNone(lunakey_service.consume_confirmation(502, self.lk_plan, token))
        self.assertIsNone(lunakey_service.consume_confirmation(501, self.legacy_plan, token))
        self.assertIsNone(lunakey_service.consume_confirmation(501, self.lk_plan, "not-a-token"))

    def test_lookup_confirmation_expired(self):
        ft = FakeTransport().queue(200, lookup_ok(uid="uid-exp"))
        plan = db.get_plan_by_id(self.lk_plan, public=False)
        token, _ = lunakey_service.lookup_and_confirm(501, plan, "someone", client=lunakey.LunaKeyClient(transport=ft))
        db.get_conn().execute("UPDATE provider_lookups SET expires_at = ?", (time.time() - 10,))
        db.get_conn().commit()
        self.assertIsNone(lunakey_service.consume_confirmation(501, self.lk_plan, token))


class ProviderJobTests(BaseLunaKeyTest):
    def test_job_creation_is_idempotent_and_payload_is_immutable(self):
        order_id, username, _uid = self._create_paid_order()
        job1 = lunakey_service.ensure_provider_job_for_order(order_id)
        job2 = lunakey_service.ensure_provider_job_for_order(order_id)
        self.assertEqual(job1["id"], job2["id"])
        self.assertEqual(job1["provider_request_id"], job2["provider_request_id"])
        original_payload = job1["payload_json"]

        # Editing the plan/username after purchase must not change the payload.
        db.get_conn().execute("UPDATE activation_orders SET locket_username = 'changed' WHERE id = ?", (order_id,))
        db.get_conn().commit()
        job3 = lunakey_service.ensure_provider_job_for_order(order_id)
        self.assertEqual(job3["payload_json"], original_payload)

    def test_claim_is_single_winner(self):
        # Isolate from jobs left by other tests so the claim is deterministic.
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='cancelled' WHERE status IN ('pending','leased')"
        )
        db.get_conn().commit()
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        claimed = db.claim_provider_job("owner-A", lease_seconds=60)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], job["id"])
        self.assertEqual(db.claim_provider_job("owner-B", lease_seconds=60), None)

    def test_expired_lease_is_reclaimed_and_stale_owner_cannot_finalize(self):
        order_id, _u, _i = self._create_paid_order()
        job_id = lunakey_service.ensure_provider_job_for_order(order_id)["id"]
        # A confirmed replay window is required before a job that may already
        # have been sent can be leased again.
        job = self._claim_target(job_id, "owner-A", window=3600)
        db.get_conn().execute("UPDATE provider_jobs SET lease_expires_at = ? WHERE id = ?", (time.time() - 1, job["id"]))
        db.get_conn().commit()
        self.assertGreaterEqual(db.reclaim_expired_provider_leases(), 1)

        job_b = self._claim_target(job_id, "owner-B", window=3600)
        # Old owner must not be able to overwrite the result.
        status, _ = db.finalize_provider_job_tx(
            job["id"], "owner-A",
            {"status": "succeeded"}, order_status="completed",
        )
        self.assertEqual(status, "stale_lease")
        # Current owner can.
        status_b, _ = db.finalize_provider_job_tx(
            job["id"], "owner-B",
            {"status": "succeeded"}, order_status="completed",
        )
        self.assertEqual(status_b, "ok")

    def test_expired_lease_without_confirmed_window_waits_for_reconciliation(self):
        order_id, _u, _i = self._create_paid_order()
        job_id = lunakey_service.ensure_provider_job_for_order(order_id)["id"]
        job = self._claim_target(job_id, "owner-A")
        db.get_conn().execute("UPDATE provider_jobs SET lease_expires_at = ? WHERE id = ?", (time.time() - 1, job["id"]))
        db.get_conn().commit()
        self.assertGreaterEqual(db.reclaim_expired_provider_leases(), 1)

        # No confirmed window: a job whose send is unclear must not be re-sent.
        db.expire_unreplayable_provider_jobs()
        after = db.get_provider_job_by_id(job_id)
        self.assertEqual(after["status"], "awaiting_reconciliation")
        self.assertIsNone(self._claim_expect_none(job_id, "owner-B"))


class ProviderWorkerTests(BaseLunaKeyTest):
    def test_success_finalizes_order_and_job(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        ft = FakeTransport().queue(200, activate_ok(job["provider_request_id"]))
        worker = self._worker(ft)
        self._lease_and_process(worker, job["id"], "w1")

        refreshed_job = db.get_provider_job_by_id(job["id"])
        self.assertEqual(refreshed_job["status"], "succeeded")
        order = db.get_activation_order_by_id(order_id)
        self.assertEqual(order["status"], "completed")
        self.assertEqual(order["provider_order_code"], "LOK-TEST-1")
        self.assertEqual(order["provider_price_deducted"], 39000)
        self.assertEqual(order["provider_currency"], "VND")
        self.assertIsNotNone(order["provider_completed_at"])

    def test_no_sqlite_transaction_held_during_http(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        observed = {}

        def transport(method, url, *, headers, json_body, timeout):
            # A concurrent writer on a separate connection must not be blocked.
            other = sqlite3.connect(temp_db_path, timeout=0.5)
            try:
                other.execute("INSERT INTO processing_times (duration, completed_at) VALUES (1, 1)")
                other.commit()
                observed["locked"] = False
            except sqlite3.OperationalError:
                observed["locked"] = True
            finally:
                other.close()
            return FakeResponse(200, activate_ok(job["provider_request_id"]))

        worker = self._worker(transport)
        self._lease_and_process(worker, job["id"], "w-nolock")
        self.assertFalse(observed.get("locked"), "HTTP call held a SQLite write transaction")

    def test_timeout_retries_with_same_request_id_and_payload(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        ft = FakeTransport()
        ft.queue_error(requests.exceptions.Timeout("slow"))
        ft.queue(200, activate_ok(job["provider_request_id"]))
        worker = self._worker(ft)

        # Retrying an unclear outcome is only allowed inside a confirmed window.
        with patch.dict(os.environ, {"LUNAKEY_IDEMPOTENCY_WINDOW_SECONDS": "3600"}):
            self._lease_and_process(worker, job["id"], "w-retry", attempt_count=1)
            mid = db.get_provider_job_by_id(job["id"])
            self.assertEqual(mid["status"], "pending")
            self.assertIsNotNone(mid["next_attempt_at"])

            self._lease_and_process(worker, job["id"], "w-retry", attempt_count=2)
        self.assertEqual(len(ft.calls), 2)
        first, second = ft.calls
        self.assertEqual(first["headers"]["Idempotency-Key"], second["headers"]["Idempotency-Key"])
        self.assertEqual(first["json"], second["json"])
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "succeeded")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")

    def test_retry_exhaustion_moves_to_reconciliation(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        db.get_conn().execute("UPDATE provider_jobs SET max_attempts = 1 WHERE id = ?", (job["id"],))
        db.get_conn().commit()
        ft = FakeTransport().queue_error(requests.exceptions.Timeout("slow"))
        worker = self._worker(ft)
        self._lease_and_process(worker, job["id"], "w-exhaust", attempt_count=1)

        refreshed = db.get_provider_job_by_id(job["id"])
        self.assertEqual(refreshed["status"], "awaiting_reconciliation")
        self.assertEqual(refreshed["last_error_code"], "retry_exhausted")
        # Customer's paid order is untouched, no auto refund.
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "paid")

    def test_402_keeps_paid_order_and_allows_admin_retry_same_key(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        ft = FakeTransport().queue(402, {"success": False})
        worker = self._worker(ft)
        self._lease_and_process(worker, job["id"], "w-402", attempt_count=1)

        refreshed = db.get_provider_job_by_id(job["id"])
        self.assertEqual(refreshed["status"], "awaiting_reconciliation")
        self.assertEqual(refreshed["last_error_code"], "insufficient_funds")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "paid")

        status, _ = db.reset_provider_job_for_retry(order_id)
        self.assertEqual(status, "ok")
        retried = db.get_provider_job_by_id(job["id"])
        self.assertEqual(retried["provider_request_id"], job["provider_request_id"])

        ft.queue(200, activate_ok(job["provider_request_id"]))
        self._lease_and_process(worker, job["id"], "w-402", attempt_count=2)
        self.assertEqual(ft.calls[0]["json"]["request_id"], ft.calls[1]["json"]["request_id"])
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")

    def test_401_pauses_provider_and_requires_admin(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        ft = FakeTransport().queue(401, {"success": False})
        worker = self._worker(ft)
        self._lease_and_process(worker, job["id"], "w-401", attempt_count=1)

        self.assertTrue(lunakey_service.is_provider_paused())
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")
        # While paused, no new claims happen.
        self.assertFalse(worker.tick("w-401b"))
        lunakey_service.resume_provider()

    def test_invalid_request_marks_confirmed_failure(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        ft = FakeTransport().queue(400, {"success": False})
        self._lease_and_process(self._worker(ft), job["id"], "w-400", attempt_count=1)
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "failed")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "failed")

    def _lease_job(self, job_id, owner):
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='leased', lease_owner=?, lease_expires_at=?, "
            "attempt_count=1, first_sent_at=? WHERE id=?",
            (owner, time.time() + 60, time.time(), job_id),
        )
        db.get_conn().commit()
        return db.get_provider_job_by_id(job_id)

    def test_configuration_error_is_deterministic_failure_not_reconciliation(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        leased = self._lease_job(job["id"], "w-cfg")
        worker = self._worker(FakeTransport())
        # unknown_category is raised BEFORE any network send.
        err = lunakey.LunaKeyConfigError("unknown_category", "Category chưa xác nhận")
        worker._handle_provider_error(leased, "w-cfg", err, order_id, 1)

        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "failed")
        self.assertEqual(after["last_outcome"], "rejected")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "failed")
        # Order-specific config error must not pause the whole provider.
        self.assertFalse(lunakey_service.is_provider_paused())

    def test_provider_wide_configuration_error_pauses_provider(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        leased = self._lease_job(job["id"], "w-cfg2")
        worker = self._worker(FakeTransport())
        err = lunakey.LunaKeyConfigError("provider_not_configured", "Thiếu API key")
        worker._handle_provider_error(leased, "w-cfg2", err, order_id, 1)

        self.assertTrue(lunakey_service.is_provider_paused())
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "failed")
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "failed")
        lunakey_service.resume_provider()

    def test_success_is_not_downgraded_by_post_lookup_failure(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        ft = FakeTransport()
        ft.queue(200, activate_ok(job["provider_request_id"]))
        ft.queue_error(requests.exceptions.Timeout("lookup slow"))
        with patch.dict(os.environ, {"LUNAKEY_LOOKUP_AFTER_ACTIVATION": "1"}):
            self._lease_and_process(self._worker(ft), job["id"], "w-postlookup", attempt_count=1)
        self.assertEqual(db.get_activation_order_by_id(order_id)["status"], "completed")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "succeeded")

    def test_crash_between_paid_and_enqueue_recovers(self):
        order_id, _u, _i = self._create_paid_order()
        # Simulate a crash: paid order with no job row.
        self.assertIsNone(db.get_provider_job_by_order(order_id))
        created = lunakey_service.recover_missing_provider_jobs()
        self.assertGreaterEqual(created, 1)
        self.assertIsNotNone(db.get_provider_job_by_order(order_id))

    def test_duplicate_uid_in_flight_is_blocked(self):
        uid = f"uid-dup-{uuid.uuid4().hex[:8]}"
        self._create_paid_order(uid=uid)
        self._set_balance(501, 100)
        status, res = db.purchase_plan_with_coin_atomic(
            user_id=501, plan_id=self.lk_plan, platform="ios",
            fulfillment_mode="auto_activation", locket_username="other-name",
            idempotency_key=f"dup-{uuid.uuid4().hex}",
            provider="lunakey", provider_category="yearly", warranty_months=0,
            provider_uid=uid, provider_username="other-name",
        )
        self.assertEqual(status, "gold_blocked", res)


class ProviderRouteTests(BaseLunaKeyTest):
    def test_lookup_route_requires_auth(self):
        client = self.app.test_client()
        res = client.post("/api/lunakey/lookup", json={"plan_id": self.lk_plan, "username": "x"})
        self.assertEqual(res.status_code, 401)

    def test_lookup_route_rejects_legacy_plan(self):
        headers, client = self._headers()
        res = client.post(
            "/api/lunakey/lookup",
            headers=headers,
            json={"plan_id": self.legacy_plan, "username": "x"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"], "invalid_provider")

    def test_lookup_route_success_returns_token_and_no_secret(self):
        headers, client = self._headers()
        ft = FakeTransport().queue(200, lookup_ok(uid="uid-route"))
        with patch("locket.providers.lunakey._default_transport", ft):
            res = client.post(
                "/api/lunakey/lookup",
                headers=headers,
                json={"plan_id": self.lk_plan, "username": "someone"},
            )
        self.assertEqual(res.status_code, 200, res.get_json())
        body = res.get_json()
        self.assertTrue(body["success"])
        self.assertTrue(body["lookup_token"])
        self.assertNotIn(TEST_KEY, json.dumps(body))

    def test_lookup_route_accepts_locket_profile_link(self):
        headers, client = self._headers()
        ft = FakeTransport().queue(200, lookup_ok(uid="uid-link"))
        with patch("locket.providers.lunakey._default_transport", ft):
            res = client.post(
                "/api/lunakey/lookup",
                headers=headers,
                json={"plan_id": self.lk_plan, "username": "https://locket.cam/Someone"},
            )
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(ft.calls[0]["json"]["user"], "Someone")

    def test_coin_purchase_end_to_end_and_redaction(self):
        headers, client = self._headers(501)
        self._set_balance(501, 100)
        ft = FakeTransport().queue(200, lookup_ok(username="routeuser", uid="uid-route-coin"))
        with patch("locket.providers.lunakey._default_transport", ft):
            look = client.post(
                "/api/lunakey/lookup",
                headers=headers,
                json={"plan_id": self.lk_plan, "username": "routeuser"},
            ).get_json()
            res = client.post(
                "/api/orders/coin",
                headers=headers,
                json={
                    "plan_id": self.lk_plan,
                    "platform": "ios",
                    "username": "routeuser",
                    "lookup_token": look["lookup_token"],
                    "idempotency_key": "route-coin-1",
                },
            )
        self.assertEqual(res.status_code, 200, res.get_json())
        body = res.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["fulfillment_mode"], "auto_activation")
        order_id = body["activation_order_id"]

        order = db.get_activation_order_by_id(order_id)
        self.assertEqual(order["activation_provider_snapshot"], "lunakey")
        self.assertEqual(order["provider_uid"], "uid-route-coin")
        self.assertEqual(order["status"], "paid")
        self.assertIsNotNone(db.get_provider_job_by_order(order_id))
        self.assertEqual(db.get_wallet_balance(501), 50)

        # Customer view must not leak internal cost/upstream/error fields.
        detail = client.get(f"/api/orders/{order_id}", headers=headers).get_json()
        safe = detail["order"]
        for field in ("provider_price_deducted", "provider_balance_snapshot", "provider_order_code",
                      "provider_last_error_msg", "provider_uid", "provider_profile_json",
                      "provider_request_id", "provider_currency", "provider_balance_at"):
            self.assertNotIn(field, safe)
        self.assertEqual(safe["provider"], "lunakey")
        self.assertEqual(safe["provider_status"], "processing")
        self.assertIsNone(detail["queue"])

    def test_coin_purchase_without_lookup_token_is_blocked(self):
        headers, client = self._headers(501)
        self._set_balance(501, 100)
        res = client.post(
            "/api/orders/coin",
            headers=headers,
            json={"plan_id": self.lk_plan, "platform": "ios", "username": "x",
                  "idempotency_key": "no-token-1"},
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "lookup_confirmation_required")

    def test_coin_purchase_blocked_for_unsupported_category_before_debit(self):
        bad_plan = db.create_plan(
            name="Bad category", slug=f"bad-cat-{uuid.uuid4().hex[:6]}", duration_days=30,
            price_vnd=10000, supported_platforms="ios", ios_fulfillment_mode="auto_activation",
            android_fulfillment_mode="disabled", activation_provider="lunakey",
            provider_category="month", warranty_months=0, is_active=1,
        )
        headers, client = self._headers(501)
        self._set_balance(501, 100)
        res = client.post(
            "/api/orders/coin",
            headers=headers,
            json={"plan_id": bad_plan, "platform": "ios", "username": "x",
                  "idempotency_key": f"bad-{uuid.uuid4().hex}"},
        )
        self.assertEqual(res.status_code, 409, res.get_json())
        self.assertEqual(res.get_json()["error"], "provider_category_unsupported")
        # No Coin was debited and no order/job was created.
        self.assertEqual(db.get_wallet_balance(501), 100)
        self.assertEqual(
            db.get_conn().execute(
                "SELECT COUNT(*) AS c FROM activation_orders WHERE plan_id = ?", (bad_plan,)
            ).fetchone()["c"],
            0,
        )

    def test_admin_plans_list_reports_unsupported_category(self):
        bad_plan = db.create_plan(
            name="Bad category admin", slug=f"bad-cat-adm-{uuid.uuid4().hex[:6]}", duration_days=30,
            price_vnd=10000, supported_platforms="ios", ios_fulfillment_mode="auto_activation",
            android_fulfillment_mode="disabled", activation_provider="lunakey",
            provider_category="month", warranty_months=0, is_active=1,
        )
        headers, client = self._headers(1)
        res = client.get("/api/admin/plans", headers=headers)
        plans = {p["id"]: p for p in res.get_json()["plans"]}
        self.assertFalse(plans[bad_plan]["sellable"])
        self.assertIn("provider_category_unsupported", plans[bad_plan]["readiness_issues"])

    def test_forged_uid_in_body_is_ignored(self):
        headers, client = self._headers(501)
        self._set_balance(501, 100)
        ft = FakeTransport().queue(200, lookup_ok(username="canon", uid="uid-canon"))
        with patch("locket.providers.lunakey._default_transport", ft):
            token = client.post(
                "/api/lunakey/lookup",
                headers=headers,
                json={"plan_id": self.lk_plan, "username": "canon"},
            ).get_json()["lookup_token"]
            res = client.post(
                "/api/orders/coin",
                headers=headers,
                json={"plan_id": self.lk_plan, "platform": "ios", "username": "canon",
                      "uid": "attacker-supplied", "lookup_token": token,
                      "idempotency_key": "forged-uid-1"},
            )
        self.assertEqual(res.status_code, 200, res.get_json())
        order = db.get_activation_order_by_id(res.get_json()["activation_order_id"])
        self.assertEqual(order["provider_uid"], "uid-canon")

    def test_existing_gold_is_blocked_until_policy_confirmed(self):
        headers, client = self._headers(501)
        self._set_balance(501, 100)
        ft = FakeTransport().queue(200, lookup_ok(username="golduser", uid="uid-gold", has_gold=True))
        with patch("locket.providers.lunakey._default_transport", ft):
            token = client.post(
                "/api/lunakey/lookup",
                headers=headers,
                json={"plan_id": self.lk_plan, "username": "golduser"},
            ).get_json()["lookup_token"]
            res = client.post(
                "/api/orders/coin",
                headers=headers,
                json={"plan_id": self.lk_plan, "platform": "ios", "username": "golduser",
                      "lookup_token": token, "idempotency_key": "gold-1"},
            )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "existing_gold_not_supported")

    def test_double_click_charges_once(self):
        headers, client = self._headers(501)
        self._set_balance(501, 100)
        ft = FakeTransport().queue(200, lookup_ok(username="dbluser", uid="uid-dbl"))
        with patch("locket.providers.lunakey._default_transport", ft):
            token = client.post(
                "/api/lunakey/lookup",
                headers=headers,
                json={"plan_id": self.lk_plan, "username": "dbluser"},
            ).get_json()["lookup_token"]
            payload = {"plan_id": self.lk_plan, "platform": "ios", "username": "dbluser",
                       "lookup_token": token, "idempotency_key": "dbl-key-1"}

            def _purchase_count():
                return db.get_conn().execute(
                    "SELECT COUNT(*) AS c FROM wallet_transactions WHERE user_id = 501 AND type = 'purchase'"
                ).fetchone()["c"]

            before = _purchase_count()
            first = client.post("/api/orders/coin", headers=headers, json=payload)
            second = client.post("/api/orders/coin", headers=headers, json=payload)
            after = _purchase_count()
        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertEqual(second.status_code, 200, second.get_json())
        self.assertEqual(first.get_json()["activation_order_id"], second.get_json()["activation_order_id"])
        self.assertEqual(db.get_wallet_balance(501), 50)
        self.assertEqual(after - before, 1)

    def test_customer_cannot_view_another_users_order(self):
        order_id, _u, _i = self._create_paid_order(user_id=501)
        headers2, client2 = self._headers(502)
        res = client2.get(f"/api/orders/{order_id}", headers=headers2)
        self.assertEqual(res.status_code, 404)

    def test_restore_endpoint_does_not_create_provider_job(self):
        headers, client = self._headers(501)
        with patch("locket.public.routes._gold_block_error", return_value=None):
            res = client.post(
                "/api/restore",
                headers=headers,
                json={"username": "restoreuser", "platform": "ios"},
            )
        # /api/restore is the legacy queue path: it may 503 when no Locket
        # account is configured, but it must never create a provider job.
        self.assertIn(res.status_code, (200, 503))
        jobs = db.get_conn().execute(
            "SELECT COUNT(*) AS c FROM provider_jobs j "
            "JOIN activation_orders o ON o.id = j.order_id WHERE o.locket_username = 'restoreuser'"
        ).fetchone()["c"]
        self.assertEqual(jobs, 0)


class ProviderAdminTests(BaseLunaKeyTest):
    def _admin_headers(self):
        return self._headers(1)

    def test_provider_status_never_exposes_key(self):
        headers, client = self._admin_headers()
        res = client.get("/api/admin/provider/status", headers=headers)
        self.assertEqual(res.status_code, 200, res.get_json())
        body = res.get_json()
        self.assertTrue(body["provider"]["configured"])
        self.assertNotIn(TEST_KEY, json.dumps(body))

    def test_job_retry_keeps_same_request_id(self):
        order_id, _u, _i = self._create_paid_order()
        job = lunakey_service.ensure_provider_job_for_order(order_id)
        # A 402 is a definite rejection: admin retry stays allowed and reuses
        # the same request_id.
        ft = FakeTransport().queue(402, {"success": False})
        self._lease_and_process(self._worker(ft), job["id"], "x", attempt_count=1)
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")
        headers, client = self._admin_headers()
        res = client.post(f"/api/admin/provider/jobs/{order_id}/retry", headers=headers, json={})
        self.assertEqual(res.status_code, 200, res.get_json())
        after = db.get_provider_job_by_id(job["id"])
        self.assertEqual(after["status"], "pending")
        self.assertEqual(after["provider_request_id"], job["provider_request_id"])

    def test_job_reconcile_requires_note(self):
        order_id, _u, _i = self._create_paid_order()
        lunakey_service.ensure_provider_job_for_order(order_id)
        headers, client = self._admin_headers()
        res = client.post(
            f"/api/admin/provider/jobs/{order_id}/reconcile",
            headers=headers, json={"outcome": "completed", "note": "no"},
        )
        self.assertEqual(res.status_code, 400)

    def test_admin_plan_update_accepts_provider_fields(self):
        headers, client = self._admin_headers()
        res = client.put(
            f"/api/admin/plans/{self.lk_plan}",
            headers=headers,
            json={"warranty_months": 6, "warranty_policy": "shop_calendar_months"},
        )
        self.assertEqual(res.status_code, 200, res.get_json())
        plan = db.get_plan_by_id(self.lk_plan, public=False)
        self.assertEqual(plan["warranty_months"], 6)
        self.assertEqual(plan["warranty_policy"], "shop_calendar_months")
        # Restore for other tests.
        client.put(
            f"/api/admin/plans/{self.lk_plan}",
            headers=headers,
            json={"warranty_months": 0, "warranty_policy": None},
        )

    def test_admin_plan_create_forces_yearly_category_for_lunakey(self):
        headers, client = self._admin_headers()
        res = client.post(
            "/api/admin/plans",
            headers=headers,
            json={
                "name": "Forced yearly", "slug": f"forced-{uuid.uuid4().hex[:6]}",
                "duration_days": 365, "price_vnd": 50000, "product_id": "forced-yearly",
                "supported_platforms": "ios", "ios_fulfillment_mode": "auto_activation",
                "android_fulfillment_mode": "disabled", "activation_provider": "lunakey",
                # Admin tries to send a wrong category; backend must force yearly.
                "provider_category": "month", "warranty_months": 1,
                "warranty_policy": "shop_calendar_months", "is_active": True,
            },
        )
        self.assertEqual(res.status_code, 201, res.get_json())
        self.assertEqual(res.get_json()["plan"]["provider_category"], "yearly")

    def test_admin_plan_update_forces_yearly_category_for_lunakey(self):
        headers, client = self._admin_headers()
        res = client.put(
            f"/api/admin/plans/{self.lk_plan}",
            headers=headers,
            json={"provider_category": "month"},
        )
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(db.get_plan_by_id(self.lk_plan, public=False)["provider_category"], "yearly")

    def test_admin_plans_list_reports_sellability(self):
        headers, client = self._admin_headers()
        res = client.get("/api/admin/plans", headers=headers)
        plans = {p["id"]: p for p in res.get_json()["plans"]}
        self.assertTrue(plans[self.lk_plan]["sellable"])
        self.assertEqual(plans[self.lk_plan]["readiness_issues"], [])


class ProviderWarrantyTests(BaseLunaKeyTest):
    def test_calendar_month_addition_handles_month_end_and_leap(self):
        from datetime import datetime, timezone

        jan31 = datetime(2025, 1, 31, tzinfo=timezone.utc).timestamp()
        result = lunakey_service.add_calendar_months(jan31, 1)
        self.assertEqual(datetime.fromtimestamp(result, tz=timezone.utc).day, 28)  # Feb 2025

        leap = datetime(2024, 1, 31, tzinfo=timezone.utc).timestamp()
        result_leap = lunakey_service.add_calendar_months(leap, 1)
        self.assertEqual(datetime.fromtimestamp(result_leap, tz=timezone.utc).day, 29)

    def test_warranty_window_requires_explicit_policy(self):
        order = {"warranty_policy_snapshot": None, "warranty_months_snapshot": 12,
                 "provider_completed_at": time.time()}
        self.assertEqual(lunakey_service.warranty_window(order), (None, None))
        order["warranty_policy_snapshot"] = "shop_calendar_months"
        start, end = lunakey_service.warranty_window(order)
        self.assertIsNotNone(start)
        self.assertGreater(end, start)


class ProviderMigrationTests(BaseLunaKeyTest):
    def test_migration_is_idempotent_and_schema_intact(self):
        # Re-running init must not fail or duplicate anything.
        db.init(force=True)
        db.init(force=True)
        conn = db.get_conn()
        plan_cols = {r["name"] for r in conn.execute("PRAGMA table_info(plans)")}
        order_cols = {r["name"] for r in conn.execute("PRAGMA table_info(activation_orders)")}
        for col in ("activation_provider", "provider_category", "warranty_months", "warranty_policy", "allow_existing_gold"):
            self.assertIn(col, plan_cols)
        for col in ("activation_provider_snapshot", "provider_uid", "provider_request_id",
                    "provider_order_code", "provider_price_deducted", "warranty_ends_at"):
            self.assertIn(col, order_cols)
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("provider_jobs", tables)
        self.assertIn("provider_lookups", tables)
        indexes = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertIn("idx_provider_jobs_claim", indexes)
        # Legacy CHECK constraint on activation_orders.status is still enforced:
        # provider-specific states must live in provider_jobs, not here.
        order_id, _u, _i = self._create_paid_order()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE activation_orders SET status = 'provider_pending' WHERE id = ?", (order_id,))


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
