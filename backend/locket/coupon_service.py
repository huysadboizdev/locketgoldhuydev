"""Coupon and Pricing service for Locket Gold plan purchases.

Implements:
1. Strict integer arithmetic for discounts and prices (multiples of 1,000 VND).
2. Coupon code normalization (uppercase, alphanumeric + dash/underscore).
3. Concurrency-safe quota checks inside SQLite BEGIN IMMEDIATE transactions.
4. Reservation state machine:
     reserved (VietQR pending) -> redeemed (VietQR paid / Coin instant)
     reserved -> released (VietQR expired / cancelled / rejected)
5. Non-zero price enforcement (minimum order price 1,000 VND).
"""

import re
import time
from typing import Any, Dict, Optional, Tuple

COUPON_CODE_REGEX = re.compile(r"^[A-Z0-9_-]{2,30}$")


def normalize_code(raw_code: str) -> str:
    """Normalize coupon code to uppercase trimmed string and validate format."""
    if not raw_code:
        raise ValueError("Mã giảm giá không được để trống.")
    cleaned = str(raw_code).strip().upper()
    if not COUPON_CODE_REGEX.match(cleaned):
        raise ValueError("Mã giảm giá chỉ được chứa chữ cái, số, dấu gạch ngang (-) hoặc gạch dưới (_), từ 2 đến 30 ký tự.")
    return cleaned


