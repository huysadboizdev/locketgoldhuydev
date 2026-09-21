"""Migration test: a real pre-LunaKey schema (extracted from git HEAD) with
representative legacy data must upgrade in place without data loss or backfill.

The fixture ``tests/fixtures/pre_lunakey_schema.sql`` is the exact ``SCHEMA``
string from ``git show HEAD:backend/locket/db.py`` (before any LunaKey table or
column existed). The test does NOT create a fresh new-schema DB and re-run
``init``; it builds the old shape, seeds data, then runs the current migration.
"""

import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["LOCKET_DB"] = temp_db_path
os.environ["FLASK_SECRET_KEY"] = "lk-migration-flask-secret-123456789"
os.environ["JWT_SECRET"] = "lk-migration-jwt-secret-1234567890"
os.environ["REFRESH_TOKEN_PEPPER"] = "lk-migration-pepper-1234567890"
os.environ["ADMIN_EMAIL"] = "mig-admin@example.com"
os.environ["ADMIN_USERNAME"] = "mig_admin"
os.environ["ADMIN_PASSWORD"] = "mig-admin-password-12345"
os.environ["LUNAKEY_API_KEY"] = "lk-migration-key-not-real"
os.environ["LUNAKEY_ENABLED"] = "1"
os.environ["LUNAKEY_WORKER_ENABLED"] = "0"
os.environ["TELEGRAM_NOTIFICATIONS_ENABLED"] = "0"

backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from locket import db, lunakey_service  # noqa: E402
from locket.providers import lunakey  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pre_lunakey_schema.sql")


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._text = json.dumps(body) if isinstance(body, (dict, list)) else (body or "")

    @property
    def text(self):
        return self._text

    def json(self):
        return json.loads(self._text)


class FakeTransport:
    def __init__(self):
        self.responses = []
        self.calls = []

    def queue(self, status_code, body):
        self.responses.append(FakeResponse(status_code, body))
        return self

    def __call__(self, method, url, *, headers, json_body, timeout):
        self.calls.append({"url": url, "json": json_body})
        if not self.responses:
            raise AssertionError("FakeTransport has no queued response")
        nxt = self.responses.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


def activate_ok(request_id):
    return {
        "success": True, "code": 200, "message": "ok",
        "order_code": "LOK-MIG-1", "request_id": request_id,
        "price_deducted": 39000, "remaining_balance": 100000,
    }


