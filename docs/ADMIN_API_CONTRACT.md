# Locket Gold Admin REST API Canonical Contract

Document version: 2.0.0
Status: APPROVED
Standard: RESTful JSON with Strict Types & Redaction

---

## 1. Global Conventions & Envelopes

### 1.1 List Response Envelope
Mọi endpoint trả về danh sách đều PHẢI dùng envelope chuẩn sau:
```json
{
  "success": true,
  "items": [],
  "pagination": {
    "total": 0,
    "limit": 20,
    "offset": 0,
    "page": 1,
    "pages": 0,
    "has_more": false
  }
}
```

### 1.2 Canonical Query Parameters for Lists
- `q`: chuỗi tìm kiếm (tối đa 100 ký tự).
- `status`: lọc theo trạng thái hợp lệ của từng domain.
- `role`: lọc theo vai trò (`user` hoặc `admin`).
- `is_active`: `1` (active) hoặc `0` (inactive/blocked).
- `platform`: `ios` hoặc `android`.
- `purpose`: `wallet_topup` hoặc `plan_purchase`.
- `page`: số nguyên >= 1 (mặc định 1).
- `limit`: số nguyên từ 1 đến 100 (mặc định 15 hoặc 20).
- `admin_user_id`: số nguyên ID của admin (cho audit logs).
- `entity_type`: loại thực thể (`user`, `payment`, `plan`, `review`, `site_settings`, `account`).
- `action`: mã hành động audit.

### 1.3 Error Response Envelope
```json
{
  "success": false,
  "error": "error_code_snake_case",
  "msg": "Mô tả lỗi tiếng Việt cho người dùng",
  "details": {}
}
```

---

## 2. Authentication & Authorization Headers

- `Authorization`: `Bearer <jwt_access_token>` (Bắt buộc cho mọi `/api/admin/*`).
- `X-CSRF-Token`: `<csrf_token>` (Bắt buộc cho mọi mutating method `POST`, `PUT`, `PATCH`, `DELETE`).
- Server trả về header: `Cache-Control: private, no-store` trên tất cả admin responses.

---

## 3. Overview API (`GET /api/admin/overview`)

- **Query**: `range=7d|30d|90d` (Mặc định `30d`).
- **Response**:
```json
{
  "success": true,
  "range": "30d",
  "timezone": "Asia/Bangkok",
  "generated_at": 1725792000,
  "cards": {
    "total_users": 150,
    "active_users": 140,
    "new_users": 25,
    "paid_revenue_vnd": 5000000,
    "topup_revenue_vnd": 3000000,
    "plan_purchase_revenue_vnd": 2000000,
    "paid_payments": 45,
    "pending_payments": 2,
    "total_orders": 80,
    "completed_orders": 72,
    "processing_orders": 3,
    "queued_orders": 2,
    "failed_orders": 3,
    "completion_rate": 90.0,
    "total_wallet_balance_coin": 1250,
    "users_with_coin": 35,
    "total_reviews": 40,
    "pending_reviews": 4,
    "average_rating": 4.8,
    "queue_waiting": 2,
    "queue_processing": 3,
    "active_workers": 1
  },
  "series": [
    {
      "date": "2026-09-01",
      "revenue_vnd": 250000,
      "paid_payments": 2,
      "orders": 3,
      "completed_orders": 3,
      "new_users": 1
    }
  ],
  "order_status_breakdown": [
    { "status": "completed", "count": 72 }
  ],
  "platform_breakdown": [
    { "platform": "ios", "count": 50 },
    { "platform": "android", "count": 30 }
  ],
  "payment_method_breakdown": [
    { "method": "coin", "count": 60 },
    { "method": "qr", "count": 20 }
  ],
  "recent_orders": [],
  "recent_payments": []
}
```

---

## 4. Users API

### 4.1 List Users: `GET /api/admin/users`
- **Query**: `q`, `role`, `status` (hoặc `is_active`), `page`, `limit`.
- **Response**: List envelope với `items`:
```json
{
  "id": 1,
  "email": "user@test.com",
  "username": "alice",
  "display_name": "Alice Wonderland",
  "role": "user",
  "is_active": true,
  "balance_coin": 50,
  "created_at": 1725700000,
  "order_count": 3,
  "payment_count": 2,
  "is_seed_admin": false
}
```

