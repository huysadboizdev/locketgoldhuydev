# MASTER FIX PROMPT — GEMINI ANTIGRAVITY CLI SỬA TRIỆT ĐỂ REACT ADMIN

Bạn đang làm việc trực tiếp trong workspace:

`D:\toolvip\locketgold\Locket_Gold_Huy_Dev`

Đây là nhiệm vụ **sửa lỗi và hoàn thiện production**, không phải nhiệm vụ viết báo cáo hoặc dựng UI minh họa. Một lần triển khai trước đã tạo React Admin và backend `/api/admin`, nhưng audit độc lập phát hiện frontend và backend lệch contract nghiêm trọng. Backend unit test và frontend build hiện đều pass nhưng phần lớn màn hình/thao tác admin vẫn hỏng ở runtime.

Hãy đóng vai trò Principal Full-stack Engineer, API Contract Engineer, Security Engineer và QA Lead. Bạn phải tự audit source, sửa end-to-end, chạy contract/integration/E2E test trên database tạm và chỉ kết luận hoàn thành khi giao diện thật gọi đúng backend thật.

## 0. Quy tắc bắt buộc về skill, agent và cách làm

1. Trước khi sửa code, tìm và đọc đầy đủ `AGENTS.md`, `CLAUDE.md`, README, file deploy và mọi instruction áp dụng cho workspace.
2. Liệt kê skill/capability đang có trong Gemini Antigravity CLI; chủ động dùng tất cả skill thực sự liên quan đến React/TypeScript, Flask/Python, SQLite, security, API contract, testing và browser/E2E. Đọc đầy đủ hướng dẫn skill trước khi dùng.
3. Nếu có sub-agent, có thể chia audit độc lập thành:
   - API contract FE–BE;
   - auth/security/database;
   - UI/browser/E2E.
   Agent chính phải tự review và tích hợp kết quả; không để agent sửa chồng file.
4. Đầu tiên xuất implementation plan ngắn theo phase, rồi tiếp tục sửa. Không dừng ở kế hoạch và không hỏi lại các quyết định kỹ thuật thông thường.
5. Không reset, không xóa thay đổi hiện có, không xóa `locket.db`, không dùng database production để test, không in hoặc commit secret.
6. Không “sửa” bằng cách thêm `any`, optional chaining hoặc fallback `|| 0` để che response sai. Phải thống nhất contract thực sự.
7. Không bỏ/tắt test đang fail. Không mock backend trong bài E2E cuối; browser phải gọi Flask API thật trên temporary SQLite database.
8. Không tuyên bố “100% hoàn thành” chỉ vì `npm run build` và Python unit tests pass.

## 1. Bằng chứng audit hiện tại — phải xác minh lại từng điểm

Các lỗi sau đã được tìm thấy trong source hiện tại. Hãy mở file và tự xác minh trước khi sửa.

### 1.1 Overview response lệch hoàn toàn

Frontend `AdminOverview.tsx` đang đọc:

```text
cards.payments.revenue_vnd
cards.activation_orders.completed
cards.active_users
cards.wallet.total_balance_coin
cards.queue.total_waiting
cards.reviews.average_rating
charts.revenue_series
recent.orders
recent.payments
```

Backend `db.get_admin_overview_stats()` lại trả:

```text
cards.paid_revenue_vnd
cards.total_orders
cards.completed_orders
cards.queue_waiting
series
recent_orders
recent_payments
```

Hậu quả: dashboard tải API thành công nhưng hiển thị gần như toàn 0/empty.

### 1.2 List response lệch key/pagination

Frontend các trang Users, Orders, Payments, Reviews, Audit Logs dùng `res.items` và `res.pages`.

Backend hiện trả không nhất quán:

```text
users:   { users, total, limit, offset }
orders:  { orders, total, limit, offset }
payments:{ payments }
reviews: { reviews }
audit:   { logs, total, limit, offset }
```

