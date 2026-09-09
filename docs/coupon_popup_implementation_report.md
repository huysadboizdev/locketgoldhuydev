# BÁO CÁO HOÀN THIỆN HỆ THỐNG MÃ GIẢM GIÁ (COUPONS) & POPUP THÔNG BÁO TOÀN TRANG
**Dự án:** Locket Gold VIP Platform (`D:\toolvip\locketgold\Locket_Gold_Huy_Dev`)  
**Ngày hoàn thiện:** 08/09/2026  
**Trạng thái kiểm thử:** 220/220 Backend Tests PASS (0 failures, 0 errors) | Frontend Build: 100% SUCCESS

---

## 1. TỔNG QUAN THỰC HIỆN

Hệ thống đã được thiết kế và triển khai hoàn thiện triệt để hai phân hệ trọng tâm:
1. **Hệ thống Mã giảm giá (Coupons):** Áp dụng độc quyền cho mua gói dịch vụ (qua Coin và chuyển khoản VietQR tự động), **tuyệt đối không áp dụng cho nạp ví (wallet topup)**.
2. **Hệ thống Popup thông báo toàn trang:** Quản lý tập trung bởi Admin với hợp đồng chuẩn 12 trường dữ liệu, hiển thị responsive, khả năng truy cập (A11y), lưu trữ trạng thái đóng theo phiên bản (versioned persistence), lọc lộ trình (route matching) và xem trước trực quan (Live Preview).
3. **Bảo vệ toàn vẹn Account Pool:** Kiểm tra và giữ nguyên 100% giao diện và nghiệp vụ của **Account Pool & Rotator** tại Subtab 1 trang Admin System, bảo đảm nguồn tài khoản cho worker queue kích hoạt tự động chạy ổn định.

---

## 2. CHI TIẾT TRIỂN KHAI PHÂN HỆ MÃ GIẢM GIÁ (COUPONS)

### 2.1. Thiết Kế Cơ Sở Dữ Liệu & Migration Tự Động (SQLite)
Hệ thống migration trong `backend/locket/db.py` thực hiện khởi tạo và cập nhật schema tự động, bảo đảm tính bất biến (idempotent):
- **Bảng `coupons`:**
  - `id`: Khóa chính tự tăng.
  - `code`: Mã coupon gốc.
  - `normalized_code`: Mã chuẩn hóa (viết hoa, lược bỏ ký tự đặc biệt, trim khoảng trắng).
  - `name`: Tên chiến dịch khuyến mãi.
  - `discount_type`: `'percent'` hoặc `'fixed_vnd'` (`'fixed'`).
  - `discount_value`: Phần trăm giảm (1–99) hoặc số tiền cố định (bội số 1.000 VNĐ).
  - `max_discount_vnd`: Giới hạn mức giảm tối đa (cho loại giảm theo %).
  - `min_order_vnd`: Giá trị đơn hàng tối thiểu (mặc định 1.000 VNĐ, bội số 1.000 VNĐ).
  - `usage_limit_total`: Giới hạn tổng số lượt toàn hệ thống (`NULL` = không giới hạn).
  - `usage_limit_per_user`: Giới hạn số lượt/người dùng (`NULL` = không giới hạn).
  - `starts_at` & `ends_at`: Cửa sổ thời gian hiệu lực (Unix timestamp).
  - `is_active`: Cờ kích hoạt (1 = hoạt động, 0 = tạm dừng).
  - `created_by_admin_id`, `created_at`, `updated_at`.
- **Bảng `coupon_plan_rules`:**
  - `id`, `coupon_id`, `plan_id`: Quy tắc giới hạn danh mục gói dịch vụ được áp dụng. Nếu không cấu hình bản ghi nào, mã có hiệu lực trên toàn bộ các gói.
- **Bảng `coupon_redemptions` (Máy trạng thái Quota Reservation):**
  - `id`, `coupon_id`, `user_id`.
  - `payment_order_id`: Liên kết đơn VietQR.
  - `activation_order_id`: Liên kết đơn kích hoạt sau cùng.
  - `original_vnd`, `discount_vnd`, `final_price_vnd`: Bản chụp giá trị tính toán.
  - `status`: `'reserved'` (giữ chỗ khi tạo VietQR) -> `'redeemed'` (khi duyệt thanh toán/mua bằng Coin) -> `'released'` (khi đơn hủy hoặc hết hạn).
  - `created_at`, `redeemed_at`.
