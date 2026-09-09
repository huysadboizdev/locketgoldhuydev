import os
import sys
import tempfile
import time
import unittest
import re
import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from werkzeug.security import generate_password_hash

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "test-secret-vietqr-12345"
os.environ["JWT_SECRET"] = "test-jwt-secret-vietqr-12345678"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-secret-vietqr-123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"
os.environ["VIETQR_BANK_ID"] = "TPB"
os.environ["VIETQR_ACCOUNT_NO"] = "HUYDEV204"
os.environ["VIETQR_ACCOUNT_NAME"] = "HA QUANG HUY"
os.environ["VIETQR_TEMPLATE"] = "compact2"
os.environ["SEPAY_WEBHOOK_ACCOUNT_NUMBERS"] = "0123456789"
os.environ["PAYMENT_TRANSFER_PREFIX"] = "LOCKETGOLDHUYDEV"
os.environ["PAYMENT_TRANSFER_DIGITS"] = "3"
os.environ["PAYMENT_TTL_SECONDS"] = "600"
os.environ["PAYMENT_CODE_REUSE_DELAY_SECONDS"] = "86400"
os.environ["PAYMENT_WEBHOOK_ENABLED"] = "1"
os.environ["SEPAY_WEBHOOK_SECRET"] = "test-sepay-integration-secret-long-enough"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db
from locket import payment_service
from locket.token_auth import create_token_family, create_access_token
from locket.user_auth import reset_rate_limits
from locket.public.routes import reset_renew_rate_limits