Hậu quả: state nhận `undefined`, pagination sai và có thể crash khi `.length`/`.map`.

### 1.3 Endpoint/payload mutation bị sai

| Chức năng | Frontend hiện gọi | Backend hiện nhận |
|---|---|---|
| Điều chỉnh ví | `/users/:id/wallet/adjust`, `{delta_coin}` | `/users/:id/adjust-wallet`, `{amount_coin}` |
| Bật/tắt plan | `POST /plans/:id/toggle` | chỉ có `PUT /plans/:id` |
| Moderate review | `POST /reviews/:id/moderate` | `POST/PATCH /reviews/:id/status` |
| Add account pool | `{username,password?}` | `{email,password}` bắt buộc |
| Delete account pool | path bằng username | path phải là `slot_id` |
| Add proxy | `{proxy_url}` | `{url}` |
| Delete proxy | path bằng URL | path phải là numeric `proxy_id` |
| Settings | `/api/admin/site-settings` | backend chỉ có `/popup`, `/maintenance`, `/theme`, `/layout` |
| Audit filter | query `admin_id` | backend đọc `admin_user_id` |

### 1.4 Queue response lệch

Frontend đợi `res.snapshot.items`, `snapshot.active_workers`, `snapshot.total_in_queue`; backend trả snapshot cũ dạng `workers`, `processing`, `waiting`, `recent` ở top-level.

### 1.5 Review có UI-only feature

Frontend có `is_pinned`, `sort_priority`, `staff_note`, endpoint `/moderate`; schema/backend hiện không có đầy đủ các field/logic/order tương ứng. Không được tiếp tục tuyên bố tính năng này hoạt động nếu chưa có database migration, API và public ordering thật.

### 1.6 Token masking không an toàn

`tokens_store.list()` trả raw payload có thể chứa `fetch_token`. Endpoint `/api/admin/tokens` hiện chỉ thay `original_purchase_date_ms`, nghĩa là secret vẫn có thể xuất hiện trong network response dù UI không render.

### 1.7 Maintenance chưa đúng

React route `/admin/*` hiện không đi qua `MaintenanceRouteWrapper`, nên `allow_admin=false` bị bỏ qua. `/register` cũng luôn mở khi bảo trì. Cần định nghĩa rõ behavior và test cả frontend lẫn backend.

### 1.8 Audit không đảm bảo cho thao tác tài chính

Helper `_audit()` nuốt mọi exception. Payment/wallet có thể commit thành công nhưng audit thất bại mà API vẫn trả success. Với thao tác tài chính quan trọng, nghiệp vụ và audit phải có đảm bảo atomic hoặc cơ chế durable outbox tương đương.

### 1.9 Migration role chưa có constraint trên DB cũ

Schema DB mới có `CHECK (role IN ('user','admin'))`, nhưng migration cũ chỉ `ALTER TABLE ... ADD COLUMN role ... DEFAULT 'user'`, không có CHECK. Direct SQL vẫn có thể ghi role rác.

### 1.10 Test coverage tạo cảm giác an toàn giả

184 backend tests và frontend build hiện pass, nhưng không test frontend gọi đúng URL/payload/response của backend. Cần bổ sung contract và E2E test thật.

## 2. Giữ nguyên các phần đang tốt

Không phá các invariant đang hoạt động:

- Một `/login` dùng chung cho user/admin.
- Admin seed từ `.env` với `ADMIN_EMAIL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_DISPLAY_NAME`.
- Public register luôn role `user`.
- Access JWT ở memory; refresh token HttpOnly; refresh rotation/replay detection.
- Backend đọc role từ database mỗi request.
- Guest `/api/admin/*` → 401; authenticated user → 403; admin → được phép.
- Mutation admin có CSRF.
- Admin seed không bị khóa/hạ quyền.
- Admin vẫn có thể dùng `/dashboard`; login mặc định admin → `/admin`, user → `/dashboard`.
- Queue/payment/wallet transaction/state machine hiện có.
- Không đổi worker count/gunicorn architecture.

