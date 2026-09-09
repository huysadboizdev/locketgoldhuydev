# MASTER PROMPT CHO ANTIGRAVITY CLI — XÂY DỰNG REACT ADMIN DÙNG CHUNG AUTH VỚI USER

Bạn đang làm việc trực tiếp trong workspace:

`D:\toolvip\locketgold\Locket_Gold_Huy_Dev`

Hãy đóng vai trò Senior Full-stack Engineer kiêm Security Engineer, Database Engineer và QA Lead. Nhiệm vụ của bạn là **phân tích, thiết kế, triển khai, kiểm thử và hoàn thiện end-to-end** một trang quản trị React mới cho hệ thống Locket Gold hiện có. Không chỉ tạo giao diện mẫu; mọi số liệu và thao tác phải nối với backend/database thật, có phân quyền thật và có test hồi quy.

## 0. Quy tắc dùng skill, agent và công cụ

Trước khi sửa code:

1. Tìm và đọc toàn bộ `AGENTS.md`, `CLAUDE.md`, README và hướng dẫn cấp workspace/repository có liên quan.
2. Liệt kê các skill/capability đang có trong Antigravity CLI và **chủ động dùng tất cả skill thực sự phù hợp** cho các mảng: lập kế hoạch, backend Flask, React/TypeScript, UI/UX, database/SQLite, authentication/security, test và browser/E2E. Phải đọc đầy đủ hướng dẫn của skill trước khi dùng.
3. Nếu CLI hỗ trợ sub-agent/parallel agent, có thể giao các audit độc lập cho backend/auth, frontend/routing và test/security; agent chính phải tự kiểm tra, tích hợp và chịu trách nhiệm kết quả cuối cùng. Không để nhiều agent sửa chồng cùng một file.
4. Không dùng skill không liên quan chỉ để đủ số lượng. Không dùng image generation cho dashboard này nếu giao diện có thể xây bằng React/CSS/icon hiện có.
5. Dùng bằng chứng từ source code hiện tại làm nguồn sự thật. Không đoán API/schema nếu có thể đọc được trong repo.
6. Trước khi code, xuất một implementation plan ngắn theo phase; sau đó tiếp tục triển khai, không dừng lại chỉ để chờ xác nhận cho các quyết định kỹ thuật thông thường.
7. Không chạy lệnh phá hủy, không reset thay đổi của người dùng, không xóa database thật, không log/hiển thị secret. Nếu worktree có thay đổi sẵn, phải giữ nguyên phần không liên quan.

## 1. Bối cảnh kỹ thuật đã biết

- Frontend: React 19, TypeScript, Vite, React Router, Tailwind CSS, `lucide-react`, `motion`.
- Backend: Flask, SQLite WAL, thread-local connection, worker queue chạy nền.
- Auth user hiện tại:
  - Access token JWT chỉ giữ trong memory phía React.
  - Refresh token opaque nằm trong HttpOnly cookie, path `/api/auth`.
  - Có refresh-token rotation, replay detection, CSRF và rate limiting.
  - `access_required` đọc lại user/session từ database ở mỗi request.
- User hiện nằm trong bảng `users`, chưa có role admin.
- Frontend user có landing page, `/login`, `/register`, `/dashboard/*`.
- Backend đang tồn tại admin cũ:
  - Flask template tại `/admin`.
  - Dùng `ADMIN_USERNAME`, `ADMIN_PASSWORD`, Flask session `session["admin"]` và CSRF riêng.
  - Có sẵn nhiều business operation cho account pool, tokens, queue, popup, maintenance, theme, layout, proxies, mobileconfig, reviews, plans, payments và wallet adjustment.