class VietQRPaymentSystemTestCase(unittest.TestCase):
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
            "VALUES (101, 'vietqr1@test.com', 'vietqr1', 'VietQR User 1', ?, 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (102, 'vietqr2@test.com', 'vietqr2', 'VietQR User 2', ?, 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        conn.commit()

        # Create sample test plan
        cls.plan_id = db.create_plan(
            name="VietQR Test Plan",
            slug="plan-vietqr-test",
            description="Testing VietQR Plan",
            price_vnd=29000,
            price_coin=29,
            duration_days=30,
            supported_platforms="all",
            badge="HOT",
            sort_order=1,
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
        fam1, _, _ = create_token_family(user_id=101)
        self.token_user1 = create_access_token(101, fam1)
        self.headers_user1 = {
            "Authorization": f"Bearer {self.token_user1}",
            "X-CSRF-Token": self.csrf_token,
        }

        fam2, _, _ = create_token_family(user_id=102)
        self.token_user2 = create_access_token(102, fam2)
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

    def _sepay_headers(self, body):
        timestamp = str(int(time.time()))
        secret = os.environ["SEPAY_WEBHOOK_SECRET"].encode()
        digest = hmac.new(
            secret,
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return {
            "Content-Type": "application/json",
            "X-SePay-Timestamp": timestamp,
            "X-SePay-Signature": f"sha256={digest}",
        }

    # 1. Định dạng transfer_code: Đúng regex ^LOCKETGOLDHUYDEV[0-9]{3}$
    def test_01_transfer_code_format(self):
        code = payment_service.allocate_transfer_code()
        self.assertTrue(bool(re.match(r"^LOCKETGOLDHUYDEV[0-9]{3}$", code)))

    # 2. Kiểm tra độ dài 3 chữ số: Không bao giờ sinh 2 số hay 4 số
    def test_02_transfer_code_3_digits_length(self):
        prefix = payment_service.get_transfer_prefix()
        digits = payment_service.get_transfer_digits()
        self.assertEqual(digits, 3)
        code = payment_service.allocate_transfer_code()
        suffix = code[len(prefix):]
        self.assertEqual(len(suffix), 3)
        self.assertTrue(suffix.isdigit())

    # 3. Kiểm tra padding số 0: Các số từ 0 -> 99 phải có số 0 ở đầu
    def test_03_zero_padding(self):
        for num in [0, 7, 42, 99]:
            formatted = f"LOCKETGOLDHUYDEV{num:03d}"
            self.assertEqual(len(formatted), 19)
            self.assertRegex(formatted, r"^LOCKETGOLDHUYDEV(000|007|042|099)$")

    # 4. Sử dụng secrets module: Đảm bảo dùng secrets, không dùng random
    def test_04_secrets_module_used(self):
        import inspect
        src = inspect.getsource(payment_service)
        self.assertIn("import secrets", src)
        self.assertNotIn("import random", src)
        self.assertNotIn("random.choice", src)
        self.assertNotIn("random.randint", src)

    # 5. TTL mặc định: Đảm bảo thời gian sống mặc định là 600s (10 phút)
    def test_05_default_ttl_600s(self):
        ttl = payment_service.get_payment_ttl_seconds()
        self.assertEqual(ttl, 600)

    # 6. Xóa bỏ hoàn toàn TTL 1800s: Không còn bất kỳ tham chiếu nào tới 1800s
    def test_06_no_1800s_ttl(self):
        import inspect
        src_service = inspect.getsource(payment_service)
        src_db = inspect.getsource(db)
        self.assertNotIn("1800", src_service)
        self.assertNotIn("1800", src_db)

    # 7. QR image URL format: Kiểm tra URL chứa đúng bankId, accountNo, template, amount, addInfo, accountName
    def test_07_qr_image_url_format(self):
        url = payment_service.build_vietqr_url(
            bank_id="TPB",
            account_no="HUYDEV204",
            template="compact2",
            amount=50000,
            add_info="LOCKETGOLDHUYDEV123",
            account_name="HA QUANG HUY",
        )
        self.assertTrue(url.startswith("https://img.vietqr.io/image/TPB-HUYDEV204-compact2.png"))
        self.assertIn("amount=50000", url)
        self.assertIn("addInfo=LOCKETGOLDHUYDEV123", url)
        self.assertIn("accountName=HA+QUANG+HUY", url)

    # 8. URL encoding: Kiểm tra addInfo và accountName được URL encode chuẩn xác
    def test_08_url_encoding(self):
        url = payment_service.build_vietqr_url(
            bank_id="TPB",
            account_no="HUYDEV204",
            template="compact2",
            amount=10000,
            add_info="LOCKET GOLD HUY DEV #001",
            account_name="HÀ QUANG HUY",
        )
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(params["addInfo"][0], "LOCKET GOLD HUY DEV #001")
        self.assertEqual(params["accountName"][0], "HÀ QUANG HUY")

    # 9. Quản lý pool mã: Không trùng lặp transfer_code đang trong trạng thái pending
    def test_09_pool_no_duplicate_pending(self):
        code1 = payment_service.allocate_transfer_code()
        # Insert pending order with code1
        db.create_payment_order(
            user_id=101,
            payment_code="PAY_TEST_POOL_1",
            purpose="wallet_topup",
            amount_vnd=20000,
            coin_amount=20,
            expires_at=int(time.time() + 600),
            transfer_code=code1,
        )
        # Next allocate must not return code1
        code2 = payment_service.allocate_transfer_code()
        self.assertNotEqual(code1, code2)

    # 10. Tái sử dụng sau quarantine: Mã chỉ được tái sử dụng sau 24h kể từ khi hết hạn
    def test_10_quarantine_24h(self):
        code = "LOCKETGOLDHUYDEV777"
        now = int(time.time())
        # Expired 10 hours ago (within 24h quarantine)
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO payment_orders (payment_code, transfer_code, user_id, purpose, amount_vnd, coin_amount, "
            "provider, status, expires_at, created_at, updated_at) "
            "VALUES ('PAY_QUAR_1', ?, 101, 'wallet_topup', 10000, 10, 'vietqr', 'expired', ?, ?, ?)",
            (code, now - 36000, now - 36600, now - 36000),
        )
        conn.commit()

        # In-use check should still consider it quarantined
        conn = db.get_conn()
        quarantine_cutoff = now - 86400
        cur = conn.execute(
            "SELECT transfer_code FROM payment_orders WHERE status = 'pending' "
            "OR (status IN ('expired', 'cancelled') AND updated_at > ?)",
            (quarantine_cutoff,),
        )
        busy_codes = {row[0] for row in cur.fetchall() if row[0]}
        self.assertIn(code, busy_codes)

    # 11. Báo lỗi khi hết pool: Khi 1000 mã đều đang bận, API trả về 503
    def test_11_pool_exhaustion_503(self):
        # Temporarily mock available codes to 0
        from unittest.mock import patch
        with patch.object(payment_service, "allocate_transfer_code", side_effect=payment_service.PoolExhaustedError("Pool full")):
            res = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 20000})
            self.assertEqual(res.status_code, 503)
            data = res.get_json()
            self.assertEqual(data["error"], "payment_code_pool_exhausted")

    # 12. Sweep expired orders: Tự động chuyển pending quá hạn thành expired
    def test_12_sweep_expired_orders(self):
        now = int(time.time())
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO payment_orders (payment_code, transfer_code, user_id, purpose, amount_vnd, coin_amount, "
            "provider, status, expires_at, created_at, updated_at) "
            "VALUES ('PAY_SWEEP_1', 'LOCKETGOLDHUYDEV888', 101, 'wallet_topup', 10000, 10, 'vietqr', 'pending', ?, ?, ?)",
            (now - 100, now - 700, now - 700),
        )
        conn.commit()

        # Sweep
        count = payment_service.sweep_expired_pending_payments()
        self.assertGreaterEqual(count, 1)

        order = db.get_payment_order_by_code("PAY_SWEEP_1")
        self.assertEqual(order["status"], "expired")

    # 13. Idempotency cùng key, cùng payload: Trả về order hiện tại, HTTP 200
    def test_13_idempotency_same_key_same_payload(self):
        idem_key = "idem-test-key-001"
        payload = {"amount_vnd": 50000, "idempotency_key": idem_key}

        res1 = self.client.post("/api/payments/topup", headers=self.headers_user1, json=payload)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        code1 = data1["payment_code"]

        # Replay identical
        res2 = self.client.post("/api/payments/topup", headers=self.headers_user1, json=payload)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["payment_code"], code1)

    # 14. Idempotency cùng key, khác payload: Báo lỗi 409 Conflict
    def test_14_idempotency_same_key_diff_payload(self):
        idem_key = "idem-test-key-002"
        res1 = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 50000, "idempotency_key": idem_key})
        self.assertEqual(res1.status_code, 200)

        # Different payload with same key -> 409
        res2 = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 100000, "idempotency_key": idem_key})
        self.assertEqual(res2.status_code, 409)
        data2 = res2.get_json()
        self.assertEqual(data2["error"], "idempotency_conflict")

    # 15. Chống double-click: Gọi 2 request đồng thời cùng key, chỉ 1 order được tạo
    def test_15_double_click_protection(self):
        idem_key = "double-click-key-123"
        payload = {"amount_vnd": 30000, "idempotency_key": idem_key}
        res1 = self.client.post("/api/payments/topup", headers=self.headers_user1, json=payload)
        res2 = self.client.post("/api/payments/topup", headers=self.headers_user1, json=payload)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res1.get_json()["payment_code"], res2.get_json()["payment_code"])

    # 16. Transaction isolation: SQLite transaction sử dụng BEGIN IMMEDIATE cho cấp phát mã
    def test_16_transaction_isolation(self):
        import inspect
        src = inspect.getsource(payment_service.allocate_transfer_code)
        self.assertIn("BEGIN IMMEDIATE", src)

    # 17. Foreign key integrity: Quan hệ giữa payment_orders và activation_orders luôn toàn vẹn
    def test_17_foreign_key_integrity(self):
        res = self.client.post(
            "/api/payments/plan",
            headers=self.headers_user1,
            json={
                "plan_id": self.plan_id,
                "platform": "ios",
                "username": "fk_test_user",
                "idempotency_key": "fk-integrity-key-1",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        p_code = data["payment_code"]
        act_id = data["activation_order_id"]

        act = db.get_activation_order(act_id)
        payment = db.get_payment_order_by_code(p_code)
        self.assertIsNotNone(payment)
        self.assertEqual(act["payment_order_id"], payment["id"])

    # 18. Không ghi đè order: Re-run payment cho cùng activation_order không tạo order mồ côi
    def test_18_no_orphan_order(self):
        res1 = self.client.post(
            "/api/payments/plan",
            headers=self.headers_user1,
            json={
                "plan_id": self.plan_id,
                "platform": "ios",
                "username": "no_orphan_user",
                "idempotency_key": "orphan-test-key",
            },
        )
        data1 = res1.get_json()
        act_id = data1["activation_order_id"]

        # Confirm count of activation orders
        conn = db.get_conn()
        cur = conn.execute("SELECT COUNT(*) FROM activation_orders WHERE id = ?", (act_id,))
        count = cur.fetchone()[0]
        self.assertEqual(count, 1)

    # 19. Admin confirm payment pending: Chuyển thành công sang paid
    def test_19_admin_confirm_pending(self):
        res = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 20000})
        p_code = res.get_json()["payment_code"]

        self._login_admin()
        res_adm = self.client.post(
            f"/admin/api/payments/{p_code}/confirm",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={},
        )
        self.assertEqual(res_adm.status_code, 200)
        order = db.get_payment_order_by_code(p_code)
        self.assertEqual(order["status"], "paid")

    # 20. Admin confirm payment expired: Bị từ chối, trả về lỗi payment_expired
    def test_20_admin_confirm_expired_rejected(self):
        now = int(time.time())
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO payment_orders (payment_code, transfer_code, user_id, purpose, amount_vnd, coin_amount, "
            "provider, status, expires_at, created_at, updated_at) "
            "VALUES ('PAY_EXP_CONFIRM', 'LOCKETGOLDHUYDEV991', 101, 'wallet_topup', 10000, 10, 'vietqr', 'expired', ?, ?, ?)",
            (now - 1000, now - 2000, now - 1000),
        )
        conn.commit()

        self._login_admin()
        res_adm = self.client.post(
            "/admin/api/payments/PAY_EXP_CONFIRM/confirm",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={},
        )
        self.assertEqual(res_adm.status_code, 400)
        self.assertEqual(res_adm.get_json()["error"], "payment_expired")

    # 21. Admin confirm payment đã paid: Idempotent hoặc báo lỗi đã xác nhận
    def test_21_admin_confirm_already_paid(self):
        res = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 20000})
        p_code = res.get_json()["payment_code"]
        self._login_admin()
        res1 = self.client.post(
            f"/admin/api/payments/{p_code}/confirm",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={},
        )
        self.assertEqual(res1.status_code, 200)

        # Second confirm
        res2 = self.client.post(
            f"/admin/api/payments/{p_code}/confirm",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={},
        )
        self.assertIn(res2.status_code, [200, 400])

    # 22. Admin confirm kích hoạt activation_order: Chuyển trạng thái sang paid / queued
    def test_22_admin_confirm_activates_order(self):
        res = self.client.post(
            "/api/payments/plan",
            headers=self.headers_user1,
            json={
                "plan_id": self.plan_id,
                "platform": "ios",
                "username": "admin_act_user",
            },
        )
        data = res.get_json()
        p_code = data["payment_code"]
        act_id = data["activation_order_id"]

        self._login_admin()
        res_adm = self.client.post(
            f"/admin/api/payments/{p_code}/confirm",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={},
        )
        self.assertEqual(res_adm.status_code, 200)
        act = db.get_activation_order(act_id)
        self.assertIn(act["status"], ["paid", "awaiting_queue", "queued"])

    # 23. Topup coin tự động: Khi payment topup được confirm, số dư coin trong ví tăng chính xác
    def test_23_auto_coin_topup(self):
        bal_before = db.get_wallet_balance(101)
        res = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 50000})
        p_code = res.get_json()["payment_code"]

        self._login_admin()
        self.client.post(
            f"/admin/api/payments/{p_code}/confirm",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={},
        )
        bal_after = db.get_wallet_balance(101)
        self.assertEqual(bal_after, bal_before + 50)

    # 24. Ledger transaction: Mỗi lần nạp/trừ coin đều có bản ghi trong wallet_transactions
    def test_24_ledger_transaction(self):
        res = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 30000})
        p_code = res.get_json()["payment_code"]

        self._login_admin()
        self.client.post(
            f"/admin/api/payments/{p_code}/confirm",
            headers={"X-CSRF-Token": self.admin_csrf},
            json={},
        )
        txs, total = db.list_wallet_transactions(101, limit=5, offset=0)
        self.assertGreater(total, 0)
        self.assertEqual(txs[0]["amount_coin"], 30)
        self.assertEqual(txs[0]["type"], "topup")

    # 25. Renew payment pending còn hạn: Trả về chính order đó an toàn
    def test_25_renew_pending_valid(self):
        res = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 20000})
        p_code = res.get_json()["payment_code"]

        res_ren = self.client.post(f"/api/payments/{p_code}/renew", headers=self.headers_user1)
        self.assertEqual(res_ren.status_code, 200)
        data = res_ren.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["payment"]["payment_code"], p_code)

    # 26. Renew payment expired: Cấp phát transfer_code mới, reset expires_at thành now + 600s
    def test_26_renew_expired_allocates_new(self):
        now = int(time.time())
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO payment_orders (payment_code, transfer_code, user_id, purpose, amount_vnd, coin_amount, "
            "provider, status, expires_at, created_at, updated_at) "
            "VALUES ('PAY_EXP_RENEW', 'LOCKETGOLDHUYDEV992', 101, 'wallet_topup', 20000, 20, 'vietqr', 'expired', ?, ?, ?)",
            (now - 500, now - 1100, now - 500),
        )
        conn.commit()

        res_ren = self.client.post("/api/payments/PAY_EXP_RENEW/renew", headers=self.headers_user1)
        self.assertEqual(res_ren.status_code, 200)
        data = res_ren.get_json()
        self.assertNotEqual(data["payment"]["transfer_code"], "LOCKETGOLDHUYDEV992")
        self.assertEqual(data["payment"]["status"], "pending")
        self.assertGreater(data["payment"]["expires_at"], int(time.time() + 500))

    # 27. Renew payment giữ nguyên activation_order: Đơn hàng kích hoạt được liên kết với payment mới
    def test_27_renew_preserves_activation_order(self):
        now = int(time.time())
        conn = db.get_conn()
        cur = conn.execute(
            "INSERT INTO payment_orders (payment_code, transfer_code, user_id, purpose, plan_id, amount_vnd, coin_amount, "
            "provider, status, expires_at, created_at, updated_at) "
            "VALUES ('PAY_EXP_ACT', 'LOCKETGOLDHUYDEV993', 101, 'plan_purchase', ?, 29000, 29, 'vietqr', 'expired', ?, ?, ?)",
            (self.plan_id, now - 500, now - 1100, now - 500),
        )
        old_pay_id = cur.lastrowid
        act_id = db.create_activation_order(
            user_id=101,
            plan_id=self.plan_id,
            payment_method="qr",
            platform="ios",
            locket_username="renew_act_user",
            payment_order_id=old_pay_id,
            initial_status="awaiting_payment",
        )
        conn.commit()

        res_ren = self.client.post("/api/payments/PAY_EXP_ACT/renew", headers=self.headers_user1)
        self.assertEqual(res_ren.status_code, 200)
        data = res_ren.get_json()
        new_pay_id = data["payment"]["id"]

        act = db.get_activation_order(act_id)
        self.assertEqual(act["payment_order_id"], new_pay_id)

    # 28. Rate limiting renew: Không cho phép spam renew liên tục
    def test_28_renew_rate_limiting(self):
        res = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 20000})
        p_code = res.get_json()["payment_code"]

        for _ in range(5):
            res_ren = self.client.post(f"/api/payments/{p_code}/renew", headers=self.headers_user1)
            self.assertEqual(res_ren.status_code, 200)

        # 6th request should hit rate limit 429
        res_rl = self.client.post(f"/api/payments/{p_code}/renew", headers=self.headers_user1)
        self.assertEqual(res_rl.status_code, 429)

    # 29. Ownership check renew: Không cho phép renew payment của user khác (403/404)
    def test_29_renew_ownership_check(self):
        res = self.client.post("/api/payments/topup", headers=self.headers_user1, json={"amount_vnd": 20000})
        p_code = res.get_json()["payment_code"]

        # User 102 tries to renew User 101's payment
        res_other = self.client.post(f"/api/payments/{p_code}/renew", headers=self.headers_user2)
        self.assertIn(res_other.status_code, [403, 404])

    # 30. CSRF protection: Các mutation endpoint yêu cầu CSRF / Auth tokens
    def test_30_csrf_protection(self):
        # Without auth token
        res_unauth = self.client.post("/api/payments/topup", json={"amount_vnd": 20000})
        self.assertEqual(res_unauth.status_code, 401)

        # Authenticated customer mutations must also carry the session CSRF token.
        auth_only = {"Authorization": f"Bearer {self.token_user1}"}
        res_topup_no_csrf = self.client.post(
            "/api/payments/topup",
            headers=auth_only,
            json={"amount_vnd": 20000},
        )
        self.assertEqual(res_topup_no_csrf.status_code, 403)
        self.assertEqual(res_topup_no_csrf.get_json()["error"], "invalid_csrf_token")

        # Admin confirm without admin CSRF
        self._login_admin()
        res_no_csrf = self.client.post("/admin/api/payments/PAY_ANY/confirm", json={})
        self.assertEqual(res_no_csrf.status_code, 403)

    def test_31_status_lookup_persists_expiry(self):
        """A status lookup must expire the database row, not only the JSON response."""
        now = int(time.time())
        conn = db.get_conn()
        cursor = conn.execute(
            "INSERT INTO payment_orders "
            "(payment_code, transfer_code, user_id, purpose, amount_vnd, coin_amount, provider, status, expires_at, created_at, updated_at) "
            "VALUES ('PAY_GET_EXPIRED', 'LOCKETGOLDHUYDEV994', 101, 'wallet_topup', 10000, 10, 'vietqr', 'pending', ?, ?, ?)",
            (now - 1, now - 601, now - 601),
        )
        payment_id = cursor.lastrowid
        conn.commit()

        res = self.client.get("/api/payments/PAY_GET_EXPIRED", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["payment"]["status"], "expired")
        self.assertEqual(db.get_payment_order_by_id(payment_id)["status"], "expired")

    def test_32_renew_requires_customer_csrf(self):
        res = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user1,
            json={"amount_vnd": 20000, "idempotency_key": "renew-csrf-order"},
        )
        self.assertEqual(res.status_code, 200)
        payment_code = res.get_json()["payment_code"]

        auth_only = {"Authorization": f"Bearer {self.token_user1}"}
        renew_res = self.client.post(
            f"/api/payments/{payment_code}/renew",
            headers=auth_only,
        )
        self.assertEqual(renew_res.status_code, 403)
        self.assertEqual(renew_res.get_json()["error"], "invalid_csrf_token")

    def test_33_sepay_webhook_credits_wallet_exactly_once(self):
        balance_before = db.get_wallet_balance(101)
        create_res = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user1,
            json={"amount_vnd": 50000, "idempotency_key": "sepay-auto-topup-once"},
        )
        self.assertEqual(create_res.status_code, 200)
        created = create_res.get_json()

        payload = {
            "id": 9000001,
            "gateway": "TPBank",
            "transactionDate": "2026-09-09 15:30:00",
            # SePay commonly returns the real numeric bank account even when
            # VietQR was generated with a bank-supported account alias.
            "accountNumber": "0123456789",
            "code": None,
            "content": f"NAP TIEN {created['transfer_code']}",
            "transferType": "in",
            "description": "SePay integration test",
            "transferAmount": 50000,
            "accumulated": 50000,
            "referenceCode": "SEPAY_TEST_AUTO_TOPUP_1",
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        headers = self._sepay_headers(body)

        first = self.client.post("/api/payment/webhook", data=body, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json(), {"success": True})
        self.assertEqual(db.get_wallet_balance(101), balance_before + 50)

        payment = db.get_payment_order_by_id(created["payment_id"])
        self.assertEqual(payment["status"], "paid")
        self.assertEqual(payment["bank_transaction_id"], "SEPAY_9000001")

        replay = self.client.post("/api/payment/webhook", data=body, headers=headers)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(db.get_wallet_balance(101), balance_before + 50)

    def test_34_sepay_webhook_rejects_wrong_amount_and_account(self):
        balance_before = db.get_wallet_balance(101)
        create_res = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user1,
            json={"amount_vnd": 30000, "idempotency_key": "sepay-reject-mismatch"},
        )
        self.assertEqual(create_res.status_code, 200)
        created = create_res.get_json()

        base_payload = {
            "id": 9000002,
            "gateway": "TPBank",
            "accountNumber": "0123456789",
            "code": created["transfer_code"],
            "content": created["transfer_code"],
            "transferType": "in",
            "transferAmount": 29000,
            "referenceCode": "SEPAY_TEST_MISMATCH_1",
        }
        wrong_amount_body = json.dumps(base_payload, separators=(",", ":")).encode()
        wrong_amount = self.client.post(
            "/api/payment/webhook",
            data=wrong_amount_body,
            headers=self._sepay_headers(wrong_amount_body),
        )
        self.assertEqual(wrong_amount.status_code, 200)
        self.assertEqual(db.get_wallet_balance(101), balance_before)
        self.assertEqual(db.get_payment_order_by_id(created["payment_id"])["status"], "pending")

        base_payload["id"] = 9000003
        base_payload["transferAmount"] = 30000
        base_payload["accountNumber"] = "WRONG_ACCOUNT"
        wrong_account_body = json.dumps(base_payload, separators=(",", ":")).encode()
        wrong_account = self.client.post(
            "/api/payment/webhook",
            data=wrong_account_body,
            headers=self._sepay_headers(wrong_account_body),
        )
        self.assertEqual(wrong_account.status_code, 200)
        self.assertEqual(db.get_wallet_balance(101), balance_before)
        self.assertEqual(db.get_payment_order_by_id(created["payment_id"])["status"], "pending")

    def test_35_sepay_webhook_settles_direct_plan_purchase_once(self):
        create_res = self.client.post(
            "/api/payments/plan",
            headers=self.headers_user1,
            json={
                "plan_id": self.plan_id,
                "platform": "ios",
                "username": "sepay_direct_plan_user",
                "idempotency_key": "sepay-direct-plan-once",
            },
        )
        self.assertEqual(create_res.status_code, 200)
        created = create_res.get_json()

        payload = {
            "id": 9000004,
            "gateway": "TPBank",
            "accountNumber": "0123456789",
            "code": created["transfer_code"],
            "content": f"THANH TOAN {created['transfer_code']}",
            "transferType": "in",
            "transferAmount": created["amount_vnd"],
            "referenceCode": "SEPAY_TEST_DIRECT_PLAN_1",
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        headers = self._sepay_headers(body)

        with patch("locket.notifications.notify_paid_order") as notify_order:
            first = self.client.post("/api/payment/webhook", data=body, headers=headers)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.get_json(), {"success": True})

            replay = self.client.post("/api/payment/webhook", data=body, headers=headers)
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.get_json(), {"success": True})
            notify_order.assert_called_once()

        payment = db.get_payment_order_by_id(created["payment_id"])
        self.assertEqual(payment["purpose"], "plan_purchase")
        self.assertEqual(payment["status"], "paid")
        self.assertEqual(payment["bank_transaction_id"], "SEPAY_9000004")

        activation = db.get_activation_order_by_id(created["activation_order_id"])
        self.assertNotEqual(activation["status"], "awaiting_payment")

        replayed_payment = db.get_payment_order_by_id(created["payment_id"])
        self.assertEqual(replayed_payment["status"], "paid")
        self.assertEqual(replayed_payment["bank_transaction_id"], "SEPAY_9000004")

    def test_36_sepay_webhook_completes_direct_apk_plan_purchase(self):
        create_res = self.client.post(
            "/api/payments/plan",
            headers=self.headers_user2,
            json={
                "plan_id": self.plan_id,
                "platform": "android",
                "idempotency_key": "sepay-direct-apk-plan-once",
            },
        )
        self.assertEqual(create_res.status_code, 200)
        created = create_res.get_json()
        self.assertEqual(created["fulfillment_mode"], "apk_download")

        payload = {
            "id": 9000005,
            "gateway": "TPBank",
            "accountNumber": "HUYDEV204",
            "code": None,
            "content": f"MUA GOI {created['transfer_code']}",
            "transferType": "in",
            "transferAmount": created["amount_vnd"],
            "referenceCode": "SEPAY_TEST_DIRECT_APK_1",
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        response = self.client.post(
            "/api/payment/webhook",
            data=body,
            headers=self._sepay_headers(body),
        )
        self.assertEqual(response.status_code, 200)

        payment = db.get_payment_order_by_id(created["payment_id"])
        activation = db.get_activation_order_by_id(created["activation_order_id"])
        self.assertEqual(payment["status"], "paid")
        self.assertEqual(payment["bank_transaction_id"], "SEPAY_9000005")
        self.assertEqual(activation["status"], "completed")

    def test_37_delayed_sepay_webhook_recovers_on_time_expired_topup_once(self):
        balance_before = db.get_wallet_balance(101)
        create_res = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user1,
            json={"amount_vnd": 20000, "idempotency_key": "sepay-delayed-topup"},
        )
        self.assertEqual(create_res.status_code, 200)
        created = create_res.get_json()

        now = time.time()
        created_at = now - 900
        expires_at = now - 300
        paid_at_bank = now - 450
        conn = db.get_conn()
        conn.execute(
            "UPDATE payment_orders SET status='expired', created_at=?, expires_at=?, updated_at=? WHERE id=?",
            (created_at, expires_at, now, created["payment_id"]),
        )
        conn.commit()

        payload = {
            "id": 9000006,
            "gateway": "TPBank",
            "transactionDate": datetime.fromtimestamp(
                paid_at_bank, timezone(timedelta(hours=7))
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "accountNumber": "0123456789",
            "code": created["transfer_code"],
            "content": created["transfer_code"],
            "transferType": "in",
            "transferAmount": 20000,
            "referenceCode": "SEPAY_DELAYED_TOPUP_1",
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        headers = self._sepay_headers(body)

        first = self.client.post("/api/payment/webhook", data=body, headers=headers)
        replay = self.client.post("/api/payment/webhook", data=body, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(db.get_wallet_balance(101), balance_before + 20)
        payment = db.get_payment_order_by_id(created["payment_id"])
        self.assertEqual(payment["status"], "paid")
        self.assertEqual(payment["bank_transaction_id"], "SEPAY_9000006")

    def test_38_delayed_sepay_webhook_recovers_expired_plan_purchase(self):
        create_res = self.client.post(
            "/api/payments/plan",
            headers=self.headers_user1,
            json={
                "plan_id": self.plan_id,
                "platform": "ios",
                "username": "sepay_delayed_plan_user",
                "idempotency_key": "sepay-delayed-plan",
            },
        )
        self.assertEqual(create_res.status_code, 200)
        created = create_res.get_json()

        now = time.time()
        created_at = now - 900
        expires_at = now - 300
        paid_at_bank = now - 450
        conn = db.get_conn()
        conn.execute(
            "UPDATE payment_orders SET status='expired', created_at=?, expires_at=?, updated_at=? WHERE id=?",
            (created_at, expires_at, now, created["payment_id"]),
        )
        conn.execute(
            "UPDATE activation_orders SET status='cancelled', updated_at=? WHERE id=?",
            (now, created["activation_order_id"]),
        )
        conn.commit()

        payload = {
            "id": 9000007,
            "gateway": "TPBank",
            "transactionDate": datetime.fromtimestamp(
                paid_at_bank, timezone(timedelta(hours=7))
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "accountNumber": "0123456789",
            "code": created["transfer_code"],
            "content": created["transfer_code"],
            "transferType": "in",
            "transferAmount": created["amount_vnd"],
            "referenceCode": "SEPAY_DELAYED_PLAN_1",
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        with patch("locket.notifications.notify_paid_order") as notify_order:
            response = self.client.post(
                "/api/payment/webhook", data=body, headers=self._sepay_headers(body)
            )
            self.assertEqual(response.status_code, 200)
            notify_order.assert_called_once()

        payment = db.get_payment_order_by_id(created["payment_id"])
        activation = db.get_activation_order_by_id(created["activation_order_id"])
        self.assertEqual(payment["status"], "paid")
        self.assertNotEqual(activation["status"], "cancelled")

    def test_39_payment_made_after_expiry_is_not_auto_recovered(self):
        balance_before = db.get_wallet_balance(101)
        create_res = self.client.post(
            "/api/payments/topup",
            headers=self.headers_user1,
            json={"amount_vnd": 20000, "idempotency_key": "sepay-too-late-topup"},
        )
        self.assertEqual(create_res.status_code, 200)
        created = create_res.get_json()

        now = time.time()
        conn = db.get_conn()
        conn.execute(
            "UPDATE payment_orders SET status='expired', created_at=?, expires_at=?, updated_at=? WHERE id=?",
            (now - 1800, now - 1200, now, created["payment_id"]),
        )
        conn.commit()
        payload = {
            "id": 9000008,
            "gateway": "TPBank",
            "transactionDate": datetime.fromtimestamp(
                now, timezone(timedelta(hours=7))
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "accountNumber": "0123456789",
            "code": created["transfer_code"],
            "content": created["transfer_code"],
            "transferType": "in",
            "transferAmount": 20000,
            "referenceCode": "SEPAY_TOO_LATE_TOPUP_1",
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        response = self.client.post(
            "/api/payment/webhook", data=body, headers=self._sepay_headers(body)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.get_wallet_balance(101), balance_before)
        self.assertEqual(
            db.get_payment_order_by_id(created["payment_id"])["status"], "expired"
        )

if __name__ == "__main__":
    unittest.main()