def calculate_discount(
    original_vnd: int,
    discount_type: str,
    discount_value: int,
    max_discount_vnd: Optional[int] = None,
) -> Dict[str, int]:
    """Calculate integer discount and final prices in VND and Coin.

    Formula rules:
    - original_vnd: positive integer divisible by 1,000
    - percent: integer (1..99). Raw discount rounded DOWN to step 1,000 VND.
    - fixed_vnd: positive integer multiple of 1,000.
    - max_discount_vnd: if set, caps discount_vnd.
    - final_vnd must be >= 1,000 VND and divisible by 1,000.
    - coin values = vnd // 1,000.
    """
    if type(original_vnd) is not int or original_vnd < 1000 or original_vnd % 1000 != 0:
        raise ValueError(f"Giá gốc không hợp lệ: {original_vnd}. Phải là bội số của 1.000 VND.")
    if type(discount_value) is not int:
        raise ValueError("Mức giảm giá phải là số nguyên.")
    if max_discount_vnd is not None and (
        type(max_discount_vnd) is not int
        or max_discount_vnd < 1000
        or max_discount_vnd % 1000 != 0
    ):
        raise ValueError("Mức giảm tối đa phải là số nguyên, chia hết cho 1.000 VND.")

    if discount_type == "percent":
        if not (1 <= discount_value <= 99):
            raise ValueError("Phần trăm giảm giá phải từ 1% đến 99%.")
        raw_discount = (original_vnd * discount_value) // 100
        # Floor to multiple of 1,000 VND
        discount_vnd = (raw_discount // 1000) * 1000
    elif discount_type in ("fixed_vnd", "fixed"):
        if discount_value < 1000 or discount_value % 1000 != 0:
            raise ValueError("Số tiền giảm cố định phải là bội số của 1.000 VND và >= 1.000 VND.")
        discount_vnd = discount_value
    else:
        raise ValueError(f"Loại giảm giá không hợp lệ: '{discount_type}'.")

    if max_discount_vnd is not None and max_discount_vnd > 0:
        discount_vnd = min(discount_vnd, max_discount_vnd)

    final_vnd = original_vnd - discount_vnd
    if final_vnd < 1000:
        raise ValueError("Mã giảm giá không hợp lệ vì dẫn đến đơn hàng dưới mức tối thiểu 1.000 VND.")

    if final_vnd % 1000 != 0:
        raise ValueError("Giá cuối cùng phải là bội số của 1.000 VND.")

    discount_coin = discount_vnd // 1000
    final_coin = final_vnd // 1000
    original_coin = original_vnd // 1000

    return {
        "original_vnd": original_vnd,
        "original_coin": original_coin,
        "discount_vnd": discount_vnd,
        "discount_coin": discount_coin,
        "final_vnd": final_vnd,
        "final_coin": final_coin,
    }


def sweep_expired_reservations(conn, now: Optional[float] = None) -> int:
    """Sweep overdue reserved coupon redemptions and release them back to quota."""
    now_ts = time.time() if now is None else now
    cur = conn.execute(
        """UPDATE coupon_redemptions
           SET status = 'released', released_at = ?
           WHERE status = 'reserved' AND expires_at < ?""",
        (now_ts, now_ts),
    )
    return cur.rowcount


def validate_and_quote_coupon(
    conn,
    raw_code: str,
    plan_id: int,
    user_id: int,
    now: Optional[float] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, int]], Optional[str], Optional[str]]:
    """Validate coupon eligibility and compute quote.

    Must be called with an active sqlite3 connection, ideally within a transaction.
    Returns (is_valid, coupon_dict, quote_dict, error_code, error_msg).
    """
    try:
        norm_code = normalize_code(raw_code)
    except ValueError as exc:
        return (False, None, None, "invalid_code_format", str(exc))

    now_ts = time.time() if now is None else now

    # Sweep overdue reservations first so released slots are immediately available
    sweep_expired_reservations(conn, now_ts)

    # 1. Fetch coupon
    row = conn.execute(
        "SELECT * FROM coupons WHERE normalized_code = ?",
        (norm_code,),
    ).fetchone()
    if not row:
        return (False, None, None, "coupon_not_found", "Mã giảm giá không tồn tại.")

    coupon = dict(row)

    # 2. Check active flag
    if not coupon.get("is_active"):
        return (False, None, None, "coupon_inactive", "Mã giảm giá hiện đang bị vô hiệu hóa.")

    # 3. Check schedule
    starts_at = coupon.get("starts_at")
    if starts_at is not None and now_ts < starts_at:
        return (False, None, None, "coupon_not_started", "Mã giảm giá chưa đến thời gian áp dụng.")

    ends_at = coupon.get("ends_at")
    if ends_at is not None and now_ts > ends_at:
        return (False, None, None, "coupon_expired", "Mã giảm giá đã hết hạn sử dụng.")

    # 4. Fetch plan
    plan_row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if not plan_row or not plan_row["is_active"]:
        return (False, None, None, "plan_unavailable", "Gói dịch vụ không tồn tại hoặc đã bị ẩn.")

    plan_price_vnd = int(plan_row["price_vnd"])

    # 5. Check plan rules
    rule_rows = conn.execute(
        "SELECT plan_id FROM coupon_plan_rules WHERE coupon_id = ?",
        (coupon["id"],),
    ).fetchall()
    if rule_rows:
        allowed_plans = {r["plan_id"] for r in rule_rows}
        if plan_id not in allowed_plans:
            return (False, None, None, "plan_not_eligible", "Mã giảm giá không áp dụng cho gói dịch vụ này.")

    # 6. Check min order VND
    min_order_vnd = int(coupon.get("min_order_vnd") or 0)
    if plan_price_vnd < min_order_vnd:
        return (
            False,
            None,
            None,
            "min_order_not_met",
            f"Đơn hàng chưa đạt giá trị tối thiểu {min_order_vnd:,}đ để áp dụng mã.",
        )

    # 7. Check usage_limit_total
    limit_total = coupon.get("usage_limit_total")
    if limit_total is not None and limit_total > 0:
        total_used_row = conn.execute(
            """SELECT COUNT(*) as cnt FROM coupon_redemptions
               WHERE coupon_id = ? AND status IN ('reserved', 'redeemed')""",
            (coupon["id"],),
        ).fetchone()
        total_used = total_used_row["cnt"] if total_used_row else 0
        if total_used >= limit_total:
            return (False, None, None, "coupon_exhausted", "Mã giảm giá đã hết lượt sử dụng.")

    # 8. Check usage_limit_per_user
    limit_user = coupon.get("usage_limit_per_user")
    if limit_user is not None and limit_user > 0 and user_id:
        user_used_row = conn.execute(
            """SELECT COUNT(*) as cnt FROM coupon_redemptions
               WHERE coupon_id = ? AND user_id = ? AND status IN ('reserved', 'redeemed')""",
            (coupon["id"], user_id),
        ).fetchone()
        user_used = user_used_row["cnt"] if user_used_row else 0
        if user_used >= limit_user:
            return (
                False,
                None,
                None,
                "user_limit_reached",
                "Bạn đã sử dụng hết số lượt cho phép của mã giảm giá này.",
            )

    # 9. Compute discount and final prices
    try:
        quote = calculate_discount(
            original_vnd=plan_price_vnd,
            discount_type=coupon["discount_type"],
            discount_value=coupon["discount_value"],
            max_discount_vnd=coupon.get("max_discount_vnd"),
        )
    except ValueError as exc:
        return (False, None, None, "discount_invalid", str(exc))

    return (True, coupon, quote, None, None)


