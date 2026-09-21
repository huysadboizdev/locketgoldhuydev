"""End-to-end QR integration for LunaKey packages through the real SePay webhook.

Only the provider HTTP boundary is mocked. The HMAC webhook verification, the
payment settlement transaction, the fulfillment dispatcher and the durable
provider job are the real application code paths. No real API call, no real
Telegram, no production DB.
"""

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import requests

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "lk-qr-flask-secret-1234567890123"
os.environ["JWT_SECRET"] = "lk-qr-jwt-secret-123456789012345"
os.environ["REFRESH_TOKEN_PEPPER"] = "lk-qr-pepper-123456789012345"
os.environ["ADMIN_EMAIL"] = "qr-admin@example.com"
os.environ["ADMIN_USERNAME"] = "qr_admin"
os.environ["ADMIN_PASSWORD"] = "qr-admin-password-12345"
os.environ["LUNAKEY_API_KEY"] = "lk-qr-key-not-real-0002"
os.environ["LUNAKEY_ENABLED"] = "1"
os.environ["LUNAKEY_WORKER_ENABLED"] = "0"
os.environ["TELEGRAM_NOTIFICATIONS_ENABLED"] = "0"
os.environ["PAYMENT_WEBHOOK_ENABLED"] = "1"
os.environ["SEPAY_WEBHOOK_SECRET"] = "sepay-qr-webhook-secret-1234567890"
os.environ["SEPAY_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS"] = "300"
os.environ["PAYMENT_TRANSFER_PREFIX"] = "LOCKETGOLDHUYDEV"
os.environ["PAYMENT_TRANSFER_DIGITS"] = "3"
os.environ["VIETQR_BANK_ID"] = "TPB"
os.environ["VIETQR_ACCOUNT_NO"] = "TESTACC123"
os.environ["VIETQR_ACCOUNT_NAME"] = "TEST NAME"
os.environ["PAYMENT_TTL_SECONDS"] = "600"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db, lunakey_service  # noqa: E402
from locket.providers import lunakey  # noqa: E402
from locket.provider_worker import ProviderWorker  # noqa: E402
from locket.token_auth import create_access_token, create_token_family  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

SECRET = os.environ["SEPAY_WEBHOOK_SECRET"]


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


def lookup_ok(username, uid):
    return {
        "success": True,
        "profile": {
            "username": username, "name": "QR User", "avatar": "https://example.com/a.jpg",
            "uid": uid, "has_gold": False, "gold_expiry": None, "gold_days_left": 0,
        },
    }


def activate_ok(request_id):
    return {
        "success": True, "code": 200, "message": "ok",
        "order_code": f"LOK-{uuid.uuid4().hex[:6].upper()}",
        "request_id": request_id, "price_deducted": 39000, "remaining_balance": 100000,
        "profile": {"username": "qruser", "name": "QR User", "avatar": "https://example.com/a.jpg"},
    }


def _bootstrap():
    os.environ["LOCKET_DB"] = temp_db_path
    db.close_conn()
    app = create_app()
    app.config["TESTING"] = True
    conn = db.get_conn()
    now = time.time()
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, role, created_at) "
        "VALUES (701, 'qrbuyer@test.com', 'qrbuyer', 'QR Buyer', ?, 1, 'user', ?)",
        (generate_password_hash("password12345"), now),
    )
    conn.commit()
    plan = db.create_plan(
        name="Locket Gold QR (LunaKey)", slug="lunakey-qr-1y", duration_days=365, price_vnd=50000,
        supported_platforms="ios", ios_fulfillment_mode="auto_activation",
        android_fulfillment_mode="disabled", activation_provider="lunakey",
        provider_category="yearly", warranty_months=0, allow_existing_gold=0, is_active=1,
    )
    lunakey_service.resume_provider()
    return app, plan


APP, PLAN = _bootstrap()