- Các file cần đọc kỹ tối thiểu:
  - `frontend/src/App.tsx`
  - `frontend/src/context/AuthContext.tsx`
  - `frontend/src/components/auth/ProtectedRoute.tsx`
  - `frontend/src/pages/LoginPage.tsx`
  - `frontend/src/pages/RegisterPage.tsx`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/api/client.ts`
  - `frontend/src/api/endpoints.ts`
  - `frontend/src/types/api.ts`
  - `frontend/src/utils/url.ts`
  - `frontend/src/hooks/useSiteSettings.ts`
  - `backend/locket/__init__.py`
  - `backend/locket/config.py`
  - `backend/locket/db.py`
  - `backend/locket/token_auth.py`
  - `backend/locket/user_auth.py`
  - `backend/locket/admin/auth.py`
  - `backend/locket/admin/routes.py`
  - `backend/locket/public/routes.py`
  - `backend/locket/site_settings.py`
  - toàn bộ `backend/tests/test_*.py`
  - file deploy/nginx liên quan.

Không được viết lại toàn bộ dự án hoặc phá vỡ worker queue hiện có. Ưu tiên tái sử dụng business logic/database helper đang hoạt động, nhưng tách logic dùng chung khỏi Flask route khi cần để không gọi route handler từ route handler.

## 2. Kết quả nghiệp vụ bắt buộc

Chỉ có **một luồng đăng nhập chung**:

```text
Landing / Register / Login dùng chung
               |
               v
       POST /api/auth/login
               |
       Backend trả user.role
          /             \
  role=user          role=admin
      |                   |
 /dashboard             /admin