### 4.2 User Detail: `GET /api/admin/users/:id`
- **Response**:
```json
{
  "success": true,
  "user": {
    "id": 1,
    "email": "user@test.com",
    "username": "alice",
    "display_name": "Alice Wonderland",
    "role": "user",
    "is_active": true,
    "balance_coin": 50,
    "is_seed_admin": false,
    "created_at": 1725700000,
    "recent_wallet_transactions": [],
    "recent_orders": [],
    "recent_payments": [],
    "review": null
  }
}
```

### 4.3 Adjust Wallet: `POST /api/admin/users/:id/adjust-wallet`
- **Request Body**:
```json
{
  "amount_coin": 20,
  "reason": "Khuyến mãi nạp coin sự kiện",
  "idempotency_key": "adj_1_1725792000"
}
```
- **Response**:
```json
{
  "success": true,
  "user_id": 1,
  "balance_coin": 70,
  "transaction": {
    "id": 10,
    "user_id": 1,
    "type": "adjustment",
    "amount_coin": 20,
    "balance_before": 50,
    "balance_after": 70,
    "description": "Khuyến mãi nạp coin sự kiện",
    "idempotency_key": "adj_1_1725792000",
    "created_at": 1725792000
  },
  "msg": "Điều chỉnh số dư ví thành công."
}
```

### 4.4 Toggle User Status: `POST /api/admin/users/:id/status`
- **Request Body**:
```json
{
  "is_active": false,
  "reason": "Vi phạm chính sách lạm dụng"
}
```

### 4.5 Update User Role: `POST /api/admin/users/:id/role`
- **Request Body**:
```json
{
  "role": "admin",
  "reason": "Bổ nhiệm quản trị viên mới"
}
```

---

## 5. Orders API

### 5.1 List Orders: `GET /api/admin/orders`
- **Query**: `q`, `status`, `platform`, `page`, `limit`.
- **Response**: List envelope với `items`:
```json
{
  "id": 1,
  "user_id": 10,
  "customer_username": "alice",
  "customer_email": "alice@test.com",
  "locket_username": "alice_locket",
  "platform": "ios",
  "plan_id": 2,
  "plan_name_snapshot": "Gói 1 Tháng VIP",
  "duration_days_snapshot": 30,
  "price_vnd_snapshot": 50000,
  "price_coin_snapshot": 50,
  "payment_method": "coin",
  "payment_order_id": null,
  "status": "completed",
  "queue_client_id": "c1a4b5-...",
  "created_at": 1725700000,
  "updated_at": 1725700030
}
```

---

## 6. Payments API

### 6.1 List Payments: `GET /api/admin/payments`
- **Query**: `q`, `status`, `purpose`, `page`, `limit`.
- **Response**: List envelope với `items`:
```json
{
  "id": 1,
  "payment_code": "PMT12345",
  "payment_ref": "REF12345",
  "transfer_code": "LOCKETGOLDHUYDEV001",
  "user_id": 10,
  "customer_username": "alice",
  "customer_email": "alice@test.com",
  "purpose": "wallet_topup",
  "plan_id": null,
  "amount_vnd": 50000,
  "coin_amount": 50,
  "status": "paid",
  "bank_transaction_id": "TX99999",
  "paid_at": 1725700010,
  "created_at": 1725700000
}
```

### 6.2 Confirm Payment: `POST /api/admin/payments/:id/confirm`
- **Request Body**:
```json
{
  "bank_transaction_id": "FT24098192837"
}
```

### 6.3 Reject Payment: `POST /api/admin/payments/:id/reject`
- **Request Body**:
```json
{
  "reason": "Chuyển khoản thiếu tiền và quá hạn giao dịch"
}
```

---

## 7. Plans API

### 7.1 List Plans: `GET /api/admin/plans`
- **Response**: `{ "success": true, "plans": [...] }`

### 7.2 Create Plan: `POST /api/admin/plans`
- **Request Body**:
```json
{
  "name": "Gói 1 Tháng VIP",
  "slug": "gold_1m",
  "short_description": "Kích hoạt Locket Gold 30 ngày",
  "duration_days": 30,
  "price_vnd": 50000,
  "price_coin": 50,
  "product_id": "gold_monthly",
  "supported_platforms": "all",
  "features": ["Kích hoạt tự động", "Bảo hành trọn đời gói"],
  "is_popular": 1,
  "is_active": 1,
  "sort_order": 1
}
```

### 7.3 Update Plan: `PUT /api/admin/plans/:id`
- **Request Body**: Partial<Plan>

### 7.4 Toggle Plan Status: `POST /api/admin/plans/:id/toggle`
- **Request Body**: `{ "is_active": true }`