Chạy test baseline trước khi sửa và ghi lại kết quả. Sau sửa phải chạy lại toàn bộ.

## 3. Thiết kế một contract duy nhất, không để hai schema song song

Tạo tài liệu `docs/ADMIN_API_CONTRACT.md` hoặc vị trí phù hợp, mô tả chính xác route, method, query, request và response. Source code và tests phải theo tài liệu này.

### 3.1 Envelope chuẩn cho list

Chuẩn hóa mọi list endpoint thành:

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

Áp dụng tối thiểu cho:

- `GET /api/admin/users`
- `GET /api/admin/orders`
- `GET /api/admin/payments`
- `GET /api/admin/reviews`
- `GET /api/admin/audit-logs`

Frontend TypeScript và component phải đọc đúng `items` + `pagination`. Không giữ đồng thời `users/items`, `orders/items` như hai contract tùy tiện.

Query canonical:

```text
q                 từ khóa tìm kiếm
status            status filter
role              role filter
is_active         1 hoặc 0
platform          ios/android
purpose           wallet_topup/plan_purchase
page              bắt đầu từ 1
limit             clamp 1..100, UI thường 15/20
admin_user_id     filter audit
entity_type       filter audit
action            filter audit
```

Backend phải validate enum, integer, range; invalid query trả 400 rõ ràng hoặc default có tài liệu, không im lặng hiểu sai. Search dùng parameter binding.

### 3.2 Contract overview canonical

Dùng contract phẳng rõ ràng để khớp logic aggregate backend, cập nhật frontend theo đúng contract này:

```json
{
  "success": true,
  "range": "30d",
  "timezone": "Asia/Bangkok",
  "generated_at": 0,
  "cards": {
    "total_users": 0,
    "active_users": 0,
    "new_users": 0,
    "paid_revenue_vnd": 0,
    "topup_revenue_vnd": 0,
    "plan_purchase_revenue_vnd": 0,
    "paid_payments": 0,
    "pending_payments": 0,
    "total_orders": 0,
    "completed_orders": 0,
    "processing_orders": 0,
    "queued_orders": 0,
    "failed_orders": 0,
    "completion_rate": 0,
    "total_wallet_balance_coin": 0,
    "users_with_coin": 0,
    "total_reviews": 0,
    "pending_reviews": 0,
    "average_rating": 0,
    "queue_waiting": 0,
    "queue_processing": 0,
    "active_workers": 0
  },
  "series": [
    {
      "date": "YYYY-MM-DD",
      "revenue_vnd": 0,
      "paid_payments": 0,
      "orders": 0,
      "completed_orders": 0,
      "new_users": 0
    }
  ],
  "order_status_breakdown": [],
  "platform_breakdown": [],
  "payment_method_breakdown": [],
  "recent_orders": [],
  "recent_payments": []
}
```

Quy tắc thống kê:

- Doanh thu chỉ lấy `payment_orders.status='paid'`, bucket bằng `paid_at` (fallback `created_at` chỉ cho legacy row có paid_at null).
- `topup_revenue_vnd` lọc `purpose='wallet_topup'`.
- `plan_purchase_revenue_vnd` lọc `purpose='plan_purchase'`.
- Tổng doanh thu phải bằng tổng hai nhóm, không cộng `activation_orders.price_vnd_snapshot` lần nữa.
- Ngày theo `Asia/Bangkok`; zero-fill đủ 7/30/90 ngày.
- Completion rate phải định nghĩa mẫu số trong contract/test và tránh chia 0.
- Query aggregate trong SQLite, không tải toàn bộ bảng vào Python.
- Frontend không hiển thị rating giả `5.0` khi không có review; phải hiển thị `—` hoặc `0.0` đúng dữ liệu.

### 3.3 User detail canonical

Chọn một cấu trúc và dùng nhất quán. Khuyến nghị:

```json
{
  "success": true,
  "user": {
    "id": 1,
    "email": "...",
    "username": "...",
    "display_name": "...",
    "role": "user",
    "is_active": true,
    "balance_coin": 0,
    "is_seed_admin": false,
    "recent_wallet_transactions": [],
    "recent_orders": [],
    "recent_payments": [],
    "review": null
  }
}
```

Frontend modal và TypeScript type phải đọc đúng cấu trúc. Không trả password hash, refresh token, Google subject hoặc secret session.

### 3.4 Queue canonical

Chuẩn hóa thành:

```json
{
  "success": true,
  "active_workers": 0,
  "workers": {},
  "processing": [],
  "waiting": [],
  "recent": [],
  "total_in_queue": 0
}
```

Hoặc dùng một `snapshot` wrapper duy nhất nếu có lý do tốt, nhưng backend, types, UI và tests phải khớp 100%. UI phải thể hiện waiting/processing/recent đúng dữ liệu thật, không giả retry/attempt nếu backend không có.

## 4. Sửa mutation route/payload dứt điểm

Ưu tiên tái sử dụng backend route/business logic hiện có và sửa frontend endpoint layer cho khớp, trừ khi route hiện có thật sự bất hợp lý.

### Users/wallet

- Canonical: `POST /api/admin/users/:id/adjust-wallet`.
- Payload: `{amount_coin: integer nonzero, reason: string, idempotency_key: string}`.
- Client phải tạo idempotency key ổn định cho một lần submit và giữ nguyên key khi retry; không tạo key mới sau timeout chưa rõ kết quả.
- Response trả `transaction` và canonical balance sau giao dịch.
- Backend không dùng `bool("false")`; validate `is_active` phải là JSON boolean thật.
- Role/status change phải revoke session đúng và chống seed-admin mutation.

### Plans

- Bật/tắt dùng `PUT /api/admin/plans/:id` với `{is_active: boolean}` hoặc triển khai `/toggle` đầy đủ; chỉ giữ một cách và test nó.
- Delete phải tuân theo hành vi database thật. Nếu là hard delete thì UI/report không được gọi “xóa mềm”. Nếu muốn soft delete, triển khai `is_active=false` rõ ràng và không giả danh DELETE.
- Không trả raw exception/SQL error cho client production.

### Reviews

- Canonical tối thiểu: `PATCH /api/admin/reviews/:id/status` với `{status, admin_note}`.
- Quyết định rõ một trong hai:
  1. Loại bỏ `is_pinned`, `sort_priority`, `staff_note` khỏi UI/types nếu không nằm trong yêu cầu; hoặc
  2. Triển khai đầy đủ migration, DB helper, admin API, public list ordering và tests cho chúng.
- Không được để feature UI-only hoặc report sai.
- Response mutation trả review canonical sau cập nhật để UI refetch/update đúng.

### Account pool

- Form phải nhập `email` và `password` đúng backend `AccountRotator.test_login`.
- List phải dùng `slot_id` làm React key và delete identifier.
- Không hiển thị/trả password.
- Add/delete worker giữ invariant ít nhất một account và không làm hỏng worker đang chạy.

### Proxies

- Add payload `{url}`.
- List response dùng object có numeric `id`, URL đã redact.
- Delete/PATCH/test dùng numeric id, không dùng raw URL trong path.
- Không trả proxy credential trong exception, `last_err`, log hoặc audit.

### Settings

Chọn một phương án canonical:

- Khuyến nghị giữ endpoint backend riêng `/popup`, `/maintenance`, `/theme`, `/layout`; frontend `fetchAdminSettings` gọi song song bốn GET và compose local object, save gọi PUT cho phần thay đổi; hoặc
- Triển khai composite `/site-settings` GET/PUT thật, có validation/audit và tests.

Không để frontend gọi endpoint không tồn tại. Field UI phải đúng schema (`message` thay vì tự tạo `content`, chỉ dùng `button_link` nếu backend thực sự hỗ trợ).

