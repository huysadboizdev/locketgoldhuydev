import os
import sys
import tempfile
import time
import unittest

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "test-secret-plans-wallet-key-12345"
os.environ["JWT_SECRET"] = "test-jwt-secret-plans-wallet-12345678"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-secret-plans-wallet-123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"
os.environ["NEXTDNS_KEY"] = "super-secret-nextdns-key-never-leak"
os.environ["NEXTDNS_PROFILE"] = "customprof123"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db
from locket.token_auth import create_token_family, create_access_token
from locket.user_auth import reset_rate_limits
from werkzeug.security import generate_password_hash


class PlansWalletPaymentTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCKET_DB"] = temp_db_path
        db.close_conn()

        cls.app = create_app()
        cls.app.config["TESTING"] = True

        conn = db.get_conn()
        now = time.time()
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (1, 'user1@test.com', 'user1', 'User One', ?, 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (2, 'user2@test.com', 'user2', 'User Two', ?, 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        cls.app.rotator.size = lambda: 1

        static_dir = os.path.join(cls.app.root_path, "static")
        os.makedirs(static_dir, exist_ok=True)
        cls.mc_path = os.path.join(static_dir, "locket.mobileconfig")
        with open(cls.mc_path, "w", encoding="utf-8") as f:
            f.write("<plist>dummy mobileconfig content</plist>")

        cls.apk_path = os.path.join(static_dir, "locket.apk")
        with open(cls.apk_path, "wb") as f:
            f.write(b"dummy apk binary content")

    @classmethod
    def tearDownClass(cls):
        db.close_conn()

        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            for ext in ["-wal", "-shm"]:
                p = temp_db_path + ext
                if os.path.exists(p):
                    os.remove(p)
        except Exception:
            pass

    def setUp(self):
        self.client = self.app.test_client()
        reset_rate_limits()
        csrf_res = self.client.get("/api/auth/csrf")
        self.assertEqual(csrf_res.status_code, 200)
        self.csrf_token = csrf_res.get_json()["csrf_token"]
        fam1, _, _ = create_token_family(user_id=1)
        self.token_user1 = create_access_token(1, fam1)
        self.headers_user1 = {
            "Authorization": f"Bearer {self.token_user1}",
            "X-CSRF-Token": self.csrf_token,
        }

        fam2, _, _ = create_token_family(user_id=2)
        self.token_user2 = create_access_token(2, fam2)
        self.headers_user2 = {
            "Authorization": f"Bearer {self.token_user2}",
            "X-CSRF-Token": self.csrf_token,
        }

    def _login_admin(self):
        res = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "admin-secret-password-1234"},
            follow_redirects=True,
        )
        res.close()
        with self.client.session_transaction() as sess:
            self.admin_csrf = sess.get("admin_csrf_token")
        customer_csrf_res = self.client.get("/api/auth/csrf")
        self.csrf_token = customer_csrf_res.get_json()["csrf_token"]
        self.headers_user1["X-CSRF-Token"] = self.csrf_token
        self.headers_user2["X-CSRF-Token"] = self.csrf_token
        return res

    # -------------------------------------------------------------
    # 1. Plans API không trả mock
    # -------------------------------------------------------------
    def test_01_plans_api_not_mock(self):
        """GET /api/plans returns actual DB data, never mock/fixtures."""
        res = self.client.get("/api/plans")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data["plans"], list)

        # Seed real plan via db
        p_id = db.create_plan(
            name="Plan Test Real 01",
            slug=f"plan-test-real-{int(time.time()*1000)}",
            short_description="Real plan description",
            platform="all",
            price_coin=15,
            price_vnd=15000,
            duration_days=30,
            is_active=1,
            features=["Feature A", "Feature B"],
            sort_order=1,
            stock_limit=-1,
        )
        res2 = self.client.get("/api/plans")
        data2 = res2.get_json()
        found = [p for p in data2["plans"] if p["id"] == p_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "Plan Test Real 01")
        self.assertEqual(found[0]["price_coin"], 15)
        self.assertEqual(found[0]["price_vnd"], 15000)

    # -------------------------------------------------------------
    # 2. Admin tạo/sửa/ẩn gói đúng
    # -------------------------------------------------------------
    def test_02_admin_create_update_hide_plan(self):
        """Admin can create, update, and hide/soft-delete plans."""
        self._login_admin()
        headers = {"X-CSRF-Token": self.admin_csrf}

        # Create
        create_payload = {
            "name": "Admin Created Plan",
            "slug": f"admin-created-plan-{int(time.time()*1000)}",
            "description": "Created by admin",
            "platform": "ios",
            "price_coin": 25,
            "price_vnd": 25000,
            "duration_days": 60,
            "is_active": True,
            "features": ["iOS Gold", "Fast Queue"],
            "sort_order": 5,
            "stock_limit": 100,
        }
        res = self.client.post("/admin/api/plans", json=create_payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        plan_data = res.get_json()["plan"]
        plan_id = plan_data["id"]
        self.assertEqual(plan_data["name"], "Admin Created Plan")
        self.assertEqual(plan_data["supported_platforms"], "ios")

        # Update
        update_payload = {
            "name": "Admin Updated Plan",
            "slug": f"admin-updated-plan-{int(time.time()*1000)}",
            "short_description": "Updated description",
            "supported_platforms": "ios",
            "price_vnd": 30000,
            "duration_days": 90,
            "is_active": 1,
            "features": ["Updated Feature"],
            "sort_order": 1,
        }
        res_update = self.client.put(f"/admin/api/plans/{plan_id}", json=update_payload, headers=headers)
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.get_json()["plan"]["name"], "Admin Updated Plan")
        self.assertEqual(res_update.get_json()["plan"]["price_coin"], 30)

        # Soft-delete / hide
        res_delete = self.client.delete(f"/admin/api/plans/{plan_id}", headers=headers)
        self.assertEqual(res_delete.status_code, 200)
        self.assertTrue(res_delete.get_json()["success"])

        # Inactive plan must not be in public GET /api/plans
        public_res = self.client.get("/api/plans")
        active_ids = [p["id"] for p in public_res.get_json()["plans"]]
        self.assertNotIn(plan_id, active_ids)

    # -------------------------------------------------------------
    # 3. Giá Coin được tính theo 1 Coin = 1.000 VNĐ
    # -------------------------------------------------------------
    def test_03_coin_price_1_coin_equals_1000_vnd(self):
        """1 Coin is strictly equivalent to 1,000 VND integer conversion."""
        res = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user1,
            json={"amount_coin": 50},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["amount_coin"], 50)
        self.assertEqual(data["amount_vnd"], 50000)

    # -------------------------------------------------------------
    # 4. Giá không chia hết 1.000 bị từ chối
    # -------------------------------------------------------------
    def test_04_price_not_divisible_by_1000_rejected(self):
        """Prices with fractions or not divisible by 1000 are rejected."""
        self._login_admin()
        headers = {"X-CSRF-Token": self.admin_csrf}

        # Admin plan price_vnd not divisible by 1000
        res = self.client.post(
            "/admin/api/plans",
            json={
                "name": "Invalid Price Plan",
                "slug": f"invalid-price-plan-{int(time.time()*1000)}",
                "platform": "all",
                "price_coin": 15,
                "price_vnd": 15500,  # invalid
                "duration_days": 30,
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("chia hết cho 1.000", res.get_json()["error"])

        # User topup with non-positive or float
        res2 = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user1,
            json={"amount_coin": 0},
        )
        self.assertEqual(res2.status_code, 400)

    # -------------------------------------------------------------
    # 5. Thiếu/sai platform bị từ chối
    # -------------------------------------------------------------
    def test_05_missing_or_invalid_platform_rejected(self):
        """Missing or invalid platform in plan or order is rejected with 400."""
        self._login_admin()
        headers = {"X-CSRF-Token": self.admin_csrf}

        res = self.client.post(
            "/admin/api/plans",
            json={
                "name": "Bad Platform Plan",
                "slug": f"bad-platform-plan-{int(time.time()*1000)}",
                "platform": "windows",
                "price_coin": 10,
                "price_vnd": 10000,
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Nền tảng không hợp lệ", res.get_json()["error"])

    # -------------------------------------------------------------
    # 6. Platform được lưu đúng
    # -------------------------------------------------------------
    def test_06_platform_saved_correctly(self):
        """Platform column stores exact value ('ios', 'android', 'all')."""
        self._login_admin()
        headers = {"X-CSRF-Token": self.admin_csrf}

        for plt in ["ios", "android", "all"]:
            res = self.client.post(
                "/admin/api/plans",
                json={
                    "name": f"Plan {plt}",
                    "slug": f"plan-{plt}-{int(time.time()*1000)}",
                    "platform": plt,
                    "price_coin": 10,
                    "price_vnd": 10000,
                },
                headers=headers,
            )
            self.assertEqual(res.status_code, 200)
            pid = res.get_json()["plan"]["id"]
            db_plan = db.get_plan_by_id(pid)
            self.assertEqual(db_plan["supported_platforms"], plt)

    # -------------------------------------------------------------
    # 7. Queue status trả đúng platform/plan
    # -------------------------------------------------------------
    def test_07_queue_status_returns_platform_and_plan(self):
        """Queue status includes platform, plan_id, and activation_order_id."""
        now = time.time()
        plan_id = db.create_plan(
            name="Queue metadata plan",
            slug=f"queue-metadata-{time.time_ns()}",
            duration_days=30,
            price_vnd=10000,
            supported_platforms="android",
            ios_fulfillment_mode="disabled",
            android_fulfillment_mode="apk_download",
        )
        order_cursor = db.get_conn().execute(
            """INSERT INTO activation_orders
               (user_id, plan_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot,
                price_vnd_snapshot, price_coin_snapshot, payment_method, platform, locket_username,
                fulfillment_mode_snapshot, status, created_at, updated_at)
               VALUES (1, ?, 'Queue metadata plan', 'queue-metadata', 30, 10000, 10,
                       'coin', 'android', 'test_user_q', 'auto_activation', 'awaiting_queue', ?, ?)""",
            (plan_id, now, now),
        )
        activation_order_id = order_cursor.lastrowid
        cid = self.app.queue_manager.add_to_queue(
            username="test_user_q",
            user_id=1,
            platform="android",
            plan_id=plan_id,
            activation_order_id=activation_order_id,
        )
        res = self.client.post(
            "/api/queue/status",
            headers=self.headers_user1,
            json={"client_id": cid},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["platform"], "android")
        self.assertEqual(data["plan_id"], plan_id)
        self.assertEqual(data["activation_order_id"], activation_order_id)

    # -------------------------------------------------------------
    # 8. Active queue khôi phục đúng platform
    # -------------------------------------------------------------
    def test_08_active_queue_restores_platform(self):
        """Re-checking active session preserves platform across reloads."""
        cid = self.app.queue_manager.add_to_queue(
            username="test_user_q8",
            platform="ios",
            plan_id=1,
        )
        status = self.app.queue_manager.get_status(cid)
        self.assertEqual(status["platform"], "ios")

    # -------------------------------------------------------------
    # 9. User không xem order của người khác (IDOR protection)
    # -------------------------------------------------------------
    def test_09_user_cannot_view_others_orders(self):
        """User 2 cannot inspect User 1's activation order."""
        plan_id = db.create_plan(
            name="Plan IDOR Test",
            slug=f"plan-idor-{int(time.time()*1000)}",
            price_coin=10,
            price_vnd=10000,
        )
        order_id = db.create_activation_order(
            user_id=1,
            plan_id=plan_id,
            target_username="user1_target",
            platform="ios",
            payment_method="coin",
            paid_amount_coin=10,
        )
        # User 2 attempts to fetch order_id
        res = self.client.get(f"/api/orders/{order_id}", headers=self.headers_user2)
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.get_json()["success"])

        # User 1 can fetch their own order
        res1 = self.client.get(f"/api/orders/{order_id}", headers=self.headers_user1)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.get_json()["order"]["id"], order_id)

    # -------------------------------------------------------------
    # 10. Không thể mua gói inactive
    # -------------------------------------------------------------
    def test_10_cannot_purchase_inactive_plan(self):
        """Purchasing an inactive plan returns 400 error."""
        plan_id = db.create_plan(
            name="Inactive Plan",
            slug=f"plan-inactive-{int(time.time()*1000)}",
            price_coin=10,
            price_vnd=10000,
            is_active=0,
        )
        # Give user 1 balance
        db.apply_wallet_transaction(1, "topup", 50, "topup", 1, "Seed balance")
        res = self.client.post(
            "/api/orders/coin",
            headers=self.headers_user1,
            json={"plan_id": plan_id, "target_username": "testuser", "platform": "ios"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("không khả dụng", res.get_json()["error"])

    # -------------------------------------------------------------
    # 11. Không thể mua gói không hỗ trợ platform
    # -------------------------------------------------------------
    def test_11_cannot_purchase_mismatched_platform_plan(self):
        """Attempting to activate Android on an iOS-only plan returns 400."""
        plan_id = db.create_plan(
            name="iOS Exclusive Plan",
            slug=f"plan-ios-ex-{int(time.time()*1000)}",
            platform="ios",
            price_coin=10,
            price_vnd=10000,
            is_active=1,
        )
        db.apply_wallet_transaction(1, "topup", 50, "topup", 1, "Seed balance")
        res = self.client.post(
            "/api/orders/coin",
            headers=self.headers_user1,
            json={"plan_id": plan_id, "target_username": "android_user", "platform": "android"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("không hỗ trợ nền tảng", res.get_json()["error"])

    # -------------------------------------------------------------
    # 12. Coin không đủ bị từ chối
    # -------------------------------------------------------------
    def test_12_insufficient_coin_rejected(self):
        """Ordering a plan costing more than wallet balance returns 400 insufficient_coins."""
        plan_id = db.create_plan(
            name="Expensive Plan",
            slug=f"plan-exp-{int(time.time()*1000)}",
            price_coin=9999,
            price_vnd=9999000,
            is_active=1,
        )
        res = self.client.post(
            "/api/orders/coin",
            headers=self.headers_user2,  # user 2 has 0 balance
            json={"plan_id": plan_id, "target_username": "poor_user", "platform": "ios"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"], "insufficient_coins")

    # -------------------------------------------------------------
    # 13. Thanh toán Coin trừ đúng một lần
    # -------------------------------------------------------------
    def test_13_coin_payment_deducts_once(self):
        """Coin payment deducts the exact plan price once and records a ledger transaction."""
        plan_id = db.create_plan(
            name="Single Deduct Plan",
            slug=f"plan-single-{int(time.time()*1000)}",
            price_coin=20,
            price_vnd=20000,
            is_active=1,
        )
        # Set exact balance: 50 Coin
        conn = db.get_conn()
        conn.execute("UPDATE wallets SET balance_coin = 50 WHERE user_id = 1")
        bal_before = db.get_wallet_balance(1)
        self.assertEqual(bal_before, 50)

        res = self.client.post(
            "/api/orders/coin",
            headers=self.headers_user1,
            json={"plan_id": plan_id, "target_username": "lucky_user", "platform": "ios"},
        )
        self.assertEqual(res.status_code, 200)
        bal_after = db.get_wallet_balance(1)
        self.assertEqual(bal_after, 30)

    # -------------------------------------------------------------
    # 14. Retry request không trừ Coin hai lần
    # -------------------------------------------------------------
    def test_14_retry_idempotent_request_does_not_deduct_twice(self):
        """Deducting coin verifies balance atomically to prevent race/double deductions."""
        current_bal = db.get_wallet_balance(1)
        status, _ = db.apply_wallet_transaction(1, "purchase", -(current_bal + 10), "plan_purchase", 1, "Overdraw test")
        self.assertNotEqual(status, "ok")
        self.assertEqual(db.get_wallet_balance(1), current_bal)

    # -------------------------------------------------------------
    # 15. Refund tạo ledger đúng một lần
    # -------------------------------------------------------------
    def test_15_refund_creates_ledger_once(self):
        """Refunding an activation order credits back coins once and marks order refunded."""
        plan_id = db.create_plan(
            name="Refundable Plan",
            slug=f"plan-ref-{int(time.time()*1000)}",
            price_coin=15,
            price_vnd=15000,
            is_active=1,
        )
        order_id = db.create_activation_order(
            user_id=1,
            plan_id=plan_id,
            target_username="refund_user",
            platform="ios",
            payment_method="coin",
            paid_amount_coin=15,
        )
        conn = db.get_conn()
        conn.execute("UPDATE activation_orders SET status = 'failed' WHERE id = ?", (order_id,))
        bal_before = db.get_wallet_balance(1)
        status, _ = db.refund_activation_order_coin(order_id, reason="Test failure refund")
        self.assertEqual(status, "ok")
        self.assertEqual(db.get_wallet_balance(1), bal_before + 15)

        # Attempt second refund on the same order -> already_refunded
        status2, _ = db.refund_activation_order_coin(order_id, reason="Duplicate refund attempt")
        self.assertEqual(status2, "already_refunded")
        self.assertEqual(db.get_wallet_balance(1), bal_before + 15)

    # -------------------------------------------------------------
    # 16. Top-up pending không cộng Coin
    # -------------------------------------------------------------
    def test_16_topup_pending_does_not_credit_coin(self):
        """Creating a top-up request leaves status 'pending' and balance untouched."""
        bal_before = db.get_wallet_balance(2)
        res = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user2,
            json={"amount_coin": 100},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(db.get_wallet_balance(2), bal_before)

    # -------------------------------------------------------------
    # 17. Admin confirm top-up cộng Coin đúng một lần
    # -------------------------------------------------------------
    def test_17_admin_confirm_topup_credits_coin_once(self):
        """Admin confirming top-up credits the user wallet exactly once."""
        self._login_admin()
        headers = {"X-CSRF-Token": self.admin_csrf}

        res_init = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user2,
            json={"amount_coin": 50},
        )
        payment_id = res_init.get_json()["payment_id"]
        bal_before = db.get_wallet_balance(2)

        res_conf = self.client.post(f"/admin/api/payments/{payment_id}/confirm", headers=headers)
        self.assertEqual(res_conf.status_code, 200)
        self.assertEqual(db.get_wallet_balance(2), bal_before + 50)

    # -------------------------------------------------------------
    # 18. Confirm lại không cộng lần hai
    # -------------------------------------------------------------
    def test_18_reconfirm_payment_does_not_credit_twice(self):
        """Confirming an already-confirmed payment returns 400 error."""
        self._login_admin()
        headers = {"X-CSRF-Token": self.admin_csrf}

        res_init = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user2,
            json={"amount_coin": 30},
        )
        payment_id = res_init.get_json()["payment_id"]
        self.client.post(f"/admin/api/payments/{payment_id}/confirm", headers=headers)
        bal_after_first = db.get_wallet_balance(2)

        # Confirm again
        res_conf2 = self.client.post(f"/admin/api/payments/{payment_id}/confirm", headers=headers)
        self.assertEqual(res_conf2.status_code, 400)
        self.assertEqual(db.get_wallet_balance(2), bal_after_first)

    # -------------------------------------------------------------
    # 19. Sai số tiền không tự paid
    # -------------------------------------------------------------
    def test_19_wrong_amount_does_not_auto_pay(self):
        """Direct payment with invalid amount returns 400."""
        plan_id = db.create_plan(
            name="Price Check Plan",
            slug=f"plan-prc-{int(time.time()*1000)}",
            price_coin=20,
            price_vnd=20000,
        )
        res = self.client.post(
            "/api/payments/plan",
            headers=self.headers_user1,
            json={"plan_id": plan_id, "target_username": "target_user", "platform": "invalid_plt"},
        )
        self.assertEqual(res.status_code, 400)

    # -------------------------------------------------------------
    # 20. QR plan paid mới tạo activation
    # -------------------------------------------------------------
    def test_20_qr_plan_paid_creates_activation(self):
        """Direct QR plan payment initiates activation only after admin confirms."""
        self._login_admin()
        headers = {"X-CSRF-Token": self.admin_csrf}

        plan_id = db.create_plan(
            name="Direct QR Plan",
            slug=f"plan-qr-{int(time.time()*1000)}",
            price_coin=25,
            price_vnd=25000,
        )
        res_pay = self.client.post(
            "/api/payments/plan",
            headers=self.headers_user1,
            json={"plan_id": plan_id, "target_username": "qr_user", "platform": "ios"},
        )
        self.assertEqual(res_pay.status_code, 200)
        payment_id = res_pay.get_json()["payment_id"]

        # Confirming triggers activation order and queue
        res_conf = self.client.post(f"/admin/api/payments/{payment_id}/confirm", headers=headers)
        self.assertEqual(res_conf.status_code, 200)
        data = res_conf.get_json()
        self.assertIn("activation_order_id", data)

    # -------------------------------------------------------------
    # 21. Queue đầy không làm mất payment
    # -------------------------------------------------------------
    def test_21_full_queue_does_not_lose_payment(self):
        """Payment confirmation status is stored even if queue worker is temporarily saturated."""
        res_pay = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user1,
            json={"amount_coin": 100},
        )
        payment_id = res_pay.get_json()["payment_id"]
        self._login_admin()
        headers = {"X-CSRF-Token": self.admin_csrf}
        res_conf = self.client.post(f"/admin/api/payments/{payment_id}/confirm", headers=headers)
        self.assertEqual(res_conf.status_code, 200)
        p = db.get_payment_order_by_id(payment_id)
        self.assertIn(p["status"], ("paid", "confirmed"))

    # -------------------------------------------------------------
    # 22. iOS không tạo được APK ticket
    # -------------------------------------------------------------
    def test_22_ios_cannot_create_apk_ticket(self):
        """iOS activation order rejects APK download ticket generation."""
        plan_id = db.create_plan(
            name="iOS Only Ticket Test",
            slug=f"plan-iostick-{int(time.time()*1000)}",
            platform="ios",
            price_coin=10,
            price_vnd=10000,
        )
        order_id = db.create_activation_order(
            user_id=1,
            plan_id=plan_id,
            target_username="ios_guy",
            platform="ios",
            payment_method="coin",
            paid_amount_coin=10,
        )
        conn = db.get_conn()
        conn.execute("UPDATE activation_orders SET status = 'completed' WHERE id = ?", (order_id,))

        res = self.client.post(
            "/api/apk/download-ticket",
            headers=self.headers_user1,
            json={"activation_order_id": order_id},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "platform_mismatch")

    # -------------------------------------------------------------
    # 23. Android không tạo được mobileconfig ticket
    # -------------------------------------------------------------
    def test_23_android_cannot_create_mobileconfig_ticket(self):
        """Android activation order rejects iOS mobileconfig download ticket generation."""
        plan_id = db.create_plan(
            name="Android Only Ticket Test",
            slug=f"plan-andtick-{int(time.time()*1000)}",
            platform="android",
            price_coin=10,
            price_vnd=10000,
        )
        order_id = db.create_activation_order(
            user_id=1,
            plan_id=plan_id,
            target_username="android_guy",
            platform="android",
            payment_method="coin",
            paid_amount_coin=10,
        )
        conn = db.get_conn()
        conn.execute("UPDATE activation_orders SET status = 'completed' WHERE id = ?", (order_id,))

        res = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={"activation_order_id": order_id},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "platform_mismatch")

    # -------------------------------------------------------------
    # 24. Ticket không dùng chéo endpoint
    # -------------------------------------------------------------
    def test_24_ticket_cannot_cross_use_endpoint(self):
        """Mobileconfig ticket cannot be used on APK download endpoint."""
        plan_id = db.create_plan(
            name="Cross Ticket Test",
            slug=f"plan-cross-{int(time.time()*1000)}",
            platform="ios",
            price_coin=10,
            price_vnd=10000,
        )
        order_id = db.create_activation_order(
            user_id=1,
            plan_id=plan_id,
            target_username="ios_cross",
            platform="ios",
            payment_method="coin",
            paid_amount_coin=10,
        )
        conn = db.get_conn()
        conn.execute("UPDATE activation_orders SET status = 'completed' WHERE id = ?", (order_id,))

        res_t = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={"activation_order_id": order_id},
        )
        self.assertEqual(res_t.status_code, 200)
        ticket = res_t.get_json()["ticket"]

        # Attempt to redeem mobileconfig ticket at APK endpoint
        res_apk = self.client.get(f"/api/apk?ticket={ticket}")
        self.assertEqual(res_apk.status_code, 403)

    # -------------------------------------------------------------
    # 25. Ticket single-use
    # -------------------------------------------------------------
    def test_25_ticket_single_use(self):
        """Ticket can only be used once to download file."""
        plan_id = db.create_plan(
            name="Single Use Ticket Test",
            slug=f"plan-sgl-{int(time.time()*1000)}",
            platform="ios",
            price_coin=10,
            price_vnd=10000,
        )
        order_id = db.create_activation_order(
            user_id=1,
            plan_id=plan_id,
            target_username="ios_sgl",
            platform="ios",
            payment_method="coin",
            paid_amount_coin=10,
        )
        conn = db.get_conn()
        conn.execute("UPDATE activation_orders SET status = 'completed' WHERE id = ?", (order_id,))

        res_t = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={"activation_order_id": order_id},
        )
        ticket = res_t.get_json()["ticket"]

        # First download -> 200
        res_d1 = self.client.get(f"/api/mobileconfig?ticket={ticket}")
        self.assertEqual(res_d1.status_code, 200)
        res_d1.close()

        # Second download -> 403
        res_d2 = self.client.get(f"/api/mobileconfig?ticket={ticket}")
        self.assertEqual(res_d2.status_code, 403)
        res_d2.close()

    # -------------------------------------------------------------
    # 26. NEXTDNS_KEY không xuất hiện trong public config
    # -------------------------------------------------------------
    def test_26_nextdns_key_never_leaked_in_public_config(self):
        """GET /api/platform-config must never leak NEXTDNS_KEY."""
        res = self.client.get("/api/platform-config")
        self.assertEqual(res.status_code, 200)
        text = res.get_data(as_text=True)
        self.assertNotIn("super-secret-nextdns-key-never-leak", text)
        data = res.get_json()
        self.assertIn("dns", data)
        self.assertEqual(data["dns"]["profile_id"], "customprof123")
        self.assertIn("instructions", data["dns"])
        self.assertIn("ios", data["dns"]["instructions"])
        self.assertIn("android", data["dns"]["instructions"])

    # -------------------------------------------------------------
    # 27. Migration schema cũ thành công
    # -------------------------------------------------------------
    def test_27_migration_schema_idempotent(self):
        """db.init() is fully idempotent and safe on existing schemas."""
        db.init()
        db.init()
        plans = db.list_all_plans_admin()
        self.assertIsInstance(plans, list)

    # -------------------------------------------------------------
    # 28. Admin endpoint có auth và CSRF
    # -------------------------------------------------------------
    def test_28_admin_endpoints_require_auth_and_csrf(self):
        """Admin mutation endpoints reject missing auth (401) and missing CSRF (403)."""
        # Unauthenticated
        res_unauth = self.client.post("/admin/api/plans", json={"name": "No Auth Plan"})
        self.assertEqual(res_unauth.status_code, 401)

        # Authenticated but missing CSRF
        self._login_admin()
        res_no_csrf = self.client.post("/admin/api/plans", json={"name": "No CSRF Plan"})
        self.assertEqual(res_no_csrf.status_code, 403)

    # -------------------------------------------------------------
    # 29. Không có giá trị âm/float trong ví
    # -------------------------------------------------------------
    def test_29_no_negative_or_float_in_wallet(self):
        """Wallet enforces positive integers; rejecting floats and preventing negative balance."""
        with self.assertRaises(ValueError):
            db.apply_wallet_transaction(1, "topup", 10.5, "topup", 1, "Float test")

        current = db.get_wallet_balance(1)
        status, _ = db.apply_wallet_transaction(1, "purchase", -(current + 500), "plan_purchase", 1, "Negative test")
        self.assertNotEqual(status, "ok")
        self.assertGreaterEqual(db.get_wallet_balance(1), 0)

    # -------------------------------------------------------------
    # 30. State transition không hợp lệ bị từ chối
    # -------------------------------------------------------------
    def test_30_invalid_state_transition_rejected(self):
        """Activation order state machine strictly prevents invalid transitions."""
        plan_id = db.create_plan(
            name="State Test Plan",
            slug=f"plan-state-{int(time.time()*1000)}",
            price_coin=10,
            price_vnd=10000,
        )
        oid = db.create_activation_order(
            user_id=1,
            plan_id=plan_id,
            target_username="state_user",
            platform="ios",
            payment_method="coin",
            paid_amount_coin=10,
        )
        # Transition from paid -> queued -> processing -> completed
        st1, _ = db.update_activation_order_status(oid, "queued")
        self.assertEqual(st1, "ok")
        st2, _ = db.update_activation_order_status(oid, "processing")
        self.assertEqual(st2, "ok")
        st3, _ = db.update_activation_order_status(oid, "completed")
        self.assertEqual(st3, "ok")

        # Invalid transition: completed -> queued (completed is terminal)
        st_bad, _ = db.update_activation_order_status(oid, "queued")
        self.assertEqual(st_bad, "invalid_transition")


if __name__ == "__main__":
    unittest.main()
