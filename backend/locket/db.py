"""SQLite-backed persistence for accounts, tokens, queue state, and recent log.

Single source of truth for state that previously lived in three JSON files
(accounts.json, tokens.json, queue_state.json). Connections are thread-local:
each worker thread and Flask request handler gets its own sqlite3 connection,
configured for WAL mode with a 5-second busy timeout. WAL allows many readers
to run alongside one writer; busy_timeout absorbs short write contention.

`init()` is idempotent — call it once on app startup. It creates schema if
absent and one-shot imports legacy JSON files into the DB, renaming them to
*.bak so subsequent restarts do not double-import.
"""

import json
import math
import os
import re
import sqlite3
import threading
import time
import uuid

def get_db_path():
    return os.environ.get("LOCKET_DB", "locket.db")


_local = threading.local()
_init_lock = threading.Lock()
_initialized = False
_initialized_paths = set()


def get_conn():
    """Return this thread's sqlite3 connection, creating it on first call or when db path changes."""
    current_path = os.path.abspath(get_db_path())
    conn = getattr(_local, "conn", None)
    conn_path = getattr(_local, "conn_path", None)
    if conn is not None and conn_path != current_path:
        try:
            conn.close()
        except Exception:
            pass
        conn = None
        _local.conn = None
        _local.conn_path = None
    if conn is None:
        conn = sqlite3.connect(current_path, isolation_level=None, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
        _local.conn_path = current_path
    return conn


def close_conn():
    """Close this thread's sqlite3 connection if open."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None
        _local.conn_path = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    slot_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    added_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_accounts_added_at ON accounts(added_at);

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    added_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    google_id TEXT,
    avatar_url TEXT,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    last_login_at REAL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

CREATE TABLE IF NOT EXISTS queue_requests (
    client_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('waiting','processing','completed','error')),
    result TEXT,
    error TEXT,
    added_at REAL NOT NULL,
    started_at REAL,
    completed_at REAL,
    slot_id TEXT,
    user_id INTEGER,
    platform TEXT CHECK (platform IN ('ios', 'android'))
);

CREATE INDEX IF NOT EXISTS idx_queue_status_added ON queue_requests(status, added_at);
CREATE INDEX IF NOT EXISTS idx_queue_completed_at ON queue_requests(completed_at);

CREATE TABLE IF NOT EXISTS processing_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    duration REAL NOT NULL,
    completed_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS recent_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT,
    username TEXT,
    slot_id TEXT,
    status TEXT,
    error TEXT,
    duration REAL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_recent_log_id ON recent_log(id);

CREATE TABLE IF NOT EXISTS site_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS proxies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    added_at REAL NOT NULL,
    last_ok_at REAL,
    last_err_at REAL,
    last_err TEXT
);

CREATE TABLE IF NOT EXISTS mobileconfig_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL CHECK (action IN ('upload','delete')),
    filename TEXT,
    size INTEGER,
    signed INTEGER,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mc_history_created ON mobileconfig_history(created_at DESC);

CREATE TABLE IF NOT EXISTS auth_sessions (
    family_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    last_used_at REAL,
    revoked_at REAL,
    revoke_reason TEXT,
    remember_me INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires ON auth_sessions(expires_at);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    parent_id TEXT,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    used_at REAL,
    revoked_at REAL,
    replaced_by TEXT,
    FOREIGN KEY (family_id) REFERENCES auth_sessions(family_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family ON refresh_tokens(family_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at);

CREATE TABLE IF NOT EXISTS download_tickets (
    ticket_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    client_id TEXT,
    artifact_type TEXT CHECK (artifact_type IN ('mobileconfig', 'apk')),
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    used_at REAL,
    claimed_at REAL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_download_tickets_expires ON download_tickets(expires_at);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    before_json TEXT,
    after_json TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_admin ON admin_audit_logs(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_action ON admin_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created ON admin_audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_entity ON admin_audit_logs(entity_type, entity_id);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'approved' CHECK (status IN ('pending', 'approved', 'rejected', 'hidden')),
    is_verified INTEGER NOT NULL DEFAULT 1 CHECK (is_verified IN (0, 1)),
    is_pinned INTEGER NOT NULL DEFAULT 0 CHECK (is_pinned IN (0, 1)),
    sort_priority INTEGER NOT NULL DEFAULT 0,
    staff_note TEXT,
    admin_note TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    approved_at REAL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_reviews_status_created ON reviews(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);


CREATE TABLE IF NOT EXISTS review_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    storage_name TEXT NOT NULL UNIQUE,
    original_filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'image/webp',
    width INTEGER,
    height INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_review_images_review_id ON review_images(review_id, sort_order ASC);
CREATE INDEX IF NOT EXISTS idx_review_images_storage ON review_images(storage_name);

CREATE TABLE IF NOT EXISTS creator_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    tiktok_handle TEXT NOT NULL UNIQUE COLLATE NOCASE,
    tiktok_url TEXT NOT NULL,
    screenshot_name TEXT NOT NULL UNIQUE,
    follower_count INTEGER CHECK (follower_count IS NULL OR follower_count >= 0),
    is_featured INTEGER NOT NULL DEFAULT 0 CHECK (is_featured IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    require_review INTEGER NOT NULL DEFAULT 0 CHECK (require_review IN (0, 1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_creator_profiles_public
    ON creator_profiles(is_active, is_featured DESC, sort_order ASC);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    short_description TEXT,
    duration_days INTEGER NOT NULL CHECK (duration_days > 0),
    price_vnd INTEGER NOT NULL CHECK (price_vnd > 0),
    product_id TEXT NOT NULL,
    features_json TEXT,
    supported_platforms TEXT NOT NULL DEFAULT 'all' CHECK (supported_platforms IN ('all', 'ios', 'android')),
    ios_fulfillment_mode TEXT NOT NULL DEFAULT 'auto_activation',
    android_fulfillment_mode TEXT NOT NULL DEFAULT 'disabled',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_popular INTEGER NOT NULL DEFAULT 0 CHECK (is_popular IN (0, 1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    inventory_status TEXT NOT NULL DEFAULT 'in_stock' CHECK (inventory_status IN ('in_stock', 'out_of_stock')),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plans_active_sort ON plans(is_active, sort_order ASC);
CREATE INDEX IF NOT EXISTS idx_plans_slug ON plans(slug);

CREATE TABLE IF NOT EXISTS wallets (
    user_id INTEGER PRIMARY KEY,
    balance_coin INTEGER NOT NULL DEFAULT 0 CHECK (balance_coin >= 0),
    updated_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('topup', 'purchase', 'refund', 'adjustment')),
    amount_coin INTEGER NOT NULL,
    balance_before INTEGER NOT NULL CHECK (balance_before >= 0),
    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
    reference_type TEXT,
    reference_id TEXT,
    description TEXT,
    idempotency_key TEXT UNIQUE,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_user_created ON wallet_transactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_idempotency ON wallet_transactions(idempotency_key);

CREATE TABLE IF NOT EXISTS payment_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_code TEXT NOT NULL UNIQUE,
    transfer_code TEXT,
    idempotency_hash TEXT,
    user_id INTEGER NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('wallet_topup', 'plan_purchase')),
    plan_id INTEGER,
    amount_vnd INTEGER NOT NULL CHECK (amount_vnd > 0),
    coin_amount INTEGER NOT NULL CHECK (coin_amount > 0),
    provider TEXT NOT NULL DEFAULT 'vietqr',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'expired', 'cancelled', 'underpaid', 'review_needed')),
    qr_payload TEXT,
    bank_transaction_id TEXT UNIQUE,
    idempotency_key TEXT UNIQUE,
    expires_at REAL NOT NULL,
    paid_at REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    original_price_vnd_snapshot INTEGER,
    discount_vnd_snapshot INTEGER NOT NULL DEFAULT 0,
    coupon_id INTEGER,
    coupon_code_snapshot TEXT,
    renewed_from_payment_id INTEGER UNIQUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL,
    FOREIGN KEY (renewed_from_payment_id) REFERENCES payment_orders(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_payment_orders_code ON payment_orders(payment_code);
CREATE INDEX IF NOT EXISTS idx_payment_orders_transfer ON payment_orders(transfer_code);
CREATE INDEX IF NOT EXISTS idx_payment_orders_user_status ON payment_orders(user_id, status);
CREATE INDEX IF NOT EXISTS idx_payment_orders_expires ON payment_orders(expires_at);

CREATE TABLE IF NOT EXISTS activation_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_id INTEGER,
    plan_name_snapshot TEXT NOT NULL,
    product_id_snapshot TEXT NOT NULL,
    duration_days_snapshot INTEGER NOT NULL,
    price_vnd_snapshot INTEGER NOT NULL,
    price_coin_snapshot INTEGER NOT NULL,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('coin', 'qr')),
    payment_order_id INTEGER,
    platform TEXT NOT NULL CHECK (platform IN ('ios', 'android')),
    locket_username TEXT NOT NULL,
    fulfillment_mode_snapshot TEXT NOT NULL DEFAULT 'auto_activation',
    contact_zalo TEXT,
    contact_facebook TEXT,
    admin_note TEXT,
    handled_by_admin_id INTEGER,
    handled_at REAL,
    download_accessed_at REAL,
    status TEXT NOT NULL CHECK (status IN ('awaiting_payment', 'paid', 'awaiting_queue', 'queued', 'processing', 'completed', 'failed', 'refunded', 'cancelled')),
    queue_client_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    original_price_vnd_snapshot INTEGER,
    original_price_coin_snapshot INTEGER,
    discount_vnd_snapshot INTEGER NOT NULL DEFAULT 0,
    discount_coin_snapshot INTEGER NOT NULL DEFAULT 0,
    coupon_id INTEGER,
    coupon_code_snapshot TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (payment_order_id) REFERENCES payment_orders(id) ON DELETE SET NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_act_orders_user_created ON activation_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_act_orders_status ON activation_orders(status);
CREATE INDEX IF NOT EXISTS idx_act_orders_client_id ON activation_orders(queue_client_id);

CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    normalized_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    discount_type TEXT NOT NULL CHECK (discount_type IN ('percent', 'fixed_vnd')),
    discount_value INTEGER NOT NULL CHECK (discount_value > 0),
    max_discount_vnd INTEGER CHECK (max_discount_vnd IS NULL OR max_discount_vnd >= 1000),
    min_order_vnd INTEGER NOT NULL DEFAULT 0 CHECK (min_order_vnd >= 0),
    usage_limit_total INTEGER CHECK (usage_limit_total IS NULL OR usage_limit_total > 0),
    usage_limit_per_user INTEGER CHECK (usage_limit_per_user IS NULL OR usage_limit_per_user > 0),
    starts_at REAL,
    ends_at REAL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_by_admin_id INTEGER,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (created_by_admin_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uidx_coupons_normalized_code ON coupons(normalized_code);
CREATE INDEX IF NOT EXISTS idx_coupons_active ON coupons(is_active);

CREATE TABLE IF NOT EXISTS coupon_plan_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE,
    UNIQUE (coupon_id, plan_id)
);
CREATE INDEX IF NOT EXISTS idx_coupon_plan_rules_coupon ON coupon_plan_rules(coupon_id);
CREATE INDEX IF NOT EXISTS idx_coupon_plan_rules_plan ON coupon_plan_rules(plan_id);

CREATE TABLE IF NOT EXISTS coupon_redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    payment_order_id INTEGER,
    activation_order_id INTEGER,
    status TEXT NOT NULL CHECK (status IN ('reserved', 'redeemed', 'released')),
    original_price_vnd INTEGER NOT NULL,
    discount_vnd INTEGER NOT NULL,
    final_price_vnd INTEGER NOT NULL,
    created_at REAL NOT NULL,
    redeemed_at REAL,
    released_at REAL,
    expires_at REAL,
    idempotency_key TEXT UNIQUE,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (payment_order_id) REFERENCES payment_orders(id) ON DELETE SET NULL,
    FOREIGN KEY (activation_order_id) REFERENCES activation_orders(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_coupon_status ON coupon_redemptions(coupon_id, status);
CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_user_coupon ON coupon_redemptions(user_id, coupon_id, status);
CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_pay ON coupon_redemptions(payment_order_id);
CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_act ON coupon_redemptions(activation_order_id);
CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_expires ON coupon_redemptions(status, expires_at);
"""


def init(force=False):
    global _initialized
    with _init_lock:
        current_path = os.path.abspath(get_db_path())
        if not force and _initialized and current_path in _initialized_paths:
            return
        conn = get_conn()
        conn.executescript(SCHEMA)

        # On startup, any rows still marked "processing" are leftovers from a
        # prior run that crashed or restarted. Reset them to waiting so a worker
        # can pick them up again.
        conn.execute(
            "UPDATE queue_requests SET status='waiting', started_at=NULL, slot_id=NULL "
            "WHERE status='processing'"
        )

        # Idempotent migration for existing database: add user_id to queue_requests
        cols = [
            r["name"] for r in conn.execute("PRAGMA table_info(queue_requests)").fetchall()
        ]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE queue_requests ADD COLUMN user_id INTEGER")
            print("db: added user_id column to queue_requests")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_user_id ON queue_requests(user_id)")

        # Idempotent migration for existing database: add platform, plan_id, activation_order_id to queue_requests
        if "platform" not in cols:
            conn.execute("ALTER TABLE queue_requests ADD COLUMN platform TEXT")
            print("db: added platform column to queue_requests")
        if "plan_id" not in cols:
            conn.execute("ALTER TABLE queue_requests ADD COLUMN plan_id INTEGER")
            print("db: added plan_id column to queue_requests")
        if "activation_order_id" not in cols:
            conn.execute("ALTER TABLE queue_requests ADD COLUMN activation_order_id INTEGER")
            print("db: added activation_order_id column to queue_requests")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_platform ON queue_requests(platform)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_act_order ON queue_requests(activation_order_id)")

        # One activation order must never be dispatched to more than one queue
        # request. Older databases may already contain duplicates from the
        # historical select-then-insert flow, so preserve the oldest linked row
        # and detach the remaining history rows before adding the constraint.
        duplicate_order_ids = conn.execute(
            """SELECT activation_order_id
               FROM queue_requests
               WHERE activation_order_id IS NOT NULL
               GROUP BY activation_order_id
               HAVING COUNT(*) > 1"""
        ).fetchall()
        for duplicate in duplicate_order_ids:
            activation_order_id = duplicate["activation_order_id"]
            linked_client = conn.execute(
                "SELECT queue_client_id FROM activation_orders WHERE id = ?",
                (activation_order_id,),
            ).fetchone()
            preferred_client_id = linked_client["queue_client_id"] if linked_client else None
            keep = None
            if preferred_client_id:
                keep = conn.execute(
                    """SELECT client_id FROM queue_requests
                       WHERE activation_order_id = ? AND client_id = ?""",
                    (activation_order_id, preferred_client_id),
                ).fetchone()
            if not keep:
                keep = conn.execute(
                    """SELECT client_id FROM queue_requests
                       WHERE activation_order_id = ?
                       ORDER BY added_at ASC, client_id ASC LIMIT 1""",
                    (activation_order_id,),
                ).fetchone()
            if keep:
                conn.execute(
                    """UPDATE queue_requests SET activation_order_id = NULL
                       WHERE activation_order_id = ? AND client_id != ?""",
                    (activation_order_id, keep["client_id"]),
                )
        conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS uq_queue_activation_order
               ON queue_requests(activation_order_id)
               WHERE activation_order_id IS NOT NULL"""
        )

        # Idempotent migration for existing database: download_tickets columns (client_id, artifact_type, claimed_at, activation_order_id)
        dt_cols = [
            r["name"] for r in conn.execute("PRAGMA table_info(download_tickets)").fetchall()
        ]
        if "client_id" not in dt_cols:
            conn.execute("ALTER TABLE download_tickets ADD COLUMN client_id TEXT")
            print("db: added client_id column to download_tickets")
        if "artifact_type" not in dt_cols:
            conn.execute("ALTER TABLE download_tickets ADD COLUMN artifact_type TEXT")
            print("db: added artifact_type column to download_tickets")
        if "claimed_at" not in dt_cols:
            conn.execute("ALTER TABLE download_tickets ADD COLUMN claimed_at REAL")
            conn.execute("UPDATE download_tickets SET claimed_at = used_at WHERE used_at IS NOT NULL AND claimed_at IS NULL")
            print("db: added claimed_at column to download_tickets")
        if "activation_order_id" not in dt_cols:
            conn.execute("ALTER TABLE download_tickets ADD COLUMN activation_order_id INTEGER")
            print("db: added activation_order_id column to download_tickets")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_download_tickets_client_id ON download_tickets(client_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_download_tickets_artifact ON download_tickets(artifact_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_download_tickets_order_id ON download_tickets(activation_order_id)")

        # Idempotent migration for existing database: add remember_me to auth_sessions
        sess_cols = [
            r["name"] for r in conn.execute("PRAGMA table_info(auth_sessions)").fetchall()
        ]
        if "remember_me" not in sess_cols:
            conn.execute("ALTER TABLE auth_sessions ADD COLUMN remember_me INTEGER NOT NULL DEFAULT 0")
            print("db: added remember_me column to auth_sessions")

        # Idempotent migration for existing database: add approved_at, is_pinned, sort_priority, staff_note to reviews
        rev_cols = [
            r["name"] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()
        ]
        if "approved_at" not in rev_cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN approved_at REAL")
            conn.execute("UPDATE reviews SET approved_at = updated_at WHERE status = 'approved' AND approved_at IS NULL")
            print("db: added approved_at column to reviews")
        # Reviews no longer require moderation. Publish legacy pending rows once,
        # while preserving explicitly rejected/hidden content for safety.
        conn.execute(
            """UPDATE reviews
               SET status = 'approved', approved_at = COALESCE(approved_at, updated_at, created_at)
               WHERE status = 'pending'"""
        )
        if "is_pinned" not in rev_cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")
            print("db: added is_pinned column to reviews")
        if "sort_priority" not in rev_cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN sort_priority INTEGER NOT NULL DEFAULT 0")
            print("db: added sort_priority column to reviews")
        if "staff_note" not in rev_cols:
            conn.execute("ALTER TABLE reviews ADD COLUMN staff_note TEXT")
            print("db: added staff_note column to reviews")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_approved_at ON reviews(status, approved_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_pinned_priority ON reviews(status, is_pinned DESC, sort_priority DESC, approved_at DESC)")

        creator_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(creator_profiles)").fetchall()
        }
        if "display_name" not in creator_cols:
            conn.execute("ALTER TABLE creator_profiles ADD COLUMN display_name TEXT")
            conn.execute(
                """UPDATE creator_profiles
                      SET display_name = COALESCE(
                          (SELECT u.display_name FROM users u WHERE u.id = creator_profiles.user_id),
                          tiktok_handle
                      )"""
            )
            print("db: added display_name column to creator_profiles")

        # Idempotent migration for existing database: add google_id and avatar_url to users
        user_cols = [
            r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()
        ]
        if "google_id" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
            print("db: added google_id column to users")
        if "avatar_url" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
            print("db: added avatar_url column to users")
        if "role" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            conn.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''")
            print("db: added role column to users")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

        # Enforce valid user role constraint at database level via triggers (covers legacy & migrated DBs)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_users_role_check_insert
            BEFORE INSERT ON users
            FOR EACH ROW
            WHEN NEW.role NOT IN ('user', 'admin')
            BEGIN
                SELECT RAISE(ABORT, 'CHECK constraint failed: role must be user or admin');
            END;
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_users_role_check_update
            BEFORE UPDATE OF role ON users
            FOR EACH ROW
            WHEN NEW.role NOT IN ('user', 'admin')
            BEGIN
                SELECT RAISE(ABORT, 'CHECK constraint failed: role must be user or admin');
            END;
        """)

        # This index must be created only after the legacy migration above.
        # A partial UNIQUE index allows multiple password-only users (NULL
        # google_id) while guaranteeing that one Google account can be linked
        # to at most one local account.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uidx_users_google_id "
            "ON users(google_id) WHERE google_id IS NOT NULL AND google_id <> ''"
        )

        # Idempotent migration for existing database: add transfer_code and idempotency_hash to payment_orders
        po_cols = [
            r["name"] for r in conn.execute("PRAGMA table_info(payment_orders)").fetchall()
        ]
        if "transfer_code" not in po_cols:
            conn.execute("ALTER TABLE payment_orders ADD COLUMN transfer_code TEXT")
            conn.execute("UPDATE payment_orders SET transfer_code = payment_code WHERE transfer_code IS NULL")
            print("db: added transfer_code column to payment_orders")
        if "idempotency_hash" not in po_cols:
            conn.execute("ALTER TABLE payment_orders ADD COLUMN idempotency_hash TEXT")
            print("db: added idempotency_hash column to payment_orders")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_orders_transfer ON payment_orders(transfer_code)")

        # Fulfillment modes are explicit business data. Runtime code must not
        # infer a workflow from a plan's display name or slug.
        plan_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(plans)").fetchall()
        }
        added_plan_flow = False
        if "ios_fulfillment_mode" not in plan_cols:
            conn.execute(
                "ALTER TABLE plans ADD COLUMN ios_fulfillment_mode TEXT NOT NULL DEFAULT 'auto_activation'"
            )
            added_plan_flow = True
        if "android_fulfillment_mode" not in plan_cols:
            conn.execute(
                "ALTER TABLE plans ADD COLUMN android_fulfillment_mode TEXT NOT NULL DEFAULT 'disabled'"
            )
            added_plan_flow = True
        if added_plan_flow:
            # One-time data mapping only. All future routing uses the persisted
            # mode fields, so renaming a plan cannot alter fulfilment.
            conn.execute(
                "UPDATE plans SET ios_fulfillment_mode='auto_activation', android_fulfillment_mode='apk_download' "
                "WHERE slug='locket_no_vpn'"
            )
            conn.execute(
                "UPDATE plans SET ios_fulfillment_mode='manual_contact', android_fulfillment_mode='disabled' "
                "WHERE slug IN ('vip_pro', 'locet_vpn')"
            )
            conn.execute(
                "UPDATE plans SET ios_fulfillment_mode='disabled', android_fulfillment_mode='apk_download' "
                "WHERE slug='locket_gold_android'"
            )
            print("db: added and initialized plan fulfillment modes")

        order_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(activation_orders)").fetchall()
        }
        order_additions = {
            "fulfillment_mode_snapshot": "TEXT NOT NULL DEFAULT 'auto_activation'",
            "contact_zalo": "TEXT",
            "contact_facebook": "TEXT",
            "admin_note": "TEXT",
            "handled_by_admin_id": "INTEGER",
            "handled_at": "REAL",
            "download_accessed_at": "REAL",
        }
        for column, definition in order_additions.items():
            if column not in order_cols:
                conn.execute(f"ALTER TABLE activation_orders ADD COLUMN {column} {definition}")
                print(f"db: added {column} column to activation_orders")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_act_orders_fulfillment_status "
            "ON activation_orders(fulfillment_mode_snapshot, status)"
        )

        # Idempotent migration for coupon snapshots in activation_orders
        coupon_order_additions = {
            "original_price_vnd_snapshot": "INTEGER",
            "original_price_coin_snapshot": "INTEGER",
            "discount_vnd_snapshot": "INTEGER NOT NULL DEFAULT 0",
            "discount_coin_snapshot": "INTEGER NOT NULL DEFAULT 0",
            "coupon_id": "INTEGER",
            "coupon_code_snapshot": "TEXT",
        }
        order_cols_current = {
            r["name"] for r in conn.execute("PRAGMA table_info(activation_orders)").fetchall()
        }
        for column, definition in coupon_order_additions.items():
            if column not in order_cols_current:
                conn.execute(f"ALTER TABLE activation_orders ADD COLUMN {column} {definition}")
                print(f"db: added {column} column to activation_orders")
        conn.execute(
            "UPDATE activation_orders SET original_price_vnd_snapshot = price_vnd_snapshot "
            "WHERE original_price_vnd_snapshot IS NULL"
        )
        conn.execute(
            "UPDATE activation_orders SET original_price_coin_snapshot = price_coin_snapshot "
            "WHERE original_price_coin_snapshot IS NULL"
        )

        # Idempotent migration for coupon snapshots in payment_orders
        po_cols_current = {
            r["name"] for r in conn.execute("PRAGMA table_info(payment_orders)").fetchall()
        }
        coupon_payment_additions = {
            "original_price_vnd_snapshot": "INTEGER",
            "discount_vnd_snapshot": "INTEGER NOT NULL DEFAULT 0",
            "coupon_id": "INTEGER",
            "coupon_code_snapshot": "TEXT",
            "renewed_from_payment_id": "INTEGER",
        }
        for column, definition in coupon_payment_additions.items():
            if column not in po_cols_current:
                conn.execute(f"ALTER TABLE payment_orders ADD COLUMN {column} {definition}")
                print(f"db: added {column} column to payment_orders")
        conn.execute(
            "UPDATE payment_orders SET original_price_vnd_snapshot = amount_vnd "
            "WHERE original_price_vnd_snapshot IS NULL"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uidx_payment_orders_renewed_from "
            "ON payment_orders(renewed_from_payment_id) "
            "WHERE renewed_from_payment_id IS NOT NULL"
        )

        _migrate_legacy_files(conn)
        _initialized = True
        _initialized_paths.add(current_path)
        print(f"db: initialized at {get_db_path()}")