def reserve_coupon_for_payment(
    conn,
    coupon_id: int,
    user_id: int,
    payment_order_id: int,
    activation_order_id: Optional[int],
    original_vnd: int,
    discount_vnd: int,
    final_vnd: int,
    ttl_seconds: int = 600,
    idempotency_key: Optional[str] = None,
    now: Optional[float] = None,
) -> int:
    """Reserve a coupon quota for a pending VietQR payment order."""
    now_ts = time.time() if now is None else now
    expires_at = now_ts + ttl_seconds

    cursor = conn.execute(
        """INSERT INTO coupon_redemptions
           (coupon_id, user_id, payment_order_id, activation_order_id, status,
            original_price_vnd, discount_vnd, final_price_vnd, created_at, expires_at, idempotency_key)
           VALUES (?, ?, ?, ?, 'reserved', ?, ?, ?, ?, ?, ?)""",
        (
            coupon_id,
            user_id,
            payment_order_id,
            activation_order_id,
            original_vnd,
            discount_vnd,
            final_vnd,
            now_ts,
            expires_at,
            idempotency_key,
        ),
    )
    return cursor.lastrowid


def redeem_reserved_coupon(
    conn,
    payment_order_id: int,
    activation_order_id: Optional[int] = None,
    now: Optional[float] = None,
    allow_released: bool = False,
) -> bool:
    """Confirm a coupon when its payment is marked paid.

    A released reservation is redeemable only for an explicit admin manual
    override. This records a real late bank payment instead of silently losing
    the coupon usage/revenue after the QR reservation expired.
    """
    now_ts = time.time() if now is None else now
    allowed_statuses = ("reserved", "released") if allow_released else ("reserved",)
    placeholders = ", ".join("?" for _ in allowed_statuses)
    cur = conn.execute(
        f"""UPDATE coupon_redemptions
            SET status = 'redeemed', redeemed_at = ?, released_at = NULL,
                activation_order_id = COALESCE(activation_order_id, ?)
            WHERE payment_order_id = ? AND status IN ({placeholders})""",
        (now_ts, activation_order_id, payment_order_id, *allowed_statuses),
    )
    return cur.rowcount > 0


def release_reserved_coupon(
    conn,
    payment_order_id: int,
    now: Optional[float] = None,
) -> bool:
    """Release a reserved coupon back to quota when payment order is expired/cancelled/rejected."""
    now_ts = time.time() if now is None else now
    cur = conn.execute(
        """UPDATE coupon_redemptions
           SET status = 'released', released_at = ?
           WHERE payment_order_id = ? AND status = 'reserved'""",
        (now_ts, payment_order_id),
    )
    return cur.rowcount > 0


def record_coin_redemption(
    conn,
    coupon_id: int,
    user_id: int,
    activation_order_id: int,
    original_vnd: int,
    discount_vnd: int,
    final_vnd: int,
    idempotency_key: Optional[str] = None,
    now: Optional[float] = None,
) -> int:
    """Record an instant redeemed coupon when paying with Coin balance."""
    now_ts = time.time() if now is None else now
    cursor = conn.execute(
        """INSERT INTO coupon_redemptions
           (coupon_id, user_id, payment_order_id, activation_order_id, status,
            original_price_vnd, discount_vnd, final_price_vnd, created_at, redeemed_at, idempotency_key)
           VALUES (?, ?, NULL, ?, 'redeemed', ?, ?, ?, ?, ?, ?)""",
        (
            coupon_id,
            user_id,
            activation_order_id,
            original_vnd,
            discount_vnd,
            final_vnd,
            now_ts,
            now_ts,
            idempotency_key,
        ),
    )
    return cursor.lastrowid
