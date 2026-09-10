import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "test-secret-gold-check-key-12345"
os.environ["JWT_SECRET"] = "test-jwt-secret-gold-check-12345678"
os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-secret-gold-check-123"
os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import create_app, db
from locket.locket_api import LocketAPI
from locket.token_auth import create_token_family, create_access_token
from locket.user_auth import reset_rate_limits
from werkzeug.security import generate_password_hash


def test_getSubscriber_parses_gold():
    api = LocketAPI(token="dummy")
    fake_resp = MagicMock()
    fake_resp.ok = True
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "subscriber": {"entitlements": {"Gold": {
            "product_identifier": "locket_199_1m",
            "expires_date": "2026-12-31T00:00:00Z"}}}
    }
    with patch("locket.locket_api._get_with_proxy", return_value=fake_resp):
        out = api.getSubscriber("UID28CHARS12345678901234567")
    assert out["subscriber"]["entitlements"]["Gold"]["product_identifier"] == "locket_199_1m"


def test_normalize_locket_username_strips_handle():
    assert db.normalize_locket_username("@TestUser ") == "testuser"


def test_normalize_locket_username_strips_link():
    assert db.normalize_locket_username("https://locket.cam/TestUser?x=1") == "testuser"


def test_normalize_locket_username_empty():
    assert db.normalize_locket_username("") == ""
    assert db.normalize_locket_username(None) == ""


UID_A = "A" * 28

GOLD_SUB = {
    "subscriber": {"entitlements": {"Gold": {
        "product_identifier": "locket_199_1m",
        "expires_date": "2026-12-31T00:00:00Z"}}}
}

NO_GOLD_SUB = {"subscriber": {"entitlements": {}}}


def _insert_activation_order(username, status="completed", user_id=1):
    conn = db.get_conn()
    now = time.time()
    cur = conn.execute(
        """INSERT INTO activation_orders
           (user_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot,
            price_vnd_snapshot, price_coin_snapshot, payment_method, platform,
            locket_username, status, created_at, updated_at)
           VALUES (?, 'Gold Plan', 'locket_199_1m', 30, 199000, 199, 'qr', 'ios', ?, ?, ?, ?)""",
        (user_id, username, status, now, now),
    )
    return cur.lastrowid