def _migrate_legacy_files(conn):
    _migrate_accounts(conn)
    _migrate_tokens(conn)
    _migrate_queue_state(conn)


def _table_empty(conn, table):
    row = conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
    return row is None


def _migrate_accounts(conn):
    path = "accounts.json"
    if not os.path.exists(path):
        return
    if not _table_empty(conn, "accounts"):
        # Already populated — leave the JSON alone, user can clean up manually.
        return
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"db: skipping accounts.json migration: {e}")
        return
    if not isinstance(data, list):
        return
    now = time.time()
    inserted = 0
    for entry in data:
        if not isinstance(entry, dict):
            continue
        email = entry.get("email")
        password = entry.get("password")
        if not email or not password:
            continue
        slot_id = entry.get("id") or str(uuid.uuid4())
        try:
            conn.execute(
                "INSERT INTO accounts (slot_id, email, password, added_at) VALUES (?,?,?,?)",
                (slot_id, email, password, now),
            )
            inserted += 1
        except sqlite3.IntegrityError as e:
            print(f"db: skip duplicate account {email}: {e}")
    if inserted:
        os.rename(path, path + ".bak")
        print(f"db: migrated {inserted} account(s) from {path} (renamed to {path}.bak)")


def _migrate_tokens(conn):
    path = "tokens.json"
    if not os.path.exists(path):
        return
    if not _table_empty(conn, "tokens"):
        return
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"db: skipping tokens.json migration: {e}")
        return
    if not isinstance(data, list):
        return
    now = time.time()
    inserted = 0
    for payload in data:
        if not isinstance(payload, dict):
            continue
        conn.execute(
            "INSERT INTO tokens (payload, added_at) VALUES (?,?)",
            (json.dumps(payload), now),
        )
        inserted += 1
    if inserted:
        os.rename(path, path + ".bak")
        print(f"db: migrated {inserted} token payload(s) from {path}")


def _migrate_queue_state(conn):
    path = "queue_state.json"
    if not os.path.exists(path):
        return
    if not _table_empty(conn, "queue_requests") or not _table_empty(conn, "processing_times"):
        return
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"db: skipping queue_state.json migration: {e}")
        return

    requests = data.get("client_requests", {}) if isinstance(data, dict) else {}
    times = data.get("processing_times", []) if isinstance(data, dict) else []

    inserted_q = 0
    for client_id, r in requests.items():
        if not isinstance(r, dict):
            continue
        # Reset any "processing" status to "waiting" — we just crashed.
        status = r.get("status")
        if status == "processing":
            status = "waiting"
        if status not in ("waiting", "completed", "error"):
            continue
        conn.execute(
            """INSERT INTO queue_requests
               (client_id, username, status, result, error,
                added_at, started_at, completed_at, slot_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                client_id,
                r.get("username", ""),
                status,
                json.dumps(r["result"]) if r.get("result") else None,
                r.get("error"),
                _iso_to_epoch(r.get("added_at")) or time.time(),
                _iso_to_epoch(r.get("started_at")) if status != "waiting" else None,
                _iso_to_epoch(r.get("completed_at")),
                None,
            ),
        )
        inserted_q += 1

    inserted_t = 0
    now = time.time()
    for d in times:
        if isinstance(d, (int, float)):
            conn.execute(
                "INSERT INTO processing_times (duration, completed_at) VALUES (?,?)",
                (float(d), now),
            )
            inserted_t += 1

    if inserted_q or inserted_t:
        os.rename(path, path + ".bak")
        print(
            f"db: migrated {inserted_q} queue request(s) and "
            f"{inserted_t} processing time(s) from {path}"
        )


def _iso_to_epoch(s):
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None


# ---- User management helpers ----

def create_user(email, username, display_name, password_hash, google_id=None, avatar_url=None, role="user"):
    """Insert a new user. Returns new user id."""
    if role not in ("user", "admin"):
        raise ValueError(f"Invalid role: {role}")
    conn = get_conn()
    now = time.time()
    cursor = conn.execute(
        "INSERT INTO users "
        "(email, username, display_name, password_hash, google_id, avatar_url, role, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            email.strip().lower(),
            username.strip().lower(),
            display_name.strip(),
            password_hash,
            str(google_id) if google_id is not None else None,
            str(avatar_url) if avatar_url is not None else None,
            role,
            now,
        ),
    )
    return cursor.lastrowid


def get_user_by_id(user_id):
    """Fetch user by primary key id."""
    if not user_id:
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(email):
    """Fetch user by email (case-insensitive)."""
    if not email:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip().lower(),)
    ).fetchone()
    return dict(row) if row else None


def get_user_by_username(username):
    """Fetch user by username (case-insensitive)."""
    if not username:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip().lower(),)
    ).fetchone()
    return dict(row) if row else None


def get_user_by_identifier(identifier):
    """Fetch user by email or username (case-insensitive)."""
    if not identifier:
        return None
    ident = identifier.strip().lower()
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE (email = ? COLLATE NOCASE OR username = ? COLLATE NOCASE)",
        (ident, ident),
    ).fetchone()
    return dict(row) if row else None


def update_user_last_login(user_id):
    """Update last_login_at timestamp for a user."""
    if not user_id:
        return
    conn = get_conn()
    conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (time.time(), user_id))


def get_user_by_google_id(google_id):
    """Fetch user by google_id."""
    if not google_id:
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE google_id = ?", (str(google_id),)).fetchone()
    return dict(row) if row else None


def update_user_google_info(user_id, google_id=None, avatar_url=None):
    """Update google_id and/or avatar_url for a user."""
    if not user_id:
        return
    conn = get_conn()
    updates = []
    params = []
    if google_id is not None:
        updates.append("google_id = ?")
        params.append(str(google_id))
    if avatar_url is not None:
        updates.append("avatar_url = ?")
        params.append(str(avatar_url))
    if updates:
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)


# ---- Auth Session & Refresh Token helpers ----

def create_auth_session(family_id, user_id, expires_at, remember_me=0):
    """Create a new auth session family."""
    conn = get_conn()
    now = time.time()
    conn.execute(
        "INSERT INTO auth_sessions (family_id, user_id, created_at, expires_at, last_used_at, remember_me) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (family_id, user_id, now, expires_at, now, 1 if remember_me else 0),
    )


def get_auth_session(family_id):
    """Fetch an auth session family by family_id."""
    if not family_id:
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM auth_sessions WHERE family_id = ?", (family_id,)).fetchone()
    return dict(row) if row else None


def revoke_auth_session(family_id, reason="revoked"):
    """Revoke an entire auth session family and all its refresh tokens."""
    if not family_id:
        return
    conn = get_conn()
    now = time.time()
    conn.execute(
        "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = ? WHERE family_id = ? AND revoked_at IS NULL",
        (now, reason, family_id),
    )
    conn.execute(
        "UPDATE refresh_tokens SET revoked_at = ? WHERE family_id = ? AND revoked_at IS NULL",
        (now, family_id),
    )


def store_refresh_token(token_id, family_id, token_hash, parent_id, expires_at):
    """Store a hashed refresh token."""
    conn = get_conn()
    now = time.time()
    conn.execute(
        "INSERT INTO refresh_tokens (id, family_id, token_hash, parent_id, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (token_id, family_id, token_hash, parent_id, now, expires_at),
    )


def get_refresh_token_by_hash(token_hash):
    """Lookup a refresh token record by token_hash."""
    if not token_hash:
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM refresh_tokens WHERE token_hash = ?", (token_hash,)).fetchone()
    return dict(row) if row else None


def rotate_refresh_token_tx(family_id, old_token_id, new_token_id, new_token_hash, new_expires_at):
    """Atomic token rotation with replay detection.
    Returns: ('ok', new_token_id) OR ('replay_detected', reason) OR ('error', reason)
    """
    conn = get_conn()
    now = time.time()

    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check session family
        session_row = conn.execute(
            "SELECT * FROM auth_sessions WHERE family_id = ?", (family_id,)
        ).fetchone()
        if not session_row:
            conn.execute("ROLLBACK")
            return ("error", "session_not_found")

        if session_row["revoked_at"] is not None:
            conn.execute("ROLLBACK")
            return ("error", "session_already_revoked")

        # Check old token
        old_tok = conn.execute(
            "SELECT * FROM refresh_tokens WHERE id = ? AND family_id = ?",
            (old_token_id, family_id),
        ).fetchone()
        if not old_tok:
            conn.execute("ROLLBACK")
            return ("error", "token_not_found")

        # REPLAY DETECTION:
        # If the old token has ALREADY been used or revoked, this is a replay attempt!
        if old_tok["used_at"] is not None or old_tok["revoked_at"] is not None:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = 'replay_detected' WHERE family_id = ?",
                (now, family_id),
            )
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE family_id = ?",
                (now, family_id),
            )
            conn.execute("COMMIT")
            return ("replay_detected", "Token reuse detected; session family revoked.")

        # Mark old token as used and replaced
        conn.execute(
            "UPDATE refresh_tokens SET used_at = ?, replaced_by = ? WHERE id = ?",
            (now, new_token_id, old_token_id),
        )

        # Insert new token
        conn.execute(
            "INSERT INTO refresh_tokens (id, family_id, token_hash, parent_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (new_token_id, family_id, new_token_hash, old_token_id, now, new_expires_at),
        )

        # Update session last_used_at
        conn.execute(
            "UPDATE auth_sessions SET last_used_at = ? WHERE family_id = ?",
            (now, family_id),
        )

        conn.execute("COMMIT")
        return ("ok", new_token_id)
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(e))


def cleanup_expired_tokens():
    """Delete expired/revoked sessions and tokens older than 7 days. Safe & bounded."""
    conn = get_conn()
    cutoff = time.time() - (7 * 86400)
    try:
        conn.execute("DELETE FROM refresh_tokens WHERE expires_at < ?", (cutoff,))
        conn.execute("DELETE FROM auth_sessions WHERE expires_at < ? OR revoked_at < ?", (cutoff, cutoff))
        conn.execute("DELETE FROM download_tickets WHERE expires_at < ?", (cutoff,))
    except Exception:
        pass


# ---- Download Ticket helpers ----

def create_download_ticket(ticket_hash, user_id, expires_at, client_id=None, artifact_type=None):
    """Store a single-use download ticket hash bound to user, client_id and artifact_type."""
    conn = get_conn()
    now = time.time()
    conn.execute(
        "INSERT INTO download_tickets (ticket_hash, user_id, client_id, artifact_type, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ticket_hash, user_id, client_id, artifact_type, now, expires_at),
    )


def claim_download_ticket(ticket_hash, expected_artifact_type=None):
    """Atomically claim a single-use download ticket.
    Returns dict(ticket) if valid, None if expired/used/not found or artifact_type mismatch.
    """
    if not ticket_hash:
        return None
    conn = get_conn()
    now = time.time()

    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM download_tickets WHERE ticket_hash = ?", (ticket_hash,)
        ).fetchone()

        if not row:
            conn.execute("ROLLBACK")
            return None

        # Check expiration and already used / claimed
        if row["expires_at"] < now or row["used_at"] is not None or ("claimed_at" in row.keys() and row["claimed_at"] is not None):
            conn.execute("ROLLBACK")
            return None

        # Check artifact_type match if requested
        if expected_artifact_type is not None and "artifact_type" in row.keys():
            ticket_artifact = row["artifact_type"]
            # If ticket has artifact_type, it must match expected_artifact_type
            if ticket_artifact and ticket_artifact != expected_artifact_type:
                conn.execute("ROLLBACK")
                return None

        # Mark ticket as used and claimed
        conn.execute(
            "UPDATE download_tickets SET used_at = ?, claimed_at = ? WHERE ticket_hash = ?",
            (now, now, ticket_hash),
        )
        conn.execute("COMMIT")
        return dict(row)
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return None


# ---- Reviews and Ratings Helpers ----

def has_completed_service(user_id):
    """Return whether the user completed any paid service fulfillment.

    ``activation_orders`` is the canonical source for current purchases.  A
    manual-contact or APK order can complete without ever creating a queue
    request, so checking the legacy queue table alone incorrectly locks those
    customers out of reviews.  Keep the queue lookup as a compatibility path
    for orders created before activation orders were introduced.
    """
    if not user_id:
        return False
    conn = get_conn()
    row = conn.execute(
        """SELECT 1
           WHERE EXISTS (
               SELECT 1
               FROM activation_orders
               WHERE user_id = ? AND status = 'completed'
           ) OR EXISTS (
               SELECT 1
               FROM queue_requests
               WHERE user_id = ? AND status = 'completed'
           )
           LIMIT 1""",
        (user_id, user_id),
    ).fetchone()
    return row is not None


def is_review_eligible(user_id):
    """Return whether a user may publish a verified review.

    Normal users qualify after completing a service. A TikTok/KOL profile
    created by an administrator is an independent verification path, so that
    creator may review immediately without purchasing a package first.
    """
    if not user_id:
        return False
    row = get_conn().execute(
        """SELECT 1
           WHERE EXISTS (
               SELECT 1
               FROM activation_orders
               WHERE user_id = ? AND status = 'completed'
           ) OR EXISTS (
               SELECT 1
               FROM queue_requests
               WHERE user_id = ? AND status = 'completed'
           ) OR EXISTS (
               SELECT 1
               FROM creator_profiles
               WHERE user_id = ?
           )
           LIMIT 1""",
        (user_id, user_id, user_id),
    ).fetchone()
    return row is not None


def create_review(user_id, rating, content, is_verified=1):
    """Insert a review and publish it immediately."""
    conn = get_conn()
    now = time.time()
    cursor = conn.execute(
        """INSERT INTO reviews (user_id, rating, content, status, is_verified, approved_at, created_at, updated_at)
           VALUES (?, ?, ?, 'approved', ?, ?, ?, ?)""",
        (user_id, rating, content.strip(), 1 if is_verified else 0, now, now, now),
    )
    return cursor.lastrowid


def update_review(review_id, rating, content):
    """Update review rating/content and keep it publicly approved."""
    conn = get_conn()
    now = time.time()
    cursor = conn.execute(
        """UPDATE reviews
           SET rating = ?, content = ?, status = 'approved', approved_at = ?, updated_at = ?
           WHERE id = ?""",
        (rating, content.strip(), now, now, review_id),
    )
    return cursor.rowcount > 0


def delete_review(review_id):
    """Delete review from DB. Returns list of storage_names for image cleanup, or None if review not found."""
    conn = get_conn()
    review = get_review_by_id(review_id)
    if not review:
        return None
    images = get_review_images(review_id)
    storage_names = [img["storage_name"] for img in images]
    cursor = conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    if cursor.rowcount == 0:
        return None
    return storage_names


def delete_review_image_by_id(image_id, review_id=None):
    """Delete a single review image record. If review_id is specified, enforces review ownership."""
    conn = get_conn()
    if review_id is not None:
        row = conn.execute(
            "SELECT storage_name FROM review_images WHERE id = ? AND review_id = ?",
            (image_id, review_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT storage_name FROM review_images WHERE id = ?",
            (image_id,),
        ).fetchone()
    if not row:
        return None
    storage_name = row["storage_name"]
    conn.execute("DELETE FROM review_images WHERE id = ?", (image_id,))
    return storage_name


def get_review_by_user_id(user_id):
    """Fetch user's review with images and user metadata."""
    if not user_id:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT r.*, u.username, u.display_name
           FROM reviews r
           JOIN users u ON r.user_id = u.id
           WHERE r.user_id = ?""",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    review = dict(row)
    review["images"] = get_review_images(review["id"])
    return review


def get_review_by_id(review_id):
    """Fetch review by primary key id with images and user metadata."""
    if not review_id:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT r.*, u.username, u.display_name, u.email
           FROM reviews r
           JOIN users u ON r.user_id = u.id
           WHERE r.id = ?""",
        (review_id,),
    ).fetchone()
    if not row:
        return None
    review = dict(row)
    review["images"] = get_review_images(review["id"])
    return review