```

Hành vi chính xác:

1. Không tạo form đăng nhập admin riêng.
2. Admin đăng nhập tại chính `/login` đang dùng cho user.
3. Sau login thành công:
   - `role=user` đi tới `/dashboard` hoặc một `returnTo` hợp lệ thuộc dashboard.
   - `role=admin` đi tới `/admin` hoặc một `returnTo` hợp lệ thuộc admin.
4. Admin vẫn có thể tự mở `/dashboard` và dùng các tính năng user; yêu cầu “khác nhau chủ yếu ở trang chuyển tới sau login”.
5. User thường không được đọc hoặc mutate bất kỳ `/api/admin/*` nào, kể cả gọi API trực tiếp ngoài UI.
6. User thường mở `/admin` phải được đưa về `/dashboard` hoặc trang 403 thân thiện; backend vẫn phải trả 403 cho API.
7. Guest mở `/admin` được đưa tới `/login?returnTo=/admin`.
8. Landing page, login page và register page vẫn là giao diện dùng chung; không làm lộ secret hoặc logic nhận diện admin trên client.
9. Public register tuyệt đối không được nhận `role`, `is_admin`, permission hoặc trường tương đương từ request. Mọi tài khoản đăng ký công khai luôn là `user`.
10. Tài khoản admin được provision tự động từ biến môi trường backend; không tạo bằng form register công khai.

## 3. Provision admin an toàn từ `.env`

Hỗ trợ các biến backend sau và cập nhật tài liệu/`.env.example` nếu repo có file example:

```env
ADMIN_EMAIL=admin@example.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-a-long-random-password
ADMIN_DISPLAY_NAME=Administrator
ADMIN_ALLOW_GOOGLE_LOGIN=0
```

Không đưa các giá trị này sang biến `VITE_*`, frontend bundle hoặc API response. Không tự ghi secret thật vào repo.

Tạo một bootstrap/provision function chạy **sau `db.init()` nhưng trước khi app nhận request**:

- Nếu tất cả biến bắt buộc đều không có: dev có thể cảnh báo rõ; production (`BEHIND_HTTPS=1`) phải fail fast theo chính sách cấu hình đã thống nhất trong code/docs.
- Nếu chỉ có một phần biến bắt buộc: fail fast với tên biến còn thiếu, không in giá trị.
- Validate email, username và độ dài/độ mạnh password ít nhất ngang public register.
- Normalize email/username giống auth hiện tại.
- Nếu chưa có record: hash bằng cơ chế hiện tại, tạo user role `admin` và wallet tương ứng nếu application invariant yêu cầu.
- Nếu email và username cùng trỏ tới đúng một record: bảo đảm role là `admin`, cập nhật display name hợp lý và chỉ re-hash password khi `check_password_hash` cho thấy password env đã đổi.
- Nếu email và username trỏ tới hai record khác nhau, hoặc một identifier xung đột với user khác: fail fast; không tự merge, xóa hay nâng quyền mơ hồ.
- Khi password hoặc role admin thay đổi, revoke các auth session hiện có của account đó để credential/permission cũ không tiếp tục dùng được.
- Chạy bootstrap nhiều lần phải idempotent, không tạo record/session/wallet trùng.
- Không cho admin seed bị xóa, khóa hoặc hạ role qua UI quản trị.

Kiểm tra và sửa vấn đề load `.env` quá muộn: hiện `create_app()` gọi `dotenv.load_dotenv()` sau khi một số module auth có thể đã được import và đọc env ở module scope. Bảo đảm `JWT_SECRET`, `REFRESH_TOKEN_PEPPER`, admin vars và config bảo mật thật sự lấy từ `.env` trước khi được đóng băng thành constant. Chọn giải pháp sạch, test được, không dựa vào side effect ngẫu nhiên của import order.

## 4. Migration database

Tạo migration idempotent theo phong cách hiện có, không làm mất dữ liệu:

1. Thêm `users.role` với default `user`; chỉ cho giá trị `user` hoặc `admin`.
2. Toàn bộ user cũ phải giữ nguyên và trở thành `user`.
3. Cân nhắc index `users(role)` và các index phục vụ thống kê sau khi kiểm tra query.
4. Thêm bảng audit log quản trị, ví dụ:

```text
admin_audit_logs
- id
- admin_user_id
- action
- entity_type
- entity_id
- before_json (đã redact)
- after_json (đã redact)
- ip_address
- user_agent (giới hạn độ dài)
- created_at
```

Audit log không bao giờ chứa password, password hash, raw refresh token, JWT, raw service token, full proxy credential, CSRF token hay dữ liệu bí mật tương đương.

Nếu cần migration bảng phức tạp trong SQLite, dùng transaction và chiến lược tương thích database hiện hữu. Tuyệt đối không xóa `locket.db` để “migration cho dễ”. Test migration trên temporary DB và trên fixture mô phỏng schema cũ.

## 5. Hợp nhất auth và phân quyền

Thêm `role` nhất quán vào user object của tất cả flow:

- register;
- password login;
- Google login;
- refresh;
- `/api/auth/me`;
- callback/state trong `AuthContext`;
- TypeScript `AuthUser`.

Yêu cầu bảo mật:

1. Xây decorator/helper admin mới dựa trên `access_required` và `g.current_user` từ database.
2. Không tin role frontend gửi lên.
3. Không dùng Flask `session["admin"]` để cấp quyền cho `/api/admin/*` mới.
4. Không chỉ kiểm tra role ở React route guard.
5. Phân biệt response:
   - 401: chưa đăng nhập/token sai/hết hạn.
   - 403: đã đăng nhập nhưng không đủ quyền.
6. Mutating admin API phải dùng Bearer auth và CSRF theo convention của `apiClient`; giữ `Cache-Control: private, no-store`.
7. `access_required` đang đọc DB mỗi request là lợi thế: dùng role mới nhất trong DB để thay đổi quyền có hiệu lực ngay. Nếu có đưa role vào JWT để tiện client thì backend vẫn phải kiểm tra role DB.
8. Mặc định từ chối Google auth/link cho record `role=admin` khi `ADMIN_ALLOW_GOOGLE_LOGIN != 1`. Trả lỗi an toàn, không tiết lộ thông tin thừa. Nếu opt-in thì chỉ cho phép Google subject đã liên kết rõ ràng, không auto-link admin chỉ dựa trên email.
9. Giữ nguyên refresh rotation, replay detection, session ownership và logout hiện có.
10. Đảm bảo React StrictMode không gây hai refresh rotation cạnh tranh; không phá `bootstrapPromise` hiện có.

## 6. Route và xử lý admin Flask cũ

Mục tiêu URL cuối:

- React SPA admin: `/admin/*`.
- JSON admin API mới: `/api/admin/*`.
- User API giữ nguyên `/api/*` hiện tại.

Backend admin cũ đang chiếm `/admin` và `/admin/api/*`. Hãy xử lý migration có kiểm soát:

1. Inventory toàn bộ endpoint cũ và chức năng UI cũ trước khi đổi route.
2. Chuyển logic JSON cần thiết sang `/api/admin/*`, bảo vệ bằng Bearer role admin mới.
3. Tái sử dụng service/db helper hiện có; tránh duplicate business rule cho payment/wallet/queue.
4. Có thể giữ template cũ tạm ở `/legacy-admin` trong giai đoạn tương thích, nhưng không để nó là cơ chế quản trị chính sau khi React admin hoàn tất.
5. `/admin/login` cũ phải chuyển về `/login?returnTo=/admin` hoặc được React Router xử lý phù hợp.
6. Legacy Flask session không được cấp quyền cho API admin mới.
7. Khi đạt parity và test pass, gỡ dependency quyền quản trị chính vào `session["admin"]`; các đường đặc biệt trong `public/routes.py` đang dựa vào session admin phải được chuyển sang cơ chế mới hoặc loại bỏ an toàn.
8. Cập nhật Vite/nginx/deploy để:
   - chỉ proxy `/api` tới Flask;
   - `/admin` và `/admin/*` trả React SPA;
   - refresh trực tiếp `/admin/users` không 404;
   - asset và upload/download route không bị SPA fallback nuốt.

## 7. Maintenance mode — không được khóa admin ở ngoài

Hiện frontend trả `MaintenanceScreen` trước toàn bộ router và backend `_maintenance_active()` dựa vào Flask admin session. Đây là điểm dễ khóa admin khỏi hệ thống.

Sửa theo các điều kiện:

- `/login` luôn truy cập được trong maintenance để admin có thể đăng nhập.
- Guest/user thường vẫn thấy maintenance screen theo cấu hình.
- Admin role mới vào được `/admin` khi `maintenance.allow_admin=true`.
- Admin API cần để tắt maintenance vẫn hoạt động cho admin.
- Không dựa vào legacy Flask session để bypass.
- Không tạo vòng lặp: maintenance → login → redirect admin → maintenance.
- Nếu backend offline thật, hiển thị trạng thái lỗi khác maintenance.

## 8. API admin mới

Trước tiên inventory response hiện có, sau đó chuẩn hóa type và lỗi. Tối thiểu cần:

### Dashboard/analytics

`GET /api/admin/overview?range=7d|30d|90d`

Response ổn định, có ít nhất:

```json
{
  "success": true,
  "range": "30d",
  "timezone": "Asia/Bangkok",
  "generated_at": 0,
  "cards": {
    "total_users": 0,
    "new_users": 0,
    "paid_revenue_vnd": 0,
    "paid_payments": 0,
    "pending_payments": 0,
    "total_orders": 0,
    "completed_orders": 0,
    "failed_orders": 0,
    "completion_rate": 0,
    "pending_reviews": 0,
    "queue_waiting": 0,
    "queue_processing": 0,
    "active_workers": 0
  },
  "series": [],
  "order_status_breakdown": [],
  "platform_breakdown": [],
  "payment_method_breakdown": [],
  "recent_orders": [],
  "recent_payments": []
}
```

Định nghĩa dữ liệu phải rõ:

- Doanh thu chỉ tính `payment_orders.status='paid'` và bucket theo `paid_at`, không cộng lại `activation_orders.price_vnd_snapshot`, tránh double count.
- Khoảng ngày và “hôm nay” tính theo `Asia/Bangkok`, dù DB lưu Unix epoch.
- Completion rate phải tránh chia 0 và ghi rõ mẫu số hợp lý trong code/test.
- Series phải lấp ngày không có dữ liệu bằng 0 để chart không gãy.
- Query aggregate ở SQLite, không tải toàn bộ rows rồi tính trong Python.
- Chặn range tùy ý; chỉ allow-list giá trị hỗ trợ.

### User management

- List/search/filter/pagination user.
- User detail gồm profile an toàn, wallet summary, orders/payments/reviews gần nhất.
- Khóa/mở user có confirm và audit.
- Điều chỉnh Coin dùng transaction atomic, bắt buộc reason và idempotency key do client gửi hoặc server tạo theo request identifier ổn định.
- Không cho thao tác gây số dư âm.
- Không trả password hash/google subject không cần thiết/token/session secrets.

### Operations parity

Port hoặc bọc lại chức năng admin cũ sang `/api/admin/*`:

- plans CRUD;
- payments list/confirm/reject;
- reviews list/moderate/delete/image access;
- queue snapshot;
- Locket account pool list/add/test/remove;
- tokens list/add/remove với masking/redaction hợp lý;
- proxy management/test/master toggle;
- popup, maintenance, theme, layout;
- mobileconfig info/upload/remove/history;
- wallet adjustment.

Mọi list lớn cần `limit`, `offset` hoặc page/page_size có clamp server-side; search phải parameterized. Validate JSON type, enum, length và numeric range ở backend. Không trả raw exception/SQL error ra client trong production.

Các thao tác tiền, confirm/reject payment, wallet adjustment, refund hoặc đổi trạng thái phải giữ transaction/state machine/idempotency hiện có. Không chuyển logic atomic thành chuỗi read-then-write ngoài transaction.

## 9. Audit admin action

Tất cả mutation quan trọng phải ghi audit sau khi transaction nghiệp vụ thành công, hoặc cùng transaction nếu thiết kế cho phép:

- user enable/disable;
- wallet adjustment;
- payment confirm/reject;
- plan create/update/delete;
- review status/delete;
- system settings;
- account/token/proxy/mobileconfig changes.

Audit record cần admin user id thật từ `g.current_user`, action, target, dữ liệu before/after đã redact, IP proxy-aware và timestamp. Audit failure không được âm thầm khiến trạng thái tiền nửa thành công; thiết kế rõ atomicity và test ít nhất các hành động tài chính.

Thêm API read-only có pagination/filter cho audit logs và một tab “Nhật ký quản trị”. Chỉ admin đọc được.

## 10. Frontend React Admin

Tạo lazy-loaded `AdminPage` và các component/module nhỏ; không tạo một file khổng lồ. Gợi ý cấu trúc:

```text
frontend/src/
  pages/admin/
    AdminPage.tsx
    AdminOverview.tsx
    AdminUsers.tsx
    AdminOrders.tsx
    AdminPayments.tsx
    AdminPlans.tsx
    AdminQueue.tsx
    AdminReviews.tsx
    AdminSystem.tsx
    AdminAuditLogs.tsx
  components/admin/
    AdminLayout.tsx
    AdminSidebar.tsx
    StatCard.tsx
    ConfirmDialog.tsx
    DataTable.tsx
    ...
  components/auth/AdminRoute.tsx
```

Có thể điều chỉnh cấu trúc nếu repo convention khác, nhưng phải tách concern rõ ràng.

Yêu cầu UI/UX:

- Tiếng Việt đầy đủ, UTF-8 đúng; không tạo mojibake.
- Đồng bộ ngôn ngữ thiết kế gold/zinc, light/dark theme của website hiện có.
- Responsive tốt cho mobile/tablet/desktop.
- Sidebar desktop, drawer/bottom navigation hợp lý trên mobile.
- Header hiển thị admin, nút sang Dashboard user, theme toggle và logout.
- Overview có stat cards, chart xu hướng, breakdown và recent activity.
- Dùng CSS/SVG hoặc một chart library nhẹ nếu thật sự cần; nếu thêm dependency phải có lý do và không làm bundle phình vô ích.
- Mọi page có loading skeleton, empty state, error state và retry.
- Filter/search có debounce; pagination server-side.
- Poll queue 5–10 giây; overview 30–60 giây hoặc refresh thủ công. Cleanup timer/AbortController khi unmount.
- Không tạo request loop do dependency của `useEffect`.
- Form mutation disable khi submit, chống double-click, hiển thị success/error rõ ràng.
- Destructive action dùng confirm dialog có nội dung cụ thể; không dùng `window.confirm` nếu đã có thể xây component nhất quán.
- Sau mutation phải refetch canonical state hoặc rollback đúng; không để optimistic UI nói thành công khi backend lỗi.
- Accessibility cơ bản: label, focus state, keyboard navigation, `aria-live`, contrast.
- Không dùng `any` tràn lan; tạo TypeScript type cho response/request admin.

Không sao chép toàn bộ HTML/CSS/JS của `templates/admin.html` vào React. Có thể dùng nó làm danh sách tính năng và tham khảo nghiệp vụ, nhưng phải xây component React sạch.

## 11. Redirect và route guard frontend

Refactor `getDashboardReturnTo` thành logic post-login theo role hoặc bổ sung helper mới:

- Chỉ chấp nhận relative internal path bắt đầu bằng đúng một `/`.
- Cấm `//`, backslash, encoded bypass, `javascript:`, `data:` và URL ngoài domain.
- User chỉ được return về `/dashboard` hoặc `/dashboard/*`.
- Admin được return về `/admin`/`/admin/*`; nếu không hợp lệ mặc định `/admin`.
- Admin vẫn được mở `/dashboard` sau khi đã login, nhưng default login redirect là `/admin`.
- Login effect không redirect sớm bằng user object stale.
- Landing entry khi authenticated phải redirect theo role.
- `/register` luôn tạo user và đi `/dashboard`, không bao giờ `/admin`.

Thêm test cho direct navigation, browser refresh, expired token refresh, forbidden route và open redirect.

## 12. Caching, lỗi mạng và hiệu năng

- Admin response chứa PII hoặc operational data: `private, no-store`.
- Không cache lỗi auth.
- Không coi mọi 403 admin là “token hết hạn”; user thiếu role phải giữ login user và hiển thị forbidden/redirect đúng.
- Chỉ refresh access token khi lỗi đúng là `access_token_expired`, giữ behavior an toàn của API client hiện tại.
- Tránh N+1 query ở overview và user list.
- Với SQLite, giữ transaction ngắn, không thực hiện HTTP/network call bên trong write transaction.
- Dùng limit clamp và index phù hợp; chạy `EXPLAIN QUERY PLAN` cho query thống kê/list quan trọng nếu cần.
- Không làm polling admin ảnh hưởng queue worker.

## 13. Security checklist bắt buộc

- [ ] Authorization server-side cho mọi admin endpoint.
- [ ] Register payload không thể mass-assign role.
- [ ] Google flow không thể chiếm admin bằng email matching.
- [ ] Legacy Flask session không cấp quyền API mới.
- [ ] CSRF cho mutation theo convention hiện có.
- [ ] Generic login error; rate limit vẫn hoạt động.
- [ ] No secret trong frontend, response, logs, audit hoặc screenshot.
- [ ] Không trả password hash/raw token/raw proxy credential.
- [ ] Upload mobileconfig giữ size/type validation và safe path.
- [ ] Search/filter dùng parameter binding, không ghép SQL từ input.
- [ ] User cannot read other users' private data qua endpoint user.
- [ ] Admin không tự khóa/xóa/hạ quyền admin seed.
- [ ] Password rotation revoke session cũ.
- [ ] Security headers/no-store cho admin.
- [ ] Open redirect bị chặn.
- [ ] Maintenance không khóa admin khỏi login/control panel.
- [ ] Error response không lộ stack trace trong production.

## 14. Test bắt buộc

Mở rộng test hiện có, dùng temporary SQLite DB; không dùng/xóa database thật.

### Backend tests

1. Migration schema cũ → role mặc định user, không mất dữ liệu.
2. Admin env bootstrap tạo đúng một admin.
3. Bootstrap chạy lại idempotent.
4. Partial env/config conflict fail an toàn.
5. Đổi env password cập nhật hash và revoke session cũ.
6. Register không nhận role/is_admin.
7. Auth response của login/refresh/me/register có role đúng.
8. Google auth không auto-link/nâng quyền admin mặc định.
9. Guest gọi admin API → 401.
10. User gọi admin API → 403.
11. Admin Bearer token → 200.
12. Legacy `session["admin"]` không vào được `/api/admin/*`.
13. Mutating API thiếu/sai CSRF bị từ chối nếu policy yêu cầu.
14. Overview thống kê đúng, không double-count revenue, range/timezone đúng, zero-fill series.
15. User pagination/filter; không lộ secret fields.
16. Wallet/payment idempotency và concurrent/double submit.
17. Audit log được ghi và đã redact.
18. Maintenance allow_admin hoạt động với role mới.
19. Toàn bộ test auth/payment/queue/reviews cũ vẫn pass.

### Frontend verification

- TypeScript compile sạch.
- Vite production build sạch.
- Không có unused import/error nghiêm trọng.
- Nếu test framework chưa có, thêm bộ test tối thiểu hợp lý cho route helper/guard; không cài framework nặng chỉ để có một test hình thức.
- Nếu có browser capability, chạy smoke/E2E:
  - guest landing/login/register;
  - user login → dashboard;
  - user direct `/admin` bị chặn;
  - admin login → admin overview;
  - refresh `/admin/users` vẫn hoạt động;
  - maintenance → login → admin bypass;
  - logout xóa trạng thái và quay về public page.
- Kiểm tra viewport mobile và desktop, light/dark theme.

Lệnh xác minh tối thiểu (điều chỉnh theo môi trường nhưng phải báo chính xác lệnh đã chạy):

```powershell
cd backend
python -m unittest discover -s tests -p "test_*.py"

cd ..\frontend
npm.cmd run build
```

Nếu test/build lỗi do code, phải sửa đến khi pass. Nếu lỗi do dependency/môi trường ngoài phạm vi, ghi rõ bằng chứng và vẫn chạy mọi kiểm tra còn khả thi.

## 15. Thứ tự triển khai đề xuất

1. Audit repo, instruction, current tests và route/deploy topology.
2. Sửa env loading order.
3. Migration `users.role`, audit table và admin bootstrap.
4. Trả role nhất quán trong auth; thêm admin authorization helper.
5. Viết test auth/bootstrap/permission trước hoặc song song với backend API.
6. Xây `/api/admin/overview`, users, audit và port operational endpoints.
7. Chuyển/giữ compatibility admin Flask cũ, giải quyết `/admin` route conflict.
8. Thêm frontend types/endpoints/AuthContext/route helpers/AdminRoute.
9. Xây Admin layout và Overview; sau đó các management tab.
10. Sửa maintenance behavior và deploy/nginx SPA fallback.
11. Chạy full tests/build, smoke test, security regression.
12. Cập nhật README/deploy/env documentation.

Mỗi phase phải tự kiểm tra trước khi đi tiếp. Không che lỗi bằng `try/catch {}` rỗng mới, `as any`, bỏ test, tắt validation hoặc nới quyền.

## 16. Definition of Done

Chỉ coi là hoàn thành khi:

- Admin account từ env được provision an toàn và idempotent.
- Cùng một `/login` phân luồng đúng admin/user.
- Admin React hoạt động thật ở `/admin` và refresh route không 404.
- User không thể truy cập dữ liệu/hành động admin ở backend.
- Overview hiển thị số liệu thật, đúng định nghĩa và timezone.
- Các chức năng quản trị cũ quan trọng đã có trong React admin hoặc được ghi rõ là legacy có đường chuyển tiếp an toàn; không được âm thầm mất chức năng.
- Maintenance không khóa admin.
- Audit log tồn tại cho mutation quan trọng.
- Full backend tests pass.
- Frontend production build pass.
- Không có secret bị commit hoặc in ra output.
- Docs mô tả env, login flow, role, route và cách chạy test/deploy.

## 17. Báo cáo cuối cùng bắt buộc

Khi làm xong, trả báo cáo ngắn nhưng có bằng chứng:

1. Tóm tắt kết quả đã hoàn thành.
2. Danh sách file chính đã tạo/sửa.
3. Migration và biến env mới cần cấu hình, chỉ nêu tên biến/placeholders, không in secret.
4. Route/API mới.
5. Quy tắc phân quyền và redirect thực tế.
6. Lệnh test/build đã chạy và kết quả pass/fail cụ thể.
7. Những rủi ro hoặc phần legacy còn lại, nếu có.
8. Không tuyên bố hoàn thành nếu test bắt buộc chưa chạy hoặc còn lỗi chức năng đã biết.

Hãy bắt đầu bằng việc đọc instruction và audit source hiện tại, sau đó trình bày plan theo phase và triển khai toàn bộ nhiệm vụ.
