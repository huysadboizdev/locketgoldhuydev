import hashlib
import json
import os
import secrets
import sys
import tempfile
import time
import unittest

# Ensure temporary DB is used before importing app
temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "test-secret-key-1234567890-test"
os.environ["JWT_SECRET"] = "test-jwt-secret-very-secure-key-12345678"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-secret-very-secure-12345"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"
os.environ["ACCESS_TOKEN_TTL_SECONDS"] = "600"
os.environ["REFRESH_TOKEN_TTL_SECONDS"] = "2592000"

# Make backend root importable
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

import jwt
from locket import create_app, db
from locket.token_auth import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    create_token_family,
    rotate_refresh_token,
    revoke_token_family,
    JWT_SECRET,
    REFRESH_TOKEN_PEPPER,
)
from locket.user_auth import reset_rate_limits
from werkzeug.security import generate_password_hash


class TokenAuthComprehensiveTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCKET_DB"] = temp_db_path
        db.close_conn()

        cls.app = create_app()
        cls.app.config["TESTING"] = True

        # Admin provisioning may already own id=1. Keep a separate login user
        # while id=1 remains available for the token-family FK tests below.
        conn = db.get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (1, 'admin@example.com', 'admin', 'Admin User', ?, 1, ?)",
            (generate_password_hash("admin-secret-password-1234"), time.time()),
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (2, 'seed@example.com', 'seeduser', 'Seed User', ?, 1, ?)",
            (generate_password_hash("password12345"), time.time()),
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

    def get_csrf(self, client=None):
        c = client or self.client
        res = c.get("/api/auth/csrf")
        data = res.get_json()
        return data.get("csrf_token")

    # =========================================================================
    # Group 1: JWT & Crypto Engine Tests
    # =========================================================================

    def test_01_create_and_decode_access_token(self):
        token = create_access_token(123, "fam-abc", expires_in=300)
        self.assertIsInstance(token, str)

        decoded = decode_access_token(token)
        self.assertEqual(decoded["sub"], "123")
        self.assertEqual(decoded["sid"], "fam-abc")
        self.assertEqual(decoded["type"], "access")
        self.assertIn("jti", decoded)
        self.assertIn("exp", decoded)
        self.assertIn("iat", decoded)

    def test_02_decode_algorithm_enforcement(self):
        token = create_access_token(123, "fam-abc")
        parts = token.split(".")
        # Tamper payload
        bad_token = f"{parts[0]}.eyJhZG1pbiI6dHJ1ZX0.{parts[2]}"
        with self.assertRaises(jwt.InvalidTokenError):
            decode_access_token(bad_token)

    def test_03_token_expiration(self):
        token = create_access_token(123, "fam-abc", expires_in=-10)
        with self.assertRaises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_04_wrong_secret_rejected(self):
        token = jwt.encode(
            {"sub": "123", "sid": "fam-abc", "type": "access", "exp": time.time() + 300},
            "wrong-secret-key-000000000000000000",
            algorithm="HS256",
        )
        with self.assertRaises(jwt.InvalidSignatureError):
            decode_access_token(token)

    def test_05_refresh_token_entropy_and_hashing(self):
        tok1 = generate_refresh_token()
        tok2 = generate_refresh_token()
        self.assertNotEqual(tok1, tok2)
        self.assertGreaterEqual(len(tok1), 48)

        h1 = hash_refresh_token(tok1)
        h2 = hash_refresh_token(tok1)
        self.assertEqual(h1, h2)
        self.assertNotEqual(hash_refresh_token(tok1), hash_refresh_token(tok2))

    # =========================================================================
    # Group 2: DB Family & Token Rotation / Replay Detection Tests
    # =========================================================================

    def test_06_create_token_family_in_db(self):
        fam_id, raw_tok, ttl = create_token_family(user_id=1)
        self.assertEqual(len(fam_id), 32)
        sess = db.get_auth_session(fam_id)
        self.assertIsNotNone(sess)
        self.assertEqual(sess["user_id"], 1)
        self.assertIsNone(sess["revoked_at"])

        tok_rec = db.get_refresh_token_by_hash(hash_refresh_token(raw_tok))
        self.assertIsNotNone(tok_rec)
        self.assertEqual(tok_rec["family_id"], fam_id)
        self.assertIsNone(tok_rec["used_at"])

    def test_07_rotate_refresh_token_success(self):
        fam_id, raw_tok_1, _ = create_token_family(user_id=1)
        status, new_raw_tok_2, new_jwt, user_dict, fam, *rest = rotate_refresh_token(raw_tok_1)
        self.assertEqual(status, "ok")
        self.assertNotEqual(raw_tok_1, new_raw_tok_2)
        self.assertIsNotNone(new_jwt)
        self.assertEqual(fam, fam_id)

        # Verify old token marked used
        old_rec = db.get_refresh_token_by_hash(hash_refresh_token(raw_tok_1))
        self.assertIsNotNone(old_rec["used_at"])
        self.assertIsNotNone(old_rec["replaced_by"])

        # Verify new token stored and unused
        new_rec = db.get_refresh_token_by_hash(hash_refresh_token(new_raw_tok_2))
        self.assertIsNotNone(new_rec)
        self.assertIsNone(new_rec["used_at"])
        self.assertEqual(new_rec["parent_id"], old_rec["id"])

    def test_08_replay_detection_revokes_family(self):
        fam_id, raw_tok_1, _ = create_token_family(user_id=1)
        # First rotation: legit
        status, raw_tok_2, _, _, _, *rest = rotate_refresh_token(raw_tok_1)
        self.assertEqual(status, "ok")

        # Replay attempt: presenting old raw_tok_1 again!
        status, _, _, _, fam, *rest = rotate_refresh_token(raw_tok_1)
        self.assertEqual(status, "replay_detected")

        # Verify family is completely revoked
        sess = db.get_auth_session(fam_id)
        self.assertIsNotNone(sess["revoked_at"])
        self.assertEqual(sess["revoke_reason"], "replay_detected")

        # Now even the legitimate token 2 cannot be rotated
        status_after, *rest = rotate_refresh_token(raw_tok_2)
        self.assertNotEqual(status_after, "ok")

    def test_09_manual_family_revocation(self):
        fam_id, raw_tok, _ = create_token_family(user_id=1)
        revoke_token_family(fam_id, reason="test_revocation")
        sess = db.get_auth_session(fam_id)
        self.assertIsNotNone(sess["revoked_at"])
        self.assertEqual(sess["revoke_reason"], "test_revocation")

        status, *rest = rotate_refresh_token(raw_tok)
        self.assertEqual(status, "session_revoked")

    # =========================================================================
    # Group 3: HTTP Auth Endpoints Tests (/api/auth)
    # =========================================================================

    def test_10_csrf_endpoint(self):
        res = self.client.get("/api/auth/csrf")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data.get("csrf_token"), str)
        self.assertIn("no-store", res.headers.get("Cache-Control", ""))

    def test_11_register_missing_csrf_fails(self):
        res = self.client.post("/api/auth/register", json={
            "email": "user1@example.com",
            "username": "userone",
            "password": "password12345",
        })
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "invalid_csrf_token")

    def test_12_register_success_returns_jwt_and_cookie(self):
        csrf = self.get_csrf()
        res = self.client.post(
            "/api/auth/register",
            headers={"X-CSRF-Token": csrf},
            json={
                "email": "user1@example.com",
                "username": "userone",
                "display_name": "User One",
                "password": "password12345",
            },
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(data["user"]["email"], "user1@example.com")
        self.assertEqual(data["user"]["username"], "userone")

        # Verify refresh cookie was set
        set_cookie = res.headers.get("Set-Cookie", "")
        self.assertIn("locket_refresh=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("Path=/api/auth", set_cookie)

    def test_13_register_duplicate_fails(self):
        csrf = self.get_csrf()
        res = self.client.post(
            "/api/auth/register",
            headers={"X-CSRF-Token": csrf},
            json={
                "email": "user1@example.com",
                "username": "userone_other",
                "password": "password12345",
            },
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "email_exists")

    def test_14_login_wrong_credentials_fails(self):
        csrf = self.get_csrf()
        res = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={
                "identifier": "userone",
                "password": "wrong_password",
            },
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "invalid_credentials")

    def test_15_login_success_returns_jwt_and_cookie(self):
        csrf = self.get_csrf()
        res = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={
                "identifier": "userone",
                "password": "password12345",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(data["user"]["username"], "userone")
        self.assertIn("locket_refresh=", res.headers.get("Set-Cookie", ""))

    def test_16_me_endpoint_requires_bearer_token(self):
        # 1. Without header -> 401
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "missing_access_token")

        # 2. With valid login token -> 200
        csrf = self.get_csrf()
        login_res = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"identifier": "userone", "password": "password12345"},
        )
        token = login_res.get_json()["access_token"]
        res2 = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertTrue(data2["success"])
        self.assertTrue(data2["authenticated"])
        self.assertEqual(data2["user"]["username"], "userone")

    def test_17_refresh_endpoint_rotates_cookie_and_issues_jwt(self):
        # Login to get initial cookie
        csrf = self.get_csrf()
        login_res = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"identifier": "userone", "password": "password12345"},
        )
        token_1 = login_res.get_json()["access_token"]

        # Call refresh endpoint with cookie
        fresh_csrf = self.get_csrf()
        ref_res = self.client.post(
            "/api/auth/refresh",
            headers={"X-CSRF-Token": fresh_csrf},
        )
        self.assertEqual(ref_res.status_code, 200)
        ref_data = ref_res.get_json()
        self.assertTrue(ref_data["success"])
        self.assertIn("access_token", ref_data)
        token_2 = ref_data["access_token"]
        self.assertNotEqual(token_1, token_2)

        # Check new access token works
        me_res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token_2}"},
        )
        self.assertEqual(me_res.status_code, 200)

    def test_18_logout_revokes_family_and_clears_cookie(self):
        csrf = self.get_csrf()
        login_res = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"identifier": "userone", "password": "password12345"},
        )
        token = login_res.get_json()["access_token"]

        logout_csrf = self.get_csrf()
        logout_res = self.client.post(
            "/api/auth/logout",
            headers={
                "X-CSRF-Token": logout_csrf,
                "Authorization": f"Bearer {token}",
            },
        )
        self.assertEqual(logout_res.status_code, 200)
        # Check cookie cleared
        self.assertIn("Expires=Thu, 01 Jan 1970", logout_res.headers.get("Set-Cookie", ""))

        # Token is now rejected because family was revoked
        me_res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(me_res.status_code, 401)
        self.assertEqual(me_res.get_json()["error"], "token_session_revoked")

    # =========================================================================
    # Group 4: Admin Isolation Tests
    # =========================================================================

    def test_19_admin_session_unaffected_by_customer_actions(self):
        admin_client = self.app.test_client()

        # 1. Admin login via form
        adm_res = admin_client.post("/admin/login", data={
            "username": "admin",
            "password": "admin-secret-password-1234",
        }, follow_redirects=False)
        self.assertIn(adm_res.status_code, (200, 302))

        # Check admin dashboard accessible
        dash_res = admin_client.get("/admin/")
        self.assertEqual(dash_res.status_code, 200)

        # 2. Perform customer actions on same client
        c_csrf = self.get_csrf(admin_client)
        admin_client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": c_csrf},
            json={"identifier": "userone", "password": "password12345"},
        )

        # Admin dashboard STILL accessible
        dash_res2 = admin_client.get("/admin/")
        self.assertEqual(dash_res2.status_code, 200)

        # Customer logout
        c_csrf2 = self.get_csrf(admin_client)
        admin_client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": c_csrf2},
        )

        # Admin dashboard STILL accessible (admin session never wiped by customer logout)
        dash_res3 = admin_client.get("/admin/")
        self.assertEqual(dash_res3.status_code, 200)

    # =========================================================================
    # Group 5: Protected Service Endpoints & Queue Ownership Tests
    # =========================================================================

    def test_20_restore_requires_access_token(self):
        res = self.client.post("/api/restore", json={"username": "someone"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "missing_access_token")

    def test_21_queue_status_ownership_enforcement(self):
        # Insert a fake queue request owned by user 999
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, user_id) "
            "VALUES (?, ?, 'waiting', ?, ?)",
            ("client-user-999", "target999", time.time(), 999),
        )

        # Customer userone logs in (id=2 in this run)
        csrf = self.get_csrf()
        login_res = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"identifier": "userone", "password": "password12345"},
        )
        token = login_res.get_json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Query request belonging to someone else (id=999) -> 404 forbidden/not_found
        res = self.client.post(
            "/api/queue/status",
            headers=headers,
            json={"client_id": "client-user-999"},
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.get_json()["error"], "not_found")

        # Anonymous query (no token) -> 401
        res_anon = self.client.post("/api/queue/status", json={"client_id": "client-user-999"})
        self.assertEqual(res_anon.status_code, 401)

    # =========================================================================
    # Group 6: Mobileconfig Single-Use Ticket Flow Tests
    # =========================================================================

    def test_22_mobileconfig_download_ticket_flow(self):
        csrf = self.get_csrf()
        login_res = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"identifier": "userone", "password": "password12345"},
        )
        token = login_res.get_json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Attempt GET without ticket -> 403
        res_no_ticket = self.client.get("/api/mobileconfig")
        self.assertEqual(res_no_ticket.status_code, 403)
        self.assertEqual(res_no_ticket.get_json()["error"], "missing_ticket")

        # Create a completed iOS queue request owned by userone
        conn = db.get_conn()
        user_row = db.get_user_by_username("userone")
        user_id = user_row["id"]
        client_id = "test-ios-order-123"
        conn.execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, completed_at, user_id, platform) "
            "VALUES (?, 'userone', 'completed', ?, ?, ?, 'ios')",
            (client_id, time.time() - 10, time.time(), user_id),
        )

        # 2. Generate download ticket
        ticket_res = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=headers,
            json={"client_id": client_id},
        )
        self.assertEqual(ticket_res.status_code, 200)
        tdata = ticket_res.get_json()
        self.assertTrue(tdata["success"])
        download_url = tdata["download_url"]
        self.assertIn("?ticket=", download_url)

        # 3. Create mock mobileconfig static file if not exists
        static_dir = os.path.join(self.app.root_path, "static")
        os.makedirs(static_dir, exist_ok=True)
        mc_path = os.path.join(static_dir, "locket.mobileconfig")
        with open(mc_path, "w", encoding="utf-8") as f:
            f.write("<plist>dummy mobileconfig</plist>")

        # 4. First download using ticket -> 200
        dl_res = self.client.get(download_url)
        self.assertEqual(dl_res.status_code, 200)
        self.assertEqual(dl_res.headers.get("Content-Type"), "application/x-apple-aspen-config")
        self.assertIn("no-store", dl_res.headers.get("Cache-Control", ""))
        dl_res.close()

        # 5. Second download using same ticket -> 403 (single-use claimed)
        dl_res_2 = self.client.get(download_url)
        self.assertEqual(dl_res_2.status_code, 403)
        self.assertEqual(dl_res_2.get_json()["error"], "invalid_ticket")
        dl_res_2.close()

    # =========================================================================
    # Group 7: Rate Limiting Tests
    # =========================================================================

    def test_23_rate_limiting_login(self):
        csrf = self.get_csrf()
        # Fire 16 rapid login requests with same identifier to exceed max_requests=15
        hit_429 = False
        for i in range(16):
            res = self.client.post(
                "/api/auth/login",
                headers={"X-CSRF-Token": csrf},
                json={"identifier": "userone", "password": "wrong_password"},
            )
            if res.status_code == 429:
                hit_429 = True
                self.assertEqual(res.get_json()["error"], "rate_limited")
                break

    # =========================================================================
    # Group 8: Edge Cases & Advanced Security Verification (Tests 24 - 38)
    # =========================================================================

    def test_24_tampered_signature_rejected(self):
        token = create_access_token(1, "fam-test")
        parts = token.split(".")
        # Modify first character of signature to guarantee byte modification
        tampered_sig = ("X" if parts[2][0] != "X" else "Y") + parts[2][1:]
        tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
        res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "invalid_access_token")

    def test_25_missing_type_claim_rejected(self):
        payload = {
            "sub": "1",
            "sid": "fam-test",
            "exp": time.time() + 300,
            "iss": "locket-gold",
            "aud": "locket-gold-web",
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "invalid_access_token")

    def test_26_wrong_token_type_rejected(self):
        payload = {
            "sub": "1",
            "sid": "fam-test",
            "type": "refresh",  # Not "access"!
            "exp": time.time() + 300,
            "iss": "locket-gold",
            "aud": "locket-gold-web",
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "invalid_access_token")

    def test_27_user_deactivated_rejects_access(self):
        # Create an inactive user
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (888, 'inactive@example.com', 'inactive_user', 'Inactive', 'dummy', 0, ?)",
            (time.time(),),
        )
        fam_id, raw_tok, _ = create_token_family(user_id=888)
        token = create_access_token(888, fam_id)

        res = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "account_inactive")

    def test_28_queue_my_active_unauthenticated_fails(self):
        res = self.client.get("/api/queue/my-active")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "missing_access_token")

    def test_29_queue_my_active_returns_only_own_request(self):
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, user_id) "
            "VALUES ('active-user-1', 'active_username', 'waiting', ?, 1)",
            (time.time(),),
        )
        fam_id, _, _ = create_token_family(user_id=1)
        token = create_access_token(1, fam_id)

        res = self.client.get(
            "/api/queue/my-active",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIsNotNone(data["active"])
        self.assertEqual(data["active"]["client_id"], "active-user-1")

    def test_30_mobileconfig_expired_ticket_fails(self):
        raw_ticket = "expired-ticket-test-1234567890"
        ticket_hash = hashlib.sha256(raw_ticket.encode()).hexdigest()
        # Insert ticket already expired 10 seconds ago
        db.create_download_ticket(ticket_hash, user_id=1, expires_at=time.time() - 10)

        res = self.client.get(f"/api/mobileconfig?ticket={raw_ticket}")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "invalid_ticket")

    def test_31_mobileconfig_tampered_ticket_fails(self):
        res = self.client.get("/api/mobileconfig?ticket=completely-random-nonexistent-ticket")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"], "invalid_ticket")

    def test_32_refresh_without_cookie_fails(self):
        fresh_client = self.app.test_client()
        csrf = self.get_csrf(fresh_client)
        res = fresh_client.post(
            "/api/auth/refresh",
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json()["error"], "missing_refresh_token")

    def test_33_refresh_rate_limiting(self):
        fresh_client = self.app.test_client()
        csrf = self.get_csrf(fresh_client)
        # Refresh limit is 30 per 60s
        hit_429 = False
        for i in range(32):
            res = fresh_client.post(
                "/api/auth/refresh",
                headers={"X-CSRF-Token": csrf},
            )
            if res.status_code == 429:
                hit_429 = True
                self.assertEqual(res.get_json()["error"], "rate_limited")
                break
        self.assertTrue(hit_429, "Expected to hit rate limit on rapid refresh calls")

    def test_34_register_rate_limiting(self):
        fresh_client = self.app.test_client()
        csrf = self.get_csrf(fresh_client)
        # Register limit is 10 per 300s
        hit_429 = False
        for i in range(12):
            res = fresh_client.post(
                "/api/auth/register",
                headers={"X-CSRF-Token": csrf},
                json={
                    "email": f"ratetest_{i}@example.com",
                    "username": f"rateuser_{i}",
                    "password": "password12345",
                },
            )
            if res.status_code == 429:
                hit_429 = True
                self.assertEqual(res.get_json()["error"], "rate_limited")
                break
        self.assertTrue(hit_429, "Expected to hit rate limit on rapid register calls")

    def test_35_logout_without_auth_is_graceful(self):
        fresh_client = self.app.test_client()
        csrf = self.get_csrf(fresh_client)
        res = fresh_client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

    def test_36_restore_success_associates_user_id(self):
        fam_id, _, _ = create_token_family(user_id=1)
        token = create_access_token(1, fam_id)

        # Ensure rotator is mock-ready or has accounts
        res = self.client.post(
            "/api/restore",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "testrestoreuser", "platform": "ios"},
        )
        # Either 200 (if rotator has accounts) or 503 (if 0 accounts in DB)
        # But NEVER 401 unauthenticated!
        self.assertIn(res.status_code, (200, 503))

    def test_37_database_cleanup_expired_tokens(self):
        # Insert old expired records (older than 7 days)
        old_time = time.time() - (8 * 86400)
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO auth_sessions (family_id, user_id, created_at, expires_at, last_used_at) "
            "VALUES ('fam-old-cleanup', 1, ?, ?, ?)",
            (old_time, old_time, old_time),
        )
        db.cleanup_expired_tokens()
        sess = db.get_auth_session("fam-old-cleanup")
        self.assertIsNone(sess, "Old expired session should have been cleaned up")

    def test_38_admin_cannot_be_logged_out_by_guest_requests(self):
        admin_client = self.app.test_client()
        admin_client.post("/admin/login", data={
            "username": "admin",
            "password": "admin-secret-password-1234",
        })

        # Random visitor requests
        guest_client = self.app.test_client()
        guest_csrf = self.get_csrf(guest_client)
        guest_client.post("/api/auth/logout", headers={"X-CSRF-Token": guest_csrf})

        # Admin is still 200 OK
        res = admin_client.get("/admin/")
        self.assertEqual(res.status_code, 200)

    def test_39_remember_me_cookie_persistence_and_ttl_decrement(self):
        # 1. Login with remember_me=False -> Browser session cookie (no Max-Age)
        c1 = self.app.test_client()
        csrf1 = self.get_csrf(c1)
        res1 = c1.post("/api/auth/login", headers={"X-CSRF-Token": csrf1}, json={
            "identifier": "seeduser",
            "password": "password12345",
            "remember_me": False,
        })
        self.assertEqual(res1.status_code, 200)
        cookie1 = res1.headers.get("Set-Cookie", "")
        self.assertIn("locket_refresh=", cookie1)
        # Session cookie has no Max-Age
        self.assertNotIn("Max-Age=", cookie1)

        # 2. Login with remember_me=True -> 30-day persistent cookie (Max-Age present)
        c2 = self.app.test_client()
        csrf2 = self.get_csrf(c2)
        res2 = c2.post("/api/auth/login", headers={"X-CSRF-Token": csrf2}, json={
            "identifier": "seeduser",
            "password": "password12345",
            "remember_me": True,
        })
        self.assertEqual(res2.status_code, 200)
        cookie2 = res2.headers.get("Set-Cookie", "")
        self.assertIn("Max-Age=", cookie2)

        # 3. Refresh with remember_me=True retains remaining TTL without extending family past expiration
        csrf2 = self.get_csrf(c2)
        ref_res = c2.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf2})
        self.assertEqual(ref_res.status_code, 200)
        ref_cookie = ref_res.headers.get("Set-Cookie", "")
        self.assertIn("Max-Age=", ref_cookie)

    def test_40_session_family_expiration_in_access_required(self):
        # Create a session family that expired 10 seconds ago
        fam_id = secrets.token_hex(16)
        past_time = time.time() - 10
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO auth_sessions (family_id, user_id, created_at, expires_at, last_used_at, remember_me) "
            "VALUES (?, 1, ?, ?, ?, 0)",
            (fam_id, past_time - 100, past_time, past_time),
        )

        token = create_access_token(1, fam_id, expires_in=300)
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json().get("error"), "session_expired")

        # Verify family was revoked in DB
        sess = db.get_auth_session(fam_id)
        self.assertIsNotNone(sess["revoked_at"])
        self.assertEqual(sess["revoke_reason"], "session_expired")

    def test_41_sub_mismatch_in_access_required(self):
        # Session family belongs to user 1
        fam_id, _, _ = create_token_family(user_id=1)
        # Forged token has sub="999" but sid=fam_id
        forged_token = create_access_token(999, fam_id)

        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json().get("error"), "invalid_access_token")

    def test_42_tampered_jwt_rejected_in_logout(self):
        # Create genuine family
        fam_id, raw_token, _ = create_token_family(user_id=1)

        # Attacker crafts forged token with fake signature attempting to revoke fam_id
        payload = {
            "sub": "1",
            "sid": fam_id,
            "type": "access",
            "iss": "locket-gold",
            "aud": "locket-gold-web",
            "exp": int(time.time()) + 300,
        }
        forged_token = jwt.encode(payload, "wrong-attacker-secret-key-123456", algorithm="HS256")

        fresh_client = self.app.test_client()
        csrf = self.get_csrf(fresh_client)

        # Logout attempt with forged token without cookie
        res = fresh_client.post(
            "/api/auth/logout",
            headers={
                "X-CSRF-Token": csrf,
                "Authorization": f"Bearer {forged_token}",
            },
        )
        self.assertEqual(res.status_code, 200)

        # Ensure fam_id was NOT revoked!
        sess = db.get_auth_session(fam_id)
        self.assertIsNone(sess["revoked_at"], "Tampered JWT must not revoke target session family!")

    def test_43_apk_download_ticket_lifecycle(self):
        fam_id, _, _ = create_token_family(user_id=1)
        token = create_access_token(1, fam_id)

        # Create a completed, paid-entitled Android activation order and its queue request.
        conn = db.get_conn()
        client_id = "test-android-order-456"
        now = time.time()
        act_cursor = conn.execute(
            """INSERT INTO activation_orders
               (user_id, plan_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot,
                price_vnd_snapshot, price_coin_snapshot, payment_method, platform, locket_username,
                fulfillment_mode_snapshot, status, queue_client_id, created_at, updated_at)
               VALUES (1, NULL, 'APK entitlement test', 'apk-test', 30, 10000, 10,
                       'coin', 'android', '', 'apk_download', 'completed', ?, ?, ?)""",
            (client_id, now - 10, now),
        )
        conn.execute(
            """INSERT INTO queue_requests
               (client_id, username, status, added_at, completed_at, user_id, platform, activation_order_id)
               VALUES (?, 'userone', 'completed', ?, ?, ?, 'android', ?)""",
            (client_id, now - 10, now, 1, act_cursor.lastrowid),
        )

        # 1. Generate download ticket
        res = self.client.post(
            "/api/apk/download-ticket",
            headers={"Authorization": f"Bearer {token}"},
            json={"client_id": client_id},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("download_url", data)

        download_url = data["download_url"]
        self.assertIn("/api/apk?ticket=", download_url)

        # 2. Claim ticket first time
        claim_res = self.client.get(download_url)
        # In test environment, returns 200 if APK exists locally or 404 if file missing, but NOT 403 invalid_ticket!
        self.assertIn(claim_res.status_code, (200, 404))
        claim_res.close()

        # 3. Second claim with SAME ticket MUST fail with 403 invalid_ticket (single-use!)
        second_res = self.client.get(download_url)
        self.assertEqual(second_res.status_code, 403)
        self.assertEqual(second_res.get_json()["error"], "invalid_ticket")
        second_res.close()


if __name__ == "__main__":
    unittest.main()