- **Mở rộng các bảng hiện hữu (Snapshot Fields):**
  - `payment_orders`: Thêm `coupon_id`, `coupon_code_snapshot`, `original_amount_vnd`, `discount_amount_vnd`.
  - `activation_orders`: Thêm `coupon_id`, `coupon_code_snapshot`, `original_price_vnd_snapshot`, `discount_vnd_snapshot`, `original_price_coin_snapshot`, `price_coin_snapshot`.

### 2.2. Thuật Toán Định Giá & Làm Tròn Số Nguyên (Integer Arithmetic)
File `backend/locket/coupon_service.py` triển khai thuật toán tính toán hoàn toàn bằng số nguyên, không dùng số thực (float) để triệt tiêu lỗi làm tròn tiền tệ:
- **Tỷ lệ quy đổi:** Cố định `1 Coin = 1.000 VNĐ`.
- **Giảm theo %:** `discount_vnd = floor(original_vnd * discount_value / 100)`.
  - Làm tròn xuống bội số 1.000 VNĐ: `discount_vnd = (discount_vnd // 1000) * 1000`.
  - Giới hạn bởi `max_discount_vnd` nếu có cấu hình.
- **Giảm cố định VNĐ:** `discount_vnd = (discount_value // 1000) * 1000`.
- **Quy tắc sàn giá trị đơn hàng:** `discount_vnd = min(discount_vnd, max(0, original_vnd - 1000))`. Đơn hàng luôn bảo đảm giá tối thiểu `final_vnd >= 1.000 VNĐ` (tương đương `final_coin >= 1 Coin`).
- **Quy đổi Coin:** `discount_coin = discount_vnd // 1000`, `final_coin = final_vnd // 1000`.

### 2.3. Máy Trạng Thái Giữ Chỗ & Đồng Quy (Concurrency & State Machine)
- **Thanh toán bằng Coin:**
  - Thực thi trong một SQLite transaction nguyên tử (`BEGIN IMMEDIATE`).
  - Kiểm tra điều kiện mã -> Trừ Coin ví người dùng theo `final_coin` -> Tạo đơn kích hoạt -> Ghi nhận redemption trạng thái `redeemed` ngay lập tức.
  - **Chính sách hoàn tiền (Refund Policy):** Khi đơn hàng lỗi và hệ thống hoàn Coin, số Coin hoàn trả được lấy trực tiếp từ `price_coin_snapshot` (số Coin thực khách đã chi trả), ngăn chặn triệt để trục lợi hoàn tiền vượt mức giá gốc.
- **Thanh toán qua chuyển khoản VietQR:**
  - Khởi tạo đơn: Đặt trạng thái `reserved` cho coupon quota.
  - Xác nhận thanh toán (`confirm_payment_order_tx`): Chuyển trạng thái từ `reserved` sang `redeemed`.
  - Từ chối/Hết hạn (`reject_payment_order_tx`): Chuyển trạng thái `reserved` sang `released`, giải phóng quota cho khách khác.
  - Gia hạn mã QR (`renew_payment_order_tx`): Hỗ trợ chuyển tiếp giữ chỗ coupon sang mã QR mới mà không tính trùng lặp lượt sử dụng.

### 2.4. Giao Diện Người Dùng & Quản Trị
- **Giao diện Mua Gói (`frontend/src/pages/dashboard/ActivationWizard.tsx`):**
  - Tích hợp ô nhập coupon trực quan, phím tắt Enter, kiểm tra báo giá tức thì (`POST /api/coupons/validate`).
  - Huy hiệu (pill) hiển thị thông tin chiết khấu rõ ràng, nút hủy áp dụng.
  - Tự động hiển thị chi tiết: Giá gốc -> Chiết khấu -> Giá thực trả cả bằng VNĐ lẫn Coin.
  - Kiểm tra số dư Coin và nút "Nạp thêm" tính toán chính xác theo `final_coin`.
  - Đồng bộ `coupon_code` vào đơn VietQR tự động.
- **Giao diện Quản trị (`frontend/src/pages/admin/AdminCoupons.tsx`):**
  - Tìm kiếm, lọc trạng thái (`all`, `active`, `inactive`, `exhausted`).
  - Bảng quản lý đầy đủ thông tin: Mã, mức giảm, đơn tối thiểu, số lượt đã dùng/tổng, gói áp dụng, nút toggle kích hoạt nhanh.
  - Modal tạo/sửa mã có validate số nguyên, bội số 1.000 VNĐ, chọn đa gói dịch vụ.
  - Modal thống kê (Stats): Tổng lượt dùng, tổng tiền giảm, doanh thu thực tế và danh sách lịch sử áp dụng chi tiết.

