"""Comprehensive Contract and Production Hardening Test Suite.

Covers:
1. SQLite trigger enforcement on users.role (raw SQL insert/update rejection).
2. Atomic wallet adjustment with rollback guarantee.
3. Review pinning and priority ordering + moderation API.
4. Strict token and secret redaction.
5. Maintenance mode enforcement on register, login, and admin API (allow_admin flag).
6. Canonical list envelope and alias endpoints compliance.
"""

import json
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch


class ContractAndHardeningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["BEHIND_HTTPS"] = "0"
        os.environ["JWT_SECRET"] = "test-jwt-secret-hardening-test-998877"
        os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper-hardening-test-112233"
        os.environ["ADMIN_EMAIL"] = "admin@example.com"
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"
        os.environ["ADMIN_DISPLAY_NAME"] = "Administrator"
        os.environ["ADMIN_ALLOW_GOOGLE_LOGIN"] = "0"

        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.db_fd)
        os.environ["LOCKET_DB"] = cls.db_path

        from locket import create_app, db
        db.close_conn()
        db._initialized = False

        cls.app = create_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            from locket.admin_provision import provision_admin_user
            provision_admin_user()

    @classmethod
    def tearDownClass(cls):
        from locket import db
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
        os.environ["ADMIN_EMAIL"] = "admin@example.com"
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "admin-secret-password-1234"
        os.environ["ADMIN_DISPLAY_NAME"] = "Administrator"
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def get_csrf(self):
        res = self.client.get("/api/auth/csrf")
        return res.get_json().get("csrf_token")

    def get_admin_token(self):
        from locket import db
        from locket.token_auth import create_access_token, create_token_family
        admin = db.get_user_by_email("admin@example.com")
        if not admin:
            from locket.admin_provision import provision_admin_user
            provision_admin_user()
            admin = db.get_user_by_email("admin@example.com")
        family_id, _, _ = create_token_family(admin["id"])
        return create_access_token(admin["id"], family_id), admin

    # 1. SQLite Trigger Role Check
    def test_users_role_trigger_rejection(self):
        from locket import db
        conn = db.get_conn()
        cur = conn.cursor()
        now = time.time()

        # Valid insert works
        cur.execute(
            "INSERT INTO users (email, username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("valid_user@test.com", "valid_user_trg", "Valid User", "hash123", "user", now),
        )
        conn.commit()

        # Invalid insert with role='superadmin' must be aborted by trigger
        with self.assertRaises(sqlite3.IntegrityError):
            cur.execute(
                "INSERT INTO users (email, username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("invalid_role@test.com", "invalid_role_trg", "Invalid Role", "hash123", "superadmin", now),
            )
            conn.commit()

        # Invalid update with role='manager' must be aborted by trigger
        with self.assertRaises(sqlite3.IntegrityError):
            cur.execute(
                "UPDATE users SET role = ? WHERE username = ?",
                ("manager", "valid_user_trg"),
            )
            conn.commit()

        # Role remains 'user'
        u = db.get_user_by_username("valid_user_trg")
        self.assertEqual(u["role"], "user")

    # 2. Atomic Wallet Adjustment Rollback
    def test_atomic_wallet_adjustment_rollback(self):
        from locket import db
        # Create a test user with 100 coins
        u_id = db.create_user(
            email="wallet_atomic@test.com",
            username="wallet_atomic",
            password_hash="pw123",
            display_name="Wallet User",
        )
        db.apply_wallet_transaction(u_id, "topup", 100, description="Initial balance")

        admin_token, admin = self.get_admin_token()

        # Test adjusting below zero returns insufficient_balance status and does not change balance
        status, err = db.admin_adjust_user_wallet_atomic(
            user_id=u_id,
            amount_coin=-150,
            reason="Overdraft attempt",
            admin_user_id=admin["id"],
            ip_address="127.0.0.1",
        )
        self.assertEqual(status, "insufficient_balance")

        bal = db.get_wallet_balance(u_id)
        self.assertEqual(bal, 100)

        # Successful atomic adjustment
        status, res = db.admin_adjust_user_wallet_atomic(
            user_id=u_id,
            amount_coin=50,
            reason="Bonus reward",
            admin_user_id=admin["id"],
            ip_address="127.0.0.1",
        )
        self.assertEqual(status, "ok")
        self.assertEqual(res["balance_coin"], 150)
        self.assertEqual(db.get_wallet_balance(u_id), 150)

    # 3. Legacy pinned ordering remains readable; HTTP moderation is retired.
    def test_review_legacy_pin_priority_and_retired_moderation(self):
        from locket import db
        u1_id = db.create_user(email="rev1@test.com", username="revuser1", password_hash="p", display_name="R1")
        u2_id = db.create_user(email="rev2@test.com", username="revuser2", password_hash="p", display_name="R2")
        u3_id = db.create_user(email="rev3@test.com", username="revuser3", password_hash="p", display_name="R3")

        r1_id = db.create_review(u1_id, 5, "Normal review 1")
        r2_id = db.create_review(u2_id, 5, "Normal review 2")
        r3_id = db.create_review(u3_id, 5, "Pinned review high priority")

        admin_token, admin = self.get_admin_token()
        csrf = self.get_csrf()

        # Moderate r1 (approved, not pinned)
        db.update_review_status_admin(r1_id, "approved", is_pinned=0, sort_priority=0)
        # Moderate r2 (approved, not pinned)
        db.update_review_status_admin(r2_id, "approved", is_pinned=0, sort_priority=10)
        # The former HTTP moderation alias is retired for auto-published reviews.
        res = self.client.post(
            f"/api/admin/reviews/{r3_id}/moderate",
            headers={"Authorization": f"Bearer {admin_token}", "X-CSRF-Token": csrf},
            json={
                "status": "approved",
                "is_pinned": True,
                "sort_priority": 50,
                "staff_note": "Verified customer with video proof",
            },
        )
        self.assertEqual(res.status_code, 410)
        self.assertEqual(res.get_json()["error"], "review_moderation_disabled")

        # Preserve old pinned data ordering for backwards-compatible reads.
        db.update_review_status_admin(
            r3_id,
            "approved",
            is_pinned=1,
            sort_priority=50,
            staff_note="Verified customer with video proof",
        )

        # Fetch public approved reviews -> pinned review MUST come first
        resp = db.get_approved_reviews()
        approved = resp["reviews"]
        self.assertGreaterEqual(len(approved), 3)
        self.assertEqual(approved[0]["id"], r3_id)
        self.assertEqual(approved[0]["is_pinned"], 1)
        self.assertEqual(approved[0]["sort_priority"], 50)

    # 4. Strict Token and Secret Redaction
    def test_token_and_secret_redaction(self):
        from locket import db

        admin_token, _ = self.get_admin_token()

        raw_secret = f"TOP_SECRET_RECEIPT_{time.time_ns()}"
        db.get_conn().execute(
            "INSERT INTO tokens (payload, added_at) VALUES (?, ?)",
            (json.dumps({"receipt": raw_secret, "product_identifier": "test.product"}), time.time()),
        )

        res_tokens = self.client.get(
            "/api/admin/tokens",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res_tokens.status_code, 200)
        tokens_json = json.dumps(res_tokens.get_json())
        self.assertNotIn(raw_secret, tokens_json)
        self.assertNotIn("fetch_token", tokens_json)
        self.assertNotIn("password_hash", tokens_json)
        self.assertNotIn("admin-secret-password-1234", tokens_json)

        with self.client.session_transaction() as session_data:
            session_data["admin"] = True
        legacy_tokens = self.client.get("/admin/api/tokens")
        self.assertEqual(legacy_tokens.status_code, 200)
        self.assertNotIn(raw_secret, json.dumps(legacy_tokens.get_json()))

        res_logs = self.client.get(
            "/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res_logs.status_code, 200)
        logs_json = json.dumps(res_logs.get_json())
        self.assertNotIn("password", logs_json.lower().replace("password_hash", ""))
        self.assertNotIn("admin-secret-password-1234", logs_json)

        with patch("locket.admin_api.proxy_pool.list_all", return_value=[{
            "id": 1,
            "url": "http://proxy-user:proxy-password@example.test:8080",
            "enabled": True,
        }]):
            proxy_response = self.client.get(
                "/api/admin/proxies",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        proxy_json = json.dumps(proxy_response.get_json())
        self.assertNotIn("proxy-password", proxy_json)
        self.assertIn("***", proxy_json)

    # 5. Maintenance Mode Enforcement
    def test_maintenance_mode_behavior(self):
        from locket import site_settings
        csrf = self.get_csrf()
        admin_token, _ = self.get_admin_token()

        # Case A: Maintenance ON, allow_admin = FALSE
        site_settings.set_maintenance({"enabled": True, "allow_admin": False, "message": "Total lockdown"})
        try:
            # Public register returns 503
            res_reg = self.client.post(
                "/api/auth/register",
                headers={"X-CSRF-Token": csrf},
                json={"email": "maint_block@test.com", "username": "maintblock", "password": "Password12345!"},
            )
            self.assertEqual(res_reg.status_code, 503)

            # Public login returns 200 (never locked out)
            res_log = self.client.post(
                "/api/auth/login",
                headers={"X-CSRF-Token": csrf},
                json={"identifier": "admin", "password": "admin-secret-password-1234"},
            )
            self.assertEqual(res_log.status_code, 200)

            # Admin API returns 503 when allow_admin=False
            res_admin = self.client.get(
                "/api/admin/overview",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(res_admin.status_code, 503)

            # Case B: Maintenance ON, allow_admin = TRUE
            site_settings.set_maintenance({"enabled": True, "allow_admin": True, "message": "Admin only"})

            # Public register still returns 503
            res_reg2 = self.client.post(
                "/api/auth/register",
                headers={"X-CSRF-Token": csrf},
                json={"email": "maint_block2@test.com", "username": "maintblock2", "password": "Password12345!"},
            )
            self.assertEqual(res_reg2.status_code, 503)

            # Admin API succeeds with 200
            res_admin2 = self.client.get(
                "/api/admin/overview",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(res_admin2.status_code, 200)
            self.assertTrue(res_admin2.get_json()["success"])
        finally:
            site_settings.set_maintenance({"enabled": False})

    # 6. Canonical List Envelope and Aliases
    def test_canonical_list_envelope_and_aliases(self):
        from locket import db
        admin_token, admin = self.get_admin_token()
        csrf = self.get_csrf()

        # Check /api/admin/users
        res_u = self.client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(res_u.status_code, 200)
        data_u = res_u.get_json()
        self.assertTrue(data_u["success"])
        self.assertIn("items", data_u)
        self.assertIn("pagination", data_u)
        self.assertIn("total", data_u["pagination"])
        self.assertIn("limit", data_u["pagination"])
        self.assertIn("page", data_u["pagination"])

        # Check /api/admin/overview flat cards
        res_ov = self.client.get("/api/admin/overview", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(res_ov.status_code, 200)
        data_ov = res_ov.get_json()
        self.assertTrue(data_ov["success"])
        self.assertIn("paid_revenue_vnd", data_ov["cards"])
        self.assertIn("completed_orders", data_ov["cards"])
        self.assertIn("series", data_ov)

        # Check wallet adjust alias /wallet/adjust with delta_coin
        dedicated_uid = db.create_user(email="dedi_wallet@test.com", username="dediwallet", password_hash="p", display_name="Dedi")
        db.apply_wallet_transaction(dedicated_uid, "topup", 50, description="Dedi initial")
        res_adj = self.client.post(
            f"/api/admin/users/{dedicated_uid}/wallet/adjust",
            headers={"Authorization": f"Bearer {admin_token}", "X-CSRF-Token": csrf},
            json={"delta_coin": 25, "reason": "Alias test adjustment"},
        )
        self.assertEqual(res_adj.status_code, 200)
        self.assertTrue(res_adj.get_json()["success"])
        self.assertEqual(res_adj.get_json()["balance_coin"], 75)

    def test_maintenance_lock_has_authenticated_recovery_path(self):
        from locket import site_settings

        admin_token, _ = self.get_admin_token()
        csrf = self.get_csrf()
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "X-CSRF-Token": csrf,
        }
        site_settings.set_maintenance({
            "enabled": True,
            "allow_admin": False,
            "message": "Recovery test",
        })
        try:
            blocked = self.client.get(
                "/api/admin/overview",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(blocked.status_code, 503)

            settings_response = self.client.get(
                "/api/admin/site-settings",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(settings_response.status_code, 200)

            recovered = self.client.post(
                "/api/admin/site-settings",
                headers=headers,
                json={"maintenance": {"enabled": False, "allow_admin": False}},
            )
            self.assertEqual(recovered.status_code, 200)
            self.assertFalse(recovered.get_json()["settings"]["maintenance"]["enabled"])
        finally:
            site_settings.set_maintenance({"enabled": False, "allow_admin": True})

    def test_strict_boolean_and_pagination_contract(self):
        from locket import db

        user_id = db.create_user(
            email=f"strict_bool_{time.time_ns()}@test.com",
            username=f"strict_bool_{time.time_ns()}",
            password_hash="p",
            display_name="Strict Bool",
        )
        admin_token, _ = self.get_admin_token()
        csrf = self.get_csrf()
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "X-CSRF-Token": csrf,
        }

        invalid = self.client.post(
            f"/api/admin/users/{user_id}/status",
            headers=headers,
            json={"is_active": "false"},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["error"], "invalid_boolean")
        self.assertTrue(bool(db.get_user_by_id(user_id)["is_active"]))

        listing = self.client.get(
            "/api/admin/users?limit=999&page=2",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(listing.status_code, 200)
        pagination = listing.get_json()["pagination"]
        self.assertEqual(pagination["limit"], 100)
        self.assertEqual(pagination["offset"], 100)

        empty = self.client.get(
            "/api/admin/users?q=definitely-no-user-with-this-value",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(empty.get_json()["pagination"]["pages"], 0)

    def test_plan_create_accepts_real_json_booleans(self):
        admin_token, _ = self.get_admin_token()
        csrf = self.get_csrf()
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "X-CSRF-Token": csrf,
        }
        suffix = time.time_ns()
        created = self.client.post(
            "/api/admin/plans",
            headers=headers,
            json={
                "name": "Boolean Contract Plan",
                "slug": f"boolean_contract_{suffix}",
                "product_id": f"boolean_contract_{suffix}",
                "duration_days": 365,
                "price_vnd": 50000,
                "price_coin": 50,
                "supported_platforms": "all",
                "features": ["Feature A"],
                "is_popular": False,
                "is_active": True,
                "sort_order": 0,
            },
        )
        self.assertEqual(created.status_code, 201)
        plan = created.get_json()["plan"]
        self.assertTrue(bool(plan["is_active"]))
        self.assertFalse(bool(plan["is_popular"]))

        rejected = self.client.post(
            "/api/admin/plans",
            headers=headers,
            json={
                "name": "Invalid Boolean Plan",
                "slug": f"invalid_boolean_{suffix}",
                "duration_days": 30,
                "price_vnd": 10000,
                "is_active": 1,
            },
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()["error"], "invalid_boolean")

    def test_payment_reject_api_and_atomic_audit_rollback(self):
        from locket import db

        user_id = db.create_user(
            email=f"payment_hardening_{time.time_ns()}@test.com",
            username=f"payment_hardening_{time.time_ns()}",
            password_hash="p",
            display_name="Payment Hardening",
        )
        admin_token, admin = self.get_admin_token()
        csrf = self.get_csrf()
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "X-CSRF-Token": csrf,
        }

        reject_id = db.create_payment_order(
            payment_code=f"REJECT_{time.time_ns()}",
            user_id=user_id,
            purpose="wallet_topup",
            amount_vnd=10000,
        )
        rejected = self.client.post(
            f"/api/admin/payments/{reject_id}/reject",
            headers=headers,
            json={"reason": "invalid transfer"},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(db.get_payment_order_by_id(reject_id)["status"], "cancelled")

        payment_id = db.create_payment_order(
            payment_code=f"ROLLBACK_{time.time_ns()}",
            user_id=user_id,
            purpose="wallet_topup",
            amount_vnd=20000,
        )
        balance_before = db.get_wallet_balance(user_id)
        audit_context = {
            "admin_user_id": admin["id"],
            "ip_address": "127.0.0.1",
            "user_agent": "hardening-test",
        }
        with patch("locket.db.record_admin_audit_log", side_effect=RuntimeError("audit unavailable")):
            status, _ = db.confirm_payment_order_tx(
                payment_id,
                f"BANK_{time.time_ns()}",
                audit_context=audit_context,
            )

        self.assertEqual(status, "error")
        self.assertEqual(db.get_payment_order_by_id(payment_id)["status"], "pending")
        self.assertEqual(db.get_wallet_balance(user_id), balance_before)

    def test_manual_confirm_recovers_expired_payment_once(self):
        from locket import db

        user_id = db.create_user(
            email=f"manual_payment_{time.time_ns()}@test.com",
            username=f"manual_payment_{time.time_ns()}",
            password_hash="p",
            display_name="Manual Payment",
        )
        payment_id = db.create_payment_order(
            payment_code=f"MANUAL_{time.time_ns()}",
            user_id=user_id,
            purpose="wallet_topup",
            amount_vnd=30000,
            expires_in=-1,
        )
        admin_token, _ = self.get_admin_token()
        csrf = self.get_csrf()
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "X-CSRF-Token": csrf,
        }
        balance_before = db.get_wallet_balance(user_id)

        automatic = self.client.post(
            f"/api/admin/payments/{payment_id}/confirm",
            headers=headers,
            json={},
        )
        self.assertEqual(automatic.status_code, 400)
        self.assertEqual(db.get_payment_order_by_id(payment_id)["status"], "expired")
        self.assertEqual(db.get_wallet_balance(user_id), balance_before)

        missing_reason = self.client.post(
            f"/api/admin/payments/{payment_id}/manual-confirm",
            headers=headers,
            json={},
        )
        self.assertEqual(missing_reason.status_code, 400)
        self.assertEqual(missing_reason.get_json()["error"], "manual_reason_required")

        manual = self.client.post(
            f"/api/admin/payments/{payment_id}/manual-confirm",
            headers=headers,
            json={"reason": "SePay unavailable; bank statement checked"},
        )
        self.assertEqual(manual.status_code, 200)
        self.assertTrue(manual.get_json()["manual"])
        self.assertEqual(db.get_payment_order_by_id(payment_id)["status"], "paid")
        self.assertEqual(db.get_wallet_balance(user_id), balance_before + 30)

        repeated = self.client.post(
            f"/api/admin/payments/{payment_id}/manual-confirm",
            headers=headers,
            json={"reason": "Second accidental click"},
        )
        self.assertEqual(repeated.status_code, 409)
        self.assertEqual(db.get_wallet_balance(user_id), balance_before + 30)

        logs = db.list_admin_audit_logs(
            action="payment_manual_confirm",
            limit=20,
            offset=0,
        )
        matching = [item for item in logs["items"] if item.get("entity_id") == str(payment_id)]
        self.assertEqual(len(matching), 1)
        self.assertTrue(matching[0]["after"]["manual_override"])


if __name__ == "__main__":
    unittest.main()