### Payments

- List phải hỗ trợ `q`, `status`, `purpose`, page/limit và trả pagination chuẩn.
- Confirm/reject phải dùng state machine/transaction/idempotency hiện có.
- Reject reason phải được validate, dùng và audit; không thu thập reason trên UI rồi bỏ qua backend.
- Confirm không được cộng Coin hai lần khi retry.

### Tokens

- `GET /api/admin/tokens` tuyệt đối không trả raw `fetch_token`, receipt, bearer, token, secret hoặc credential.
- Dùng recursive redaction allow-list/deny-list đã kiểm thử; response chỉ trả metadata/preview đủ nhận diện và index/id dùng để xóa.
- Nếu UI nói quản lý token, phải có add/delete thật. Add nhận secret qua request bảo mật nhưng response và audit phải redact.
- Không ghi raw token vào audit/log/error.

## 5. Audit log và tính nguyên tử

1. `_audit()` không được nuốt lỗi đối với mutation tài chính quan trọng.
2. Wallet adjustment: wallet ledger + admin audit phải commit atomically trong cùng DB transaction, hoặc dùng durable outbox cùng transaction.
3. Payment confirm/reject: trạng thái payment, wallet/order effect và audit phải có guarantee rõ ràng, test failure injection.
4. Mutation phi tài chính có thể dùng best-effort chỉ khi tài liệu nêu rõ, nhưng lỗi audit phải log an toàn và không chứa secret.
5. `before` và `after` phải phản ánh record thật, không ghi `before=None` nếu có thể lấy được.
6. Frontend audit log đọc đúng `before`/`after`; không đợi field `details` nếu backend không trả nó.
7. Recursive redaction phải bắt key nhạy cảm nhưng không redact nhầm field vô hại vì substring quá rộng; viết test với nested dict/list.

## 6. Role constraint cho database cũ

Đảm bảo cả DB mới và DB đã migrate đều từ chối role ngoài `user/admin` ở database layer.

Có thể:

- rebuild table trong transaction theo migration SQLite an toàn; hoặc
- thêm trigger `BEFORE INSERT/UPDATE` dùng `RAISE(ABORT, ...)` cho migrated DB.

Viết test direct SQL `UPDATE users SET role='superadmin'` phải thất bại trên database mô phỏng legacy đã migrate. Migration chạy nhiều lần phải idempotent và không mất dữ liệu/index/foreign key.

## 7. Maintenance behavior canonical

Thực hiện và test đúng:

- `/login` luôn mở để admin có thể đăng nhập.
- Khi maintenance active, guest/user không được dùng landing service/dashboard/track/register hoặc API nghiệp vụ.
- `/register` không cho tạo account mới trong maintenance; có thể render maintenance screen hoặc backend trả 503.
- Admin vào `/admin/*` khi `allow_admin=true`.
- Khi `allow_admin=false`, admin UI phải tuân theo cấu hình thay vì bypass vô điều kiện.
- Giữ một recovery path có tài liệu để seed admin tắt maintenance an toàn, tối thiểu auth và endpoint maintenance được bảo vệ bằng admin token vẫn có thể dùng; không mở public bypass.
- Không có redirect loop maintenance → login → admin → maintenance.
- Backend offline phải được phân biệt với maintenance.

## 8. Frontend robustness

