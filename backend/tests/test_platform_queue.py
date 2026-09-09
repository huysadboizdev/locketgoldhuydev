import hashlib
import json
import os
import secrets
import sys
import tempfile
import time
import unittest

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "test-secret-platform-queue-key-12345"
os.environ["JWT_SECRET"] = "test-jwt-secret-platform-queue-12345678"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-secret-platform-queue-123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"
os.environ["NEXTDNS_PROFILE"] = "customprof123"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db
from locket.token_auth import create_token_family, create_access_token
from locket.user_auth import reset_rate_limits
from werkzeug.security import generate_password_hash


class PlatformQueueComprehensiveTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCKET_DB"] = temp_db_path
        db.close_conn()

        cls.app = create_app()
        cls.app.config["TESTING"] = True

        conn = db.get_conn()
        now = time.time()
        # Seed user 1
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (1, 'user1@test.com', 'user1', 'User One', ?, 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        # Seed user 2 (for IDOR / cross-user checks)
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (2, 'user2@test.com', 'user2', 'User Two', ?, 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        # Mock rotator.size so /api/restore passes account availability check
        cls.app.rotator.size = lambda: 1

        # Create static mobileconfig dummy file for download tests
        static_dir = os.path.join(cls.app.root_path, "static")
        os.makedirs(static_dir, exist_ok=True)
        cls.mc_path = os.path.join(static_dir, "locket.mobileconfig")
        with open(cls.mc_path, "w", encoding="utf-8") as f:
            f.write("<plist>dummy mobileconfig content</plist>")

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
        fam1, _, _ = create_token_family(user_id=1)
        self.token_user1 = create_access_token(1, fam1)
        self.headers_user1 = {"Authorization": f"Bearer {self.token_user1}"}

        fam2, _, _ = create_token_family(user_id=2)
        self.token_user2 = create_access_token(2, fam2)
        self.headers_user2 = {"Authorization": f"Bearer {self.token_user2}"}

    def test_01_restore_missing_platform(self):
        """POST /api/restore without platform field returns 400 invalid_platform."""
        res = self.client.post(
            "/api/restore",
            headers=self.headers_user1,
            json={"username": "user_no_platform"},
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "invalid_platform")

    def test_02_restore_invalid_platform(self):
        """POST /api/restore with invalid platform returns 400 invalid_platform."""
        for invalid_val in ["windows", "mac", "linux", "ios-android", "", 123]:
            res = self.client.post(
                "/api/restore",
                headers=self.headers_user1,
                json={"username": "user_invalid", "platform": invalid_val},
            )
            self.assertEqual(res.status_code, 400)
            data = res.get_json()
            self.assertFalse(data["success"])
            self.assertEqual(data["error"], "invalid_platform")

    def test_03_restore_ios_success(self):
        """POST /api/restore with platform: ios succeeds and stores platform."""
        res = self.client.post(
            "/api/restore",
            headers=self.headers_user1,
            json={"username": "ios_user_test", "platform": "ios"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["platform"], "ios")
        self.assertIn("client_id", data)

        # Verify in DB
        row = db.get_conn().execute(
            "SELECT platform FROM queue_requests WHERE client_id = ?", (data["client_id"],)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["platform"], "ios")

    def test_04_restore_android_success(self):
        """POST /api/restore with platform: android succeeds and stores platform."""
        res = self.client.post(
            "/api/restore",
            headers=self.headers_user1,
            json={"username": "android_user_test", "platform": "android"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["platform"], "android")
        self.assertIn("client_id", data)

        # Verify in DB
        row = db.get_conn().execute(
            "SELECT platform FROM queue_requests WHERE client_id = ?", (data["client_id"],)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["platform"], "android")

    def test_05_queue_status_returns_platform(self):
        """POST /api/queue/status returns the correct platform."""
        cid = "status-test-android"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, user_id, platform) "
            "VALUES (?, 'test_q_status', 'waiting', ?, 1, 'android')",
            (cid, time.time()),
        )
        res = self.client.post(
            "/api/queue/status",
            headers=self.headers_user1,
            json={"client_id": cid},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["platform"], "android")

    def test_06_queue_my_active_returns_platform(self):
        """GET /api/queue/my-active returns the active item's platform."""
        cid = "active-test-ios"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, user_id, platform) "
            "VALUES (?, 'active_user_ios', 'processing', ?, 1, 'ios')",
            (cid, time.time() + 100),
        )
        res = self.client.get("/api/queue/my-active", headers=self.headers_user1)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIsNotNone(data["active"])
        self.assertEqual(data["active"]["platform"], "ios")

    def test_07_legacy_queue_request_platform_null(self):
        """Legacy row with platform IS NULL returns platform: None without error or forced default."""
        cid = "legacy-null-platform"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, user_id, platform) "
            "VALUES (?, 'legacy_user', 'waiting', ?, 1, NULL)",
            (cid, time.time()),
        )
        res = self.client.post(
            "/api/queue/status",
            headers=self.headers_user1,
            json={"client_id": cid},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIsNone(data["platform"])

    def test_08_mobileconfig_ticket_requires_client_id(self):
        """POST /api/mobileconfig/download-ticket without client_id returns 400 client_id_required."""
        res = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={},
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "client_id_required")

    def test_09_mobileconfig_ticket_requires_ios_platform(self):
        """POST /api/mobileconfig/download-ticket with android completed order returns 403 platform_mismatch."""
        cid = "completed-android-order"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, completed_at, user_id, platform) "
            "VALUES (?, 'android_done', 'completed', ?, ?, 1, 'android')",
            (cid, time.time() - 10, time.time()),
        )
        res = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={"client_id": cid},
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "platform_mismatch")

    def test_10_mobileconfig_ticket_requires_completed_order(self):
        """POST /api/mobileconfig/download-ticket with uncompleted order returns 403 order_not_completed."""
        cid = "waiting-ios-order"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, user_id, platform) "
            "VALUES (?, 'ios_wait', 'waiting', ?, 1, 'ios')",
            (cid, time.time()),
        )
        res = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={"client_id": cid},
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "order_not_completed")

    def test_11_mobileconfig_ticket_requires_order_ownership(self):
        """User 1 cannot request ticket for User 2's completed order -> 403 order_not_found."""
        cid = "user2-ios-completed"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, completed_at, user_id, platform) "
            "VALUES (?, 'user2_done', 'completed', ?, ?, 2, 'ios')",
            (cid, time.time() - 10, time.time()),
        )
        res = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={"client_id": cid},
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "order_not_found")

    def test_12_apk_ticket_requires_android_platform(self):
        """POST /api/apk/download-ticket with ios completed order returns 403 platform_mismatch."""
        cid = "completed-ios-for-apk-check"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, completed_at, user_id, platform) "
            "VALUES (?, 'ios_done', 'completed', ?, ?, 1, 'ios')",
            (cid, time.time() - 10, time.time()),
        )
        res = self.client.post(
            "/api/apk/download-ticket",
            headers=self.headers_user1,
            json={"client_id": cid},
        )
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "platform_mismatch")

    def test_13_cross_artifact_ticket_claim_prevention(self):
        """A mobileconfig ticket cannot be claimed for APK, and vice versa."""
        # 1. Create valid mobileconfig ticket
        cid_ios = "valid-ios-comp"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, completed_at, user_id, platform) "
            "VALUES (?, 'ios_ticket', 'completed', ?, ?, 1, 'ios')",
            (cid_ios, time.time() - 10, time.time()),
        )
        res_mc = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={"client_id": cid_ios},
        )
        self.assertEqual(res_mc.status_code, 200)
        mc_url = res_mc.get_json()["download_url"]
        mc_raw_ticket = mc_url.split("ticket=")[1]

        # Try to use this mobileconfig ticket at /api/apk
        cross_apk_res = self.client.get(f"/api/apk?ticket={mc_raw_ticket}")
        self.assertEqual(cross_apk_res.status_code, 403)
        self.assertEqual(cross_apk_res.get_json()["error"], "invalid_ticket")

        # 2. Create valid APK ticket
        cid_android = "valid-android-comp"
        now = time.time()
        conn = db.get_conn()
        act_cursor = conn.execute(
            """INSERT INTO activation_orders
               (user_id, plan_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot,
                price_vnd_snapshot, price_coin_snapshot, payment_method, platform, locket_username,
                fulfillment_mode_snapshot, status, queue_client_id, created_at, updated_at)
               VALUES (1, NULL, 'APK entitlement test', 'apk-test', 30, 10000, 10,
                       'coin', 'android', '', 'apk_download', 'completed', ?, ?, ?)""",
            (cid_android, now - 10, now),
        )
        conn.execute(
            """INSERT INTO queue_requests
               (client_id, username, status, added_at, completed_at, user_id, platform, activation_order_id)
               VALUES (?, 'android_ticket', 'completed', ?, ?, 1, 'android', ?)""",
            (cid_android, now - 10, now, act_cursor.lastrowid),
        )
        res_apk = self.client.post(
            "/api/apk/download-ticket",
            headers=self.headers_user1,
            json={"client_id": cid_android},
        )
        self.assertEqual(res_apk.status_code, 200)
        apk_url = res_apk.get_json()["download_url"]
        apk_raw_ticket = apk_url.split("ticket=")[1]

        # Try to use this APK ticket at /api/mobileconfig
        cross_mc_res = self.client.get(f"/api/mobileconfig?ticket={apk_raw_ticket}")
        self.assertEqual(cross_mc_res.status_code, 403)
        self.assertEqual(cross_mc_res.get_json()["error"], "invalid_ticket")

    def test_14_site_settings_public_dns(self):
        """GET /api/site-settings returns dynamic DNS config without leaking NEXTDNS_KEY."""
        res = self.client.get("/api/site-settings")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("dns", data)
        self.assertEqual(data["nextdns_profile"], "customprof123")
        self.assertEqual(data["nextdns_hostname"], "customprof123.dns.nextdns.io")
        self.assertIn("customprof123", data["nextdns_apple_url"])

        # Check that no secrets or API keys are present
        res_str = json.dumps(data)
        self.assertNotIn("NEXTDNS_KEY", res_str)
        self.assertNotIn("ef6092ba7798eaa58cb0cc06752d4c5acb237008", res_str)

    def test_15_ticket_single_use_atomicity(self):
        """Claiming a ticket marks it as used/claimed and prevents subsequent claims."""
        cid_ios = "atomic-ios-comp"
        db.get_conn().execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at, completed_at, user_id, platform) "
            "VALUES (?, 'atomic_ios', 'completed', ?, ?, 1, 'ios')",
            (cid_ios, time.time() - 10, time.time()),
        )
        res = self.client.post(
            "/api/mobileconfig/download-ticket",
            headers=self.headers_user1,
            json={"client_id": cid_ios},
        )
        self.assertEqual(res.status_code, 200)
        url = res.get_json()["download_url"]

        # First claim -> 200 OK
        claim1 = self.client.get(url)
        self.assertEqual(claim1.status_code, 200)
        claim1.close()

        # Second claim with SAME ticket -> 403 invalid_ticket
        claim2 = self.client.get(url)
        self.assertEqual(claim2.status_code, 403)
        self.assertEqual(claim2.get_json()["error"], "invalid_ticket")
        claim2.close()


if __name__ == "__main__":
    unittest.main()
