"""Unit tests for Google customer authentication and token verification."""

import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from locket import create_app, db
from locket.google_auth import verify_google_token
from locket.user_auth import reset_rate_limits


class GoogleAuthTestCase(unittest.TestCase):
    ENV_KEYS = (
        "LOCKET_DB",
        "FLASK_SECRET_KEY",
        "JWT_SECRET",
        "REFRESH_TOKEN_PEPPER",
        "GOOGLE_CLIENT_ID",
    )

    def setUp(self):
        self.previous_env = {key: os.environ.get(key) for key in self.ENV_KEYS}
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        os.environ.update({
            "LOCKET_DB": self.db_path,
            "FLASK_SECRET_KEY": "test-secret-key-12345678901234567890",
            "JWT_SECRET": "test-jwt-secret-12345678901234567890",
            "REFRESH_TOKEN_PEPPER": "test-refresh-pepper-123456789012345",
            "GOOGLE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
        })

        db.close_conn()
        db._initialized = False
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        reset_rate_limits()

    def tearDown(self):
        db.close_conn()
        db._initialized = False
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except OSError:
                pass
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def get_csrf(self):
        return self.client.get("/api/auth/csrf").get_json()["csrf_token"]

    def google_claims(self, **overrides):
        claims = {
            "sub": "1001234567890",
            "email": "huytest@gmail.com",
            "email_verified": "true",
            "name": "Huy Nguyen",
            "picture": "https://lh3.googleusercontent.com/a/photo123",
            "aud": "test-client-id.apps.googleusercontent.com",
            "iss": "https://accounts.google.com",
            "exp": str(int(time.time()) + 300),
        }
        claims.update(overrides)
        return claims

    def test_csrf_is_required(self):
        with patch("locket.user_auth.verify_google_token") as verify:
            response = self.client.post("/api/auth/google", json={"credential": "token"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "invalid_csrf_token")
        verify.assert_not_called()

    def test_missing_credential_returns_400(self):
        response = self.client.post(
            "/api/auth/google",
            headers={"X-CSRF-Token": self.get_csrf()},
            json={},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "missing_credential")

    def test_missing_server_client_id_fails_closed(self):
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        response = self.client.post(
            "/api/auth/google",
            headers={"X-CSRF-Token": self.get_csrf()},
            json={"credential": "token"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "google_not_configured")

    def test_legacy_users_schema_migrates_before_google_index(self):
        with self.app.app_context():
            conn = db.get_conn()
            conn.execute("DROP TABLE users")
            conn.execute(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "email TEXT NOT NULL UNIQUE COLLATE NOCASE, "
                "username TEXT NOT NULL UNIQUE COLLATE NOCASE, "
                "display_name TEXT NOT NULL, password_hash TEXT NOT NULL, "
                "is_active INTEGER NOT NULL DEFAULT 1, "
                "created_at REAL NOT NULL, last_login_at REAL)"
            )
            db._initialized = False
            db.init()
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            self.assertIn("google_id", columns)
            self.assertIn("avatar_url", columns)

            db.create_user("one@example.com", "userone", "One", "hash", google_id="same-sub")
            with self.assertRaises(sqlite3.IntegrityError):
                db.create_user("two@example.com", "usertwo", "Two", "hash", google_id="same-sub")

    @patch("locket.user_auth.verify_google_token")
    def test_invalid_google_token_returns_401(self, verify):
        verify.return_value = (False, None, "invalid")
        response = self.client.post(
            "/api/auth/google",
            headers={"X-CSRF-Token": self.get_csrf()},
            json={"credential": "invalid"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "invalid_google_token")

    @patch("locket.user_auth.verify_google_token")
    def test_google_auth_registers_new_user(self, verify):
        verify.return_value = (True, self.google_claims(), None)
        response = self.client.post(
            "/api/auth/google",
            headers={"X-CSRF-Token": self.get_csrf()},
            json={"credential": "valid"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertIn("access_token", body)
        self.assertEqual(body["user"]["email"], "huytest@gmail.com")
        self.assertIn("HttpOnly", response.headers.get("Set-Cookie", ""))

        with self.app.app_context():
            user = db.get_user_by_email("huytest@gmail.com")
            self.assertEqual(user["google_id"], "1001234567890")
            self.assertEqual(user["avatar_url"], "https://lh3.googleusercontent.com/a/photo123")

    @patch("locket.user_auth.verify_google_token")
    def test_existing_password_user_can_link_verified_google_email(self, verify):
        with self.app.app_context():
            user_id = db.create_user(
                "existing@example.com",
                "existinguser",
                "Existing User",
                generate_password_hash("password12345"),
            )
        verify.return_value = (
            True,
            self.google_claims(sub="999888777", email="existing@example.com"),
            None,
        )
        response = self.client.post(
            "/api/auth/google",
            headers={"X-CSRF-Token": self.get_csrf()},
            json={"credential": "valid"},
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.get_user_by_id(user_id)["google_id"], "999888777")

    @patch("locket.user_auth.verify_google_token")
    def test_different_google_subject_cannot_replace_existing_link(self, verify):
        with self.app.app_context():
            db.create_user(
                "linked@example.com",
                "linkeduser",
                "Linked User",
                generate_password_hash("password12345"),
                google_id="original-subject",
            )
        verify.return_value = (
            True,
            self.google_claims(sub="attacker-subject", email="linked@example.com"),
            None,
        )
        response = self.client.post(
            "/api/auth/google",
            headers={"X-CSRF-Token": self.get_csrf()},
            json={"credential": "valid"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "google_account_mismatch")

    @patch("locket.user_auth.verify_google_token")
    def test_google_subject_is_primary_identity(self, verify):
        with self.app.app_context():
            user_id = db.create_user(
                "old@example.com",
                "samegoogle",
                "Same Google User",
                generate_password_hash("password12345"),
                google_id="stable-subject",
            )
        verify.return_value = (
            True,
            self.google_claims(sub="stable-subject", email="new@example.com"),
            None,
        )
        response = self.client.post(
            "/api/auth/google",
            headers={"X-CSRF-Token": self.get_csrf()},
            json={"credential": "valid"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["id"], user_id)
        self.assertEqual(response.get_json()["user"]["email"], "old@example.com")

    @patch("locket.google_auth.requests.get")
    def test_verifier_rejects_wrong_audience(self, get):
        response = MagicMock(status_code=200)
        response.json.return_value = self.google_claims(aud="other-client")
        get.return_value = response
        valid, _, _ = verify_google_token("token")
        self.assertFalse(valid)

    @patch("locket.google_auth.requests.get")
    def test_verifier_rejects_missing_subject_and_expiry(self, get):
        response = MagicMock(status_code=200)
        response.json.return_value = self.google_claims(sub="")
        get.return_value = response
        self.assertFalse(verify_google_token("token")[0])

        response.json.return_value = self.google_claims(exp=None)
        self.assertFalse(verify_google_token("token")[0])


if __name__ == "__main__":
    unittest.main()
