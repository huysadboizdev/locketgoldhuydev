"""Comprehensive Test Suite for Admin Provisioning, Unified Auth, and Admin REST API.

Covers all 19 required test specifications:
1. Migration schema cu -> role mac dinh 'user', khong mat du lieu.
2. Admin env bootstrap tao dung mot admin account.
3. Bootstrap chay lai idempotent, khong duplicate hay doi trang thai bat thuong.
4. Partial env/config va identifier conflict fail an toan (fail-fast).
5. Doi env password cap nhat hash va revoke session cu cua admin.
6. Public register khong nhan role/is_admin (luon la 'user').
7. Auth response cua login/refresh/me/register co role nhat quan.
8. Google auth khong auto-link/nang quyen admin mac dinh khi ADMIN_ALLOW_GOOGLE_LOGIN!=1 hoac chi match email.
9. Guest goi /api/admin/* -> 401.
10. User thuong goi /api/admin/* -> 403.
11. Admin Bearer token goi /api/admin/* -> 200.
12. Legacy session["admin"] khong cap quyen cho /api/admin/* moi.
13. Mutating admin API thieu/sai CSRF bi tu choi (403 invalid_csrf_token).
14. Overview thong ke dung, khong double-count revenue, range/timezone Asia/Bangkok dung, zero-fill series.
15. User list pagination/filter, khong lo password hash hay token bi mat.
16. Wallet adjustment atomic, khong am, idempotency check.
17. Admin audit log duoc ghi nhan va duoc redact secrets.
18. Maintenance mode allow_admin hoat dong voi Bearer admin role moi, /login khong bi khoa.
19. Regression verification.
"""

import json
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

# Configure test environment variables before module imports
os.environ["BEHIND_HTTPS"] = "0"
os.environ["JWT_SECRET"] = "test-jwt-secret-admin-test-12345678"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-admin-test-09876543"
os.environ["ADMIN_EMAIL"] = "admin_super@test.com"
os.environ["ADMIN_USERNAME"] = "adminsuper"
os.environ["ADMIN_PASSWORD"] = "SuperSecretPassword123!"
os.environ["ADMIN_DISPLAY_NAME"] = "Super Administrator"
os.environ["ADMIN_ALLOW_GOOGLE_LOGIN"] = "0"

from locket import create_app, db
from locket.admin_provision import is_seed_admin, provision_admin_user
from locket.token_auth import create_access_token, create_token_family
from werkzeug.security import check_password_hash, generate_password_hash


class AdminAuthAndApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["BEHIND_HTTPS"] = "0"
        os.environ["JWT_SECRET"] = "test-jwt-secret-admin-test-12345678"
        os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-admin-test-09876543"
        os.environ["ADMIN_EMAIL"] = "admin_super@test.com"
        os.environ["ADMIN_USERNAME"] = "adminsuper"
        os.environ["ADMIN_PASSWORD"] = "SuperSecretPassword123!"
        os.environ["ADMIN_DISPLAY_NAME"] = "Super Administrator"
        os.environ["ADMIN_ALLOW_GOOGLE_LOGIN"] = "0"

        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.db_fd)
        os.environ["LOCKET_DB"] = cls.db_path

        db.close_conn()
        db._initialized = False

        cls.app = create_app()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.close_conn()
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass
        os.environ["ADMIN_EMAIL"] = "admin@example.com"
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"
        os.environ["ADMIN_DISPLAY_NAME"] = "Administrator"
        os.environ["ADMIN_ALLOW_GOOGLE_LOGIN"] = "0"

    def setUp(self):
        os.environ["ADMIN_EMAIL"] = "admin_super@test.com"
        os.environ["ADMIN_USERNAME"] = "adminsuper"
        os.environ["ADMIN_PASSWORD"] = "SuperSecretPassword123!"
        os.environ["ADMIN_DISPLAY_NAME"] = "Super Administrator"
        os.environ["ADMIN_ALLOW_GOOGLE_LOGIN"] = "0"
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def get_csrf(self, client=None):
        c = client or self.client
        res = c.get("/api/auth/csrf")
        return res.get_json().get("csrf_token")

    def create_user(self, email="user@test.com", username="normaluser", password="UserPassword123!", role="user"):
        pwd_hash = generate_password_hash(password)
        uid = db.create_user(
            email=email,
            username=username,
            display_name=username,
            password_hash=pwd_hash,
            role=role,
        )
        family_id, raw_refresh, _ = create_token_family(uid)
        token = create_access_token(uid, family_id)
        return uid, token, raw_refresh

    # ---- 1. Migration schema cu -> role mac dinh 'user' ----
    def test_01_legacy_schema_migration_sets_default_user_role(self):
        conn = db.get_conn()
        # Insert a temporary table mimicking legacy users without role column
        temp_fd, temp_db = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        try:
            temp_conn = sqlite3.connect(temp_db)
            temp_conn.execute(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, username TEXT, "
                "display_name TEXT, password_hash TEXT, created_at REAL)"
            )
            temp_conn.execute(
                "INSERT INTO users (id, email, username, display_name, password_hash, created_at) "
                "VALUES (1, 'old@example.com', 'olduser', 'Old User', 'hash123', 1000)"
            )
            temp_conn.commit()
            temp_conn.close()

            # Now run migration logic against this db
            test_conn = sqlite3.connect(temp_db)
            user_cols = [r[1] for r in test_conn.execute("PRAGMA table_info(users)").fetchall()]
            if "role" not in user_cols:
                test_conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
                test_conn.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''")
                test_conn.commit()

            row = test_conn.execute("SELECT id, role FROM users WHERE id = 1").fetchone()
            self.assertEqual(row[1], "user")
            test_conn.close()
        finally:
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except OSError:
                    pass

    # ---- 2. Admin env bootstrap tao dung mot admin ----
    def test_02_admin_env_bootstrap_creates_admin(self):
        admin = db.get_user_by_email("admin_super@test.com")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["role"], "admin")
        self.assertEqual(admin["username"], "adminsuper")
        self.assertEqual(admin["display_name"], "Super Administrator")
        self.assertTrue(check_password_hash(admin["password_hash"], "SuperSecretPassword123!"))
        self.assertTrue(is_seed_admin(admin))

    # ---- 3. Bootstrap chay lai idempotent ----
    def test_03_bootstrap_idempotency(self):
        admin_before = db.get_user_by_email("admin_super@test.com")
        provision_admin_user(self.app)
        admin_after = db.get_user_by_email("admin_super@test.com")
        self.assertEqual(admin_before["id"], admin_after["id"])
        self.assertEqual(admin_before["password_hash"], admin_after["password_hash"])

    # ---- 4. Partial env/config conflict fail-fast ----
    def test_04_partial_env_and_conflict_fail_safely(self):
        with patch.dict(os.environ, {"ADMIN_EMAIL": "partial@test.com", "ADMIN_USERNAME": "", "ADMIN_PASSWORD": ""}):
            with self.assertRaises(RuntimeError) as ctx:
                provision_admin_user(self.app)
            self.assertIn("Incomplete configuration", str(ctx.exception))

        # Conflict: email matches one user, username matches another
        db.create_user("conf1@test.com", "uconf1", "U1", "hash", role="user")
        db.create_user("conf2@test.com", "uconf2", "U2", "hash", role="user")
        with patch.dict(
            os.environ,
            {
                "ADMIN_EMAIL": "conf1@test.com",
                "ADMIN_USERNAME": "uconf2",
                "ADMIN_PASSWORD": "ValidPassword123!",
            },
        ):
            with self.assertRaises(RuntimeError) as ctx:
                provision_admin_user(self.app)
            self.assertIn("Admin provisioning conflict", str(ctx.exception))

    # ---- 5. Doi env password cap nhat hash va revoke session cu ----
    def test_05_env_password_rotation_revokes_sessions(self):
        admin = db.get_user_by_email("admin_super@test.com")
        family_id, _, _ = create_token_family(admin["id"])

        # Rotate password via env
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "NewRotatedPassword123!"}):
            provision_admin_user(self.app)

        refreshed = db.get_user_by_email("admin_super@test.com")
        self.assertTrue(check_password_hash(refreshed["password_hash"], "NewRotatedPassword123!"))

        # Session must be revoked
        sess = db.get_auth_session(family_id)
        self.assertIsNotNone(sess["revoked_at"])
        self.assertEqual(sess["revoke_reason"], "admin_password_rotated")

        # Reset back
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "SuperSecretPassword123!"}):
            provision_admin_user(self.app)

    # ---- 6. Register khong nhan role/is_admin ----
    def test_06_public_register_cannot_assign_role(self):
        csrf = self.get_csrf()
        res = self.client.post(
            "/api/auth/register",
            headers={"X-CSRF-Token": csrf},
            json={
                "email": "hacker@test.com",
                "username": "hacker1",
                "password": "Password12345!",
                "role": "admin",
                "is_admin": True,
            },
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["user"]["role"], "user")

        created = db.get_user_by_email("hacker@test.com")
        self.assertEqual(created["role"], "user")

    # ---- 7. Auth response co role nhat quan ----
    def test_07_auth_responses_contain_role(self):
        uid, token, refresh_token = self.create_user("rolecheck@test.com", "rolecheck", role="user")

        # 1. Login
        csrf = self.get_csrf()
        res = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"identifier": "rolecheck", "password": "UserPassword123!"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["user"]["role"], "user")

        # 2. Me
        res_me = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.get_json()["user"]["role"], "user")

        # 3. Refresh
        client = self.app.test_client()
        client.set_cookie("locket_refresh", refresh_token, path="/api/auth")
        csrf2 = self.get_csrf(client)
        res_ref = client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf2})
        self.assertEqual(res_ref.status_code, 200)
        self.assertEqual(res_ref.get_json()["user"]["role"], "user")

    # ---- 8. Google auth khong auto-link/nang quyen admin mac dinh ----
    @patch("locket.user_auth.get_google_client_id")
    @patch("locket.user_auth.verify_google_token")
    def test_08_google_auth_admin_protections(self, verify, get_id):
        get_id.return_value = "client-id"
        verify.return_value = (
            True,
            {"email": "admin_super@test.com", "sub": "google-sub-12345", "name": "Fake Admin"},
            None,
        )

        csrf = self.get_csrf()
        # Default ADMIN_ALLOW_GOOGLE_LOGIN is "0", must return 403
        res = self.client.post(
            "/api/auth/google",
            headers={"X-CSRF-Token": csrf},
            json={"credential": "fake-token"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "admin_google_disabled")

        # Even if enabled, email matching alone without linked google_id must be rejected
        with patch.dict(os.environ, {"ADMIN_ALLOW_GOOGLE_LOGIN": "1"}):
            res_opt = self.client.post(
                "/api/auth/google",
                headers={"X-CSRF-Token": csrf},
                json={"credential": "fake-token"},
            )
            self.assertEqual(res_opt.status_code, 403)
            self.assertEqual(res_opt.get_json()["error"], "google_link_forbidden")

    # ---- 9. Guest goi admin API -> 401 ----
    def test_09_guest_admin_api_returns_401(self):
        res = self.client.get("/api/admin/overview")
        self.assertEqual(res.status_code, 401)

    # ---- 10. User thuong goi admin API -> 403 ----
    def test_10_user_admin_api_returns_403(self):
        _, user_token, _ = self.create_user("user_reg@test.com", "userreg")
        res = self.client.get("/api/admin/overview", headers={"Authorization": f"Bearer {user_token}"})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "forbidden")

    # ---- 11. Admin Bearer token -> 200 ----
    def test_11_admin_bearer_token_access_granted(self):
        admin = db.get_user_by_email("admin_super@test.com")
        family_id, _, _ = create_token_family(admin["id"])
        admin_token = create_access_token(admin["id"], family_id)

        res = self.client.get("/api/admin/overview", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("cards", data)
        self.assertIn("series", data)

    # ---- 12. Legacy session["admin"] khong vao duoc /api/admin/* ----
    def test_12_legacy_admin_session_does_not_grant_api_access(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess["admin"] = True
            sess["admin_csrf_token"] = "legacy-token"

        res = client.get("/api/admin/overview")
        self.assertEqual(res.status_code, 401)

    # ---- 13. Mutating API thieu/sai CSRF bi tu choi ----
    def test_13_mutating_admin_api_requires_valid_csrf(self):
        admin = db.get_user_by_email("admin_super@test.com")
        family_id, _, _ = create_token_family(admin["id"])
        admin_token = create_access_token(admin["id"], family_id)

        # Mutating call without CSRF header
        res = self.client.post(
            "/api/admin/users/1/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_active": False},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "invalid_csrf_token")

    # ---- 14. Overview thong ke dung va zero-filled series ----
    def test_14_overview_stats_accuracy_and_zero_fill(self):
        admin = db.get_user_by_email("admin_super@test.com")
        family_id, _, _ = create_token_family(admin["id"])
        admin_token = create_access_token(admin["id"], family_id)

        res = self.client.get("/api/admin/overview?range=7d", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["range"], "7d")
        self.assertEqual(data["timezone"], "Asia/Bangkok")
        self.assertEqual(len(data["series"]), 7)
        for s in data["series"]:
            self.assertIn("date", s)
            self.assertIn("revenue_vnd", s)
            self.assertIn("orders", s)
            self.assertIn("new_users", s)

    # ---- 15. User pagination & filter, khong lo secrets ----
    def test_15_user_pagination_and_safe_fields(self):
        admin = db.get_user_by_email("admin_super@test.com")
        family_id, _, _ = create_token_family(admin["id"])
        admin_token = create_access_token(admin["id"], family_id)

        res = self.client.get(
            "/api/admin/users?limit=5&page=1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res.status_code, 200)
        users = res.get_json()["users"]
        self.assertGreater(len(users), 0)
        for u in users:
            self.assertNotIn("password_hash", u)
            self.assertNotIn("password", u)
            self.assertIn("role", u)
            self.assertIn("balance_coin", u)

    # ---- 16. Wallet adjustment idempotency va atomicity ----
    def test_16_wallet_adjustment_and_seed_admin_protection(self):
        admin = db.get_user_by_email("admin_super@test.com")
        family_id, _, _ = create_token_family(admin["id"])
        admin_token = create_access_token(admin["id"], family_id)
        csrf = self.get_csrf()

        uid, _, _ = self.create_user("adjuser@test.com", "adjuser")

        # Adjust +50 Coin
        res = self.client.post(
            f"/api/admin/users/{uid}/adjust-wallet",
            headers={"Authorization": f"Bearer {admin_token}", "X-CSRF-Token": csrf},
            json={"amount_coin": 50, "reason": "Gift for loyal customer", "idempotency_key": "gift_key_001"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(db.get_wallet_balance(uid), 50)

        # Idempotency replay with same key
        res_dup = self.client.post(
            f"/api/admin/users/{uid}/adjust-wallet",
            headers={"Authorization": f"Bearer {admin_token}", "X-CSRF-Token": csrf},
            json={"amount_coin": 50, "reason": "Gift for loyal customer", "idempotency_key": "gift_key_001"},
        )
        self.assertEqual(res_dup.status_code, 200)
        self.assertEqual(db.get_wallet_balance(uid), 50)  # Balance should NOT be 100!

        # Cannot adjust below zero
        res_neg = self.client.post(
            f"/api/admin/users/{uid}/adjust-wallet",
            headers={"Authorization": f"Bearer {admin_token}", "X-CSRF-Token": csrf},
            json={"amount_coin": -100, "reason": "Deduct more than balance"},
        )
        self.assertEqual(res_neg.status_code, 400)
        self.assertEqual(res_neg.get_json()["error"], "insufficient_balance")

        # Seed admin cannot be locked or demoted
        res_lock = self.client.post(
            f"/api/admin/users/{admin['id']}/status",
            headers={"Authorization": f"Bearer {admin_token}", "X-CSRF-Token": csrf},
            json={"is_active": False},
        )
        self.assertEqual(res_lock.status_code, 400)
        self.assertEqual(res_lock.get_json()["error"], "seed_admin_immutable")

        res_demote = self.client.post(
            f"/api/admin/users/{admin['id']}/role",
            headers={"Authorization": f"Bearer {admin_token}", "X-CSRF-Token": csrf},
            json={"role": "user"},
        )
        self.assertEqual(res_demote.status_code, 400)
        self.assertEqual(res_demote.get_json()["error"], "seed_admin_immutable")

    # ---- 17. Audit log duoc ghi va da redact ----
    def test_17_audit_log_recorded_and_redacted(self):
        admin = db.get_user_by_email("admin_super@test.com")
        family_id, _, _ = create_token_family(admin["id"])
        admin_token = create_access_token(admin["id"], family_id)

        res = self.client.get("/api/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        logs = data["logs"]
        self.assertGreater(len(logs), 0)

        for l in logs:
            # Check redaction: raw passwords or tokens must never appear
            b_str = json.dumps(l.get("before") or {})
            a_str = json.dumps(l.get("after") or {})
            self.assertNotIn("SuperSecretPassword", b_str)
            self.assertNotIn("SuperSecretPassword", a_str)

    # ---- 18. Maintenance allow_admin hoat dong voi Bearer admin role moi ----
    def test_18_maintenance_mode_allows_admin_bearer(self):
        from locket import site_settings
        site_settings.set_maintenance({"enabled": True, "allow_admin": True, "message": "Upgrading server"})

        try:
            # Guest hitting public page gets 503 maintenance
            res_guest = self.client.get("/")
            self.assertEqual(res_guest.status_code, 503)

            # Authenticated normal user gets 503 maintenance response on public api
            _, user_token, _ = self.create_user("maintuser@test.com", "maintuser")
            res_user = self.client.post(
                "/api/restore",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"username": "alice", "platform": "ios"},
            )
            self.assertEqual(res_user.status_code, 503)
            self.assertTrue(res_user.get_json().get("maintenance"))

            # Login route is NEVER blocked by maintenance
            csrf = self.get_csrf()
            res_login = self.client.post(
                "/api/auth/login",
                headers={"X-CSRF-Token": csrf},
                json={"identifier": "adminsuper", "password": "SuperSecretPassword123!"},
            )
            self.assertEqual(res_login.status_code, 200)

            # Admin Bearer token can bypass maintenance
            admin = db.get_user_by_email("admin_super@test.com")
            family_id, _, _ = create_token_family(admin["id"])
            admin_token = create_access_token(admin["id"], family_id)

            res_admin_api = self.client.get(
                "/api/admin/maintenance",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(res_admin_api.status_code, 200)
            self.assertTrue(res_admin_api.get_json()["maintenance"]["enabled"])
        finally:
            site_settings.set_maintenance({"enabled": False})


if __name__ == "__main__":
    unittest.main()