class QrIntegrationTests(unittest.TestCase):
    app = APP
    plan = PLAN
    _tx_counter = 900000

    def setUp(self):
        lunakey_service.resume_provider()

    # -- helpers --------------------------------------------------------

    def _headers(self, user_id=701):
        client = self.app.test_client()
        csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
        family_id, _, _ = create_token_family(user_id=user_id)
        return {
            "Authorization": f"Bearer {create_access_token(user_id, family_id)}",
            "X-CSRF-Token": csrf,
            "Content-Type": "application/json",
        }, client

    def _create_qr_order(self):
        headers, client = self._headers()
        username = f"qr_{uuid.uuid4().hex[:8]}"
        uid = f"uid-{uuid.uuid4().hex[:10]}"
        ft = FakeTransport().queue(200, lookup_ok(username, uid))
        key = f"qr-{uuid.uuid4().hex}"
        with patch("locket.providers.lunakey._default_transport", ft):
            look = client.post(
                "/api/lunakey/lookup", headers=headers,
                json={"plan_id": self.plan, "username": username},
            ).get_json()
            res = client.post(
                "/api/payments/plan", headers=headers,
                json={"plan_id": self.plan, "platform": "ios", "username": username,
                      "lookup_token": look["lookup_token"], "idempotency_key": key},
            )
        self.assertEqual(res.status_code, 200, res.get_json())
        body = res.get_json()
        payment = db.get_payment_order_by_id(body["payment_id"])
        return client, body, payment, username, uid

    def _payload(self, payment, amount=None, account="TESTACC123", content=None, tx_id=None):
        if tx_id is None:
            QrIntegrationTests._tx_counter += 1
            tx_id = QrIntegrationTests._tx_counter
        return {
            "id": tx_id,
            "gateway": "TPBank",
            "accountNumber": account,
            "code": None,
            "content": content if content is not None else payment["transfer_code"],
            "transferType": "in",
            "transferAmount": amount if amount is not None else payment["amount_vnd"],
            "referenceCode": f"FT{uuid.uuid4().hex[:10]}",
            "transactionDate": datetime.now(timezone.utc).isoformat(),
        }

    def _post_webhook(self, client, payload, secret=None, timestamp=None):
        body = json.dumps(payload, separators=(",", ":")).encode()
        ts = str(timestamp if timestamp is not None else int(time.time()))
        digest = hmac.new((secret or SECRET).encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-SePay-Timestamp": ts,
            "X-SePay-Signature": f"sha256={digest}",
        }
        return client.post("/api/payment/webhook", data=body, headers=headers)

    def _worker(self, transport):
        return ProviderWorker(app=self.app, client_factory=lambda: lunakey.LunaKeyClient(transport=transport))

    def _claim_target(self, job_id, owner):
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='cancelled' WHERE id != ? AND status IN ('pending','leased')",
            (job_id,),
        )
        db.get_conn().commit()
        claimed = db.claim_provider_job(owner, lease_seconds=60)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], job_id)
        return claimed

    def _job_count(self, order_id):
        return db.get_conn().execute(
            "SELECT COUNT(*) AS c FROM provider_jobs WHERE order_id=?", (order_id,)
        ).fetchone()["c"]

    def _refund_ledger_count(self, order_id):
        return db.get_conn().execute(
            "SELECT COUNT(*) AS c FROM wallet_transactions "
            "WHERE reference_type='activation_order' AND reference_id=? AND type='refund'",
            (str(order_id),),
        ).fetchone()["c"]

    # -- happy path -----------------------------------------------------

    def test_qr_lunakey_full_settlement_to_completed(self):
        client, body, payment, username, uid = self._create_qr_order()
        act_id = body["activation_order_id"]
        order = db.get_activation_order_by_id(act_id)
        self.assertEqual(order["status"], "awaiting_payment")
        self.assertEqual(order["activation_provider_snapshot"], "lunakey")
        self.assertEqual(order["provider_uid"], uid)
        self.assertEqual(order["provider_category_snapshot"], "yearly")
        self.assertEqual(order["price_vnd_snapshot"], payment["amount_vnd"])
        self.assertIsNone(db.get_provider_job_by_order(act_id))

        res = self._post_webhook(client, self._payload(payment))
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(db.get_payment_order_by_id(payment["id"])["status"], "paid")
        order = db.get_activation_order_by_id(act_id)
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["payment_method"], "qr")
        job = db.get_provider_job_by_order(act_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "pending")

        ft = FakeTransport().queue(200, activate_ok(job["provider_request_id"]))
        claimed = self._claim_target(job["id"], "qr-worker")
        self._worker(ft)._process(claimed, "qr-worker")
        self.assertEqual(db.get_activation_order_by_id(act_id)["status"], "completed")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "succeeded")
        self.assertEqual(len(ft.calls), 1)

    def test_duplicate_webhook_does_not_activate_twice(self):
        client, body, payment, username, uid = self._create_qr_order()
        act_id = body["activation_order_id"]
        payload = self._payload(payment)
        first = self._post_webhook(client, payload)
        self.assertEqual(first.status_code, 200)
        jobs_after_first = self._job_count(act_id)
        orders_after_first = db.get_conn().execute(
            "SELECT COUNT(*) AS c FROM activation_orders WHERE locket_username=?", (username,)
        ).fetchone()["c"]
        tx_after_first = self._refund_ledger_count(act_id)

        second = self._post_webhook(client, payload)  # same transaction id
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self._job_count(act_id), jobs_after_first)
        self.assertEqual(
            db.get_conn().execute(
                "SELECT COUNT(*) AS c FROM activation_orders WHERE locket_username=?", (username,)
            ).fetchone()["c"],
            orders_after_first,
        )
        self.assertEqual(self._refund_ledger_count(act_id), tx_after_first)
        self.assertEqual(db.get_payment_order_by_id(payment["id"])["status"], "paid")

    # -- rejection paths ------------------------------------------------

    def test_wrong_signature_does_not_activate(self):
        client, body, payment, _u, _i = self._create_qr_order()
        act_id = body["activation_order_id"]
        res = self._post_webhook(client, self._payload(payment), secret="wrong-secret")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(db.get_payment_order_by_id(payment["id"])["status"], "pending")
        self.assertEqual(db.get_activation_order_by_id(act_id)["status"], "awaiting_payment")
        self.assertEqual(self._job_count(act_id), 0)

    def test_wrong_account_does_not_activate(self):
        client, body, payment, _u, _i = self._create_qr_order()
        act_id = body["activation_order_id"]
        res = self._post_webhook(client, self._payload(payment, account="SOMEONE_ELSE"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(db.get_payment_order_by_id(payment["id"])["status"], "pending")
        self.assertEqual(self._job_count(act_id), 0)

    def test_wrong_amount_does_not_activate(self):
        client, body, payment, _u, _i = self._create_qr_order()
        act_id = body["activation_order_id"]
        res = self._post_webhook(client, self._payload(payment, amount=1))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(db.get_payment_order_by_id(payment["id"])["status"], "pending")
        self.assertEqual(self._job_count(act_id), 0)

    def test_unknown_transfer_code_does_not_activate(self):
        client, body, payment, _u, _i = self._create_qr_order()
        act_id = body["activation_order_id"]
        res = self._post_webhook(client, self._payload(payment, content="no matching code here"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(db.get_payment_order_by_id(payment["id"])["status"], "pending")
        self.assertEqual(self._job_count(act_id), 0)

    # -- recovery / unclear outcomes -----------------------------------

    def test_paid_without_dispatch_recovers_exactly_one_job(self):
        client, body, payment, _u, _i = self._create_qr_order()
        act_id = body["activation_order_id"]
        # Settle the money without running the dispatcher (crash between them).
        status, _ = db.confirm_payment_order_tx(payment["id"], "MANUAL_TEST_RECOVER")
        self.assertEqual(status, "ok")
        self.assertEqual(db.get_activation_order_by_id(act_id)["status"], "paid")
        self.assertIsNone(db.get_provider_job_by_order(act_id))

        self.assertGreaterEqual(lunakey_service.recover_missing_provider_jobs(), 1)
        self.assertEqual(self._job_count(act_id), 1)
        # A second recovery must not create a duplicate.
        lunakey_service.recover_missing_provider_jobs()
        self.assertEqual(self._job_count(act_id), 1)

    def test_paid_then_provider_402_keeps_money_state_and_no_auto_refund(self):
        client, body, payment, _u, _i = self._create_qr_order()
        act_id = body["activation_order_id"]
        self._post_webhook(client, self._payload(payment))
        job = db.get_provider_job_by_order(act_id)
        ft = FakeTransport().queue(402, {"success": False})
        claimed = self._claim_target(job["id"], "qr-402")
        self._worker(ft)._process(claimed, "qr-402")

        self.assertEqual(db.get_payment_order_by_id(payment["id"])["status"], "paid")
        self.assertEqual(db.get_activation_order_by_id(act_id)["status"], "paid")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")
        self.assertEqual(self._refund_ledger_count(act_id), 0)

    def test_paid_then_provider_timeout_keeps_money_state(self):
        client, body, payment, _u, _i = self._create_qr_order()
        act_id = body["activation_order_id"]
        self._post_webhook(client, self._payload(payment))
        job = db.get_provider_job_by_order(act_id)
        ft = FakeTransport().queue_error(requests.exceptions.Timeout("slow"))
        claimed = self._claim_target(job["id"], "qr-timeout")
        self._worker(ft)._process(claimed, "qr-timeout")

        self.assertEqual(db.get_payment_order_by_id(payment["id"])["status"], "paid")
        self.assertEqual(db.get_activation_order_by_id(act_id)["status"], "paid")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "awaiting_reconciliation")
        self.assertEqual(self._refund_ledger_count(act_id), 0)

    def test_worker_does_not_call_provider_for_unpaid_order(self):
        client, body, payment, username, _uid = self._create_qr_order()
        act_id = body["activation_order_id"]
        self.assertIsNone(db.get_provider_job_by_order(act_id))
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='cancelled' WHERE status IN ('pending','leased')"
        )
        db.get_conn().commit()
        ft = FakeTransport()
        self._worker(ft).tick("qr-unpaid")
        self.assertEqual(ft.calls, [])
        self.assertEqual(db.get_activation_order_by_id(act_id)["status"], "awaiting_payment")
        self.assertEqual(self._job_count(act_id), 0)


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