def add_review_image(review_id, storage_name, original_filename, file_size, mime_type="image/webp", width=None, height=None, sort_order=0):
    """Insert a review image record."""
    conn = get_conn()
    now = time.time()
    cursor = conn.execute(
        """INSERT INTO review_images
           (review_id, storage_name, original_filename, file_size, mime_type, width, height, sort_order, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (review_id, storage_name, original_filename, file_size, mime_type, width, height, sort_order, now),
    )
    return cursor.lastrowid


def get_review_images(review_id):
    """Fetch images for a review ordered by sort_order."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM review_images WHERE review_id = ? ORDER BY sort_order ASC, id ASC",
        (review_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_review_images(review_id):
    """Delete all images of a review. Returns list of storage_names."""
    conn = get_conn()
    images = get_review_images(review_id)
    storage_names = [img["storage_name"] for img in images]
    conn.execute("DELETE FROM review_images WHERE review_id = ?", (review_id,))
    return storage_names


def get_review_image_by_storage_name(storage_name):
    """Fetch image record with review status."""
    if not storage_name:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT img.*, r.status as review_status, r.user_id
           FROM review_images img
           JOIN reviews r ON img.review_id = r.id
           WHERE img.storage_name = ?""",
        (storage_name,),
    ).fetchone()
    return dict(row) if row else None


def get_review_image_by_id_and_user(image_id, user_id):
    """Fetch image record verifying it belongs to current user's review (IDOR protection)."""
    if not image_id or not user_id:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT img.*, r.status as review_status, r.user_id
           FROM review_images img
           JOIN reviews r ON img.review_id = r.id
           WHERE img.id = ? AND r.user_id = ?""",
        (image_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def get_approved_reviews(limit=12, offset=0):
    """Fetch approved reviews with author display info and images.
    Ordered by r.approved_at DESC, r.id DESC with pagination."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 12
    limit = max(1, min(50, limit))

    try:
        offset = int(offset)
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    conn = get_conn()
    total_row = conn.execute(
        "SELECT COUNT(*) as cnt, AVG(rating) as avg_rating FROM reviews WHERE status = 'approved'"
    ).fetchone()
    total = total_row["cnt"] if total_row else 0
    avg_rating = round(float(total_row["avg_rating"] or 0), 1) if total > 0 else 0.0

    dist_rows = conn.execute(
        "SELECT rating, COUNT(*) as cnt FROM reviews WHERE status = 'approved' GROUP BY rating"
    ).fetchall()
    distribution = {str(i): 0 for i in range(1, 6)}
    for r in dist_rows:
        distribution[str(r["rating"])] = r["cnt"]

    rows = conn.execute(
        """SELECT r.id, r.rating, r.content, r.is_verified, r.is_pinned, r.sort_priority,
                  r.approved_at, r.created_at, u.display_name, u.username
           FROM reviews r
           JOIN users u ON r.user_id = u.id
           WHERE r.status = 'approved'
           ORDER BY r.is_pinned DESC, r.sort_priority DESC, r.approved_at DESC, r.id DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()

    reviews = []
    for r in rows:
        item = dict(r)
        uname = item.get("username") or ""
        masked_username = uname[:2] + "***" if len(uname) > 2 else uname + "***"
        item["masked_username"] = masked_username
        item["images"] = get_review_images(item["id"])
        reviews.append(item)

    return {
        "reviews": reviews,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(reviews)) < total,
        },
        "stats": {
            "total": total,
            "average_rating": avg_rating,
            "distribution": distribution,
        },
    }


def list_reviews_admin(status=None, limit=100, offset=0, query=None, return_meta=False):
    """List reviews for admin portal with full user details, pinning, and filtering."""
    conn = get_conn()
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    where = []
    params = []
    if status and status != "all":
        where.append("r.status = ?")
        params.append(status)
    if query:
        q = f"%{query.strip().lower()}%"
        where.append("(LOWER(u.username) LIKE ? OR LOWER(u.display_name) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(r.content) LIKE ?)")
        params.extend([q, q, q, q])

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    total_row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM reviews r JOIN users u ON r.user_id = u.id {where_clause}",
        params,
    ).fetchone()
    total = total_row["cnt"] if total_row else 0

    sql = f"""
        SELECT r.*, u.username, u.display_name, u.email
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        {where_clause}
        ORDER BY r.is_pinned DESC, r.sort_priority DESC, r.created_at DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, tuple(params + [limit, offset])).fetchall()
    reviews = []
    for r in rows:
        item = dict(r)
        item["images"] = get_review_images(item["id"])
        reviews.append(item)

    if return_meta:
        return {
            "items": reviews,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    return reviews


def update_review_status_admin(review_id, status, admin_note=None, staff_note=None, is_pinned=None, sort_priority=None):
    """Admin moderation update of review status, note, staff note, pinning, and priority.
    Returns True only if review exists and was updated, else False."""
    if status not in ("pending", "approved", "rejected", "hidden"):
        return False
    conn = get_conn()
    now = time.time()
    existing = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not existing:
        return False

    final_admin_note = admin_note if admin_note is not None else existing["admin_note"]
    final_staff_note = staff_note if staff_note is not None else (existing["staff_note"] if "staff_note" in existing.keys() else None)
    final_is_pinned = (1 if is_pinned else 0) if is_pinned is not None else (existing["is_pinned"] if "is_pinned" in existing.keys() else 0)
    final_sort_priority = int(sort_priority) if sort_priority is not None else (existing["sort_priority"] if "sort_priority" in existing.keys() else 0)
    approved_at = now if status == "approved" else (existing["approved_at"] if status == existing["status"] else None)

    cursor = conn.execute(
        """UPDATE reviews
           SET status = ?, admin_note = ?, staff_note = ?, is_pinned = ?, sort_priority = ?, approved_at = ?, updated_at = ?
           WHERE id = ?""",
        (status, final_admin_note, final_staff_note, final_is_pinned, final_sort_priority, approved_at, now, review_id),
    )
    return cursor.rowcount > 0


# ---- TikTok Creator / KOL Profiles ----

def get_creator_by_id(creator_id):
    row = get_conn().execute(
        """SELECT cp.*, u.email, u.username,
                  COALESCE(NULLIF(cp.display_name, ''), u.display_name) AS display_name,
                  u.display_name AS account_display_name, u.is_active AS user_is_active
           FROM creator_profiles cp
           JOIN users u ON u.id = cp.user_id
           WHERE cp.id = ?""",
        (creator_id,),
    ).fetchone()
    return dict(row) if row else None


def get_creator_by_storage_name(storage_name):
    row = get_conn().execute(
        """SELECT cp.*, u.is_active AS user_is_active
           FROM creator_profiles cp
           JOIN users u ON u.id = cp.user_id
           WHERE cp.screenshot_name = ?""",
        (storage_name,),
    ).fetchone()
    return dict(row) if row else None


def list_creators_admin(query=None, limit=50, offset=0):
    conn = get_conn()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    where = []
    params = []
    if query:
        q = f"%{str(query).strip().lower()}%"
        where.append(
            "(LOWER(u.email) LIKE ? OR LOWER(u.username) LIKE ? OR "
            "LOWER(u.display_name) LIKE ? OR LOWER(cp.tiktok_handle) LIKE ?)"
        )
        params.extend([q, q, q, q])
    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(
        f"""SELECT COUNT(*) AS cnt FROM creator_profiles cp
            JOIN users u ON u.id = cp.user_id {where_clause}""",
        params,
    ).fetchone()["cnt"]
    rows = conn.execute(
        f"""SELECT cp.*, u.email, u.username,
                   COALESCE(NULLIF(cp.display_name, ''), u.display_name) AS display_name,
                   u.display_name AS account_display_name,
                   u.is_active AS user_is_active,
                   r.id AS review_id, r.rating, r.content AS review_content,
                   (SELECT ao.plan_name_snapshot
                      FROM activation_orders ao
                     WHERE ao.user_id = cp.user_id AND ao.status = 'completed'
                     ORDER BY ao.updated_at DESC, ao.id DESC LIMIT 1) AS plan_name
              FROM creator_profiles cp
              JOIN users u ON u.id = cp.user_id
              LEFT JOIN reviews r ON r.user_id = cp.user_id AND r.status = 'approved'
              {where_clause}
             ORDER BY cp.is_featured DESC, cp.sort_order ASC, cp.id DESC
             LIMIT ? OFFSET ?""",
        tuple(params + [limit, offset]),
    ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def list_public_creators():
    rows = get_conn().execute(
        """SELECT cp.id, cp.tiktok_handle, cp.tiktok_url, cp.screenshot_name,
                  cp.follower_count, cp.is_featured, cp.sort_order,
                  COALESCE(NULLIF(cp.display_name, ''), u.display_name) AS display_name,
                  r.id AS review_id, r.rating,
                  r.content AS review_content, r.created_at AS review_created_at,
                  (SELECT ao.plan_name_snapshot
                     FROM activation_orders ao
                    WHERE ao.user_id = cp.user_id AND ao.status = 'completed'
                    ORDER BY ao.updated_at DESC, ao.id DESC LIMIT 1) AS plan_name
             FROM creator_profiles cp
             JOIN users u ON u.id = cp.user_id AND u.is_active = 1
             LEFT JOIN reviews r ON r.user_id = cp.user_id AND r.status = 'approved'
            WHERE cp.is_active = 1
              AND (cp.require_review = 0 OR r.id IS NOT NULL)
            ORDER BY cp.is_featured DESC, cp.sort_order ASC, cp.id DESC"""
    ).fetchall()
    return [dict(row) for row in rows]


def create_creator_profile(user_id, display_name, tiktok_handle, tiktok_url, screenshot_name,
                           follower_count=None, is_featured=False, is_active=True,
                           require_review=False, sort_order=0):
    conn = get_conn()
    now = time.time()
    cursor = conn.execute(
        """INSERT INTO creator_profiles
           (user_id, display_name, tiktok_handle, tiktok_url, screenshot_name, follower_count,
            is_featured, is_active, require_review, sort_order, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, display_name, tiktok_handle, tiktok_url, screenshot_name, follower_count,
         1 if is_featured else 0, 1 if is_active else 0, 1 if require_review else 0,
         int(sort_order), now, now),
    )
    return cursor.lastrowid


def update_creator_profile(creator_id, display_name, tiktok_handle, tiktok_url, screenshot_name,
                           follower_count=None, is_featured=False, is_active=True,
                           require_review=False, sort_order=0):
    cursor = get_conn().execute(
        """UPDATE creator_profiles
              SET display_name = ?, tiktok_handle = ?, tiktok_url = ?, screenshot_name = ?,
                  follower_count = ?, is_featured = ?, is_active = ?,
                  require_review = ?, sort_order = ?, updated_at = ?
            WHERE id = ?""",
        (display_name, tiktok_handle, tiktok_url, screenshot_name, follower_count,
         1 if is_featured else 0, 1 if is_active else 0,
         1 if require_review else 0, int(sort_order), time.time(), creator_id),
    )
    return cursor.rowcount > 0


def delete_creator_profile(creator_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT screenshot_name FROM creator_profiles WHERE id = ?", (creator_id,)
    ).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM creator_profiles WHERE id = ?", (creator_id,))
    return row["screenshot_name"]


def cleanup_orphaned_and_temp_images(storage_root, max_age_seconds=3600):
    """Safely delete .tmp files and unreferenced image files older than max_age_seconds.
    Never touches images currently referenced in review_images table."""
    if not storage_root or not os.path.exists(storage_root):
        return 0
    now = time.time()
    conn = get_conn()
    active_rows = conn.execute("SELECT storage_name FROM review_images").fetchall()
    active_names = {r["storage_name"] for r in active_rows}

    deleted_count = 0
    try:
        for fname in os.listdir(storage_root):
            fpath = os.path.join(storage_root, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                mtime = os.path.getmtime(fpath)
            except OSError:
                continue

            if now - mtime < max_age_seconds:
                continue

            # Case 1: .tmp file older than max_age_seconds
            if fname.endswith(".tmp"):
                try:
                    os.remove(fpath)
                    deleted_count += 1
                except OSError:
                    pass
            # Case 2: .webp file not referenced in database and older than max_age_seconds
            elif fname.endswith(".webp") and fname not in active_names:
                try:
                    os.remove(fpath)
                    deleted_count += 1
                except OSError:
                    pass
    except Exception:
        pass
    return deleted_count


# ---- Plans Helpers ----

VALID_IOS_FULFILLMENT_MODES = {"auto_activation", "manual_contact", "disabled"}
VALID_ANDROID_FULFILLMENT_MODES = {"apk_download", "manual_contact", "disabled"}


def validate_plan_fulfillment(supported_platforms, ios_mode, android_mode):
    if ios_mode not in VALID_IOS_FULFILLMENT_MODES:
        raise ValueError("invalid ios_fulfillment_mode")
    if android_mode not in VALID_ANDROID_FULFILLMENT_MODES:
        raise ValueError("invalid android_fulfillment_mode")
    if supported_platforms == "ios" and (ios_mode == "disabled" or android_mode != "disabled"):
        raise ValueError("Gói chỉ iOS phải bật luồng iOS và tắt luồng Android.")
    if supported_platforms == "android" and (android_mode == "disabled" or ios_mode != "disabled"):
        raise ValueError("Gói chỉ Android phải bật luồng Android và tắt luồng iOS.")
    if supported_platforms == "all" and (ios_mode == "disabled" or android_mode == "disabled"):
        raise ValueError("Gói hỗ trợ tất cả phải cấu hình cả luồng iOS và Android.")


def resolve_plan_fulfillment(plan, platform):
    if not plan or platform not in ("ios", "android"):
        raise ValueError("invalid_platform")
    if plan.get("supported_platforms") not in ("all", platform):
        raise ValueError("platform_not_supported")
    mode = plan.get(f"{platform}_fulfillment_mode")
    if not mode:
        mode = "auto_activation" if platform == "ios" else "disabled"
    if mode == "disabled":
        raise ValueError("fulfillment_disabled")
    return mode

def create_plan(name, slug, short_description="", duration_days=30, price_vnd=10000, product_id=None,
                features=None, supported_platforms='all', is_active=1, is_popular=0,
                sort_order=0, inventory_status='in_stock', ios_fulfillment_mode=None,
                android_fulfillment_mode=None, **kwargs):
    """Create a new service plan.
    price_vnd must be integer > 0 and divisible by 1000.
    features can be a list or a JSON string.
    """
    if "platform" in kwargs:
        supported_platforms = kwargs["platform"]
    if "price_coin" in kwargs and (price_vnd is None or price_vnd == 10000):
        price_vnd = int(kwargs["price_coin"]) * 1000
    if "description" in kwargs and not short_description:
        short_description = kwargs["description"]
    if product_id is None:
        product_id = slug

    if not isinstance(price_vnd, int) or price_vnd <= 0:
        raise ValueError("price_vnd must be a positive integer")
    if price_vnd % 1000 != 0:
        raise ValueError("price_vnd must be divisible by 1000")
    if not isinstance(duration_days, int) or duration_days <= 0:
        raise ValueError("duration_days must be a positive integer")
    if not name or not slug or not product_id:
        raise ValueError("name, slug, and product_id are required")
    if supported_platforms not in ('all', 'ios', 'android'):
        raise ValueError("supported_platforms must be 'all', 'ios', or 'android'")
    if inventory_status not in ('in_stock', 'out_of_stock'):
        raise ValueError("inventory_status must be 'in_stock' or 'out_of_stock'")
    if ios_fulfillment_mode is None:
        ios_fulfillment_mode = "disabled" if supported_platforms == "android" else "auto_activation"
    if android_fulfillment_mode is None:
        android_fulfillment_mode = "disabled" if supported_platforms == "ios" else "apk_download"
    validate_plan_fulfillment(supported_platforms, ios_fulfillment_mode, android_fulfillment_mode)

    features_json = json.dumps(features) if isinstance(features, list) else (features or "[]")
    now = time.time()
    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO plans
           (name, slug, short_description, duration_days, price_vnd, product_id,
            features_json, supported_platforms, ios_fulfillment_mode, android_fulfillment_mode,
            is_active, is_popular, sort_order,
            inventory_status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name.strip(),
            slug.strip().lower(),
            (short_description or "").strip(),
            duration_days,
            price_vnd,
            product_id.strip(),
            features_json,
            supported_platforms,
            ios_fulfillment_mode,
            android_fulfillment_mode,
            1 if is_active else 0,
            1 if is_popular else 0,
            int(sort_order),
            inventory_status,
            now,
            now,
        ),
    )
    return cursor.lastrowid


def update_plan(plan_id, **kwargs):
    """Update an existing plan."""
    allowed = {
        "name", "slug", "short_description", "duration_days", "price_vnd",
        "product_id", "features_json", "features", "supported_platforms",
        "is_active", "is_popular", "sort_order", "inventory_status",
        "ios_fulfillment_mode", "android_fulfillment_mode"
    }
    current = get_plan_by_id(plan_id, public=False)
    if not current:
        return False
    candidate_platform = kwargs.get("supported_platforms", current["supported_platforms"])
    candidate_ios = kwargs.get("ios_fulfillment_mode", current.get("ios_fulfillment_mode", "auto_activation"))
    candidate_android = kwargs.get("android_fulfillment_mode", current.get("android_fulfillment_mode", "disabled"))
    validate_plan_fulfillment(candidate_platform, candidate_ios, candidate_android)
    updates = []
    params = []
    for k, v in kwargs.items():
        if k not in allowed:
            continue
        if k == "price_vnd":
            if not isinstance(v, int) or v <= 0 or v % 1000 != 0:
                raise ValueError("price_vnd must be an integer > 0 divisible by 1000")
            updates.append("price_vnd = ?")
            params.append(v)
        elif k == "duration_days":
            if not isinstance(v, int) or v <= 0:
                raise ValueError("duration_days must be a positive integer")
            updates.append("duration_days = ?")
            params.append(v)
        elif k == "features":
            updates.append("features_json = ?")
            params.append(json.dumps(v) if isinstance(v, list) else str(v))
        elif k in ("is_active", "is_popular"):
            updates.append(f"{k} = ?")
            params.append(1 if v else 0)
        elif k == "supported_platforms":
            if v not in ('all', 'ios', 'android'):
                raise ValueError("supported_platforms must be 'all', 'ios', or 'android'")
            updates.append(f"{k} = ?")
            params.append(v)
        elif k == "inventory_status":
            if v not in ('in_stock', 'out_of_stock'):
                raise ValueError("inventory_status must be 'in_stock' or 'out_of_stock'")
            updates.append(f"{k} = ?")
            params.append(v)
        elif k == "ios_fulfillment_mode":
            if v not in VALID_IOS_FULFILLMENT_MODES:
                raise ValueError("invalid ios_fulfillment_mode")
            updates.append("ios_fulfillment_mode = ?")
            params.append(v)
        elif k == "android_fulfillment_mode":
            if v not in VALID_ANDROID_FULFILLMENT_MODES:
                raise ValueError("invalid android_fulfillment_mode")
            updates.append("android_fulfillment_mode = ?")
            params.append(v)
        else:
            updates.append(f"{k} = ?")
            params.append(v)

    if not updates:
        return False
    updates.append("updated_at = ?")
    now = time.time()
    params.append(now)
    params.append(plan_id)

    conn = get_conn()
    cursor = conn.execute(
        f"UPDATE plans SET {', '.join(updates)} WHERE id = ?", params
    )
    return cursor.rowcount > 0


def delete_plan(plan_id):
    """Delete a plan by ID."""
    conn = get_conn()
    cursor = conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    return cursor.rowcount > 0


def _format_plan_row(row, public=True):
    if not row:
        return None
    d = dict(row)
    try:
        d["features"] = json.loads(d.get("features_json") or "[]")
    except Exception:
        d["features"] = []
    # Coin price is strictly computed by backend: 1 Coin = 1,000 VND
    d["price_coin"] = int(d["price_vnd"] // 1000)
    if public:
        # Never leak internal details in public view
        d.pop("features_json", None)
    return d


def get_plan_by_id(plan_id, public=True):
    conn = get_conn()
    row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    return _format_plan_row(row, public=public)


def get_plan_by_slug(slug, public=True):
    if not slug:
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM plans WHERE slug = ?", (slug.strip().lower(),)).fetchone()
    return _format_plan_row(row, public=public)


def list_active_plans():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM plans WHERE is_active = 1 ORDER BY sort_order ASC, id ASC"
    ).fetchall()
    return [_format_plan_row(r, public=True) for r in rows]


def list_all_plans_admin():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM plans ORDER BY sort_order ASC, id ASC"
    ).fetchall()
    return [_format_plan_row(r, public=False) for r in rows]


# ---- Wallets & Ledger Helpers ----

def get_or_create_wallet(user_id):
    """Fetch wallet for user, initializing with 0 coins if not present."""
    if not user_id:
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return dict(row)
    now = time.time()
    try:
        conn.execute(
            "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (?, 0, ?)",
            (user_id, now),
        )
        return {"user_id": user_id, "balance_coin": 0, "updated_at": now}
    except Exception:
        row = conn.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else {"user_id": user_id, "balance_coin": 0, "updated_at": now}


def get_wallet_balance(user_id):
    w = get_or_create_wallet(user_id)
    return w["balance_coin"] if w else 0


def apply_wallet_transaction(user_id, tx_type, amount_coin, reference_type=None,
                             reference_id=None, description=None, idempotency_key=None):
    """Execute a wallet transaction with ledger recording and idempotency.
    tx_type: 'topup', 'purchase', 'refund', 'adjustment'
    amount_coin: signed integer delta (positive to add, negative to subtract).
    Returns (status, tx_or_error) where status is 'ok', 'idempotent', 'insufficient_balance', or 'error'.
    """
    if not user_id:
        return ("error", "user_id_required")
    if tx_type not in ('topup', 'purchase', 'refund', 'adjustment'):
        return ("error", "invalid_tx_type")
    if isinstance(amount_coin, bool) or not isinstance(amount_coin, int):
        raise ValueError("amount_coin must be an integer")

    conn = get_conn()
    now = time.time()

    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check idempotency first
        if idempotency_key:
            existing = conn.execute(
                "SELECT * FROM wallet_transactions WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                conn.execute("COMMIT")
                return ("idempotent", dict(existing))

        # Fetch or initialize wallet
        wallet_row = conn.execute(
            "SELECT * FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not wallet_row:
            conn.execute(
                "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (?, 0, ?)",
                (user_id, now),
            )
            balance_before = 0
        else:
            balance_before = wallet_row["balance_coin"]

        balance_after = balance_before + amount_coin
        if balance_after < 0:
            conn.execute("ROLLBACK")
            return ("insufficient_balance", f"Số dư không đủ ({balance_before} Coin, cần {-amount_coin} Coin)")

        conn.execute(
            "UPDATE wallets SET balance_coin = ?, updated_at = ? WHERE user_id = ?",
            (balance_after, now, user_id),
        )

        cursor = conn.execute(
            """INSERT INTO wallet_transactions
               (user_id, type, amount_coin, balance_before, balance_after,
                reference_type, reference_id, description, idempotency_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                tx_type,
                amount_coin,
                balance_before,
                balance_after,
                reference_type,
                str(reference_id) if reference_id is not None else None,
                description,
                idempotency_key,
                now,
            ),
        )
        tx_id = cursor.lastrowid
        conn.execute("COMMIT")

        return ("ok", {
            "id": tx_id,
            "user_id": user_id,
            "type": tx_type,
            "amount_coin": amount_coin,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "reference_type": reference_type,
            "reference_id": str(reference_id) if reference_id is not None else None,
            "description": description,
            "idempotency_key": idempotency_key,
            "created_at": now,
        })
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(e))


def admin_adjust_user_wallet_atomic(user_id: int, amount_coin: int, reason: str,
                                    admin_user_id: int, idempotency_key: str = None,
                                    ip_address: str = None, user_agent: str = None):
    """Atomically adjust user wallet balance and record an admin audit log in the same transaction.
    If either wallet update or audit logging fails, the whole transaction rolls back.
    Returns (status, result_dict_or_error_msg).
    """
    if not user_id:
        return ("error", "user_id_required")
    if isinstance(amount_coin, bool) or not isinstance(amount_coin, int):
        raise ValueError("amount_coin must be an integer")
    if amount_coin == 0:
        return ("error", "zero_amount")

    conn = get_conn()
    now = time.time()

    try:
        conn.execute("BEGIN IMMEDIATE")

        # Idempotency check
        if idempotency_key:
            existing = conn.execute(
                "SELECT * FROM wallet_transactions WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                conn.execute("COMMIT")
                tx_dict = dict(existing)
                wallet_row = conn.execute("SELECT balance_coin FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
                current_bal = wallet_row["balance_coin"] if wallet_row else tx_dict["balance_after"]
                return ("idempotent", {
                    "id": tx_dict["id"],
                    "user_id": user_id,
                    "type": tx_dict["type"],
                    "amount_coin": tx_dict["amount_coin"],
                    "balance_before": tx_dict["balance_before"],
                    "balance_after": tx_dict["balance_after"],
                    "current_balance_coin": current_bal,
                    "description": tx_dict["description"],
                    "idempotency_key": idempotency_key,
                    "created_at": tx_dict["created_at"],
                })

        # Fetch or initialize wallet
        wallet_row = conn.execute(
            "SELECT * FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not wallet_row:
            conn.execute(
                "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (?, 0, ?)",
                (user_id, now),
            )
            balance_before = 0
        else:
            balance_before = wallet_row["balance_coin"]

        balance_after = balance_before + amount_coin
        if balance_after < 0:
            conn.execute("ROLLBACK")
            return ("insufficient_balance", f"Số dư không đủ ({balance_before} Coin, cần {-amount_coin} Coin)")

        conn.execute(
            "UPDATE wallets SET balance_coin = ?, updated_at = ? WHERE user_id = ?",
            (balance_after, now, user_id),
        )

        cursor = conn.execute(
            """INSERT INTO wallet_transactions
               (user_id, type, amount_coin, balance_before, balance_after,
                reference_type, reference_id, description, idempotency_key, created_at)
               VALUES (?, 'adjustment', ?, ?, ?, 'admin_adjustment', ?, ?, ?, ?)""",
            (
                user_id,
                amount_coin,
                balance_before,
                balance_after,
                str(admin_user_id) if admin_user_id else "admin",
                f"Admin điều chỉnh: {reason}",
                idempotency_key,
                now,
            ),
        )
        tx_id = cursor.lastrowid

        # Insert audit log inside the same transaction
        before_data = {"user_id": user_id, "balance_coin": balance_before}
        after_data = {"user_id": user_id, "balance_coin": balance_after, "amount_coin": amount_coin, "reason": reason}
        b_json = json.dumps(_redact_sensitive_keys(before_data), ensure_ascii=False)
        a_json = json.dumps(_redact_sensitive_keys(after_data), ensure_ascii=False)
        ua = (user_agent or "")[:255] if user_agent else None

        conn.execute(
            """INSERT INTO admin_audit_logs
               (admin_user_id, action, entity_type, entity_id, before_json, after_json, ip_address, user_agent, created_at)
               VALUES (?, 'wallet_adjustment', 'wallet', ?, ?, ?, ?, ?, ?)""",
            (
                admin_user_id or 1,
                str(user_id),
                b_json,
                a_json,
                ip_address,
                ua,
                now,
            ),
        )

        conn.execute("COMMIT")

        tx_dict = {
            "id": tx_id,
            "user_id": user_id,
            "type": "adjustment",
            "amount_coin": amount_coin,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "reference_type": "admin_adjustment",
            "reference_id": str(admin_user_id),
            "description": f"Admin điều chỉnh: {reason}",
            "idempotency_key": idempotency_key,
            "created_at": now,
        }

        return ("ok", {
            "transaction": tx_dict,
            "balance_coin": balance_after,
            "user_id": user_id,
        })
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(e))



def get_wallet_transactions(user_id, limit=20, offset=0):
    try:
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        limit = 20
        offset = 0

    conn = get_conn()
    total_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM wallet_transactions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    total = total_row["cnt"] if total_row else 0

    rows = conn.execute(
        """SELECT * FROM wallet_transactions
           WHERE user_id = ?
           ORDER BY created_at DESC, id DESC
           LIMIT ? OFFSET ?""",
        (user_id, limit, offset),
    ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(rows)) < total,
        }
    }


def list_wallet_transactions(user_id, limit=20, offset=0):
    res = get_wallet_transactions(user_id, limit, offset)
    return res["items"], res["pagination"]["total"]


# ---- Payment Orders Helpers ----

def create_payment_order(payment_code, user_id, purpose, amount_vnd, plan_id=None,
                         provider='vietqr', qr_payload=None, idempotency_key=None,
                         expires_in=600, transfer_code=None, idempotency_hash=None, **kwargs):
    if not isinstance(amount_vnd, int) or amount_vnd <= 0:
        raise ValueError("amount_vnd must be a positive integer")
    if amount_vnd % 1000 != 0:
        raise ValueError("amount_vnd must be divisible by 1000")
    if purpose not in ('wallet_topup', 'plan_purchase'):
        raise ValueError("purpose must be 'wallet_topup' or 'plan_purchase'")

    coin_amount = kwargs.get("coin_amount") or (amount_vnd // 1000)
    now = time.time()
    expires_at = kwargs.get("expires_at") or (now + expires_in)
    conn = get_conn()

    cursor = conn.execute(
        """INSERT INTO payment_orders
           (payment_code, transfer_code, idempotency_hash, user_id, purpose, plan_id,
            amount_vnd, coin_amount, provider, status, qr_payload, idempotency_key,
            expires_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
        (
            payment_code,
            transfer_code,
            idempotency_hash,
            user_id,
            purpose,
            plan_id,
            amount_vnd,
            coin_amount,
            provider,
            qr_payload,
            idempotency_key,
            expires_at,
            now,
            now,
        ),
    )
    return cursor.lastrowid


def get_payment_order_by_code(payment_code):
    if not payment_code:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT p.*, u.username, u.display_name, u.email
           FROM payment_orders p
           JOIN users u ON p.user_id = u.id
           WHERE p.payment_code = ? OR p.transfer_code = ?
           ORDER BY p.id DESC LIMIT 1""",
        (payment_code, payment_code),
    ).fetchone()
    return dict(row) if row else None


def get_payment_order_by_id(payment_id):
    if not payment_id:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT p.*, u.username, u.display_name, u.email
           FROM payment_orders p
           JOIN users u ON p.user_id = u.id
           WHERE p.id = ?""",
        (payment_id,),
    ).fetchone()
    return dict(row) if row else None


def get_payment_order_by_idempotency(user_id, idempotency_key):
    if not idempotency_key:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT p.*, u.username, u.display_name, u.email
           FROM payment_orders p
           JOIN users u ON p.user_id = u.id
           WHERE p.user_id = ? AND p.idempotency_key = ?""",
        (user_id, idempotency_key),
    ).fetchone()
    return dict(row) if row else None


def list_payment_orders_admin(status=None, query=None, limit=50, offset=0, return_meta=False, purpose=None):
    conn = get_conn()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    where = []
    params = []
    if status and status != 'all':
        where.append("p.status = ?")
        params.append(status)
    if purpose and purpose != 'all':
        where.append("p.purpose = ?")
        params.append(purpose)
    if query:
        q = f"%{query.strip().lower()}%"
        where.append("(LOWER(p.payment_code) LIKE ? OR LOWER(COALESCE(p.transfer_code, '')) LIKE ? OR LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(COALESCE(p.bank_transaction_id, '')) LIKE ?)")
        params.extend([q, q, q, q, q])

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    total_row = conn.execute(
        f"SELECT COUNT(*) as total FROM payment_orders p JOIN users u ON p.user_id = u.id {where_clause}",
        params,
    ).fetchone()
    total = total_row["total"] if total_row else 0

    sql = f"""
        SELECT p.*, u.username, u.display_name, u.email
        FROM payment_orders p
        JOIN users u ON p.user_id = u.id
        {where_clause}
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, tuple(params + [limit, offset])).fetchall()
    items = [dict(r) for r in rows]
    if return_meta:
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    return items



def confirm_payment_order_tx(payment_id, bank_transaction_id, audit_context=None,
                             manual_override=False, manual_reason=None,
                             recover_expired=False):
    """Atomically confirm payment order with bank_transaction_id.
    If wallet_topup: credits coin with topup ledger.
    If plan_purchase: marks payment paid and sets activation_order status to 'paid'.
    Returns ('ok', payment_dict) or ('already_paid', ...) or ('expired', ...) or ('error', reason)
    """
    if not payment_id or not bank_transaction_id:
        return ("error", "payment_id and bank_transaction_id are required")
    if manual_override and len((manual_reason or "").strip()) < 5:
        return ("error", "manual_reason_required")

    bank_ref = str(bank_transaction_id).strip()
    conn = get_conn()
    now = time.time()

    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if bank_transaction_id was already used
        existing_bank = conn.execute(
            "SELECT id FROM payment_orders WHERE bank_transaction_id = ? AND id != ?",
            (bank_ref, payment_id),
        ).fetchone()
        if existing_bank:
            conn.execute("ROLLBACK")
            return ("error", f"Mã giao dịch ngân hàng '{bank_ref}' đã được sử dụng cho thanh toán #{existing_bank['id']}.")

        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (payment_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return ("error", "not_found")

        if row["status"] == "paid":
            conn.execute("ROLLBACK")
            return ("already_paid", "Đơn thanh toán này đã được xác nhận trước đó.")

        can_recover_expired = bool(manual_override or recover_expired)

        if row["status"] == "expired" and not can_recover_expired:
            conn.execute("ROLLBACK")
            return ("expired", "Mã thanh toán đã hết hạn, không thể xác nhận.")

        if row["status"] == "pending" and row["expires_at"] < now and not can_recover_expired:
            conn.execute(
                "UPDATE payment_orders SET status = 'expired', updated_at = ? WHERE id = ?",
                (now, payment_id),
            )
            conn.execute(
                "UPDATE activation_orders SET status = 'cancelled', updated_at = ? WHERE payment_order_id = ? AND status = 'awaiting_payment'",
                (now, payment_id),
            )
            conn.execute("COMMIT")
            return ("expired", "Mã thanh toán đã hết hạn, không thể xác nhận.")

        allowed_statuses = {"pending"}
        if manual_override:
            allowed_statuses.update({"expired", "underpaid", "review_needed"})
        elif recover_expired:
            allowed_statuses.add("expired")
        if row["status"] not in allowed_statuses:
            conn.execute("ROLLBACK")
            return ("error", f"Không thể xác nhận đơn ở trạng thái '{row['status']}'.")

        # Update payment order
        conn.execute(
            """UPDATE payment_orders
               SET status = 'paid', bank_transaction_id = ?, paid_at = ?, updated_at = ?
               WHERE id = ?""",
            (bank_ref, now, now, payment_id),
        )

        user_id = row["user_id"]
        purpose = row["purpose"]
        coin_amount = row["coin_amount"]
        act_row = None

        if purpose == "wallet_topup":
            # Apply wallet topup
            wallet_row = conn.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
            balance_before = wallet_row["balance_coin"] if wallet_row else 0
            balance_after = balance_before + coin_amount

            if not wallet_row:
                conn.execute(
                    "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (?, ?, ?)",
                    (user_id, balance_after, now),
                )
            else:
                conn.execute(
                    "UPDATE wallets SET balance_coin = ?, updated_at = ? WHERE user_id = ?",
                    (balance_after, now, user_id),
                )

            idempotency_key = f"pay_{payment_id}_topup"
            conn.execute(
                """INSERT INTO wallet_transactions
                   (user_id, type, amount_coin, balance_before, balance_after,
                    reference_type, reference_id, description, idempotency_key, created_at)
                   VALUES (?, 'topup', ?, ?, ?, 'payment_order', ?, ?, ?, ?)""",
                (
                    user_id,
                    coin_amount,
                    balance_before,
                    balance_after,
                    str(payment_id),
                    f"Nạp Coin từ thanh toán #{row['transfer_code'] or row['payment_code']}",
                    idempotency_key,
                    now,
                ),
            )

        elif purpose == "plan_purchase":
            # Update associated activation order
            act_row = conn.execute(
                "SELECT id, status, fulfillment_mode_snapshot FROM activation_orders WHERE payment_order_id = ?",
                (payment_id,),
            ).fetchone()
            recoverable_activation_statuses = {"awaiting_payment"}
            if can_recover_expired and row["status"] == "expired":
                recoverable_activation_statuses.add("cancelled")
            if act_row and act_row["status"] in recoverable_activation_statuses:
                next_status = (
                    "completed"
                    if act_row["fulfillment_mode_snapshot"] == "apk_download"
                    else "paid"
                )
                conn.execute(
                    "UPDATE activation_orders SET status = ?, updated_at = ? WHERE id = ?",
                    (next_status, now, act_row["id"]),
                )

        # Confirm any reserved coupon redemption for this payment order
        from . import coupon_service
        act_id_for_coupon = act_row["id"] if act_row else None
        coupon_service.redeem_reserved_coupon(
            conn,
            payment_id,
            act_id_for_coupon,
            now,
            allow_released=can_recover_expired,
        )

        updated_row = conn.execute(
            "SELECT * FROM payment_orders WHERE id = ?", (payment_id,)
        ).fetchone()
        updated = dict(updated_row) if updated_row else None
        if audit_context:
            audit_after = dict(updated or {})
            if manual_override:
                audit_after["manual_override"] = True
                audit_after["manual_reason"] = (manual_reason or "").strip()[:500]
                audit_after["previous_status"] = row["status"]
            record_admin_audit_log(
                admin_user_id=audit_context["admin_user_id"],
                action="payment_manual_confirm" if manual_override else "payment_confirm",
                entity_type="payment_order",
                entity_id=payment_id,
                before_data=dict(row),
                after_data=audit_after,
                ip_address=audit_context.get("ip_address"),
                user_agent=audit_context.get("user_agent"),
            )
        conn.execute("COMMIT")
        return ("ok", updated)
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(e))


def renew_payment_order_tx(old_payment_id, user_id, new_payment_code, new_transfer_code, qr_payload, expires_in=600):
    """Atomically renew an expired/cancelled payment order.
    Creates a brand-new payment order record with 10-min TTL and new codes.
    For plan purchases, re-links the existing awaiting_payment activation order without duplicating it.
    Returns ('ok', new_payment_dict) or ('error_code', msg).
    """
    conn = get_conn()
    now = time.time()
    expires_at = now + expires_in
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (old_payment_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return ("not_found", "Không tìm thấy giao dịch cũ.")
        if row["user_id"] != user_id:
            conn.execute("ROLLBACK")
            return ("forbidden", "Bạn không có quyền thao tác trên đơn này.")
        row = dict(row)

        prior_renewal = conn.execute(
            "SELECT id FROM payment_orders WHERE renewed_from_payment_id = ?",
            (old_payment_id,),
        ).fetchone()
        if prior_renewal:
            conn.execute("COMMIT")
            return ("ok", get_payment_order_by_id(prior_renewal["id"]))

        st = row["status"]
        if st == "paid":
            conn.execute("ROLLBACK")
            return ("cannot_renew_paid", "Đơn thanh toán này đã được xác nhận thành công, không thể tạo lại mã.")
        if st in ("underpaid", "review_needed"):
            conn.execute("ROLLBACK")
            return ("invalid_status", f"Đơn ở trạng thái '{st}' không thể tự động tạo lại mã.")
        if st == "pending":
            if row["expires_at"] >= now:
                conn.execute("ROLLBACK")
                return ("payment_still_active", "Mã thanh toán hiện tại vẫn còn hiệu lực.")
            # Overdue pending -> mark expired
            conn.execute(
                "UPDATE payment_orders SET status = 'expired', updated_at = ? WHERE id = ?",
                (now, old_payment_id),
            )

        # Insert new payment order with coupon snapshots preserved
        orig_price_snap = row.get("original_price_vnd_snapshot") or row["amount_vnd"]
        disc_snap = row.get("discount_vnd_snapshot") or 0
        c_id = row.get("coupon_id")
        c_code_snap = row.get("coupon_code_snapshot")
        redemption = conn.execute(
            "SELECT * FROM coupon_redemptions WHERE payment_order_id = ? ORDER BY id DESC LIMIT 1",
            (old_payment_id,),
        ).fetchone()
        if c_id is not None:
            if not redemption or redemption["status"] == "redeemed":
                conn.execute("ROLLBACK")
                return ("coupon_reservation_unavailable", "Lượt giữ chỗ của mã giảm giá không còn hợp lệ.")
            if redemption["status"] == "released":
                from . import coupon_service
                coupon_service.sweep_expired_reservations(conn, now)
                coupon = conn.execute(
                    "SELECT usage_limit_total, usage_limit_per_user FROM coupons WHERE id = ?",
                    (c_id,),
                ).fetchone()
                if not coupon:
                    conn.execute("ROLLBACK")
                    return ("coupon_not_found", "Mã giảm giá không còn tồn tại.")
                total_in_use = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM coupon_redemptions "
                    "WHERE coupon_id = ? AND id != ? AND status IN ('reserved', 'redeemed')",
                    (c_id, redemption["id"]),
                ).fetchone()["cnt"]
                user_in_use = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM coupon_redemptions "
                    "WHERE coupon_id = ? AND user_id = ? AND id != ? "
                    "AND status IN ('reserved', 'redeemed')",
                    (c_id, user_id, redemption["id"]),
                ).fetchone()["cnt"]
                if coupon["usage_limit_total"] is not None and total_in_use >= coupon["usage_limit_total"]:
                    conn.execute("ROLLBACK")
                    return ("coupon_exhausted", "Mã giảm giá đã hết lượt sử dụng.")
                if coupon["usage_limit_per_user"] is not None and user_in_use >= coupon["usage_limit_per_user"]:
                    conn.execute("ROLLBACK")
                    return ("user_limit_reached", "Người dùng đã hết lượt sử dụng mã giảm giá.")

        cursor = conn.execute(
            """INSERT INTO payment_orders
               (payment_code, transfer_code, user_id, purpose, plan_id, amount_vnd, coin_amount,
                provider, status, qr_payload, idempotency_key, expires_at, created_at, updated_at,
                original_price_vnd_snapshot, discount_vnd_snapshot, coupon_id, coupon_code_snapshot,
                renewed_from_payment_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_payment_code,
                new_transfer_code,
                user_id,
                row["purpose"],
                row["plan_id"],
                row["amount_vnd"],
                row["coin_amount"],
                row["provider"],
                qr_payload,
                f"renew_{old_payment_id}_{int(now)}",
                expires_at,
                now,
                now,
                orig_price_snap,
                disc_snap,
                c_id,
                c_code_snap,
                old_payment_id,
            ),
        )
        new_id = cursor.lastrowid

        # Transfer existing coupon redemption to new payment order without duplicating
        if redemption:
            conn.execute(
                """UPDATE coupon_redemptions
                   SET payment_order_id = ?, status = 'reserved', expires_at = ?, released_at = NULL
                   WHERE id = ?""",
                (new_id, expires_at, redemption["id"]),
            )

        # If plan purchase, re-link existing activation order
        if row["purpose"] == "plan_purchase":
            act = conn.execute(
                "SELECT id, status FROM activation_orders WHERE payment_order_id = ? ORDER BY id DESC LIMIT 1",
                (old_payment_id,),
            ).fetchone()
            if not act:
                conn.execute("ROLLBACK")
                return ("activation_order_missing", "Đơn kích hoạt liên kết không còn tồn tại.")
            conn.execute(
                "UPDATE activation_orders SET payment_order_id = ?, status = 'awaiting_payment', updated_at = ? WHERE id = ?",
                (new_id, now, act["id"]),
            )

        conn.execute("COMMIT")
        new_row = get_payment_order_by_id(new_id)
        return ("ok", new_row)
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(e))



def reject_payment_order_tx(payment_id, status='cancelled', note=None, audit_context=None):
    if status not in ('expired', 'cancelled', 'underpaid', 'review_needed'):
        return ("error", "invalid_status")
    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (payment_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return ("error", "not_found")
        if row["status"] == "paid":
            conn.execute("ROLLBACK")
            return ("error", "cannot_reject_paid_order")

        conn.execute(
            "UPDATE payment_orders SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, payment_id),
        )

        # Cancel activation order if pending
        conn.execute(
            "UPDATE activation_orders SET status = 'cancelled', updated_at = ? WHERE payment_order_id = ? AND status = 'awaiting_payment'",
            (now, payment_id),
        )

        # Release any reserved coupon quota
        from . import coupon_service
        coupon_service.release_reserved_coupon(conn, payment_id, now)

        updated_row = conn.execute(
            "SELECT * FROM payment_orders WHERE id = ?", (payment_id,)
        ).fetchone()
        updated = dict(updated_row) if updated_row else None
        if audit_context:
            audit_after = dict(updated or {})
            if note:
                audit_after["admin_reason"] = str(note)[:500]
            record_admin_audit_log(
                admin_user_id=audit_context["admin_user_id"],
                action="payment_reject",
                entity_type="payment_order",
                entity_id=payment_id,
                before_data=dict(row),
                after_data=audit_after,
                ip_address=audit_context.get("ip_address"),
                user_agent=audit_context.get("user_agent"),
            )
        conn.execute("COMMIT")
        return ("ok", updated)
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(e))


# ---- Activation Orders Helpers ----

VALID_ACT_TRANSITIONS = {
    "awaiting_payment": {"paid", "cancelled"},
    "paid": {"awaiting_queue", "queued", "processing", "completed", "refunded", "cancelled"},
    "awaiting_queue": {"queued", "cancelled", "refunded"},
    "queued": {"processing", "failed", "cancelled"},
    "processing": {"completed", "failed"},
    "failed": {"awaiting_queue", "refunded"},
    "completed": set(),
    "refunded": set(),
    "cancelled": set(),
}


def purchase_plan_with_coin_atomic(user_id, plan_id, platform, fulfillment_mode,
                                   locket_username="", contact_zalo=None,
                                   contact_facebook=None, idempotency_key=None,
                                   coupon_code=None):
    """Debit Coin and create exactly one activation order in one transaction.

    The fulfillment mode is resolved again from the persisted plan so callers
    cannot force a cheaper/easier delivery path. Reusing an idempotency key is
    allowed only when every purchase input matches the original order.
    """
    if not idempotency_key:
        return ("error", "idempotency_key_required")

    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        plan_row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan_row or not plan_row["is_active"]:
            conn.execute("ROLLBACK")
            return ("error", "plan_unavailable")
        plan = _format_plan_row(plan_row, public=False)
        if plan.get("inventory_status") == "out_of_stock":
            conn.execute("ROLLBACK")
            return ("error", "out_of_stock")
        if platform not in ("ios", "android"):
            conn.execute("ROLLBACK")
            return ("error", "invalid_platform")
        if plan["supported_platforms"] not in ("all", platform):
            conn.execute("ROLLBACK")
            return ("error", "platform_not_supported")

        resolved_mode = resolve_plan_fulfillment(plan, platform)
        if fulfillment_mode != resolved_mode:
            conn.execute("ROLLBACK")
            return ("error", "fulfillment_mode_mismatch")

        # Normalize the requested code before the idempotency lookup. A replay
        # must return the original order even if the coupon has since expired,
        # been disabled, reached its quota, or had its discount edited.
        normalized_coupon_code = None
        if coupon_code:
            from . import coupon_service
            try:
                normalized_coupon_code = coupon_service.normalize_code(coupon_code)
            except ValueError as exc:
                conn.execute("ROLLBACK")
                return ("coupon_error", {"error": "invalid_code_format", "msg": str(exc)})

        existing_tx = conn.execute(
            "SELECT * FROM wallet_transactions WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing_tx:
            existing_order = None
            if existing_tx["reference_type"] == "activation_order" and existing_tx["reference_id"]:
                existing_order = conn.execute(
                    "SELECT * FROM activation_orders WHERE id = ?",
                    (existing_tx["reference_id"],),
                ).fetchone()
            expected = (
                existing_order
                and existing_order["user_id"] == user_id
                and existing_order["plan_id"] == plan_id
                and existing_order["platform"] == platform
                and existing_order["fulfillment_mode_snapshot"] == resolved_mode
                and (existing_order["locket_username"] or "") == (locket_username or "").strip()
                and (existing_order["contact_zalo"] or "") == (contact_zalo or "").strip()
                and (existing_order["contact_facebook"] or "") == (contact_facebook or "").strip()
                and (existing_order["coupon_code_snapshot"] or "") == (normalized_coupon_code or "")
            )
            if not expected:
                conn.execute("ROLLBACK")
                return ("idempotency_conflict", "idempotency_key_reused_with_different_payload")
            conn.execute("COMMIT")
            return ("idempotent", {
                "order": dict(existing_order),
                "remaining_balance": existing_tx["balance_after"],
            })

        # Resolve coupon quote only for a new purchase.
        coupon_info = None
        quote = None
        if normalized_coupon_code:
            from . import coupon_service
            is_valid, c_dict, q_dict, err_code, err_msg = coupon_service.validate_and_quote_coupon(
                conn, normalized_coupon_code, plan_id, user_id, now=now
            )
            if not is_valid:
                conn.execute("ROLLBACK")
                return ("coupon_error", {"error": err_code, "msg": err_msg})
            coupon_info = c_dict
            quote = q_dict

        price_vnd = quote["final_vnd"] if quote else plan["price_vnd"]
        price_coin = quote["final_coin"] if quote else int(plan["price_coin"])
        orig_vnd = quote["original_vnd"] if quote else plan["price_vnd"]
        orig_coin = quote["original_coin"] if quote else int(plan["price_coin"])
        disc_vnd = quote["discount_vnd"] if quote else 0
        disc_coin = quote["discount_coin"] if quote else 0
        coupon_id = coupon_info["id"] if coupon_info else None
        coupon_code_snapshot = coupon_info["code"] if coupon_info else None

        wallet = conn.execute(
            "SELECT balance_coin FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not wallet:
            conn.execute(
                "INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (?, 0, ?)",
                (user_id, now),
            )
            balance_before = 0
        else:
            balance_before = wallet["balance_coin"]
        if balance_before < price_coin:
            conn.execute("ROLLBACK")
            return ("insufficient_balance", {
                "current_balance": balance_before,
                "required_coin": price_coin,
                "shortage_coin": price_coin - balance_before,
            })

        initial_status = {
            "auto_activation": "awaiting_queue",
            "manual_contact": "paid",
            "apk_download": "completed",
        }[resolved_mode]
        cursor = conn.execute(
            """INSERT INTO activation_orders
               (user_id, plan_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot,
                price_vnd_snapshot, price_coin_snapshot, payment_method, payment_order_id,
                platform, locket_username, fulfillment_mode_snapshot, contact_zalo,
                contact_facebook, status, created_at, updated_at,
                original_price_vnd_snapshot, original_price_coin_snapshot,
                discount_vnd_snapshot, discount_coin_snapshot, coupon_id, coupon_code_snapshot)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'coin', NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, plan_id, plan["name"], plan["product_id"], plan["duration_days"],
                price_vnd, price_coin, platform, (locket_username or "").strip(),
                resolved_mode, (contact_zalo or "").strip() or None,
                (contact_facebook or "").strip() or None, initial_status, now, now,
                orig_vnd, orig_coin, disc_vnd, disc_coin, coupon_id, coupon_code_snapshot,
            ),
        )
        order_id = cursor.lastrowid
        balance_after = balance_before - price_coin
        conn.execute(
            "UPDATE wallets SET balance_coin = ?, updated_at = ? WHERE user_id = ?",
            (balance_after, now, user_id),
        )
        conn.execute(
            """INSERT INTO wallet_transactions
               (user_id, type, amount_coin, balance_before, balance_after,
                reference_type, reference_id, description, idempotency_key, created_at)
               VALUES (?, 'purchase', ?, ?, ?, 'activation_order', ?, ?, ?, ?)""",
            (
                user_id, -price_coin, balance_before, balance_after, str(order_id),
                f"Mua gói {plan['name']}", idempotency_key, now,
            ),
        )
        if coupon_info:
            from . import coupon_service
            coupon_service.record_coin_redemption(
                conn=conn,
                coupon_id=coupon_id,
                user_id=user_id,
                activation_order_id=order_id,
                original_vnd=orig_vnd,
                discount_vnd=disc_vnd,
                final_vnd=price_vnd,
                idempotency_key=f"coin_act_{order_id}",
                now=now,
            )
        order = conn.execute(
            "SELECT * FROM activation_orders WHERE id = ?", (order_id,)
        ).fetchone()
        conn.execute("COMMIT")
        return ("ok", {"order": dict(order), "remaining_balance": balance_after})
    except ValueError as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(exc))
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(exc))

def create_activation_order(user_id, plan_id, payment_method='coin', platform='ios', locket_username=None,
                            payment_order_id=None, initial_status=None, fulfillment_mode=None,
                            contact_zalo=None, contact_facebook=None, **kwargs):
    """Create an activation order with immutable plan snapshot."""
    if locket_username is None:
        locket_username = kwargs.get("target_username") or kwargs.get("username") or ""
    if not payment_method and "payment_method" in kwargs:
        payment_method = kwargs["payment_method"]
    if "platform" in kwargs:
        platform = kwargs["platform"]
    if platform == "all":
        platform = "ios"

    plan = get_plan_by_id(plan_id, public=False)
    if not plan:
        raise ValueError("Kế hoạch dịch vụ không tồn tại.")
    if not plan["is_active"]:
        raise ValueError("Gói dịch vụ này hiện đang tạm ngừng cung cấp.")
    if plan.get("inventory_status") == "out_of_stock":
        raise ValueError("Gói dịch vụ này hiện đang tạm hết hàng.")

    # Validate platform compatibility
    if plan["supported_platforms"] != "all" and plan["supported_platforms"] != platform:
        raise ValueError(f"Gói này chỉ hỗ trợ nền tảng {plan['supported_platforms']}.")

    if payment_method not in ('coin', 'qr'):
        raise ValueError("payment_method must be 'coin' or 'qr'")
    if platform not in ('ios', 'android'):
        raise ValueError("platform must be 'ios' or 'android'")

    resolved_mode = resolve_plan_fulfillment(plan, platform)
    if fulfillment_mode is not None and fulfillment_mode != resolved_mode:
        raise ValueError("fulfillment mode does not match plan configuration")
    fulfillment_mode = resolved_mode

    if initial_status is None:
        if payment_method == "qr":
            initial_status = "awaiting_payment"
        else:
            initial_status = {
                "auto_activation": "awaiting_queue",
                "manual_contact": "paid",
                "apk_download": "completed",
            }[fulfillment_mode]

    now = time.time()
    conn = get_conn()

    cursor = conn.execute(
        """INSERT INTO activation_orders
           (user_id, plan_id, plan_name_snapshot, product_id_snapshot, duration_days_snapshot,
            price_vnd_snapshot, price_coin_snapshot, payment_method, payment_order_id,
            platform, locket_username, fulfillment_mode_snapshot, contact_zalo,
            contact_facebook, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            plan_id,
            plan["name"],
            plan["product_id"],
            plan["duration_days"],
            plan["price_vnd"],
            plan["price_coin"],
            payment_method,
            payment_order_id,
            platform,
            locket_username.strip(),
            fulfillment_mode,
            (contact_zalo or "").strip() or None,
            (contact_facebook or "").strip() or None,
            initial_status,
            now,
            now,
        ),
    )
    return cursor.lastrowid


def get_activation_order_by_id(order_id, user_id=None):
    conn = get_conn()
    if user_id is not None:
        row = conn.execute(
            "SELECT * FROM activation_orders WHERE id = ? AND user_id = ?",
            (order_id, user_id),
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM activation_orders WHERE id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


get_activation_order = get_activation_order_by_id


def normalize_locket_username(raw):
    if not raw:
        return ""
    s = str(raw).strip()
    if s.startswith("@"):
        s = s[1:]
    if "locket.cam/" in s:
        s = s.split("locket.cam/")[-1].split("?")[0].strip("/")
    elif "locket.camera/links/" in s:
        s = s.split("locket.camera/links/")[-1].split("?")[0].strip("/")
    return s.strip().lower()


def has_prior_activation_for_locket_username(username):
    if not username or not str(username).strip():
        return (False, None)
    key = str(username).strip().lower()
    conn = get_conn()
    row = conn.execute(
        """SELECT id, status, locket_username, created_at FROM activation_orders
           WHERE LOWER(locket_username)=? AND status IN ('paid','awaiting_queue','queued','processing','completed')
           ORDER BY id DESC LIMIT 1""",
        (key,),
    ).fetchone()
    if row:
        return (True, dict(row))
    q = conn.execute(
        """SELECT client_id, status FROM queue_requests
           WHERE LOWER(username)=? AND status IN ('waiting','processing','completed')
           ORDER BY added_at DESC LIMIT 1""",
        (key,),
    ).fetchone()
    if q:
        return (True, {"queue_client_id": q["client_id"], "status": q["status"]})
    return (False, None)


def get_activation_order_by_payment_code(payment_code):
    if not payment_code:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT a.* FROM activation_orders a
           JOIN payment_orders p ON a.payment_order_id = p.id
           WHERE p.payment_code = ? OR p.transfer_code = ?
           ORDER BY a.id DESC LIMIT 1""",
        (payment_code, payment_code),
    ).fetchone()
    if row:
        return dict(row)
    row2 = conn.execute(
        "SELECT * FROM activation_orders WHERE payment_order_id = ? ORDER BY id DESC LIMIT 1",
        (payment_code,),
    ).fetchone()
    return dict(row2) if row2 else None


def list_activation_orders_by_user(user_id, limit=20, offset=0):
    try:
        limit = max(1, min(50, int(limit)))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        limit = 20
        offset = 0

    conn = get_conn()
    total_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM activation_orders WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    total = total_row["cnt"] if total_row else 0

    rows = conn.execute(
        """SELECT * FROM activation_orders
           WHERE user_id = ?
           ORDER BY created_at DESC, id DESC
           LIMIT ? OFFSET ?""",
        (user_id, limit, offset),
    ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(rows)) < total,
        }
    }


def update_activation_order_status(order_id, new_status, queue_client_id=None):
    """Enforce state machine transition for activation order."""
    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT status FROM activation_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return ("error", "not_found")

        current_status = row["status"]
        if new_status != current_status:
            allowed = VALID_ACT_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                conn.execute("ROLLBACK")
                return ("invalid_transition", f"Cannot transition from '{current_status}' to '{new_status}'.")

        updates = ["status = ?", "updated_at = ?"]
        params = [new_status, now]
        if queue_client_id is not None:
            updates.append("queue_client_id = ?")
            params.append(queue_client_id)
        params.append(order_id)

        conn.execute(
            f"UPDATE activation_orders SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.execute("COMMIT")
        return ("ok", None)
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(e))


def admin_transition_manual_order(order_id, action, admin_user_id, note=None,
                                  ip_address=None, user_agent=None):
    """Start or complete a paid manual-contact order with an audit record."""
    transitions = {
        "start": ("paid", "processing"),
        "complete": ("processing", "completed"),
    }
    if action not in transitions:
        return ("error", "invalid_action")
    note = (note or "").strip()
    if len(note) > 500:
        return ("error", "admin_note_too_long")

    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM activation_orders WHERE id = ?", (order_id,)
        ).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return ("not_found", "not_found")
        before = dict(row)
        if row["fulfillment_mode_snapshot"] != "manual_contact":
            conn.execute("ROLLBACK")
            return ("error", "not_manual_contact")

        expected_status, next_status = transitions[action]
        if row["status"] == next_status:
            conn.execute("COMMIT")
            return ("idempotent", before)
        if row["status"] != expected_status:
            conn.execute("ROLLBACK")
            return ("invalid_transition", f"{row['status']}->{next_status}")

        conn.execute(
            """UPDATE activation_orders
               SET status = ?, admin_note = ?, handled_by_admin_id = ?, handled_at = ?, updated_at = ?
               WHERE id = ?""",
            (next_status, note or row["admin_note"], admin_user_id, now, now, order_id),
        )
        updated = conn.execute(
            "SELECT * FROM activation_orders WHERE id = ?", (order_id,)
        ).fetchone()
        record_admin_audit_log(
            admin_user_id=admin_user_id,
            action=f"manual_order_{action}",
            entity_type="activation_order",
            entity_id=order_id,
            before_data=before,
            after_data=dict(updated),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        conn.execute("COMMIT")
        return ("ok", dict(updated))
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(exc))


def get_manual_pending_orders_count() -> int:
    """Return count of manual_contact activation orders currently waiting in 'paid' status."""
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM activation_orders WHERE fulfillment_mode_snapshot = 'manual_contact' AND status = 'paid'"
    ).fetchone()
    return int(row["cnt"]) if row else 0


def admin_cancel_manual_order(order_id, reason, admin_user_id, ip_address=None, user_agent=None):
    """Cancel a manual_contact order with a mandatory reason (5-500 chars). Does NOT refund."""
    reason = (reason or "").strip()
    if len(reason) < 5 or len(reason) > 500:
        return ("error", "invalid_reason")

    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM activation_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return ("not_found", "not_found")
        before = dict(row)
        if row["fulfillment_mode_snapshot"] != "manual_contact":
            conn.execute("ROLLBACK")
            return ("error", "not_manual_contact")
        if row["status"] in ("completed", "refunded"):
            conn.execute("ROLLBACK")
            return ("invalid_state_transition", f"Không thể hủy đơn ở trạng thái {row['status']}.")
        if row["status"] == "cancelled":
            conn.execute("ROLLBACK")
            return ("invalid_state_transition", "Đơn đã bị hủy trước đó.")

        note = (row["admin_note"] or "").strip()
        new_note = f"{note}\n[Hủy đơn: {reason}]".strip() if note else f"[Hủy đơn: {reason}]"

        conn.execute(
            """UPDATE activation_orders
               SET status = 'cancelled', admin_note = ?, handled_by_admin_id = ?, handled_at = ?, updated_at = ?
               WHERE id = ?""",
            (new_note, admin_user_id, now, now, order_id),
        )
        updated = conn.execute("SELECT * FROM activation_orders WHERE id = ?", (order_id,)).fetchone()
        record_admin_audit_log(
            admin_user_id=admin_user_id,
            action="manual_order_cancel",
            entity_type="activation_order",
            entity_id=order_id,
            before_data=before,
            after_data=dict(updated),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        conn.execute("COMMIT")
        return ("ok", dict(updated))
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(exc))


def admin_refund_manual_order(order_id, reason, admin_user_id, confirmed_external_refund=False,
                              refund_reference=None, ip_address=None, user_agent=None):
    """Refund a manual_contact order (atomic coin return for coin, external reference validation for QR)."""
    reason = (reason or "").strip()
    if len(reason) < 5 or len(reason) > 500:
        return ("error", "invalid_reason")

    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM activation_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return ("not_found", "not_found")
        before = dict(row)

        if row["status"] == "refunded":
            conn.execute("ROLLBACK")
            return ("already_refunded", "Đơn đã được hoàn tiền trước đó.")
        if row["status"] == "completed":
            conn.execute("ROLLBACK")
            return ("invalid_state_transition", "Không thể hoàn tiền đơn đã hoàn tất.")
        if row["status"] not in ("paid", "processing", "failed", "cancelled"):
            conn.execute("ROLLBACK")
            return ("invalid_state_transition", f"Không thể hoàn tiền đơn ở trạng thái {row['status']}.")

        payment_method = row["payment_method"]
        note = (row["admin_note"] or "").strip()

        if payment_method == "coin":
            user_id = row["user_id"]
            amount_coin = row["price_coin_snapshot"]
            idempotency_key = f"admin_refund_manual_{order_id}"

            # Check if this refund tx was already applied
            existing_tx = conn.execute(
                "SELECT * FROM wallet_transactions WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if existing_tx:
                conn.execute("ROLLBACK")
                return ("already_refunded", "Giao dịch hoàn Coin đã tồn tại.")

            wallet_row = conn.execute("SELECT balance_coin FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
            balance_before = wallet_row["balance_coin"] if wallet_row else 0
            balance_after = balance_before + amount_coin

            if wallet_row:
                conn.execute("UPDATE wallets SET balance_coin = ?, updated_at = ? WHERE user_id = ?",
                             (balance_after, now, user_id))
            else:
                conn.execute("INSERT INTO wallets (user_id, balance_coin, updated_at) VALUES (?, ?, ?)",
                             (user_id, balance_after, now))

            conn.execute(
                """INSERT INTO wallet_transactions
                   (user_id, type, amount_coin, balance_before, balance_after, reference_type, reference_id, description, idempotency_key, created_at)
                   VALUES (?, 'refund', ?, ?, ?, 'activation_order', ?, ?, ?, ?)""",
                (user_id, amount_coin, balance_before, balance_after, str(order_id),
                 f"Hoàn Coin đơn #{order_id}: {reason}", idempotency_key, now),
            )
            new_note = f"{note}\n[Hoàn Coin: {amount_coin} Coin - Lý do: {reason}]".strip() if note else f"[Hoàn Coin: {amount_coin} Coin - Lý do: {reason}]"

        elif payment_method == "qr":
            if not confirmed_external_refund:
                conn.execute("ROLLBACK")
                return ("error", "external_refund_confirmation_required")
            ref = (refund_reference or "").strip()
            if len(ref) < 3 or len(ref) > 200:
                conn.execute("ROLLBACK")
                return ("error", "refund_reference_required")
            new_note = f"{note}\n[Hoàn tiền QR: {reason} | Mã GD: {ref}]".strip() if note else f"[Hoàn tiền QR: {reason} | Mã GD: {ref}]"
        else:
            conn.execute("ROLLBACK")
            return ("error", "unsupported_payment_method")

        conn.execute(
            """UPDATE activation_orders
               SET status = 'refunded', admin_note = ?, handled_by_admin_id = ?, handled_at = ?, updated_at = ?
               WHERE id = ?""",
            (new_note, admin_user_id, now, now, order_id),
        )
        updated = conn.execute("SELECT * FROM activation_orders WHERE id = ?", (order_id,)).fetchone()
        record_admin_audit_log(
            admin_user_id=admin_user_id,
            action="manual_order_refund",
            entity_type="activation_order",
            entity_id=order_id,
            before_data=before,
            after_data=dict(updated),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        conn.execute("COMMIT")
        return ("ok", dict(updated))
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(exc))


def refund_activation_order_coin(order_id, reason="Hoàn Coin do đơn kích hoạt không thành công"):
    """Refund coins for an activation order paid via coin."""
    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM activation_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return ("error", "not_found")

        if row["payment_method"] != "coin":
            conn.execute("ROLLBACK")
            return ("error", "not_a_coin_order")

        if row["status"] == "refunded":
            conn.execute("ROLLBACK")
            return ("already_refunded", "Đơn đã được hoàn Coin trước đó.")

        if row["status"] not in ("failed", "awaiting_queue", "queued"):
            conn.execute("ROLLBACK")
            return ("error", f"Không thể hoàn tiền đơn ở trạng thái '{row['status']}'.")

        user_id = row["user_id"]
        amount_coin = row["price_coin_snapshot"]
        idempotency_key = f"refund_act_{order_id}"

        # Fetch wallet
        wallet_row = conn.execute("SELECT balance_coin FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        balance_before = wallet_row["balance_coin"] if wallet_row else 0
        balance_after = balance_before + amount_coin

        conn.execute(
            "UPDATE wallets SET balance_coin = ?, updated_at = ? WHERE user_id = ?",
            (balance_after, now, user_id),
        )

        conn.execute(
            """INSERT INTO wallet_transactions
               (user_id, type, amount_coin, balance_before, balance_after,
                reference_type, reference_id, description, idempotency_key, created_at)
               VALUES (?, 'refund', ?, ?, ?, 'activation_order', ?, ?, ?, ?)""",
            (
                user_id,
                amount_coin,
                balance_before,
                balance_after,
                str(order_id),
                reason,
                idempotency_key,
                now,
            ),
        )

        conn.execute(
            "UPDATE activation_orders SET status = 'refunded', updated_at = ? WHERE id = ?",
            (now, order_id),
        )

        conn.execute("COMMIT")
        return ("ok", {"refunded_coin": amount_coin, "balance_after": balance_after})
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(e))


# ---- Admin User Management & Session Revocation ----

def revoke_all_user_sessions(user_id: int, reason: str = "admin_revoked"):
    """Revoke all auth sessions and refresh tokens belonging to user_id."""
    if not user_id:
        return
    conn = get_conn()
    now = time.time()
    rows = conn.execute(
        "SELECT family_id FROM auth_sessions WHERE user_id = ? AND revoked_at IS NULL",
        (user_id,),
    ).fetchall()
    family_ids = [r["family_id"] for r in rows]
    if family_ids:
        placeholders = ",".join("?" for _ in family_ids)
        conn.execute(
            f"UPDATE auth_sessions SET revoked_at = ?, revoke_reason = ? WHERE family_id IN ({placeholders})",
            [now, reason] + family_ids,
        )
        conn.execute(
            f"UPDATE refresh_tokens SET revoked_at = ? WHERE family_id IN ({placeholders}) AND revoked_at IS NULL",
            [now] + family_ids,
        )


def update_user_password(user_id: int, new_password_hash: str):
    """Update password_hash for a user."""
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user_id))


def update_user_role(user_id: int, role: str):
    """Update role for a user ('user' or 'admin')."""
    if role not in ("user", "admin"):
        raise ValueError("Invalid role")
    conn = get_conn()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def update_user_display_name(user_id: int, display_name: str):
    """Update display_name for a user."""
    conn = get_conn()
    conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name.strip()[:50], user_id))


def set_user_active(user_id: int, is_active: bool):
    """Enable or disable a user account."""
    conn = get_conn()
    conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))


def list_users_admin(query: str = None, role: str = None, is_active: bool = None, limit: int = 50, offset: int = 0):
    """List users for admin management with filtering, pagination, and wallet balances."""
    conn = get_conn()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    where = []
    params = []

    if query:
        q = f"%{query.strip().lower()}%"
        where.append("(LOWER(u.email) LIKE ? OR LOWER(u.username) LIKE ? OR LOWER(u.display_name) LIKE ?)")
        params.extend([q, q, q])
    if role and role in ("user", "admin"):
        where.append("u.role = ?")
        params.append(role)
    if is_active is not None:
        where.append("u.is_active = ?")
        params.append(1 if is_active else 0)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    total_row = conn.execute(f"SELECT COUNT(*) as total FROM users u {where_clause}", params).fetchone()
    total = total_row["total"] if total_row else 0

    sql = f"""
        SELECT u.id, u.email, u.username, u.display_name, u.role, u.is_active,
               u.avatar_url, (u.google_id IS NOT NULL AND u.google_id <> '') as has_google,
               u.created_at, u.last_login_at,
               COALESCE(w.balance_coin, 0) as balance_coin
        FROM users u
        LEFT JOIN wallets w ON u.id = w.user_id
        {where_clause}
        ORDER BY u.id DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, params + [limit, offset]).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_user_detail_admin(user_id: int):
    """Fetch user profile, wallet, and recent activity for admin view."""
    conn = get_conn()
    u = conn.execute(
        "SELECT id, email, username, display_name, role, is_active, avatar_url, "
        "(google_id IS NOT NULL AND google_id <> '') as has_google, created_at, last_login_at "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not u:
        return None
    user_dict = dict(u)

    wallet = get_or_create_wallet(user_id)
    user_dict["wallet"] = wallet

    act_rows = conn.execute(
        "SELECT * FROM activation_orders WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (user_id,),
    ).fetchall()
    user_dict["recent_orders"] = [dict(r) for r in act_rows]

    pay_rows = conn.execute(
        "SELECT * FROM payment_orders WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (user_id,),
    ).fetchall()
    user_dict["recent_payments"] = [dict(r) for r in pay_rows]

    rev_row = conn.execute(
        "SELECT * FROM reviews WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    user_dict["review"] = dict(rev_row) if rev_row else None

    return user_dict


# ---- Admin Audit Logs ----

def mask_zalo(phone: str | None) -> str:
    """Mask phone/Zalo numbers preserving prefix and suffix (e.g. 0912345678 -> 091***5678)."""
    if not phone:
        return ""
    raw = str(phone).strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7:
        return raw[:2] + "***" + raw[-2:] if len(raw) >= 4 else "***"
    return raw[:3] + "***" + raw[-4:]


def _redact_sensitive_keys(data):
    """Recursively redact secrets and sensitive credentials from data dict/list."""
    if not data:
        return data
    SENSITIVE_KEYS = {
        "password", "password_hash", "token", "access_token", "refresh_token",
        "raw_token", "secret", "csrf_token", "admin_csrf_token", "jwt",
        "cookie", "authorization", "id_token", "credential", "receipt",
        "contact_zalo", "contact_facebook", "zalo", "facebook", "phone", "phone_number",
    }
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                redacted[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                redacted[k] = _redact_sensitive_keys(v)
            else:
                redacted[k] = v
        return redacted
    elif isinstance(data, list):
        return [_redact_sensitive_keys(item) for item in data]
    return data


def record_admin_audit_log(admin_user_id: int, action: str, entity_type: str,
                           entity_id=None, before_data=None, after_data=None,
                           ip_address: str = None, user_agent: str = None) -> int:
    """Record a redacted admin audit log entry."""
    conn = get_conn()
    now = time.time()
    b_json = json.dumps(_redact_sensitive_keys(before_data), ensure_ascii=False) if before_data is not None else None
    a_json = json.dumps(_redact_sensitive_keys(after_data), ensure_ascii=False) if after_data is not None else None
    ua = (user_agent or "")[:255] if user_agent else None
    cursor = conn.execute(
        "INSERT INTO admin_audit_logs "
        "(admin_user_id, action, entity_type, entity_id, before_json, after_json, ip_address, user_agent, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            admin_user_id,
            action,
            entity_type,
            str(entity_id) if entity_id is not None else None,
            b_json,
            a_json,
            ip_address,
            ua,
            now,
        ),
    )
    return cursor.lastrowid


def list_admin_audit_logs(admin_user_id=None, action=None, entity_type=None, limit: int = 50, offset: int = 0):
    """List admin audit logs with filtering and pagination."""
    conn = get_conn()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    where = []
    params = []
    if admin_user_id:
        where.append("l.admin_user_id = ?")
        params.append(admin_user_id)
    if action:
        where.append("l.action = ?")
        params.append(action)
    if entity_type:
        where.append("l.entity_type = ?")
        params.append(entity_type)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    total_row = conn.execute(f"SELECT COUNT(*) as total FROM admin_audit_logs l {where_clause}", params).fetchone()
    total = total_row["total"] if total_row else 0

    sql = f"""
        SELECT l.*, u.username as admin_username, u.display_name as admin_display_name
        FROM admin_audit_logs l
        LEFT JOIN users u ON l.admin_user_id = u.id
        {where_clause}
        ORDER BY l.id DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, params + [limit, offset]).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        try:
            d["before"] = json.loads(d["before_json"]) if d.get("before_json") else None
        except Exception:
            d["before"] = None
        try:
            d["after"] = json.loads(d["after_json"]) if d.get("after_json") else None
        except Exception:
            d["after"] = None
        items.append(d)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---- Admin Activation Orders Management ----

def list_activation_orders_admin(status=None, platform=None, fulfillment_mode=None,
                                 query=None, limit: int = 50, offset: int = 0):
    """List activation orders with filtering, user information, and pagination."""
    conn = get_conn()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    where = []
    params = []

    if status and status != "all":
        where.append("o.status = ?")
        params.append(status)
    if platform and platform != "all":
        where.append("o.platform = ?")
        params.append(platform)
    if fulfillment_mode and fulfillment_mode != "all":
        where.append("o.fulfillment_mode_snapshot = ?")
        params.append(fulfillment_mode)
    if query:
        q = f"%{query.strip().lower()}%"
        where.append("(LOWER(o.locket_username) LIKE ? OR LOWER(COALESCE(o.contact_zalo, '')) LIKE ? OR LOWER(COALESCE(o.contact_facebook, '')) LIKE ? OR LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(o.plan_name_snapshot) LIKE ?)")
        params.extend([q, q, q, q, q, q])

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    total_row = conn.execute(
        f"SELECT COUNT(*) as total FROM activation_orders o LEFT JOIN users u ON o.user_id = u.id {where_clause}",
        params,
    ).fetchone()
    total = total_row["total"] if total_row else 0

    sql = f"""
        SELECT o.*, u.username as user_username, u.email as user_email, u.display_name as user_display_name
        FROM activation_orders o
        LEFT JOIN users u ON o.user_id = u.id
        {where_clause}
        ORDER BY o.id DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, params + [limit, offset]).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---- Admin Overview Analytics ----

def get_admin_overview_stats(range_str: str = "30d"):
    """Calculate dashboard overview metrics strictly in Asia/Bangkok timezone with zero-fill series."""
    valid_ranges = {"7d": 7, "30d": 30, "90d": 90}
    if range_str not in valid_ranges:
        range_str = "30d"
    range_days = valid_ranges[range_str]

    from datetime import datetime, timezone, timedelta
    tz_bkk = timezone(timedelta(hours=7))
    now_bkk = datetime.now(tz_bkk)
    start_date = (now_bkk - timedelta(days=range_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_ts = start_date.timestamp()

    conn = get_conn()

    # Cards metrics
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
    new_users = conn.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (start_ts,)).fetchone()[0]

    # Revenue only from paid payment_orders, avoiding double counting
    rev_row = conn.execute(
        "SELECT COALESCE(SUM(amount_vnd), 0) as rev, COUNT(*) as cnt "
        "FROM payment_orders WHERE status = 'paid' AND COALESCE(paid_at, created_at) >= ?",
        (start_ts,),
    ).fetchone()
    paid_revenue_vnd = int(rev_row["rev"])
    paid_payments = int(rev_row["cnt"])

    topup_revenue_vnd = int(conn.execute(
        "SELECT COALESCE(SUM(amount_vnd), 0) FROM payment_orders WHERE status = 'paid' AND purpose = 'wallet_topup' AND COALESCE(paid_at, created_at) >= ?",
        (start_ts,),
    ).fetchone()[0])

    plan_purchase_revenue_vnd = int(conn.execute(
        "SELECT COALESCE(SUM(amount_vnd), 0) FROM payment_orders WHERE status = 'paid' AND purpose = 'plan_purchase' AND COALESCE(paid_at, created_at) >= ?",
        (start_ts,),
    ).fetchone()[0])

    pending_payments = conn.execute(
        "SELECT COUNT(*) FROM payment_orders WHERE status = 'pending' AND created_at >= ?",
        (start_ts,),
    ).fetchone()[0]

    orders_row = conn.execute(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed, "
        "SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing, "
        "SUM(CASE WHEN status IN ('queued', 'awaiting_queue') THEN 1 ELSE 0 END) as queued, "
        "SUM(CASE WHEN status IN ('failed', 'cancelled') THEN 1 ELSE 0 END) as failed "
        "FROM activation_orders WHERE created_at >= ?",
        (start_ts,),
    ).fetchone()
    total_orders = int(orders_row["total"] or 0)
    completed_orders = int(orders_row["completed"] or 0)
    processing_orders = int(orders_row["processing"] or 0)
    queued_orders = int(orders_row["queued"] or 0)
    failed_orders = int(orders_row["failed"] or 0)

    completion_rate = round((completed_orders / total_orders * 100), 1) if total_orders > 0 else 0.0

    total_wallet_balance_coin = int(conn.execute("SELECT COALESCE(SUM(balance_coin), 0) FROM wallets").fetchone()[0])
    users_with_coin = int(conn.execute("SELECT COUNT(*) FROM wallets WHERE balance_coin > 0").fetchone()[0])

    total_reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    pending_reviews = conn.execute("SELECT COUNT(*) FROM reviews WHERE status = 'pending'").fetchone()[0]
    avg_row = conn.execute("SELECT AVG(rating) FROM reviews WHERE status = 'approved'").fetchone()[0]
    average_rating = round(float(avg_row or 0), 1) if avg_row else 5.0

    queue_waiting = conn.execute("SELECT COUNT(*) FROM queue_requests WHERE status = 'waiting'").fetchone()[0]
    queue_processing = conn.execute("SELECT COUNT(*) FROM queue_requests WHERE status = 'processing'").fetchone()[0]

    # Series: Build list of dates for the range
    date_keys = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(range_days)]
    series_map = {d: {
        "date": d,
        "revenue_vnd": 0,
        "paid_payments": 0,
        "orders": 0,
        "completed_orders": 0,
        "new_users": 0,
    } for d in date_keys}

    # Aggregate revenue by Asia/Bangkok date (+7 hours)
    rev_by_date = conn.execute(
        "SELECT strftime('%Y-%m-%d', datetime(COALESCE(paid_at, created_at), 'unixepoch', '+7 hours')) as d, "
        "SUM(amount_vnd) as total, COUNT(*) as cnt "
        "FROM payment_orders WHERE status = 'paid' AND COALESCE(paid_at, created_at) >= ? "
        "GROUP BY d",
        (start_ts,),
    ).fetchall()
    for r in rev_by_date:
        d = r["d"]
        if d in series_map:
            series_map[d]["revenue_vnd"] = int(r["total"] or 0)
            series_map[d]["paid_payments"] = int(r["cnt"] or 0)

    # Aggregate orders by date
    orders_by_date = conn.execute(
        "SELECT strftime('%Y-%m-%d', datetime(created_at, 'unixepoch', '+7 hours')) as d, "
        "COUNT(*) as total, "
        "SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as comp "
        "FROM activation_orders WHERE created_at >= ? "
        "GROUP BY d",
        (start_ts,),
    ).fetchall()
    for r in orders_by_date:
        d = r["d"]
        if d in series_map:
            series_map[d]["orders"] = int(r["total"] or 0)
            series_map[d]["completed_orders"] = int(r["comp"] or 0)

    # Aggregate new users by date
    users_by_date = conn.execute(
        "SELECT strftime('%Y-%m-%d', datetime(created_at, 'unixepoch', '+7 hours')) as d, "
        "COUNT(*) as total "
        "FROM users WHERE created_at >= ? "
        "GROUP BY d",
        (start_ts,),
    ).fetchall()
    for r in users_by_date:
        d = r["d"]
        if d in series_map:
            series_map[d]["new_users"] = int(r["total"] or 0)

    series = [series_map[d] for d in date_keys]

    # Order status breakdown
    status_rows = conn.execute(
        "SELECT status, COUNT(*) as count FROM activation_orders WHERE created_at >= ? GROUP BY status",
        (start_ts,),
    ).fetchall()
    order_status_breakdown = [{"status": r["status"], "count": r["count"]} for r in status_rows]

    # Platform breakdown
    plat_rows = conn.execute(
        "SELECT platform, COUNT(*) as count FROM activation_orders WHERE created_at >= ? GROUP BY platform",
        (start_ts,),
    ).fetchall()
    platform_breakdown = [{"platform": r["platform"], "count": r["count"]} for r in plat_rows]

    # Payment method breakdown
    method_rows = conn.execute(
        "SELECT payment_method, COUNT(*) as count FROM activation_orders WHERE created_at >= ? GROUP BY payment_method",
        (start_ts,),
    ).fetchall()
    payment_method_breakdown = [{"payment_method": r["payment_method"], "count": r["count"]} for r in method_rows]

    # Recent orders
    recent_orders_rows = conn.execute(
        "SELECT o.*, u.username as user_username, u.email as user_email "
        "FROM activation_orders o LEFT JOIN users u ON o.user_id = u.id "
        "ORDER BY o.id DESC LIMIT 8",
    ).fetchall()
    recent_orders = [dict(r) for r in recent_orders_rows]

    # Recent payments
    recent_pay_rows = conn.execute(
        "SELECT p.*, u.username as user_username, u.email as user_email "
        "FROM payment_orders p LEFT JOIN users u ON p.user_id = u.id "
        "ORDER BY p.id DESC LIMIT 8",
    ).fetchall()
    recent_payments = [dict(r) for r in recent_pay_rows]

    # Recent audit logs
    recent_audit_rows = conn.execute(
        "SELECT l.*, u.username as admin_username FROM admin_audit_logs l LEFT JOIN users u ON l.admin_user_id = u.id ORDER BY l.id DESC LIMIT 5"
    ).fetchall()
    recent_audits = [dict(r) for r in recent_audit_rows]

    cards_data = {
        # Canonical flat cards
        "total_users": total_users,
        "active_users": active_users,
        "new_users": new_users,
        "paid_revenue_vnd": paid_revenue_vnd,
        "topup_revenue_vnd": topup_revenue_vnd,
        "plan_purchase_revenue_vnd": plan_purchase_revenue_vnd,
        "paid_payments": paid_payments,
        "pending_payments": pending_payments,
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "processing_orders": processing_orders,
        "queued_orders": queued_orders,
        "failed_orders": failed_orders,
        "completion_rate": completion_rate,
        "total_wallet_balance_coin": total_wallet_balance_coin,
        "users_with_coin": users_with_coin,
        "total_reviews": total_reviews,
        "pending_reviews": pending_reviews,
        "average_rating": average_rating,
        "queue_waiting": queue_waiting,
        "queue_processing": queue_processing,
        "active_workers": 0,

        # Backward compatibility nested structure
        "activation_orders": {
            "total": total_orders,
            "completed": completed_orders,
            "processing": processing_orders,
            "queued": queued_orders,
            "failed": failed_orders,
        },
        "payments": {
            "total_paid": paid_payments,
            "pending": pending_payments,
            "revenue_vnd": paid_revenue_vnd,
            "topup_revenue_vnd": topup_revenue_vnd,
            "plan_purchase_revenue_vnd": plan_purchase_revenue_vnd,
        },
        "wallet": {
            "total_balance_coin": total_wallet_balance_coin,
            "total_users_with_coin": users_with_coin,
        },
        "reviews": {
            "total": total_reviews,
            "pending": pending_reviews,
            "average_rating": average_rating,
        },
        "queue": {
            "total_waiting": queue_waiting,
            "total_processing": queue_processing,
        },
    }

    # Backward compatibility charts map
    charts_data = {
        "revenue_series": [{"date": s["date"], "revenue_vnd": s["revenue_vnd"], "order_count": s["orders"]} for s in series],
        "registrations_series": [{"date": s["date"], "count": s["new_users"]} for s in series],
        "orders_by_status": {r["status"]: r["count"] for r in order_status_breakdown},
        "orders_by_platform": {r["platform"]: r["count"] for r in platform_breakdown},
        "payments_by_status": {},
    }

    return {
        "success": True,
        "range": range_str,
        "timezone": "Asia/Bangkok",
        "generated_at": int(now_bkk.timestamp()),
        "cards": cards_data,
        "series": series,
        "order_status_breakdown": order_status_breakdown,
        "platform_breakdown": platform_breakdown,
        "payment_method_breakdown": payment_method_breakdown,
        "recent_orders": recent_orders,
        "recent_payments": recent_payments,
        # Backward compatibility
        "charts": charts_data,
        "recent": {
            "orders": recent_orders,
            "payments": recent_payments,
            "audit_logs": recent_audits,
        },
    }



# ---- Coupon Management Database Helpers ----

_COUPON_UNSET = object()


def _coupon_int(value, field_name, *, minimum=None, multiple=None):
    """Parse a coupon integer without silently truncating floats or booleans."""
    if type(value) is not int:
        raise ValueError(f"{field_name} phải là số nguyên.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field_name} phải lớn hơn hoặc bằng {minimum}.")
    if multiple is not None and value % multiple != 0:
        raise ValueError(f"{field_name} phải chia hết cho {multiple:,}.")
    return value


def _coupon_optional_positive_int(value, field_name):
    if value is None:
        return None
    return _coupon_int(value, field_name, minimum=1)


def _coupon_optional_money(value, field_name):
    if value is None:
        return None
    return _coupon_int(value, field_name, minimum=1000, multiple=1000)


def _coupon_timestamp(value, field_name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} không hợp lệ.")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} không hợp lệ.")
    return parsed


def _validated_coupon_plan_ids(conn, plan_ids):
    if plan_ids is None:
        return None
    if not isinstance(plan_ids, list):
        raise ValueError("Danh sách gói áp dụng phải là một mảng.")
    normalized = []
    seen = set()
    for plan_id in plan_ids:
        parsed = _coupon_int(plan_id, "ID gói áp dụng", minimum=1)
        if parsed not in seen:
            normalized.append(parsed)
            seen.add(parsed)
    if normalized:
        placeholders = ",".join("?" for _ in normalized)
        rows = conn.execute(
            f"SELECT id FROM plans WHERE id IN ({placeholders})", tuple(normalized)
        ).fetchall()
        found = {row["id"] for row in rows}
        missing = [plan_id for plan_id in normalized if plan_id not in found]
        if missing:
            raise ValueError(f"Không tìm thấy gói áp dụng có ID: {', '.join(map(str, missing))}.")
    return normalized

def get_coupon_by_id(coupon_id, conn=None):
    c = conn or get_conn()
    row = c.execute("SELECT * FROM coupons WHERE id = ?", (coupon_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    rules = c.execute("SELECT plan_id FROM coupon_plan_rules WHERE coupon_id = ?", (coupon_id,)).fetchall()
    d["applicable_plan_ids"] = [r["plan_id"] for r in rules]
    return d


def get_coupon_by_code(code, conn=None):
    from . import coupon_service
    try:
        norm = coupon_service.normalize_code(code)
    except ValueError:
        return None
    c = conn or get_conn()
    row = c.execute("SELECT * FROM coupons WHERE normalized_code = ?", (norm,)).fetchone()
    if not row:
        return None
    d = dict(row)
    rules = c.execute("SELECT plan_id FROM coupon_plan_rules WHERE coupon_id = ?", (d["id"],)).fetchall()
    d["applicable_plan_ids"] = [r["plan_id"] for r in rules]
    return d


def list_coupons(search=None, status_filter=None, limit=50, offset=0, conn=None):
    c = conn or get_conn()
    from . import coupon_service
    coupon_service.sweep_expired_reservations(c)
    query = "SELECT * FROM coupons"
    params = []
    where_clauses = []

    if search:
        search_pattern = f"%{str(search).strip()}%"
        where_clauses.append("(code LIKE ? OR name LIKE ?)")
        params.extend([search_pattern, search_pattern])

    now_ts = time.time()
    if status_filter == "active":
        where_clauses.append("is_active = 1 AND (starts_at IS NULL OR starts_at <= ?) AND (ends_at IS NULL OR ends_at >= ?)")
        params.extend([now_ts, now_ts])
    elif status_filter == "inactive":
        where_clauses.append("is_active = 0")
    elif status_filter == "upcoming":
        where_clauses.append("starts_at > ?")
        params.append(now_ts)
    elif status_filter == "expired":
        where_clauses.append("ends_at < ?")
        params.append(now_ts)
    elif status_filter == "exhausted":
        where_clauses.append(
            "usage_limit_total IS NOT NULL AND "
            "(SELECT COUNT(*) FROM coupon_redemptions cr "
            " WHERE cr.coupon_id = coupons.id "
            " AND cr.status IN ('reserved', 'redeemed')) >= usage_limit_total"
        )

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = c.execute(query, tuple(params)).fetchall()
    results = []
    for r in rows:
        item = dict(r)
        cid = item["id"]
        counts = c.execute(
            """SELECT
               SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved_count,
               SUM(CASE WHEN status = 'redeemed' THEN 1 ELSE 0 END) as redeemed_count,
               SUM(CASE WHEN status = 'released' THEN 1 ELSE 0 END) as released_count
               FROM coupon_redemptions WHERE coupon_id = ?""",
            (cid,),
        ).fetchone()
        item["reserved_count"] = counts["reserved_count"] or 0
        item["redeemed_count"] = counts["redeemed_count"] or 0
        item["released_count"] = counts["released_count"] or 0

        rules = c.execute("SELECT plan_id FROM coupon_plan_rules WHERE coupon_id = ?", (cid,)).fetchall()
        item["applicable_plan_ids"] = [pr["plan_id"] for pr in rules]

        total_used = item["reserved_count"] + item["redeemed_count"]
        item["total_used"] = total_used
        item["is_exhausted"] = (
            item["usage_limit_total"] is not None and total_used >= item["usage_limit_total"]
        )
        results.append(item)

    count_query = "SELECT COUNT(*) as total FROM coupons"
    if where_clauses:
        count_query += " WHERE " + " AND ".join(where_clauses)
    total_count = c.execute(count_query, tuple(params[:len(params)-2])).fetchone()["total"]

    return results, total_count


def create_coupon(code, name, discount_type, discount_value, description=None,
                  max_discount_vnd=None, min_order_vnd=0, usage_limit_total=None,
                  usage_limit_per_user=None, starts_at=None, ends_at=None,
                  is_active=1, plan_ids=None, admin_user_id=None):
    from . import coupon_service
    norm = coupon_service.normalize_code(code)

    if not name or len(str(name).strip()) == 0:
        raise ValueError("Tên mã giảm giá không được để trống.")
    if len(str(name).strip()) > 100:
        raise ValueError("Tên mã giảm giá không được quá 100 ký tự.")

    if discount_type == "fixed":
        discount_type = "fixed_vnd"
    if discount_type not in ("percent", "fixed_vnd"):
        raise ValueError("Loại giảm giá phải là 'percent' hoặc 'fixed_vnd'.")

    discount_value = _coupon_int(discount_value, "Mức giảm giá", minimum=1)
    if discount_type == "percent" and not (1 <= discount_value <= 99):
        raise ValueError("Mức giảm phần trăm phải từ 1% đến 99%.")
    if discount_type == "fixed_vnd" and (discount_value < 1000 or discount_value % 1000 != 0):
        raise ValueError("Mức giảm cố định phải chia hết cho 1.000 VND và tối thiểu 1.000 VND.")

    max_discount_vnd = _coupon_optional_money(max_discount_vnd, "Mức giảm tối đa")
    min_order_vnd = _coupon_int(min_order_vnd, "Giá trị đơn tối thiểu", minimum=0, multiple=1000)
    usage_limit_total = _coupon_optional_positive_int(usage_limit_total, "Tổng lượt sử dụng")
    usage_limit_per_user = _coupon_optional_positive_int(
        usage_limit_per_user, "Lượt sử dụng mỗi khách"
    )
    starts_at = _coupon_timestamp(starts_at, "Thời gian bắt đầu")
    ends_at = _coupon_timestamp(ends_at, "Thời gian kết thúc")

    if starts_at and ends_at and ends_at <= starts_at:
        raise ValueError("Thời gian kết thúc phải sau thời gian bắt đầu.")

    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id FROM coupons WHERE normalized_code = ?", (norm,)).fetchone()
        if existing:
            conn.execute("ROLLBACK")
            raise ValueError(f"Mã giảm giá '{norm}' đã tồn tại trong hệ thống.")

        valid_plan_ids = _validated_coupon_plan_ids(conn, plan_ids if plan_ids is not None else [])
        cur = conn.execute(
            """INSERT INTO coupons
               (code, normalized_code, name, description, discount_type, discount_value,
                max_discount_vnd, min_order_vnd, usage_limit_total, usage_limit_per_user,
                starts_at, ends_at, is_active, created_by_admin_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                norm,
                norm,
                str(name).strip(),
                str(description).strip() if description else None,
                discount_type,
                discount_value,
                max_discount_vnd,
                min_order_vnd,
                usage_limit_total,
                usage_limit_per_user,
                starts_at,
                ends_at,
                1 if is_active else 0,
                admin_user_id,
                now,
                now,
            ),
        )
        new_id = cur.lastrowid

        if valid_plan_ids:
            for pid in valid_plan_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO coupon_plan_rules (coupon_id, plan_id) VALUES (?, ?)",
                    (new_id, pid),
                )

        conn.execute("COMMIT")
        return get_coupon_by_id(new_id)
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise


def update_coupon(coupon_id, name=None, description=None, discount_type=None,
                  discount_value=None, max_discount_vnd=_COUPON_UNSET,
                  min_order_vnd=_COUPON_UNSET, usage_limit_total=_COUPON_UNSET,
                  usage_limit_per_user=_COUPON_UNSET, starts_at=_COUPON_UNSET,
                  ends_at=_COUPON_UNSET, is_active=None, plan_ids=None):
    conn = get_conn()
    now = time.time()
    try:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT * FROM coupons WHERE id = ?", (coupon_id,)).fetchone()
        if not current:
            conn.execute("ROLLBACK")
            raise ValueError("Không tìm thấy mã giảm giá.")

        new_name = str(name).strip() if name is not None else current["name"]
        new_desc = str(description).strip() if description is not None else current["description"]
        new_type = discount_type if discount_type is not None else current["discount_type"]
        new_val = (
            _coupon_int(discount_value, "Mức giảm giá", minimum=1)
            if discount_value is not None else current["discount_value"]
        )
        new_max = (
            current["max_discount_vnd"] if max_discount_vnd is _COUPON_UNSET
            else _coupon_optional_money(max_discount_vnd, "Mức giảm tối đa")
        )
        new_min = (
            current["min_order_vnd"] if min_order_vnd is _COUPON_UNSET
            else _coupon_int(min_order_vnd, "Giá trị đơn tối thiểu", minimum=0, multiple=1000)
        )
        new_lim_tot = (
            current["usage_limit_total"] if usage_limit_total is _COUPON_UNSET
            else _coupon_optional_positive_int(usage_limit_total, "Tổng lượt sử dụng")
        )
        new_lim_usr = (
            current["usage_limit_per_user"] if usage_limit_per_user is _COUPON_UNSET
            else _coupon_optional_positive_int(usage_limit_per_user, "Lượt sử dụng mỗi khách")
        )
        new_starts = (
            current["starts_at"] if starts_at is _COUPON_UNSET
            else _coupon_timestamp(starts_at, "Thời gian bắt đầu")
        )
        new_ends = (
            current["ends_at"] if ends_at is _COUPON_UNSET
            else _coupon_timestamp(ends_at, "Thời gian kết thúc")
        )
        new_active = (1 if is_active else 0) if is_active is not None else current["is_active"]

        if not new_name:
            raise ValueError("Tên mã giảm giá không được để trống.")
        if len(new_name) > 100:
            raise ValueError("Tên mã giảm giá không được quá 100 ký tự.")

        if new_type == "fixed":
            new_type = "fixed_vnd"
        if new_type not in ("percent", "fixed_vnd"):
            raise ValueError("Loại giảm giá không hợp lệ.")
        if new_type == "percent" and not (1 <= new_val <= 99):
            raise ValueError("Phần trăm giảm phải từ 1 đến 99%.")
        if new_type == "fixed_vnd" and (new_val < 1000 or new_val % 1000 != 0):
            raise ValueError("Mức giảm cố định phải chia hết cho 1.000 VND.")
        if new_max is not None and (new_max < 1000 or new_max % 1000 != 0):
            raise ValueError("Mức giảm tối đa phải chia hết cho 1.000 VND.")
        if new_starts and new_ends and new_ends <= new_starts:
            raise ValueError("Thời gian kết thúc phải sau thời gian bắt đầu.")

        conn.execute(
            """UPDATE coupons
               SET name = ?, description = ?, discount_type = ?, discount_value = ?,
                   max_discount_vnd = ?, min_order_vnd = ?, usage_limit_total = ?,
                   usage_limit_per_user = ?, starts_at = ?, ends_at = ?, is_active = ?,
                   updated_at = ?
               WHERE id = ?""",
            (
                new_name, new_desc, new_type, new_val, new_max, new_min, new_lim_tot,
                new_lim_usr, new_starts, new_ends, new_active, now, coupon_id,
            ),
        )

        valid_plan_ids = _validated_coupon_plan_ids(conn, plan_ids)
        if valid_plan_ids is not None:
            conn.execute("DELETE FROM coupon_plan_rules WHERE coupon_id = ?", (coupon_id,))
            for pid in valid_plan_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO coupon_plan_rules (coupon_id, plan_id) VALUES (?, ?)",
                    (coupon_id, pid),
                )

        conn.execute("COMMIT")
        return get_coupon_by_id(coupon_id)
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise


def toggle_coupon_active(coupon_id, is_active):
    conn = get_conn()
    now = time.time()
    conn.execute(
        "UPDATE coupons SET is_active = ?, updated_at = ? WHERE id = ?",
        (1 if is_active else 0, now, coupon_id),
    )
    return get_coupon_by_id(coupon_id)


def delete_coupon(coupon_id):
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        used = conn.execute(
            "SELECT COUNT(*) as cnt FROM coupon_redemptions WHERE coupon_id = ?",
            (coupon_id,),
        ).fetchone()["cnt"]
        if used > 0:
            conn.execute("ROLLBACK")
            return ("cannot_delete", f"Mã giảm giá đã phát sinh {used} bản ghi lịch sử, không thể xóa cứng. Vui lòng vô hiệu hóa mã thay vì xóa.")

        conn.execute("DELETE FROM coupon_plan_rules WHERE coupon_id = ?", (coupon_id,))
        conn.execute("DELETE FROM coupon_redemptions WHERE coupon_id = ?", (coupon_id,))
        conn.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))
        conn.execute("COMMIT")
        return ("ok", None)
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return ("error", str(exc))


def get_coupon_stats(coupon_id):
    conn = get_conn()
    from . import coupon_service
    coupon_service.sweep_expired_reservations(conn)
    coupon = get_coupon_by_id(coupon_id, conn)
    if not coupon:
        return None

    counts = conn.execute(
        """SELECT
           SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved_count,
           SUM(CASE WHEN status = 'redeemed' THEN 1 ELSE 0 END) as redeemed_count,
           SUM(CASE WHEN status = 'released' THEN 1 ELSE 0 END) as released_count,
           SUM(CASE WHEN status = 'redeemed' THEN discount_vnd ELSE 0 END) as total_discount_vnd,
           SUM(CASE WHEN status = 'redeemed' THEN final_price_vnd ELSE 0 END) as total_revenue_vnd
           FROM coupon_redemptions WHERE coupon_id = ?""",
        (coupon_id,),
    ).fetchone()

    recent_redemptions = conn.execute(
        """SELECT r.*, u.username, u.email
           FROM coupon_redemptions r
           LEFT JOIN users u ON r.user_id = u.id
           WHERE r.coupon_id = ?
           ORDER BY r.id DESC LIMIT 15""",
        (coupon_id,),
    ).fetchall()

    return {
        "coupon": coupon,
        "reserved_count": counts["reserved_count"] or 0,
        "redeemed_count": counts["redeemed_count"] or 0,
        "released_count": counts["released_count"] or 0,
        "total_discount_vnd": counts["total_discount_vnd"] or 0,
        "total_revenue_vnd": counts["total_revenue_vnd"] or 0,
        "recent_redemptions": [dict(r) for r in recent_redemptions],
    }