- Sửa `frontend/src/types/admin.ts` theo contract runtime thật; giảm `any` ở response quan trọng.
- `apiClient<T>` generic không phải runtime validation. Với admin response quan trọng, thêm parser/assertion nhẹ hoặc schema validator nếu project phù hợp để lỗi contract hiển thị rõ thay vì biến thành số 0 giả.
- Loading, empty, error, retry đầy đủ.
- Không set array state bằng field có thể undefined.
- Pagination tính từ response chuẩn.
- Search debounce hoặc submit không tạo double request từ state update + gọi trực tiếp.
- Poll overview/queue cleanup timer và abort request khi unmount.
- Mutation disable button, chống double-click, refetch canonical state sau success.
- Thay `window.alert`/`window.confirm` ở AdminSystem bằng modal/notice component nhất quán.
- Form account phải dùng email/password; proxy dùng id; setting fields đúng backend.
- Không hiển thị thành công nếu response không `success` hoặc request fail.
- Review image fetch có Bearer header. Không dùng `<img src="/api/admin/...">` nếu endpoint cần Authorization mà browser không tự gắn; dùng authenticated blob loader hoặc ticket an toàn.
- Kiểm tra light/dark nếu admin cố định dark thì phải có chủ ý; theme toggle không được giả hoạt động.
- Không để mojibake tiếng Việt.

## 9. Security hardening

- Mọi `/api/admin/*`: Bearer + DB role.
- Mutation: CSRF đúng session/token convention.
- Guest 401, user 403, không refresh-loop trên 403 forbidden.
- Clamp list limit, validate offset/page/range/enum.
- Không raw exception trong production response.
- Không raw secret trong tokens/proxies/accounts/audit/log.
- Upload mobileconfig giữ size/type/path safety và atomic replace.
- Admin seed không bị khóa/hạ role.
- Nếu promote user thành admin, phải có confirm mạnh, reason bắt buộc, audit và revoke session; cân nhắc giới hạn chỉ seed admin được promote/demote.
- Google login admin giữ policy `ADMIN_ALLOW_GOOGLE_LOGIN` an toàn hiện tại.
- Không thay đổi hoặc làm yếu refresh rotation/replay detection.

## 10. Test bắt buộc — đây là điều kiện chặn hoàn thành

### 10.1 Backend contract tests

Mở rộng `test_admin_auth_and_api.py` hoặc tách file hợp lý. Test exact keys/types của:

- overview 7d/30d/90d và số liệu seed khác 0;
- users list + pagination + q/role/is_active;
- user detail;
- orders list + q/status/platform;
- payments list + q/status/purpose/pagination;
- reviews list + mutation canonical;
- queue canonical;
- audit list + filter/pagination;
- settings endpoints;
- account/proxy/token response redaction.

Test mutation exact route/payload mà frontend dùng:

- wallet adjustment và retry cùng idempotency key;
- user status/role;
- plan create/update/toggle/delete behavior;
- payment confirm/reject + reason;
- review approve/reject/hide;
- account add/delete với mock network/rotator an toàn;
- proxy add/delete bằng id;
- maintenance/popup/theme/layout;
- token add/list-masked/delete;
- mobileconfig temp file, không ghi production static file.

Test failure injection audit cho wallet/payment. Test direct SQL invalid role trên migrated legacy DB.

### 10.2 Frontend endpoint tests

Thêm test cho `adminEndpoints.ts` xác minh chính xác:

- URL;
- HTTP method;
- query param;
- JSON/FormData payload;
- mapping response/pagination.

Không chỉ snapshot UI.

### 10.3 Browser E2E với backend thật

Khởi động Flask bằng temporary SQLite DB và credential admin test; khởi động Vite/preview. Seed dữ liệu test có user, wallet, payment, order, review và queue để UI không toàn số 0.

E2E tối thiểu:

1. Guest `/admin` → `/login?returnTo=...`.
2. User login → dashboard; direct admin → 403 UI; admin API → 403.
3. Admin login tại cùng `/login` → `/admin`.
4. Overview hiển thị đúng số liệu seed, chart có dữ liệu, recent tables có rows.
5. Users list render; search/filter/page hoạt động; mở detail không crash.
6. Điều chỉnh ví +10; UI và DB tăng đúng một lần; retry không tăng lần hai.
7. Orders list/search/filter render đúng.
8. Payments list render; confirm/reject trên fixture an toàn và audit xuất hiện.
9. Plan toggle gọi endpoint thành công và trạng thái tồn tại sau reload.
10. Review moderation thành công; ảnh admin load được với auth.
11. Queue hiển thị waiting/processing/recent theo fixture.
12. Account/proxy system form gửi đúng payload; dùng mock external network ở backend test fixture để không gọi dịch vụ thật.
13. Settings load/save thành công; maintenance behavior đúng `allow_admin`.
14. Audit log render `before/after` đúng.
15. Không có request 404/405/500 ngoài tình huống test cố ý.
16. Không có uncaught exception hoặc console error React.
17. Refresh trực tiếp `/admin/users` không 404 ở cấu hình production SPA.
18. Logout xóa auth state.