### 7.5 Delete Plan: `DELETE /api/admin/plans/:id`
- **Response**: `{ "success": true, "msg": "Gói dịch vụ đã được ẩn khỏi hệ thống." }`

---

## 8. Queue API (`GET /api/admin/queue`)

- **Response**:
```json
{
  "success": true,
  "active_workers": 1,
  "total_in_queue": 2,
  "workers": {
    "slot-uuid-1": { "busy": false, "current_client_id": null }
  },
  "waiting": [],
  "processing": [],
  "recent": []
}
```

---

## 9. Reviews API

### 9.1 List Reviews: `GET /api/admin/reviews`
- **Query**: `status`, `page`, `limit`.
- **Response**: List envelope với `items`:
```json
{
  "id": 1,
  "user_id": 10,
  "username": "alice",
  "display_name": "Alice Wonderland",
  "email": "alice@test.com",
  "rating": 5,
  "content": "Dịch vụ rất tốt và nhanh!",
  "status": "approved",
  "is_pinned": 0,
  "sort_priority": 0,
  "staff_note": null,
  "is_verified": 1,
  "created_at": 1725700000,
  "images": [
    {
      "id": 1,
      "url": "/api/admin/reviews/images/1",
      "original_filename": "proof.png"
    }
  ]
}
```

### 9.2 Moderate Review: `PATCH /api/admin/reviews/:id/status` (alias: `POST /api/admin/reviews/:id/moderate`)
- **Request Body**:
```json
{
  "status": "approved",
  "admin_note": "Ảnh chuyển khoản hợp lệ",
  "is_pinned": true,
  "sort_priority": 10
}
```

### 9.3 Delete Review: `DELETE /api/admin/reviews/:id`
- **Response**: `{ "success": true, "msg": "Đã xóa đánh giá thành công." }`

---

## 10. System Operations API

### 10.1 Account Pool
- `GET /api/admin/accounts` -> `{ "success": true, "accounts": [{"slot_id": "...", "username": "..."}], "rotator_summary": {...} }`
- `POST /api/admin/accounts` -> `{ "email": "acc@locket.com", "password": "pass" }`
- `DELETE /api/admin/accounts/:slot_id` -> `{ "success": true, "msg": "..." }`

### 10.2 Proxies
- `GET /api/admin/proxies` -> `{ "success": true, "proxies": [{"id": 1, "url": "http://***:***@proxy.com:8080"}] }`
- `POST /api/admin/proxies` -> `{ "url": "http://user:pass@proxy.com:8080" }`
- `DELETE /api/admin/proxies/:id` -> `{ "success": true, "msg": "..." }`

### 10.3 Token Cache
- `GET /api/admin/tokens` -> `{ "success": true, "tokens": [{"index": 0, "product_identifier": "...", "account": "acc1", "expires_at": 1725792000}] }`
  *(Bảo mật nghiêm ngặt: KHÔNG BAO GIỜ trả về `fetch_token`, receipts, bearer tokens)*

### 10.4 Mobileconfig
- `POST /api/admin/mobileconfig` (multipart/form-data with `file`)
- `DELETE /api/admin/mobileconfig`

### 10.5 Site Settings (Composite)
- `GET /api/admin/site-settings` -> `{ "success": true, "settings": { "maintenance": {...}, "popup": {...}, "theme": {...}, "layout": {...} } }`
- `POST /api/admin/site-settings` -> `{ "maintenance": {...}, "popup": {...}, "theme": {...}, "layout": {...} }`

---

## 11. Audit Logs API (`GET /api/admin/audit-logs`)

- **Query**: `admin_user_id`, `action`, `entity_type`, `page`, `limit`.
- **Response**: List envelope với `items`:
```json
{
  "id": 1,
  "admin_user_id": 1,
  "admin_username": "admin",
  "admin_email": "admin@example.com",
  "action": "adjust_wallet",
  "entity_type": "user",
  "entity_id": "10",
  "before": { "balance_coin": 50 },
  "after": { "balance_coin": 70 },
  "details": { "delta_coin": 20, "reason": "Khuyến mãi" },
  "ip_address": "127.0.0.1",
  "user_agent": "Mozilla/5.0 ...",
  "created_at": 1725792000
}
```
*(Bảo mật nghiêm ngặt: `before`, `after`, `details` tự động lọc sạch các khoá nhạy cảm như `password`, `token`, `secret`, `key`)*
