import os
import sys
import tempfile
import time
import unittest
import threading
from werkzeug.security import generate_password_hash

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "test-secret-coupon-popup-12345"
os.environ["JWT_SECRET"] = "test-jwt-secret-coupon-popup-12345678"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-coupon-popup-123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"
os.environ["VIETQR_BANK_ID"] = "TPB"
os.environ["VIETQR_ACCOUNT_NO"] = "HUYDEV204"
os.environ["VIETQR_ACCOUNT_NAME"] = "HA QUANG HUY"
os.environ["VIETQR_TEMPLATE"] = "compact2"
os.environ["PAYMENT_TRANSFER_PREFIX"] = "LOCKETGOLDCPN"
os.environ["PAYMENT_TRANSFER_DIGITS"] = "3"
os.environ["PAYMENT_TTL_SECONDS"] = "600"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db, coupon_service, site_settings, payment_service
from locket.token_auth import create_token_family, create_access_token
from locket.user_auth import reset_rate_limits
from locket.public.routes import reset_renew_rate_limits


class CouponPopupSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCKET_DB"] = temp_db_path
        db.close_conn()

        cls.app = create_app()
        cls.app.config["TESTING"] = True

        conn = db.get_conn()
        now = time.time()
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, role, is_active, created_at) "
            "VALUES (1, 'admin@test.com', 'admin', 'Administrator', ?, 'admin', 1, ?)",
            (generate_password_hash("admin-secret-password-1234"), now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, role, is_active, created_at) "
            "VALUES (201, 'coupon_user1@test.com', 'cpuser1', 'Coupon User 1', ?, 'user', 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, role, is_active, created_at) "
            "VALUES (202, 'coupon_user2@test.com', 'cpuser2', 'Coupon User 2', ?, 'user', 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        conn.commit()

        # Create plans for tests
        cls.plan_30k = db.create_plan(
            name="Plan 30K",
            slug="plan-30k",
            description="30K VND Plan",
            price_vnd=30000,
            price_coin=30,
            duration_days=30,
            supported_platforms="all",
            badge="POPULAR",
            sort_order=1,
            is_active=1,
        )
        cls.plan_100k = db.create_plan(
            name="Plan 100K",
            slug="plan-100k",
            description="100K VND Plan",
            price_vnd=100000,
            price_coin=100,
            duration_days=90,
            supported_platforms="all",
            badge="BEST",
            sort_order=2,
            is_active=1,
        )

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
        reset_renew_rate_limits()

        csrf_res = self.client.get("/api/auth/csrf")
        self.assertEqual(csrf_res.status_code, 200)
        self.csrf_token = csrf_res.get_json()["csrf_token"]

        fam1, _, _ = create_token_family(user_id=201)
        self.token_user1 = create_access_token(201, fam1)
        self.headers_user1 = {
            "Authorization": f"Bearer {self.token_user1}",
            "X-CSRF-Token": self.csrf_token,
        }

        fam2, _, _ = create_token_family(user_id=202)
        self.token_user2 = create_access_token(202, fam2)
        self.headers_user2 = {
            "Authorization": f"Bearer {self.token_user2}",
            "X-CSRF-Token": self.csrf_token,
        }

        fam_admin, _, _ = create_token_family(user_id=1)
        self.token_admin = create_access_token(1, fam_admin)
        self.admin_headers = {
            "Authorization": f"Bearer {self.token_admin}",
            "X-CSRF-Token": self.csrf_token,
        }

    # ==================== 1. Normalization & Math Tests ====================
    def test_coupon_normalization(self):
        self.assertEqual(coupon_service.normalize_code("  diScOunt50  "), "DISCOUNT50")
        self.assertEqual(coupon_service.normalize_code("PROMO_2026"), "PROMO_2026")
        self.assertEqual(coupon_service.normalize_code("SALE-OFF"), "SALE-OFF")
        with self.assertRaises(ValueError):
            coupon_service.normalize_code("")
        with self.assertRaises(ValueError):
            coupon_service.normalize_code("   ")
        with self.assertRaises(ValueError):
            coupon_service.normalize_code("INVALID@CHAR!")

    def test_coupon_pricing_math(self):
        # 10% on 30,000 -> 3,000 discount, final 27,000 VND
        res = coupon_service.calculate_discount(
            original_vnd=30000,
            discount_type="percent",
            discount_value=10,
            max_discount_vnd=None,
        )
        self.assertEqual(res["discount_vnd"], 3000)
        self.assertEqual(res["final_vnd"], 27000)
        self.assertEqual(res["final_coin"], 27)

        # 50% on 100,000 with max_discount 20,000 -> capped at 20,000 discount, final 80,000 VND
        res_capped = coupon_service.calculate_discount(
            original_vnd=100000,
            discount_type="percent",
            discount_value=50,
            max_discount_vnd=20000,
        )
        self.assertEqual(res_capped["discount_vnd"], 20000)
        self.assertEqual(res_capped["final_vnd"], 80000)
        self.assertEqual(res_capped["final_coin"], 80)

        # Fixed discount 15,000 VND on 30,000 VND -> final 15,000 VND
        res_fixed = coupon_service.calculate_discount(
            original_vnd=30000,
            discount_type="fixed",
            discount_value=15000,
            max_discount_vnd=None,
        )
        self.assertEqual(res_fixed["discount_vnd"], 15000)
        self.assertEqual(res_fixed["final_vnd"], 15000)
        self.assertEqual(res_fixed["final_coin"], 15)

        # Enforce minimum payable amount: 50,000 fixed discount on 30,000 order raises ValueError (cannot drop below 1,000 VND)
        with self.assertRaises(ValueError):
            coupon_service.calculate_discount(
                original_vnd=30000,
                discount_type="fixed",
                discount_value=50000,
            )

    # ==================== 2. Validate Endpoint Tests ====================
    def test_validate_coupon_api(self):
        now = time.time()
        c_obj = db.create_coupon(
            code="API_TEST_10",
            name="API Test Coupon 10%",
            discount_type="percent",
            discount_value=10,
            min_order_vnd=20000,
            max_discount_vnd=50000,
            usage_limit_total=10,
            usage_limit_per_user=1,
            starts_at=now - 100,
            ends_at=now + 3600,
            is_active=1,
            description="API test coupon",
            plan_ids=[self.plan_30k],
        )
        self.assertIsNotNone(c_obj)

        # Valid validation request
        res = self.client.post(
            "/api/coupons/validate",
            json={"code": " api_test_10 ", "plan_id": self.plan_30k},
            headers=self.headers_user1,
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["valid"])
        quote = data["quote"]
        self.assertEqual(quote["discount_vnd"], 3000)
        self.assertEqual(quote["final_vnd"], 27000)
        self.assertEqual(quote["final_coin"], 27)

        # Test plan restriction
        res_wrong_plan = self.client.post(
            "/api/coupons/validate",
            json={"code": "API_TEST_10", "plan_id": self.plan_100k},
            headers=self.headers_user1,
        )
        self.assertEqual(res_wrong_plan.status_code, 400)
        data_wrong = res_wrong_plan.get_json()
        self.assertFalse(data_wrong["valid"])
        self.assertEqual(data_wrong["error"], "plan_not_eligible")

        # Test not found
        res_nf = self.client.post(
            "/api/coupons/validate",
            json={"code": "NONEXISTENT", "plan_id": self.plan_30k},
            headers=self.headers_user1,
        )
        self.assertEqual(res_nf.status_code, 400)
        self.assertFalse(res_nf.get_json()["valid"])
        self.assertEqual(res_nf.get_json()["error"], "coupon_not_found")

    # ==================== 3. Coin Purchase Flow & Refund Snapshots ====================
    def test_coin_purchase_with_coupon_and_refund(self):
        now = time.time()
        conn = db.get_conn()
        conn.execute("INSERT OR REPLACE INTO wallets (user_id, balance_coin, updated_at) VALUES (201, 100, ?)", (now,))
        conn.commit()

        c_obj = db.create_coupon(
            code="COIN_SAVE_20",
            name="Coin Save 20%",
            discount_type="percent",
            discount_value=20,
            usage_limit_total=5,
            usage_limit_per_user=1,
            is_active=1,
            plan_ids=[self.plan_30k],
        )
        c_id = c_obj["id"]

        # Purchase with coin (30 coin plan with 20% off -> 24 coin)
        res = self.client.post(
            "/api/orders/coin",
            json={
                "plan_id": self.plan_30k,
                "platform": "ios",
                "username": "test_locket_user",
                "device_id": "test-device-uuid-1",
                "coupon_code": "COIN_SAVE_20",
            },
            headers=self.headers_user1,
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        order_id = data["order"]["id"]

        # Check user balance: 100 - 24 = 76
        wallet = db.get_conn().execute("SELECT balance_coin FROM wallets WHERE user_id = 201").fetchone()
        self.assertEqual(wallet["balance_coin"], 76)

        # Check snapshots in activation_orders
        order = db.get_activation_order_by_id(order_id)
        self.assertEqual(order["price_coin_snapshot"], 24)
        self.assertEqual(order["original_price_coin_snapshot"], 30)
        self.assertEqual(order["original_price_vnd_snapshot"], 30000)
        self.assertEqual(order["discount_vnd_snapshot"], 6000)
        self.assertEqual(order["coupon_id"], c_id)
        self.assertEqual(order["coupon_code_snapshot"], "COIN_SAVE_20")

        # Verify redemption record status is 'redeemed'
        conn = db.get_conn()
        redemptions = conn.execute("SELECT * FROM coupon_redemptions WHERE coupon_id = ?", (c_id,)).fetchall()
        self.assertEqual(len(redemptions), 1)
        self.assertEqual(redemptions[0]["status"], "redeemed")
        self.assertEqual(redemptions[0]["discount_vnd"], 6000)

        # Test per-user limit reached for User 201
        res_limit = self.client.post(
            "/api/orders/coin",
            json={
                "plan_id": self.plan_30k,
                "platform": "ios",
                "username": "test_locket_user",
                "device_id": "test-device-uuid-2",
                "coupon_code": "COIN_SAVE_20",
            },
            headers=self.headers_user1,
        )
        self.assertEqual(res_limit.status_code, 400)
        self.assertTrue("limit" in res_limit.get_json().get("error", ""))

        # Test refund: cancel/refund order -> refunds actual paid coin (24), NOT 30!
        refund_ok, refund_msg = db.refund_activation_order_coin(order_id, reason="Customer cancelled")
        self.assertEqual(refund_ok, "ok")
        wallet_after_refund = db.get_conn().execute("SELECT balance_coin FROM wallets WHERE user_id = 201").fetchone()
        self.assertEqual(wallet_after_refund["balance_coin"], 100)  # 76 + 24 = 100

    # ==================== 4. VietQR Flow: Reservation, Confirm, Reject ====================
    def test_vietqr_payment_order_with_coupon_lifecycle(self):
        c_obj = db.create_coupon(
            code="QR_SAVE_5K",
            name="QR Save 5K",
            discount_type="fixed_vnd",
            discount_value=5000,
            usage_limit_total=2,
            usage_limit_per_user=1,
            is_active=1,
        )
        c_id = c_obj["id"]

        # 1. Create plan payment order with coupon
        res = self.client.post(
            "/api/payments/plan",
            json={
                "plan_id": self.plan_30k,
                "platform": "android",
                "username": "test_locket_user",
                "coupon_code": "QR_SAVE_5K",
            },
            headers=self.headers_user1,
        )
        self.assertEqual(res.status_code, 200)
        pay_data = res.get_json()
        payment_id = pay_data.get("payment_id")
        self.assertIsNotNone(payment_id)

        # Original 30,000 - 5,000 = 25,000 VND
        self.assertEqual(pay_data["amount_vnd"], 25000)

        # Check DB payment_orders snapshots
        pay_row = db.get_payment_order_by_id(payment_id)
        self.assertEqual(pay_row["amount_vnd"], 25000)
        self.assertEqual(pay_row["original_price_vnd_snapshot"], 30000)
        self.assertEqual(pay_row["discount_vnd_snapshot"], 5000)
        self.assertEqual(pay_row["coupon_code_snapshot"], "QR_SAVE_5K")

        # Verify coupon is in 'reserved' status
        conn = db.get_conn()
        red = conn.execute("SELECT * FROM coupon_redemptions WHERE payment_order_id = ?", (payment_id,)).fetchone()
        self.assertIsNotNone(red)
        self.assertEqual(red["status"], "reserved")
        self.assertEqual(red["coupon_id"], c_id)

        # 2. Confirm payment order -> redemption status transitions to 'redeemed'
        bank_ref = f"BANK_TEST_{int(time.time())}"
        status, updated = db.confirm_payment_order_tx(payment_id, bank_ref)
        self.assertEqual(status, "ok")
        self.assertEqual(updated["status"], "paid")

        red_after = conn.execute("SELECT * FROM coupon_redemptions WHERE payment_order_id = ?", (payment_id,)).fetchone()
        self.assertEqual(red_after["status"], "redeemed")
        self.assertIsNotNone(red_after["redeemed_at"])

    def test_vietqr_payment_reject_releases_coupon(self):
        c_obj = db.create_coupon(
            code="QR_REJECT_TEST",
            name="QR Reject Test",
            discount_type="percent",
            discount_value=10,
            usage_limit_total=1,
            usage_limit_per_user=1,
            is_active=1,
        )
        c_id = c_obj["id"]

        # User 1 creates payment order -> takes 1/1 quota
        res1 = self.client.post(
            "/api/payments/plan",
            json={"plan_id": self.plan_30k, "platform": "ios", "username": "test_locket_user", "coupon_code": "QR_REJECT_TEST"},
            headers=self.headers_user1,
        )
        self.assertEqual(res1.status_code, 200)
        pay_id = res1.get_json()["payment_id"]

        # User 2 tries to use the coupon -> quota exceeded because User 1 holds reservation
        res2 = self.client.post(
            "/api/payments/plan",
            json={"plan_id": self.plan_30k, "platform": "ios", "username": "test_locket_user", "coupon_code": "QR_REJECT_TEST"},
            headers=self.headers_user2,
        )
        self.assertEqual(res2.status_code, 400)
        err = res2.get_json().get("error", "")
        self.assertTrue("exhausted" in err or "usage_limit" in err)

        # Admin cancels/rejects User 1 payment order -> releases coupon quota
        rej_status, _ = db.reject_payment_order_tx(pay_id, status="cancelled", note="User cancelled")
        self.assertEqual(rej_status, "ok")

        # Now User 2 can successfully use the released coupon!
        res2_retry = self.client.post(
            "/api/payments/plan",
            json={"plan_id": self.plan_30k, "platform": "ios", "username": "test_locket_user", "coupon_code": "QR_REJECT_TEST"},
            headers=self.headers_user2,
        )
        self.assertEqual(res2_retry.status_code, 200)

    # ==================== 5. Renew Payment Order Preserves Coupon ====================
    def test_renew_payment_order_preserves_coupon(self):
        c_obj = db.create_coupon(
            code="RENEW_COUPON_10K",
            name="Renew Coupon 10K",
            discount_type="fixed_vnd",
            discount_value=10000,
            usage_limit_total=1,
            is_active=1,
        )
        c_id = c_obj["id"]

        res = self.client.post(
            "/api/payments/plan",
            json={"plan_id": self.plan_30k, "platform": "ios", "username": "test_locket_user", "coupon_code": "RENEW_COUPON_10K"},
            headers=self.headers_user1,
        )
        self.assertEqual(res.status_code, 200)
        old_pay_data = res.get_json()
        old_pay_id = old_pay_data["payment_id"]
        old_pay_code = old_pay_data["payment_code"]

        # Manually expire the payment to allow renewal
        conn = db.get_conn()
        past = time.time() - 700
        conn.execute("UPDATE payment_orders SET expires_at = ?, status = 'pending' WHERE id = ?", (past, old_pay_id))
        conn.commit()

        # Call renew endpoint using payment_code
        res_renew = self.client.post(
            f"/api/payments/{old_pay_code}/renew",
            headers=self.headers_user1,
        )
        self.assertEqual(res_renew.status_code, 200)
        renew_data = res_renew.get_json()
        new_pay_id = renew_data["payment_id"]
        self.assertNotEqual(old_pay_id, new_pay_id)
        self.assertEqual(renew_data["amount_vnd"], 20000)

        # Check DB payment_orders snapshots on new payment
        new_pay_row = db.get_payment_order_by_id(new_pay_id)
        self.assertEqual(new_pay_row["discount_vnd_snapshot"], 10000)
        self.assertEqual(new_pay_row["coupon_code_snapshot"], "RENEW_COUPON_10K")

        # Check that there is STILL only 1 redemption record in the DB (transferred, not duplicated)
        conn = db.get_conn()
        reds = conn.execute("SELECT * FROM coupon_redemptions WHERE coupon_id = ?", (c_id,)).fetchall()
        self.assertEqual(len(reds), 1)
        self.assertEqual(reds[0]["payment_order_id"], new_pay_id)
        self.assertEqual(reds[0]["status"], "reserved")

    # ==================== 6. Concurrency / Race Condition ====================
    def test_coupon_concurrency_race_condition(self):
        c_obj = db.create_coupon(
            code="RACE_COUPON_1",
            name="Race Coupon 1",
            discount_type="fixed_vnd",
            discount_value=5000,
            usage_limit_total=1,
            usage_limit_per_user=1,
            is_active=1,
        )

        results = []

        def worker(headers):
            res = self.client.post(
                "/api/payments/plan",
                json={"plan_id": self.plan_30k, "platform": "ios", "username": "test_locket_user", "coupon_code": "RACE_COUPON_1"},
                headers=headers,
            )
            results.append((res.status_code, res.get_json()))

        t1 = threading.Thread(target=worker, args=(self.headers_user1,))
        t2 = threading.Thread(target=worker, args=(self.headers_user2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0] == 200]
        failures = [r for r in results if r[0] == 400]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        err = failures[0][1].get("error", "")
        self.assertTrue("exhausted" in err or "usage_limit" in err)

    def test_coupon_idempotent_retries_do_not_double_charge_or_conflict(self):
        conn = db.get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO wallets (user_id, balance_coin, updated_at) VALUES (201, 100, ?)",
            (time.time(),),
        )
        conn.commit()
        coupon = db.create_coupon(
            code="IDEMPOTENT_RETRY_25",
            name="Idempotent retry 25%",
            discount_type="percent",
            discount_value=25,
            usage_limit_total=2,
            usage_limit_per_user=2,
            plan_ids=[self.plan_100k],
        )

        coin_payload = {
            "plan_id": self.plan_100k,
            "platform": "ios",
            "username": "retry_coin_user",
            "coupon_code": "  idempotent_retry_25  ",
            "idempotency_key": "coupon-coin-retry-key",
        }
        first_coin = self.client.post("/api/orders/coin", json=coin_payload, headers=self.headers_user1)
        second_coin = self.client.post("/api/orders/coin", json=coin_payload, headers=self.headers_user1)
        self.assertEqual(first_coin.status_code, 200)
        self.assertEqual(second_coin.status_code, 200)
        self.assertEqual(first_coin.get_json()["activation_order_id"], second_coin.get_json()["activation_order_id"])
        self.assertTrue(second_coin.get_json()["idempotent"])
        self.assertEqual(
            db.get_conn().execute("SELECT balance_coin FROM wallets WHERE user_id = 201").fetchone()["balance_coin"],
            25,
        )

        qr_payload = {
            "plan_id": self.plan_100k,
            "platform": "ios",
            "username": "retry_qr_user",
            "coupon_code": "IDEMPOTENT_RETRY_25",
            "idempotency_key": "coupon-qr-retry-key",
        }
        first_qr = self.client.post("/api/payments/plan", json=qr_payload, headers=self.headers_user2)
        second_qr = self.client.post("/api/payments/plan", json=qr_payload, headers=self.headers_user2)
        self.assertEqual(first_qr.status_code, 200)
        self.assertEqual(second_qr.status_code, 200)
        self.assertEqual(first_qr.get_json()["payment_id"], second_qr.get_json()["payment_id"])
        self.assertEqual(
            db.get_conn().execute(
                "SELECT COUNT(*) AS cnt FROM coupon_redemptions WHERE coupon_id = ?",
                (coupon["id"],),
            ).fetchone()["cnt"],
            2,
        )

    def test_renew_reacquires_released_quota_and_is_idempotent(self):
        coupon = db.create_coupon(
            code="RENEW_QUOTA_GUARD",
            name="Renew quota guard",
            discount_type="fixed_vnd",
            discount_value=5000,
            usage_limit_total=1,
            usage_limit_per_user=1,
        )
        payload = {
            "plan_id": self.plan_30k,
            "platform": "ios",
            "username": "renew_guard_user",
            "coupon_code": coupon["code"],
        }
        first = self.client.post("/api/payments/plan", json=payload, headers=self.headers_user1)
        self.assertEqual(first.status_code, 200)
        first_data = first.get_json()
        self.assertEqual(db.reject_payment_order_tx(first_data["payment_id"], status="expired")[0], "ok")

        other = self.client.post("/api/payments/plan", json=payload, headers=self.headers_user2)
        self.assertEqual(other.status_code, 200)
        blocked = self.client.post(
            f"/api/payments/{first_data['payment_code']}/renew",
            headers=self.headers_user1,
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["error"], "coupon_exhausted")

        # Releasing the competing reservation allows one renewal. Repeating the
        # request against the old payment returns that same replacement.
        self.assertEqual(db.reject_payment_order_tx(other.get_json()["payment_id"], status="expired")[0], "ok")
        renewed = self.client.post(
            f"/api/payments/{first_data['payment_code']}/renew",
            headers=self.headers_user1,
        )
        self.assertEqual(renewed.status_code, 200)
        reset_renew_rate_limits()
        replay = self.client.post(
            f"/api/payments/{first_data['payment_code']}/renew",
            headers=self.headers_user1,
        )
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(renewed.get_json()["payment_id"], replay.get_json()["payment_id"])

    def test_manual_late_confirmation_redeems_released_coupon(self):
        coupon = db.create_coupon(
            code="LATE_MANUAL_CONFIRM",
            name="Late manual confirm",
            discount_type="fixed_vnd",
            discount_value=5000,
            usage_limit_total=2,
        )
        created = self.client.post(
            "/api/payments/plan",
            json={
                "plan_id": self.plan_30k,
                "platform": "ios",
                "username": "late_paid_user",
                "coupon_code": coupon["code"],
            },
            headers=self.headers_user1,
        )
        self.assertEqual(created.status_code, 200)
        payment_id = created.get_json()["payment_id"]
        self.assertEqual(db.reject_payment_order_tx(payment_id, status="expired")[0], "ok")
        status, _ = db.confirm_payment_order_tx(
            payment_id,
            "BANK_LATE_MANUAL_CONFIRM",
            manual_override=True,
            manual_reason="Đã kiểm tra sao kê ngân hàng",
        )
        self.assertEqual(status, "ok")
        redemption = db.get_conn().execute(
            "SELECT status, released_at FROM coupon_redemptions WHERE payment_order_id = ?",
            (payment_id,),
        ).fetchone()
        self.assertEqual(redemption["status"], "redeemed")
        self.assertIsNone(redemption["released_at"])

    def test_user_cancel_payment_releases_coupon_and_checks_ownership(self):
        coupon = db.create_coupon(
            code="USER_CANCEL_RELEASE",
            name="User cancellation release",
            discount_type="fixed_vnd",
            discount_value=5000,
            usage_limit_total=1,
        )
        created = self.client.post(
            "/api/payments/plan",
            json={
                "plan_id": self.plan_30k,
                "platform": "ios",
                "username": "cancel_owner",
                "coupon_code": coupon["code"],
            },
            headers=self.headers_user1,
        )
        self.assertEqual(created.status_code, 200)
        payment_code = created.get_json()["payment_code"]
        payment_id = created.get_json()["payment_id"]

        forbidden = self.client.post(
            f"/api/payments/{payment_code}/cancel", headers=self.headers_user2
        )
        self.assertEqual(forbidden.status_code, 403)
        cancelled = self.client.post(
            f"/api/payments/{payment_code}/cancel", headers=self.headers_user1
        )
        self.assertEqual(cancelled.status_code, 200)
        redemption = db.get_conn().execute(
            "SELECT status FROM coupon_redemptions WHERE payment_order_id = ?",
            (payment_id,),
        ).fetchone()
        self.assertEqual(redemption["status"], "released")

    # ==================== 7. Global Announcement Popup System ====================
    def test_popup_payload_validation_and_url_security(self):
        valid_payload = {
            "enabled": True,
            "version": 1,
            "title": "Welcome Announcement",
            "message": "Welcome to Locket Gold Huy Dev!",
            "icon": "party",
            "button_text": "Explore Plans",
            "button_url": "/dashboard/plans",
            "dismissible": True,
            "audience": "all",
            "display_mode": "once_per_version",
            "routes": ["/dashboard", "/"],
            "start_at": "2026-01-01T00:00:00Z",
            "end_at": "2026-12-31T23:59:59Z",
        }
        # Should not raise
        site_settings.validate_popup_payload(valid_payload)

        # Relative safe URL should not raise
        site_settings.validate_popup_payload({**valid_payload, "button_url": "https://example.com/promo"})

        # Unsafe button URL rejection
        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({**valid_payload, "button_url": "javascript:alert(1)"})

        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({**valid_payload, "button_url": "http://insecure.com"})

        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({**valid_payload, "button_url": "//evil.example/promo"})

        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({**valid_payload, "button_url": "https://user@example.com/promo"})

        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({**valid_payload, "button_text": "", "button_url": "/dashboard"})

        # Inverted date order
        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({
                **valid_payload,
                "start_at": "2026-12-31T00:00:00Z",
                "end_at": "2026-01-01T00:00:00Z",
            })

        # Invalid icon
        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({**valid_payload, "icon": "invalid_icon_name"})

        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({**valid_payload, "routes": ["//evil.example"]})

        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({**valid_payload, "version": True})

        # Mixed aware/naive ISO values are normalized before comparison and
        # must produce a validation error, never an internal TypeError/500.
        with self.assertRaises(ValueError):
            site_settings.validate_popup_payload({
                **valid_payload,
                "start_at": "2026-12-31T00:00:00",
                "end_at": "2026-01-01T00:00:00Z",
            })

    def test_popup_active_and_public_settings_api(self):
        popup_data = {
            "enabled": True,
            "version": 2,
            "title": "Sale Flash 50%",
            "message": "Nhập mã SALE50 để nhận ưu đãi đặc biệt!",
            "icon": "sparkles",
            "button_text": "Mua Ngay",
            "button_url": "/dashboard",
            "dismissible": True,
            "audience": "all",
            "display_mode": "every_visit",
            "routes": [],
            "start_at": None,
            "end_at": None,
        }
        res_put = self.client.put(
            "/api/admin/popup",
            json=popup_data,
            headers=self.admin_headers,
        )
        self.assertEqual(res_put.status_code, 200)

        # Check public site settings endpoint
        res_pub = self.client.get("/api/site/settings")
        self.assertEqual(res_pub.status_code, 200)
        pub_data = res_pub.get_json()
        self.assertIn("popup", pub_data)
        pop = pub_data["popup"]
        self.assertEqual(pop["title"], "Sale Flash 50%")
        self.assertEqual(pop["version"], 2)
        self.assertTrue(pop["active"])

    # ==================== 8. Admin Coupon CRUD & Stats API ====================
    def test_admin_coupon_crud_api_and_stats(self):
        # Create coupon
        create_payload = {
            "code": "admin_promo_30",
            "name": "Admin Promo 30%",
            "discount_type": "percent",
            "discount_value": 30,
            "min_order_vnd": 20000,
            "max_discount_vnd": 60000,
            "usage_limit_total": 50,
            "usage_limit_per_user": 2,
            "plan_ids": [self.plan_30k],
            "description": "Admin created discount",
        }
        res_create = self.client.post(
            "/api/admin/coupons",
            json=create_payload,
            headers=self.admin_headers,
        )
        self.assertEqual(res_create.status_code, 201)
        created_coupon = res_create.get_json()["coupon"]
        c_id = created_coupon["id"]
        self.assertEqual(created_coupon["code"], "ADMIN_PROMO_30")

        # List coupons
        res_list = self.client.get(
            "/api/admin/coupons?search=ADMIN_PROMO",
            headers=self.admin_headers,
        )
        self.assertEqual(res_list.status_code, 200)
        list_data = res_list.get_json()
        self.assertGreaterEqual(list_data["total"], 1)

        # Toggle active
        res_toggle = self.client.post(
            f"/api/admin/coupons/{c_id}/toggle",
            json={"is_active": False},
            headers=self.admin_headers,
        )
        self.assertEqual(res_toggle.status_code, 200)
        self.assertFalse(res_toggle.get_json()["coupon"]["is_active"])

        # Update coupon
        res_update = self.client.put(
            f"/api/admin/coupons/{c_id}",
            json={"discount_value": 35, "description": "Updated promo 35%"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.get_json()["coupon"]["discount_value"], 35)

        # Get stats
        res_stats = self.client.get(
            f"/api/admin/coupons/{c_id}/stats",
            headers=self.admin_headers,
        )
        self.assertEqual(res_stats.status_code, 200)
        stats = res_stats.get_json()["stats"]
        self.assertIn("total_discount_vnd", stats)
        self.assertIn("total_revenue_vnd", stats)

    def test_admin_coupon_strict_integers_clearable_limits_and_exhausted_filter(self):
        bad_float = self.client.post(
            "/api/admin/coupons",
            json={
                "code": "FLOAT_NOT_ALLOWED",
                "name": "Float must fail",
                "discount_type": "percent",
                "discount_value": 10.5,
            },
            headers=self.admin_headers,
        )
        self.assertEqual(bad_float.status_code, 400)

        created = self.client.post(
            "/api/admin/coupons",
            json={
                "code": "CLEARABLE_LIMITS",
                "name": "Clearable limits",
                "discount_type": "percent",
                "discount_value": 10,
                "max_discount_vnd": 10000,
                "min_order_vnd": 1000,
                "usage_limit_total": 1,
                "usage_limit_per_user": 1,
            },
            headers=self.admin_headers,
        )
        self.assertEqual(created.status_code, 201)
        coupon_id = created.get_json()["coupon"]["id"]
        cleared = self.client.put(
            f"/api/admin/coupons/{coupon_id}",
            json={
                "max_discount_vnd": None,
                "usage_limit_total": None,
                "usage_limit_per_user": None,
            },
            headers=self.admin_headers,
        )
        self.assertEqual(cleared.status_code, 200)
        cleared_coupon = cleared.get_json()["coupon"]
        self.assertIsNone(cleared_coupon["max_discount_vnd"])
        self.assertIsNone(cleared_coupon["usage_limit_total"])
        self.assertIsNone(cleared_coupon["usage_limit_per_user"])

        exhausted_coupon = db.create_coupon(
            code="EXHAUSTED_FILTER_ONLY",
            name="Exhausted filter",
            discount_type="fixed_vnd",
            discount_value=5000,
            usage_limit_total=1,
            usage_limit_per_user=1,
        )
        reserved = self.client.post(
            "/api/payments/plan",
            json={
                "plan_id": self.plan_30k,
                "platform": "ios",
                "username": "filter_user",
                "coupon_code": exhausted_coupon["code"],
            },
            headers=self.headers_user1,
        )
        self.assertEqual(reserved.status_code, 200)
        filtered = self.client.get(
            "/api/admin/coupons?status=exhausted&search=EXHAUSTED_FILTER_ONLY",
            headers=self.admin_headers,
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual([item["code"] for item in filtered.get_json()["items"]], ["EXHAUSTED_FILTER_ONLY"])

    # ==================== 9. DB Migration Idempotency ====================
    def test_db_migration_idempotency(self):
        try:
            db.init()
            db.init()
            db.init()
        except Exception as e:
            self.fail(f"db.init() failed during idempotent re-initialization: {e}")


if __name__ == "__main__":
    unittest.main()