Nếu Antigravity không có browser automation, vẫn phải viết E2E/contract test chạy được và ghi rõ chưa chạy; không được tuyên bố production-ready. Ưu tiên dùng browser capability nếu có.

## 11. Kiểm tra nginx/deploy

- `/api/admin/*` phải được proxy Flask, giữ Authorization, cookie và body upload.
- `/admin` và `/admin/*` phải về React `index.html`, trừ các legacy path được ghi rõ.
- Kiểm tra regex legacy không nuốt React route mới.
- `client_max_body_size` cho mobileconfig phù hợp backend limit.
- `/api/admin/reviews/images/*` hoạt động với auth hoặc cơ chế blob/ticket.
- Kiểm tra cấu hình bằng `nginx -t` nếu môi trường có nginx; nếu không, review route precedence và ghi rõ chưa chạy được.
- Update deploy docs và không tuyên bố nginx đã test nếu chỉ sửa text config.

## 12. Lệnh xác minh cuối

Chạy từ đúng thư mục và ghi exit code:

```powershell
cd D:\toolvip\locketgold\Locket_Gold_Huy_Dev\backend
C:\Python314\python.exe -m unittest discover -s tests -p "test_*.py"

cd D:\toolvip\locketgold\Locket_Gold_Huy_Dev\frontend
npm.cmd run build
```

Sau đó chạy frontend contract tests và browser E2E mới. Nếu thêm dependency test, cập nhật lockfile. Không được dùng DB thật hoặc secret thật.

## 13. Definition of Done

Chỉ hoàn thành khi tất cả điều sau đúng:

- FE/BE có một documented contract và exact contract tests.
- Overview hiển thị số thật, không fallback về 0 do field sai.
- Users/Orders/Payments/Reviews/Audit/Queue render dữ liệu thật và pagination đúng.
- Toàn bộ mutation UI gọi endpoint thật thành công, không còn 404/405 do mismatch.
- Account/proxy/settings dùng đúng identifier/payload.
- Không còn review feature UI-only.
- Token API không lộ `fetch_token` hay secret tương đương.
- Financial mutation có audit guarantee đã test.
- Legacy DB có role constraint thực sự.
- Maintenance và `allow_admin` hoạt động đúng.
- Backend full suite pass.
- Frontend build pass.
- Frontend endpoint/contract tests pass.
- Browser E2E với Flask thật pass.
- Network log của luồng E2E không có 404/405/500 bất ngờ.
- Browser console không có uncaught error.
- Không secret nào xuất hiện trong response fixture, log, audit hoặc commit.

## 14. Báo cáo cuối — phải trung thực và có bằng chứng

Báo cáo theo cấu trúc:

1. Root cause đã sửa.
2. Contract cuối cùng và route/payload thay đổi.
3. File chính đã sửa/tạo.
4. Migration và compatibility impact.
5. Test command, số test, thời gian, exit code.
6. Browser E2E scenarios và kết quả.
7. Các request lỗi còn lại nếu có.
8. Phần nào chưa kiểm tra được phải ghi thẳng là chưa kiểm tra; không dùng từ “100%”, “production-ready” nếu còn bất kỳ điều kiện Definition of Done nào chưa đạt.

Bắt đầu ngay bằng audit source và baseline tests. Sau đó sửa theo từng phase, liên tục chạy test hẹp, cuối cùng chạy full suite + build + contract + E2E.