class MigrationTests(unittest.TestCase):
    def setUp(self):
        db.close_conn()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(temp_db_path + suffix)
            except OSError:
                pass

        conn = sqlite3.connect(temp_db_path)
        conn.row_factory = sqlite3.Row
        with open(FIXTURE, encoding="utf-8") as handle:
            conn.executescript(handle.read())

        now = time.time()
        conn.execute(
            "INSERT INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (1, 'legacy@test.com', 'legacyuser', 'Legacy User', 'hash', 1, ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (1, 12345, ?)", (now,)
        )
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, type, amount_coin, balance_before, balance_after, "
            "reference_type, reference_id, description, idempotency_key, created_at) "
            "VALUES (1, 'topup', 12345, 0, 12345, 'payment_order', '100', 'Nạp Coin cũ', 'legacy_topup', ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO plans (id, name, slug, duration_days, price_vnd, product_id, supported_platforms, "
            "ios_fulfillment_mode, android_fulfillment_mode, is_active, created_at, updated_at) "
            "VALUES (10, 'Legacy Plan', 'legacy-plan', 30, 10000, 'legacy-product', 'ios', "
            "'auto_activation', 'disabled', 1, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO payment_orders (id, payment_code, transfer_code, user_id, purpose, plan_id, amount_vnd, "
            "coin_amount, provider, status, qr_payload, expires_at, created_at, updated_at) "
            "VALUES (100, 'PAY_LEGACY', 'LOCKETGOLDHUYDEV999', 1, 'plan_purchase', 10, 10000, 10, 'vietqr', "
            "'pending', 'qr', ?, ?, ?)",
            (now + 600, now, now),
        )
        conn.execute(
            "INSERT INTO activation_orders (id, user_id, plan_id, plan_name_snapshot, product_id_snapshot, "
            "duration_days_snapshot, price_vnd_snapshot, price_coin_snapshot, payment_method, payment_order_id, "
            "platform, locket_username, fulfillment_mode_snapshot, status, created_at, updated_at, "
            "original_price_vnd_snapshot, original_price_coin_snapshot) "
            "VALUES (50, 1, 10, 'Legacy Plan', 'legacy-product', 30, 10000, 10, 'qr', 100, 'ios', 'legacyuser', "
            "'auto_activation', 'awaiting_payment', ?, ?, 10000, 10)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO activation_orders (id, user_id, plan_id, plan_name_snapshot, product_id_snapshot, "
            "duration_days_snapshot, price_vnd_snapshot, price_coin_snapshot, payment_method, "
            "platform, locket_username, fulfillment_mode_snapshot, status, created_at, updated_at, "
            "original_price_vnd_snapshot, original_price_coin_snapshot) "
            "VALUES (51, 1, 10, 'Legacy Plan', 'legacy-product', 30, 10000, 10, 'coin', 'ios', 'oldcoin', "
            "'auto_activation', 'completed', ?, ?, 10000, 10)",
            (now, now),
        )
        conn.commit()
        conn.close()
        db.init(force=True)

    def tearDown(self):
        db.close_conn()

    def test_migration_preserves_legacy_data_and_defaults(self):
        conn = db.get_conn()
        self.assertEqual(conn.execute("SELECT balance_coin FROM wallets WHERE user_id=1").fetchone()[0], 12345)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM wallet_transactions WHERE user_id=1").fetchone()[0], 1
        )
        order = conn.execute("SELECT * FROM activation_orders WHERE id=51").fetchone()
        self.assertEqual(order["status"], "completed")
        self.assertEqual(order["price_vnd_snapshot"], 10000)
        self.assertEqual(order["price_coin_snapshot"], 10)
        # Legacy rows keep the default provider and get no backfilled provider data.
        self.assertEqual(order["activation_provider_snapshot"], "legacy_locket")
        self.assertIsNone(order["request_fingerprint"])
        self.assertIsNone(order["provider_request_id"])
        plan = conn.execute("SELECT * FROM plans WHERE id=10").fetchone()
        self.assertEqual(plan["activation_provider"], "legacy_locket")
        self.assertEqual(plan["allow_existing_gold"], 0)
        # No provider job is fabricated for legacy orders.
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM provider_jobs").fetchone()[0], 0
        )

    def test_migration_adds_provider_schema_and_keeps_constraints(self):
        conn = db.get_conn()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("provider_jobs", tables)
        self.assertIn("provider_lookups", tables)
        order_cols = {r[1] for r in conn.execute("PRAGMA table_info(activation_orders)")}
        for col in ("activation_provider_snapshot", "provider_uid", "provider_request_id",
                    "warranty_started_at", "warranty_ends_at", "request_fingerprint"):
            self.assertIn(col, order_cols)
        job_cols = {r[1] for r in conn.execute("PRAGMA table_info(provider_jobs)")}
        for col in ("first_sent_at", "replay_deadline", "last_outcome"):
            self.assertIn(col, job_cols)
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        for idx in ("idx_plans_provider", "idx_act_orders_provider", "idx_act_orders_provider_uid",
                    "idx_provider_jobs_claim"):
            self.assertIn(idx, indexes)
        # Legacy CHECK constraint still enforced.
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE activation_orders SET status='provider_pending' WHERE id=51")
        # FK still enforced.
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (999, 1, 1)"
            )

    def test_migration_is_idempotent_and_lunakey_purchase_works_afterwards(self):
        # Re-run migration: must not fail or duplicate anything.
        db.init(force=True)
        db.init(force=True)
        conn = db.get_conn()
        self.assertEqual(conn.execute("SELECT balance_coin FROM wallets WHERE user_id=1").fetchone()[0], 12345)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM activation_orders WHERE id=51").fetchone()[0], 1)

        now = time.time()
        conn.execute(
            "INSERT INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
            "VALUES (2, 'new@test.com', 'newbuyer', 'New Buyer', 'hash', 1, ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (2, 100, ?)", (now,)
        )
        conn.commit()
        plan_id = db.create_plan(
            name="LunaKey 1y", slug="lk-mig-1y", duration_days=365, price_vnd=50000,
            supported_platforms="ios", ios_fulfillment_mode="auto_activation",
            android_fulfillment_mode="disabled", activation_provider="lunakey",
            provider_category="yearly", warranty_months=0, is_active=1,
        )
        status, res = db.purchase_plan_with_coin_atomic(
            user_id=2, plan_id=plan_id, platform="ios", fulfillment_mode="auto_activation",
            locket_username="miguser", idempotency_key=f"mig-{uuid.uuid4().hex}",
            provider="lunakey", provider_category="yearly", warranty_months=0,
            provider_uid="uid-mig", provider_username="miguser",
            provider_profile_json=json.dumps({"username": "miguser", "uid": "uid-mig"}),
        )
        self.assertEqual(status, "ok", res)
        order = res["order"]
        self.assertEqual(order["activation_provider_snapshot"], "lunakey")
        self.assertEqual(order["provider_uid"], "uid-mig")
        job = lunakey_service.ensure_provider_job_for_order(order["id"])
        self.assertIsNotNone(job)

        ft = FakeTransport().queue(200, activate_ok(job["provider_request_id"]))
        from locket.provider_worker import ProviderWorker

        worker = ProviderWorker(
            client_factory=lambda: lunakey.LunaKeyClient(transport=ft)
        )
        db.get_conn().execute(
            "UPDATE provider_jobs SET status='leased', lease_owner='mig-worker', lease_expires_at=?, "
            "attempt_count=1, first_sent_at=? WHERE id=?",
            (time.time() + 60, time.time(), job["id"]),
        )
        db.get_conn().commit()
        worker._process(db.get_provider_job_by_id(job["id"]), "mig-worker")
        self.assertEqual(db.get_activation_order_by_id(order["id"])["status"], "completed")
        self.assertEqual(db.get_provider_job_by_id(job["id"])["status"], "succeeded")


    def test_migration_adds_replay_fields_to_lunakey_era_db(self):
        """A DB that already had LunaKey provider_jobs but NOT the replay fields
        must gain them without backfilling a stale outcome onto an in-flight job."""
        import tempfile as _tf

        fd, path = _tf.mkstemp(suffix=".db")
        os.close(fd)
        previous = os.environ["LOCKET_DB"]
        try:
            db.close_conn()
            os.environ["LOCKET_DB"] = path
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            with open(FIXTURE, encoding="utf-8") as handle:
                conn.executescript(handle.read())
            # LunaKey-era outbox table WITHOUT first_sent_at/replay_deadline/last_outcome.
            conn.executescript(
                """
                CREATE TABLE provider_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL UNIQUE,
                    provider TEXT NOT NULL,
                    provider_request_id TEXT NOT NULL UNIQUE,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 5,
                    next_attempt_at REAL, lease_owner TEXT, lease_expires_at REAL,
                    last_error_code TEXT, last_error_msg TEXT, result_json TEXT,
                    provider_order_code TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    completed_at REAL
                );
                CREATE TABLE provider_lookups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT NOT NULL UNIQUE,
                    provider TEXT NOT NULL, user_id INTEGER NOT NULL, plan_id INTEGER NOT NULL,
                    username TEXT NOT NULL, uid TEXT, profile_json TEXT,
                    created_at REAL NOT NULL, expires_at REAL NOT NULL, used_at REAL
                );
                """
            )
            now = time.time()
            conn.execute(
                "INSERT INTO users (id, email, username, display_name, password_hash, is_active, created_at) "
                "VALUES (1, 'era@test.com', 'erauser', 'Era User', 'hash', 1, ?)",
                (now,),
            )
            conn.execute(
                "INSERT INTO plans (id, name, slug, duration_days, price_vnd, product_id, supported_platforms, "
                "is_active, created_at, updated_at) VALUES (10, 'Era', 'era-plan', 30, 10000, 'p', 'ios', 1, ?, ?)",
                (now, now),
            )
            conn.execute(
                "INSERT INTO activation_orders (id, user_id, plan_id, plan_name_snapshot, product_id_snapshot, "
                "duration_days_snapshot, price_vnd_snapshot, price_coin_snapshot, payment_method, platform, "
                "locket_username, fulfillment_mode_snapshot, status, created_at, updated_at) "
                "VALUES (60, 1, 10, 'Era', 'p', 30, 10000, 10, 'coin', 'ios', 'erauser', "
                "'auto_activation', 'paid', ?, ?)",
                (now, now),
            )
            conn.execute(
                "INSERT INTO provider_jobs (order_id, provider, provider_request_id, payload_hash, payload_json, "
                "status, attempt_count, created_at, updated_at) "
                "VALUES (60, 'lunakey', 'req-era', 'h', '{}', 'awaiting_reconciliation', 1, ?, ?)",
                (now, now),
            )
            conn.commit()
            conn.close()

            db.init(force=True)

            c = db.get_conn()
            job_cols = {r[1] for r in c.execute("PRAGMA table_info(provider_jobs)")}
            for col in ("first_sent_at", "replay_deadline", "last_outcome"):
                self.assertIn(col, job_cols)
            row = c.execute(
                "SELECT * FROM provider_jobs WHERE provider_request_id='req-era'"
            ).fetchone()
            self.assertEqual(row["status"], "awaiting_reconciliation")
            # No backfill of an uncertain history into a definite outcome.
            self.assertIsNone(row["last_outcome"])
            self.assertIsNone(row["first_sent_at"])
            self.assertIsNone(row["replay_deadline"])
        finally:
            db.close_conn()
            os.environ["LOCKET_DB"] = previous
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.remove(path + suffix)
                except OSError:
                    pass


def _cleanup_temp_db():
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(temp_db_path + suffix)
        except OSError:
            pass


import atexit  # noqa: E402

atexit.register(_cleanup_temp_db)


if __name__ == "__main__":
    unittest.main(verbosity=2)
