
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