---

## 3. CHI TIẾT TRIỂN KHAI PHÂN HỆ POPUP THÔNG BÁO TOÀN TRANG

### 3.1. Hợp Đồng Dữ Liệu Chuẩn 12 Trường (Unified 12-Field Contract)
1. `enabled`: (boolean) Bật/tắt popup toàn hệ thống.
2. `version`: (integer >= 1) Phiên bản cấu hình, dùng để reset trạng thái đã đóng của người dùng.
3. `title`: (string) Tiêu đề thông báo.
4. `message`: (string) Nội dung chi tiết (hỗ trợ xuống dòng, tự động tương thích trường cũ `content`).
5. `icon`: (enum) 1 trong 12 biểu tượng: `info`, `sparkles`, `party`, `warning`, `help`, `gift`, `bell`, `wrench`, `shield`, `success`, `error`, `question`.
6. `button_text`: (string) Nhãn nút kêu gọi hành động (CTA).
7. `button_url`: (string) Liên kết nút bấm (tương thích trường cũ `button_link`).
8. `dismissible`: (boolean) Cho phép người dùng đóng popup hay không.
9. `audience`: (enum) Đối tượng hiển thị (`all`, `guests`, `logged_in`).
10. `display_mode`: (enum) Tần suất xuất hiện (`once_per_version`, `once_per_session`, `every_visit`).
11. `routes`: (array of strings) Danh sách đường dẫn áp dụng (ví dụ: `["*"]` hoặc `["/", "/dashboard", "/track"]`).
12. `start_at` & `end_at`: (ISO 8601 string / null) Lịch trình thời gian hiệu lực tự động.

### 3.2. Bảo Mật & Xác Thực Đường Dẫn
- Backend (`backend/locket/site_settings.py`) kiểm duyệt chặt chẽ `button_url`:
  - Chỉ chấp nhận đường dẫn nội bộ bắt đầu bằng `/` (ví dụ `/dashboard`) hoặc liên kết an toàn ngoài bắt đầu bằng `https://`.
  - Chặn đứng các scheme nguy hiểm như `javascript:`, `data:`, `file:`.
- Tính toán cờ `active` tự động tại backend dựa trên `start_at` và `end_at`.

### 3.3. Thành Phần Frontend Khả Dụng (`GlobalAnnouncementPopup.tsx`)
- Gắn duy nhất 1 lần tại gốc ứng dụng `frontend/src/App.tsx`, bao quát tất cả route.
- Tuân thủ tiêu chuẩn trợ năng WAI-ARIA (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `aria-describedby`).
- Hỗ trợ đóng bằng phím ESC và bấm ra ngoài nền mờ khi `dismissible = true`.
- Tự động điều hướng SPA qua `navigate()` cho đường dẫn nội bộ và mở tab mới an toàn (`rel="noopener,noreferrer"`) cho `https://`.
- Lưu trữ trạng thái đóng theo `version`: Khách đã đóng phiên bản cũ sẽ được hiển thị lại ngay khi Admin tăng `version` lên +1.

### 3.4. Quản Trị & Xem Trước (Subtab Popup trong `AdminSystem.tsx`)
- Giao diện biên tập đầy đủ 12 trường cấu hình.
- Bộ chọn biểu tượng trực quan hiển thị cả 12 icon.
- Nút bấm **+1 Version** giúp tăng phiên bản nhanh chóng để phát hành lại thông báo.
- Nút **Xem thử Popup (Live Preview Modal)** giúp Admin trải nghiệm giao diện popup thực tế trước khi lưu cấu hình.

---

## 4. BẢO VỆ TOÀN VẸN ACCOUNT POOL & WORKER QUEUE

- Đã kiểm tra đối chiếu trực tiếp `AdminSystem.tsx` Subtab 1:
  - Danh sách tài khoản Locket Pool xoay vòng được giữ nguyên vẹn.
  - Nghiệp vụ thêm tài khoản (`addAdminAccount`) và xóa tài khoản (`deleteAdminAccount`) hoạt động chuẩn xác.
  - Phục vụ liên tục cho `AccountRotator` và background worker queue cấp phép tự động, không gây gián đoạn bất kỳ luồng xử lý nào.

---

## 5. KẾT QUẢ KIỂM THỬ TỔNG THỂ

