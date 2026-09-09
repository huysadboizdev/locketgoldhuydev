import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest


temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "fulfillment-test-flask-secret-123456789"
os.environ["JWT_SECRET"] = "fulfillment-test-jwt-secret-12345678901"
os.environ["REFRESH_TOKEN_PEPPER"] = "fulfillment-test-pepper-123456789"
os.environ["ADMIN_EMAIL"] = "flow-admin@example.com"
os.environ["ADMIN_USERNAME"] = "flow_admin"
os.environ["ADMIN_PASSWORD"] = "flow-admin-password-12345"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db, payment_service
from locket.token_auth import create_access_token, create_token_family
from werkzeug.security import generate_password_hash


class FulfillmentFlowsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCKET_DB"] = temp_db_path
        db.close_conn()

        cls.app = create_app()
        cls.app.config["TESTING"] = True
        now = time.time()
        db.get_conn().execute(
            """INSERT INTO users
               (id, email, username, display_name, password_hash, is_active, role, created_at)
               VALUES (101, 'flow-user@example.com', 'flow-user', 'Flow User', ?, 1, 'user', ?)""",
            (generate_password_hash("password-12345"), now),
        )
        cls.auto_plan = db.create_plan(
            name="Auto iOS", slug="flow-auto-ios", duration_days=30,
            price_vnd=10000, supported_platforms="ios",
            ios_fulfillment_mode="auto_activation",
            android_fulfillment_mode="disabled",
        )
        cls.manual_plan = db.create_plan(
            name="VPN Manual", slug="flow-vpn-manual", duration_days=30,
            price_vnd=20000, supported_platforms="ios",
            ios_fulfillment_mode="manual_contact",
            android_fulfillment_mode="disabled",
        )
        cls.apk_plan = db.create_plan(
            name="Android APK", slug="flow-android-apk", duration_days=30,
            price_vnd=30000, supported_platforms="android",
            ios_fulfillment_mode="disabled",
            android_fulfillment_mode="apk_download",
        )

    @classmethod
    def tearDownClass(cls):
        db.close_conn()

        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            for suffix in ("-wal", "-shm"):
                if os.path.exists(temp_db_path + suffix):
                    os.remove(temp_db_path + suffix)
        except OSError:
            pass

    def setUp(self):
        self.client = self.app.test_client()
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        family_id, _, _ = create_token_family(user_id=101)
        self.headers = {
            "Authorization": f"Bearer {create_access_token(101, family_id)}",
            "X-CSRF-Token": csrf,
        }
        admin_family_id, _, _ = create_token_family(user_id=1)
        self.admin_headers = {
            "Authorization": f"Bearer {create_access_token(1, admin_family_id)}",
            "X-CSRF-Token": csrf,
        }

    def _credit(self, amount=200):
        status, _ = db.apply_wallet_transaction(
            101, "topup", amount,
            idempotency_key=f"flow-credit-{time.time_ns()}",
        )
        self.assertEqual(status, "ok")

    def test_manual_coin_requires_contact_and_is_idempotent(self):
        self._credit()
        missing = self.client.post(
            "/api/orders/coin", headers=self.headers,
            json={"plan_id": self.manual_plan, "platform": "ios"},
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.get_json()["error"], "invalid_contact_zalo")

        payload = {
            "plan_id": self.manual_plan,
            "platform": "ios",
            "contact_zalo": "0912 345 678",
            "contact_facebook": "https://facebook.com/flow.user",
            "idempotency_key": "manual-flow-once",
        }
        first = self.client.post("/api/orders/coin", headers=self.headers, json=payload)
        self.assertEqual(first.status_code, 200)
        first_data = first.get_json()
        self.assertEqual(first_data["status"], "paid")
        self.assertEqual(first_data["fulfillment_mode"], "manual_contact")
        self.assertIsNone(first_data["client_id"])

        second = self.client.post("/api/orders/coin", headers=self.headers, json=payload)
        second_data = second.get_json()
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second_data["idempotent"])
        self.assertEqual(second_data["activation_order_id"], first_data["activation_order_id"])
        queue_count = db.get_conn().execute(
            "SELECT COUNT(*) FROM queue_requests WHERE activation_order_id = ?",
            (first_data["activation_order_id"],),
        ).fetchone()[0]
        self.assertEqual(queue_count, 0)

    def test_android_coin_completes_and_grants_single_use_ticket(self):
        self._credit()
        response = self.client.post(
            "/api/orders/coin", headers=self.headers,
            json={
                "plan_id": self.apk_plan,
                "platform": "android",
                "idempotency_key": "apk-flow-once",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["fulfillment_mode"], "apk_download")
        self.assertIsNone(data["client_id"])

        ticket = self.client.post(
            "/api/apk/download-ticket", headers=self.headers,
            json={"activation_order_id": data["activation_order_id"]},
        )
        self.assertEqual(ticket.status_code, 200)
        url = ticket.get_json()["download_url"]
        first_claim = self.client.get(url)
        self.assertIn(first_claim.status_code, (200, 404))
        first_claim.close()
        second_claim = self.client.get(url)
        self.assertEqual(second_claim.status_code, 403)

    def test_qr_manual_payment_never_enters_queue_and_admin_can_finish(self):
        response = self.client.post(
            "/api/payments/plan", headers=self.headers,
            json={
                "plan_id": self.manual_plan,
                "platform": "ios",
                "contact_zalo": "+84912345678",
                "contact_facebook": "https://www.facebook.com/flow.user",
                "idempotency_key": "manual-qr-once",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        status, paid = payment_service.confirm_payment(
            data["payment_id"], "FLOW_BANK_TX_001", self.app
        )
        self.assertEqual(status, "ok")
        self.assertEqual(paid["fulfillment_mode"], "manual_contact")
        order = db.get_activation_order_by_id(data["activation_order_id"])
        self.assertEqual(order["status"], "paid")
        self.assertIsNone(order["queue_client_id"])

        start = self.client.post(
            f"/api/admin/orders/{order['id']}/start",
            headers=self.admin_headers,
            json={"note": "Đã liên hệ khách"},
        )
        self.assertEqual(start.status_code, 200)
        order = start.get_json()["order"]
        self.assertEqual(order["status"], "processing")
        complete = self.client.post(
            f"/api/admin/orders/{order['id']}/complete",
            headers=self.admin_headers,
            json={},
        )
        self.assertEqual(complete.status_code, 200)
        order = complete.get_json()["order"]
        self.assertEqual(order["status"], "completed")

    def test_auto_activation_still_requires_username_and_queues(self):
        self._credit()
        missing = self.client.post(
            "/api/orders/coin", headers=self.headers,
            json={"plan_id": self.auto_plan, "platform": "ios"},
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.get_json()["error"], "username_required")

        response = self.client.post(
            "/api/orders/coin", headers=self.headers,
            json={
                "plan_id": self.auto_plan,
                "platform": "ios",
                "username": "flow_locket",
                "idempotency_key": "auto-flow-once",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["fulfillment_mode"], "auto_activation")
        self.assertTrue(data["client_id"])
        self.assertEqual(data["status"], "queued")

    def test_dispatch_paid_activation_order_direct(self):
        self._credit()
        # 1. auto_activation
        auto_res = self.client.post(
            "/api/orders/coin", headers=self.headers,
            json={
                "plan_id": self.auto_plan,
                "platform": "ios",
                "username": "direct_disp_user",
                "idempotency_key": "disp-auto-1",
            },
        ).get_json()
        order_id = auto_res["activation_order_id"]
        status, disp = payment_service.dispatch_paid_activation_order(order_id, app=self.app)
        self.assertEqual(status, "ok")
        self.assertTrue(disp["queue_client_id"])
        first_client_id = disp["queue_client_id"]
        status, repeated = payment_service.dispatch_paid_activation_order(order_id, app=self.app)
        self.assertEqual(status, "ok")
        self.assertEqual(repeated["queue_client_id"], first_client_id)
        queue_count = db.get_conn().execute(
            "SELECT COUNT(*) FROM queue_requests WHERE activation_order_id = ?",
            (order_id,),
        ).fetchone()[0]
        self.assertEqual(queue_count, 1)
        with self.assertRaises(sqlite3.IntegrityError):
            db.get_conn().execute(
                """INSERT INTO queue_requests
                   (client_id, username, status, added_at, user_id, platform, plan_id, activation_order_id)
                   VALUES (?, ?, 'waiting', ?, ?, 'ios', ?, ?)""",
                ("forced-duplicate-queue", "direct_disp_user", time.time(), 101, self.auto_plan, order_id),
            )

        # 2. manual_contact stays in paid
        manual_res = self.client.post(
            "/api/orders/coin", headers=self.headers,
            json={
                "plan_id": self.manual_plan,
                "platform": "ios",
                "contact_zalo": "0987654321",
                "contact_facebook": "https://facebook.com/direct.manual",
                "idempotency_key": "disp-manual-1",
            },
        ).get_json()
        status, disp_man = payment_service.dispatch_paid_activation_order(
            manual_res["activation_order_id"], app=self.app
        )
        self.assertEqual(status, "ok")
        self.assertEqual(disp_man["status"], "paid")
        self.assertIsNone(disp_man.get("queue_client_id"))

        # 3. apk_download transitions to completed
        now = time.time()
        c = db.get_conn().execute(
            """INSERT INTO activation_orders
               (user_id, plan_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot, price_vnd_snapshot,
                price_coin_snapshot, payment_method, platform, locket_username, fulfillment_mode_snapshot, status,
                created_at, updated_at)
               VALUES (101, ?, 'APK Plan', 'apk-pid', 30, 30000, 30, 'qr', 'android', '', 'apk_download', 'paid', ?, ?)""",
            (self.apk_plan, now, now),
        )
        apk_act_id = c.lastrowid
        status, disp_apk = payment_service.dispatch_paid_activation_order(apk_act_id, app=self.app)
        self.assertEqual(status, "ok")
        self.assertEqual(disp_apk["status"], "completed")

    def test_admin_cancel_manual_order_and_audit_redaction(self):
        self._credit()
        created = self.client.post(
            "/api/orders/coin", headers=self.headers,
            json={
                "plan_id": self.manual_plan,
                "platform": "ios",
                "contact_zalo": "0918889999",
                "contact_facebook": "https://facebook.com/audit.secret",
                "idempotency_key": "cancel-flow-1",
            },
        ).get_json()
        act_id = created["activation_order_id"]

        # Attempt cancel with short reason -> 400
        short_res = self.client.post(
            f"/api/admin/orders/{act_id}/cancel",
            headers=self.admin_headers,
            json={"reason": "bad"},
        )
        self.assertEqual(short_res.status_code, 400)

        # Successful cancel
        cancel_res = self.client.post(
            f"/api/admin/orders/{act_id}/cancel",
            headers=self.admin_headers,
            json={"reason": "Khách hàng đổi ý muốn hủy đơn"},
        )
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.get_json()["order"]["status"], "cancelled")

        # Verify audit log redacts sensitive contacts
        audit_row = db.get_conn().execute(
            """SELECT * FROM admin_audit_logs
               WHERE entity_type = 'activation_order' AND entity_id = ? AND action = 'manual_order_cancel'
               ORDER BY id DESC LIMIT 1""",
            (act_id,),
        ).fetchone()
        self.assertIsNotNone(audit_row)
        import json
        before_data = json.loads(audit_row["before_json"])
        self.assertEqual(before_data.get("contact_zalo"), "[REDACTED]")
        self.assertEqual(before_data.get("contact_facebook"), "[REDACTED]")

        # Repeat cancel -> 409 invalid_state_transition
        repeat_res = self.client.post(
            f"/api/admin/orders/{act_id}/cancel",
            headers=self.admin_headers,
            json={"reason": "Khách hàng muốn hủy tiếp"},
        )
        self.assertEqual(repeat_res.status_code, 409)
        self.assertEqual(repeat_res.get_json()["error"], "invalid_state_transition")

    def test_admin_refund_manual_order_coin(self):
        self._credit(100)
        wallet_before = db.get_conn().execute("SELECT balance_coin FROM wallets WHERE user_id = 101").fetchone()["balance_coin"]
        created = self.client.post(
            "/api/orders/coin", headers=self.headers,
            json={
                "plan_id": self.manual_plan,
                "platform": "ios",
                "contact_zalo": "0912345678",
                "contact_facebook": "https://facebook.com/refund.coin",
                "idempotency_key": "refund-coin-1",
            },
        ).get_json()
        act_id = created["activation_order_id"]
        wallet_after_buy = db.get_conn().execute("SELECT balance_coin FROM wallets WHERE user_id = 101").fetchone()["balance_coin"]
        self.assertEqual(wallet_after_buy, wallet_before - 20)

        refund_res = self.client.post(
            f"/api/admin/orders/{act_id}/refund",
            headers=self.admin_headers,
            json={"reason": "Không liên hệ được với người mua sau 24h"},
        )
        self.assertEqual(refund_res.status_code, 200)
        self.assertEqual(refund_res.get_json()["order"]["status"], "refunded")

        wallet_after_refund = db.get_conn().execute("SELECT balance_coin FROM wallets WHERE user_id = 101").fetchone()["balance_coin"]
        self.assertEqual(wallet_after_refund, wallet_before)

        # Check wallet transaction
        tx = db.get_conn().execute(
            "SELECT * FROM wallet_transactions WHERE reference_type = 'activation_order' AND reference_id = ?",
            (str(act_id),),
        ).fetchall()
        refund_tx = [t for t in tx if t["type"] == "refund"]
        self.assertEqual(len(refund_tx), 1)

        # Repeat refund -> 409
        repeat_res = self.client.post(
            f"/api/admin/orders/{act_id}/refund",
            headers=self.admin_headers,
            json={"reason": "Hoàn tiền lần hai"},
        )
        self.assertEqual(repeat_res.status_code, 409)

    def test_admin_refund_manual_order_qr(self):
        pay_res = self.client.post(
            "/api/payments/plan", headers=self.headers,
            json={
                "plan_id": self.manual_plan,
                "platform": "ios",
                "contact_zalo": "0933334444",
                "contact_facebook": "https://facebook.com/refund.qr",
                "idempotency_key": "refund-qr-once",
            },
        ).get_json()
        payment_service.confirm_payment(pay_res["payment_id"], "FLOW_QR_TX_1", self.app)
        act_id = pay_res["activation_order_id"]

        # Refund without confirmation flag -> 400
        fail1 = self.client.post(
            f"/api/admin/orders/{act_id}/refund",
            headers=self.admin_headers,
            json={"reason": "Hoàn tiền ngân hàng"},
        )
        self.assertEqual(fail1.status_code, 400)
        self.assertEqual(fail1.get_json()["error"], "external_refund_confirmation_required")

        # Refund without reference -> 400
        fail2 = self.client.post(
            f"/api/admin/orders/{act_id}/refund",
            headers=self.admin_headers,
            json={"reason": "Hoàn tiền ngân hàng", "confirmed_external_refund": True},
        )
        self.assertEqual(fail2.status_code, 400)
        self.assertEqual(fail2.get_json()["error"], "refund_reference_required")

        # Successful refund with confirmation and ref
        ok_res = self.client.post(
            f"/api/admin/orders/{act_id}/refund",
            headers=self.admin_headers,
            json={
                "reason": "Đã chuyển khoản trả lại khách hàng",
                "confirmed_external_refund": True,
                "refund_reference": "VIB_REFUND_998877",
            },
        )
        self.assertEqual(ok_res.status_code, 200)
        self.assertEqual(ok_res.get_json()["order"]["status"], "refunded")

    def test_invalid_state_transition_returns_409(self):
        pay_res = self.client.post(
            "/api/payments/plan", headers=self.headers,
            json={
                "plan_id": self.manual_plan,
                "platform": "ios",
                "contact_zalo": "0977778888",
                "contact_facebook": "https://facebook.com/transition.test",
                "idempotency_key": "trans-test-once",
            },
        ).get_json()
        payment_service.confirm_payment(pay_res["payment_id"], "FLOW_QR_TX_2", self.app)
        act_id = pay_res["activation_order_id"]

        # Order is in 'paid'. Calling /complete directly must return 409
        comp_res = self.client.post(
            f"/api/admin/orders/{act_id}/complete",
            headers=self.admin_headers,
            json={},
        )
        self.assertEqual(comp_res.status_code, 409)
        self.assertEqual(comp_res.get_json()["error"], "invalid_state_transition")

        # Call /start -> 200
        start_res = self.client.post(
            f"/api/admin/orders/{act_id}/start",
            headers=self.admin_headers,
            json={"note": "Bắt đầu làm"},
        )
        self.assertEqual(start_res.status_code, 200)

        # Call /start second time -> 409 invalid_state_transition
        start2_res = self.client.post(
            f"/api/admin/orders/{act_id}/start",
            headers=self.admin_headers,
            json={"note": "Bắt đầu lại"},
        )
        self.assertEqual(start2_res.status_code, 409)
        self.assertEqual(start2_res.get_json()["error"], "invalid_state_transition")

    def test_user_orders_masking_and_no_empty_username_at(self):
        orders_res = self.client.get("/api/orders", headers=self.headers)
        self.assertEqual(orders_res.status_code, 200)
        items = orders_res.get_json()["items"]
        for ord_item in items:
            if ord_item.get("contact_zalo"):
                self.assertIn("***", ord_item["contact_zalo"])
            if ord_item.get("fulfillment_mode_snapshot") in ("manual_contact", "apk_download"):
                self.assertEqual(ord_item["locket_username"], "")

    def test_platform_config_apk_metadata(self):
        cfg_res = self.client.get("/api/platform-config")
        self.assertEqual(cfg_res.status_code, 200)
        data = cfg_res.get_json()
        self.assertIn("apk_available", data)
        self.assertIn("apk_delivery", data)
        self.assertIn(data["apk_delivery"], ("external", "local", "unavailable"))

        os.environ["ANDROID_APK_VERSION"] = "v1.200.0"
        os.environ["ANDROID_APK_SHA256"] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        try:
            cfg2 = self.client.get("/api/platform-config").get_json()
            self.assertEqual(cfg2["apk_version"], "v1.200.0")
            self.assertEqual(cfg2["apk_sha256"], "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        finally:
            os.environ.pop("ANDROID_APK_VERSION", None)
            os.environ.pop("ANDROID_APK_SHA256", None)

    def test_apk_ticket_rejects_unlinked_legacy_queue_request(self):
        client_id = f"legacy-android-{time.time_ns()}"
        now = time.time()
        db.get_conn().execute(
            """INSERT INTO queue_requests
               (client_id, username, status, added_at, completed_at, user_id, platform)
               VALUES (?, 'legacy_user', 'completed', ?, ?, 101, 'android')""",
            (client_id, now - 10, now),
        )
        response = self.client.post(
            "/api/apk/download-ticket",
            headers=self.headers,
            json={"client_id": client_id},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "paid_order_required")

    def test_concurrent_auto_dispatch_creates_exactly_one_queue_request(self):
        now = time.time()
        cursor = db.get_conn().execute(
            """INSERT INTO activation_orders
               (user_id, plan_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot,
                price_vnd_snapshot, price_coin_snapshot, payment_method, platform, locket_username,
                fulfillment_mode_snapshot, status, created_at, updated_at)
               VALUES (101, ?, 'Concurrent Auto', 'concurrent-auto', 30, 10000, 10,
                       'coin', 'ios', 'concurrent_user', 'auto_activation', 'awaiting_queue', ?, ?)""",
            (self.auto_plan, now, now),
        )
        order_id = cursor.lastrowid
        barrier = threading.Barrier(6)
        results = []
        errors = []

        def dispatch_once():
            try:
                with self.app.app_context():
                    barrier.wait(timeout=5)
                    status, result = payment_service.dispatch_paid_activation_order(
                        order_id, app=self.app
                    )
                    results.append((status, result.get("queue_client_id")))
            except Exception as exc:
                errors.append(exc)
            finally:
                db.close_conn()

        threads = [threading.Thread(target=dispatch_once) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertEqual(len(results), 6)
        self.assertTrue(all(status == "ok" for status, _ in results))
        client_ids = {client_id for _, client_id in results}
        self.assertEqual(len(client_ids), 1)
        queue_count = db.get_conn().execute(
            "SELECT COUNT(*) FROM queue_requests WHERE activation_order_id = ?",
            (order_id,),
        ).fetchone()[0]
        self.assertEqual(queue_count, 1)


if __name__ == "__main__":
    unittest.main()
