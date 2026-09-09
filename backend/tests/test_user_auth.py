import os
import sys
import tempfile
import unittest

# Ensure temporary DB is used before importing app
temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "test-secret-key-1234567890-test"
os.environ["JWT_SECRET"] = "test-jwt-secret-key-1234567890-test"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-secret-key-0987654321-test"

# Make backend root importable
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db


class UserAuthTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCKET_DB"] = temp_db_path
        db.close_conn()

        cls.app = create_app()
        cls.app.config["TESTING"] = True

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

    def get_csrf(self, client):
        res = client.get("/api/auth/csrf")
        data = res.get_json()
        return data.get("csrf_token")

    def test_01_me_unauthenticated(self):
        # Without Bearer token, /api/auth/me rejects with 401 missing_access_token
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data.get("error"), "missing_access_token")

    def test_02_register_csrf_missing(self):
        res = self.client.post("/api/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "password12345",
        })
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertEqual(data.get("error"), "invalid_csrf_token")

    def test_03_register_validation_errors(self):
        csrf = self.get_csrf(self.client)
        headers = {"X-CSRF-Token": csrf}

        # Invalid email
        res = self.client.post("/api/auth/register", headers=headers, json={
            "email": "not-an-email",
            "username": "testuser",
            "password": "password12345",
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get("error"), "invalid_email")

        # Short password (<10)
        res = self.client.post("/api/auth/register", headers=headers, json={
            "email": "valid@example.com",
            "username": "testuser",
            "password": "short",
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get("error"), "invalid_password")

        # Invalid username (special characters)
        res = self.client.post("/api/auth/register", headers=headers, json={
            "email": "valid@example.com",
            "username": "bad user!",
            "password": "password12345",
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get("error"), "invalid_username")

    def test_04_register_success_and_duplicate_check(self):
        csrf = self.get_csrf(self.client)
        headers = {"X-CSRF-Token": csrf}

        res = self.client.post("/api/auth/register", headers=headers, json={
            "email": "huy@example.com",
            "username": "huy_dev",
            "display_name": "Huy Dev",
            "password": "SecurePassword123!",
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["email"], "huy@example.com")
        self.assertEqual(data["user"]["username"], "huy_dev")
        self.assertEqual(data["user"]["display_name"], "Huy Dev")
        self.assertIn("access_token", data)

        access_token = data["access_token"]

        # Verify session state via /api/auth/me with Bearer token
        me_res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.get_json()
        self.assertTrue(me_data["authenticated"])
        self.assertEqual(me_data["user"]["username"], "huy_dev")

        # Duplicate email test
        client2 = self.app.test_client()
        csrf2 = self.get_csrf(client2)
        dup_email_res = client2.post("/api/auth/register", headers={"X-CSRF-Token": csrf2}, json={
            "email": "huy@example.com",
            "username": "other_user",
            "password": "SecurePassword123!",
        })
        self.assertEqual(dup_email_res.status_code, 409)
        self.assertEqual(dup_email_res.get_json().get("error"), "email_exists")

        # Duplicate username test
        dup_user_res = client2.post("/api/auth/register", headers={"X-CSRF-Token": csrf2}, json={
            "email": "other@example.com",
            "username": "huy_dev",
            "password": "SecurePassword123!",
        })
        self.assertEqual(dup_user_res.status_code, 409)
        self.assertEqual(dup_user_res.get_json().get("error"), "username_exists")

    def test_05_login_flow(self):
        client = self.app.test_client()
        csrf = self.get_csrf(client)
        headers = {"X-CSRF-Token": csrf}

        # Wrong password
        bad_pass = client.post("/api/auth/login", headers=headers, json={
            "identifier": "huy_dev",
            "password": "wrongpassword123",
        })
        self.assertEqual(bad_pass.status_code, 401)

        # Login by username
        login_user = client.post("/api/auth/login", headers=headers, json={
            "identifier": "huy_dev",
            "password": "SecurePassword123!",
        })
        self.assertEqual(login_user.status_code, 200)
        login_data = login_user.get_json()
        self.assertTrue(login_data["success"])
        self.assertIn("access_token", login_data)

        access_token = login_data["access_token"]

        # Logout revokes session family
        csrf = self.get_csrf(client)
        logout_res = client.post(
            "/api/auth/logout",
            headers={
                "X-CSRF-Token": csrf,
                "Authorization": f"Bearer {access_token}",
            },
        )
        self.assertEqual(logout_res.status_code, 200)

        # Token is now revoked
        me_after_logout = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(me_after_logout.status_code, 401)
        self.assertEqual(me_after_logout.get_json().get("error"), "token_session_revoked")

        # Login by email (case-insensitive)
        csrf = self.get_csrf(client)
        login_email = client.post("/api/auth/login", headers={"X-CSRF-Token": csrf}, json={
            "identifier": "HUY@example.com",
            "password": "SecurePassword123!",
        })
        self.assertEqual(login_email.status_code, 200)
        self.assertTrue(login_email.get_json()["success"])

    def test_06_service_protection_and_queue_ownership(self):
        unauth_client = self.app.test_client()

        # Unauthenticated calls without Bearer token fail with 401 missing_access_token
        res_info = unauth_client.post("/api/get-user-info", json={"username": "test"})
        self.assertEqual(res_info.status_code, 401)
        self.assertEqual(res_info.get_json().get("error"), "missing_access_token")

        res_restore = unauth_client.post("/api/restore", json={"username": "test"})
        self.assertEqual(res_restore.status_code, 401)
        self.assertEqual(res_restore.get_json().get("error"), "missing_access_token")

        # Register User A
        client_a = self.app.test_client()
        csrf_a = self.get_csrf(client_a)
        reg_a = client_a.post("/api/auth/register", headers={"X-CSRF-Token": csrf_a}, json={
            "email": "user_a@test.com",
            "username": "user_a",
            "password": "password12345",
        })
        self.assertEqual(reg_a.status_code, 201)
        data_a = reg_a.get_json()
        user_a_id = data_a["user"]["id"]
        token_a = data_a["access_token"]

        # Directly insert a queue request for User A to test ownership
        conn = db.get_conn()
        client_id_a = "req-user-a-1234"
        conn.execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, user_id) "
            "VALUES (?, ?, 'waiting', ?, ?)",
            (client_id_a, "target_a", 1000.0, user_a_id),
        )

        # User A can query their queue request with Bearer token
        status_a = client_a.post(
            "/api/queue/status",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"client_id": client_id_a},
        ).get_json()
        self.assertEqual(status_a.get("status"), "waiting")

        # Register User B
        client_b = self.app.test_client()
        csrf_b = self.get_csrf(client_b)
        reg_b = client_b.post("/api/auth/register", headers={"X-CSRF-Token": csrf_b}, json={
            "email": "user_b@test.com",
            "username": "user_b",
            "password": "password12345",
        })
        self.assertEqual(reg_b.status_code, 201)
        token_b = reg_b.get_json()["access_token"]

        # User B queries User A's client_id -> status is not_found (Ownership isolation!)
        status_b = client_b.post(
            "/api/queue/status",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"client_id": client_id_a},
        ).get_json()
        self.assertEqual(status_b.get("status"), "not_found")

    def test_07_admin_session_isolation(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess["admin"] = True

        # Register customer
        csrf = self.get_csrf(client)
        res = client.post("/api/auth/register", headers={"X-CSRF-Token": csrf}, json={
            "email": "admin_also_user@test.com",
            "username": "admin_user",
            "password": "password12345",
        })
        self.assertEqual(res.status_code, 201)
        access_token = res.get_json()["access_token"]

        # Ensure admin session is still intact and customer auth never touches session["user_id"]
        with client.session_transaction() as sess:
            self.assertTrue(sess.get("admin"))
            self.assertIsNone(sess.get("user_id"))

        # Logout customer
        csrf = self.get_csrf(client)
        client.post(
            "/api/auth/logout",
            headers={
                "X-CSRF-Token": csrf,
                "Authorization": f"Bearer {access_token}",
            },
        )

        # Ensure admin session is STILL intact after customer logout!
        with client.session_transaction() as sess:
            self.assertTrue(sess.get("admin"))
            self.assertIsNone(sess.get("user_id"))


if __name__ == "__main__":
    unittest.main()