### 5.1. Backend Test Suite
Chạy toàn bộ 220 tests với lệnh `python -m unittest discover -s tests`:
```
Ran 220 tests in 4.218s
OK (0 failures, 0 errors)
```
Trong đó bộ kiểm thử chuyên sâu `tests/test_coupon_popup_system.py` bao gồm 12 bài test toàn diện:
1. `test_coupon_normalization`: Chuẩn hóa mã, loại bỏ khoảng trắng và ký tự lạ.
2. `test_coupon_pricing_math`: Kiểm tra số học nguyên, làm tròn 1.000 VNĐ, trần chiết khấu, sàn giá đơn hàng 1.000 VNĐ.
3. `test_validate_coupon_api`: Xác thực API báo giá cho người dùng.
4. `test_coin_purchase_with_coupon_and_refund`: Mua gói bằng Coin áp dụng coupon, kiểm tra số dư và hoàn tiền theo giá thực trả.
5. `test_vietqr_payment_order_with_coupon_lifecycle`: Chu trình VietQR (giữ chỗ -> duyệt -> hoàn tất).
6. `test_vietqr_payment_reject_releases_coupon`: Hủy đơn giải phóng quota.
7. `test_renew_payment_order_preserves_coupon`: Gia hạn đơn VietQR bảo lưu quota không trùng lặp.
8. `test_coupon_concurrency_race_condition`: Kiểm tra chống oversell đồng quy khi nhiều user cùng dùng coupon giới hạn.
9. `test_popup_payload_validation_and_url_security`: Bảo mật URL và chuẩn hóa 12 trường của popup.
10. `test_popup_active_and_public_settings_api`: Kiểm tra cờ active và API cài đặt công khai.
11. `test_admin_coupon_crud_api_and_stats`: CRUD coupon qua Admin API và báo cáo thống kê.
12. `test_db_migration_idempotency`: Khởi tạo DB lặp lại an toàn không phát sinh lỗi schema.

### 5.2. Frontend Production Build
Chạy lệnh `npm.cmd run build` tại thư mục `frontend/`:
```
vite v6.4.3 building for production...
✓ 1672 modules transformed.
dist/index.html                                       1.25 kB
dist/assets/index-C9_Nnhdx.css                      137.41 kB
dist/assets/DashboardPage-Bx2sCQp9.js               140.41 kB
dist/assets/AdminPage-dUqZBFPi.js                   192.38 kB
dist/assets/index-D8tyBe2l.js                       365.20 kB
✓ built in 1.79s
```
0 lỗi TypeScript, 0 cảnh báo phân giải gói, sẵn sàng bàn giao vận hành trên môi trường production.

---

## 6. HẬU KIỂM VÀ GIA CỐ SAU NGHIỆM THU (08/09/2026)

Hậu kiểm trực tiếp đã phát hiện và sửa thêm các trường hợp biên chưa được 12 test ban đầu bao phủ:

- Retry cùng `idempotency_key` khi có coupon giờ trả đúng đơn Coin/VietQR cũ, không trừ Coin hai lần, không chiếm thêm quota và không phụ thuộc việc coupon đã đổi/hết hạn sau lần mua đầu.
- Renew QR chuyển reservation trong cùng một `BEGIN IMMEDIATE`; nếu reservation đã được giải phóng thì phải lấy lại quota hợp lệ. Mỗi payment cũ chỉ sinh tối đa một payment thay thế qua `renewed_from_payment_id` unique.
- Xác nhận thủ công khoản chuyển đến muộn chuyển redemption `released -> redeemed` để thống kê phản ánh đúng khoản đã thu.
- Người dùng có endpoint hủy QR thuộc sở hữu của mình; việc đổi/bỏ coupon trên wizard đóng QR cũ và trả quota ngay.
- Validation Admin coupon không còn âm thầm cắt phần thập phân/boolean thành số nguyên; giới hạn tùy chọn có thể xóa về `null`; bộ lọc `exhausted` hoạt động đúng; lịch sử redemption không bị xóa cứng.
- Popup chặn protocol-relative URL, URL chứa credentials, route sai định dạng, CTA thiếu một nửa và datetime lệch kiểu timezone; modal toàn cục có focus management, focus trap, khóa cuộn và khôi phục focus.
- Wizard không còn tự POST tạo QR vô hạn khi API lỗi và có nút thử lại rõ ràng.

Kết quả cuối sau gia cố:

```text
Backend: Ran 225 tests — OK
Frontend: npm.cmd run build — OK (0 TypeScript errors)
Python: python -m compileall -q locket tests — OK
Legacy DB migration dry-run trên bản sao backup — OK
```