class GoldCheckTestCase(unittest.TestCase):
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
            "VALUES (1, 'golduser@test.com', 'golduser', 'Gold User', ?, 1, ?)",
            (generate_password_hash("password12345"), now),
        )
        cls.plan_id = db.create_plan(
            "Gold Precheck Plan", "gold-precheck-plan", price_vnd=199000,
            supported_platforms="all",
        )
        cls.app.rotator.size = lambda: 1

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
        conn = db.get_conn()
        conn.execute("DELETE FROM activation_orders")
        conn.execute("DELETE FROM queue_requests")
        csrf_res = self.client.get("/api/auth/csrf")
        self.assertEqual(csrf_res.status_code, 200)
        self.csrf_token = csrf_res.get_json()["csrf_token"]
        fam, _, _ = create_token_family(user_id=1)
        token = create_access_token(1, fam)
        self.headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": self.csrf_token,
        }

    def _mock_live(self, sub_result=None, side_effect=None, uid=UID_A):
        """Patch UID resolution + RevenueCat live check for the check-gold flow."""
        p1 = patch("locket.user_resolver.resolve_locket_uid", return_value=uid)
        p2 = patch.object(
            self.app.queue_manager, "call_round_robin",
            side_effect=Exception("no fallback"),
        )
        fake_api = MagicMock()
        if side_effect is not None:
            fake_api.getSubscriber.side_effect = side_effect
        else:
            fake_api.getSubscriber.return_value = sub_result
        p3 = patch.object(self.app.rotator, "list_ids", return_value=["slot1"])
        p4 = patch.object(self.app.rotator, "get", return_value=fake_api)
        for p in (p1, p2, p3, p4):
            p.start()
            self.addCleanup(p.stop)
        return fake_api

    # ---- POST /api/check-gold ----

    def test_check_gold_blocks_prior_completed_order(self):
        _insert_activation_order("testuser", status="completed")
        self._mock_live(sub_result=NO_GOLD_SUB, uid=None)
        res = self.client.post(
            "/api/check-gold", json={"username": "testuser"}, headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["already_registered"])
        self.assertEqual(data["order_status"], "completed")

    def test_check_gold_live_gold_blocked(self):
        self._mock_live(sub_result=GOLD_SUB)
        res = self.client.post(
            "/api/check-gold", json={"username": "newuser"}, headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["is_gold"])
        self.assertTrue(data["blocked"])
        self.assertEqual(data["check"], "live")

    def test_check_gold_timeout_fail_open_for_new_user(self):
        """New user + RevenueCat timeout → ALLOW purchase (fail-open)."""
        self._mock_live(side_effect=Exception("Gold check unavailable: timeout"))
        res = self.client.post(
            "/api/check-gold", json={"username": "newuser"}, headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["blocked"])
        self.assertEqual(data["check"], "timeout")

    def test_check_gold_allows_new_user(self):
        self._mock_live(sub_result=NO_GOLD_SUB)
        res = self.client.post(
            "/api/check-gold", json={"username": "brandnew"}, headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["is_gold"])
        self.assertFalse(data["already_registered"])
        self.assertFalse(data["blocked"])

    def test_check_gold_requires_username(self):
        res = self.client.post(
            "/api/check-gold", json={"username": ""}, headers=self.headers
        )
        self.assertEqual(res.status_code, 400)

    # ---- history helper ----

    def test_has_prior_activation_finds_completed_order(self):
        _insert_activation_order("HistoryUser", status="completed")
        found, order = db.has_prior_activation_for_locket_username("historyuser")
        self.assertTrue(found)
        self.assertEqual(order["status"], "completed")

    def test_has_prior_activation_finds_queue_request(self):
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO queue_requests (client_id, username, status, added_at) "
            "VALUES ('cid-gold-1', 'queueuser', 'waiting', ?)",
            (time.time(),),
        )
        found, info = db.has_prior_activation_for_locket_username("QueueUser")
        self.assertTrue(found)
        self.assertEqual(info["status"], "waiting")

    def test_has_prior_activation_empty_for_new_user(self):
        found, order = db.has_prior_activation_for_locket_username("never_seen_xyz")
        self.assertFalse(found)
        self.assertIsNone(order)

    # ---- 409 enforcement ----

    def test_restore_blocked_for_prior_order_409(self):
        _insert_activation_order("repeatbuyer", status="completed")
        self._mock_live(sub_result=NO_GOLD_SUB, uid=None)
        res = self.client.post(
            "/api/restore",
            json={"username": "repeatbuyer", "platform": "ios"},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "already_registered")

    def test_restore_blocked_for_live_gold_409(self):
        self._mock_live(sub_result=GOLD_SUB)
        res = self.client.post(
            "/api/restore",
            json={"username": "goldlive", "platform": "ios"},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "already_gold_live")

    def test_restore_timeout_fail_open_for_new_user(self):
        """New user + RevenueCat timeout → ALLOW restore (fail-open)."""
        self._mock_live(side_effect=Exception("Gold check unavailable: timeout"))
        res = self.client.post(
            "/api/restore",
            json={"username": "unknownlive", "platform": "ios"},
            headers=self.headers,
        )
        # ✅ Fail-open: new user with timeout should be allowed (queued or 503)
        self.assertIn(res.status_code, [200, 503])

    def test_plan_payment_blocked_for_prior_order_409(self):
        _insert_activation_order("planrepeat", status="paid")
        self._mock_live(sub_result=NO_GOLD_SUB, uid=None)
        res = self.client.post(
            "/api/payments/plan",
            json={"plan_id": self.plan_id, "platform": "ios",
                  "username": "planrepeat"},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "already_registered")

    def test_coin_order_blocked_for_live_gold_409(self):
        self._mock_live(sub_result=GOLD_SUB)
        res = self.client.post(
            "/api/orders/coin",
            json={"plan_id": self.plan_id, "platform": "ios",
                  "username": "coinlive"},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "already_gold_live")

    def test_check_gold_cache_hit_returns_cached_result(self):
        """Verify gold check cache stores and retrieves results correctly."""
        from locket.public.routes import _get_cached_gold_check, _set_cached_gold_check, _gold_check, _GOLD_CACHE
        _GOLD_CACHE.clear()

        username = f"cache_user_{int(time.time()*1000)}"
        self._mock_live(uid=None)  # Returns NO_GOLD_SUB for this user

        # Simulate what the endpoint does: compute result, cache it
        result = _gold_check(username)
        _set_cached_gold_check(username, result)

        # Verify cache was populated via internal function
        self.assertIn(username, _GOLD_CACHE)
        cached_ts, cached_result = _GOLD_CACHE[username]
        self.assertFalse(cached_result["is_gold"])

        # Verify cache retrieval works
        retrieved = _get_cached_gold_check(username)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["is_gold"], result["is_gold"])

        # Verify cache expires
        import time as _time
        old_ts = cached_ts
        _GOLD_CACHE[username] = (old_ts - 301, cached_result)  # expired
        expired = _get_cached_gold_check(username)
        self.assertIsNone(expired)  # should return None after expiry

    def test_check_gold_timeout_not_cached(self):
        """Timeout/error results should NOT be cached (fail-open for new user)."""
        from locket.public.routes import _GOLD_CACHE
        _GOLD_CACHE.clear()

        # Mock live gold check to raise an exception (timeout)
        def mock_subscriber(uid):
            raise Exception("Gold check unavailable: timeout")

        self._mock_live(side_effect=mock_subscriber)

        username = f"timeout_user_{int(time.time()*1000)}"
        res = self.client.post(
            "/api/check-gold",
            json={"username": username},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)  # ✅ fail-open for new user
        self.assertFalse(res.get_json()["blocked"])

        # Verify cache is empty for this username (timeout should NOT be cached)
        self.assertNotIn(username, _GOLD_CACHE)


if __name__ == "__main__":
    unittest.main()
