# Thiết kế mapping No VPN và cổng cài DNS

Ngày: 2026-10-05

## Mục tiêu

Sửa tích hợp LunaKey để bốn gói No VPN gửi đúng `category` lên API, hiển thị đúng thời hạn Gold/giá bán/bảo hành của shop, và buộc người mua đi qua hướng dẫn cài DNS trước khi tiếp tục. Sau khi thanh toán, màn theo dõi đơn và lịch sử đơn phải tiếp tục hiển thị hướng dẫn DNS để người dùng có thể cài lại hoặc kiểm tra.

Website không được yêu cầu hoặc thu thập Apple ID, mật khẩu iCloud hay mã xác minh. Nội dung an toàn phải giải thích đúng phạm vi của profile DNS, không tuyên bố rằng trình duyệt có thể xác minh profile đã được cài.

## Mapping chuẩn

| Gói | Category LunaKey | Thời hạn Gold | Giá bán | Bảo hành |
| --- | --- | ---: | ---: | ---: |
| Locket Gold 1 tháng | `1month` | 30 ngày | 5.000đ | 1 tháng |
| Locket Gold 3 tháng | `3month` | 90 ngày | 8.000đ | 1 tháng |
| Locket Gold 6 tháng | `6month` | 180 ngày | 9.000đ | 2 tháng |
| Locket Gold 1 năm | `yearly` | 365 ngày | 10.000đ | 2 tháng |

Giá trên là giá bán của website và vẫn được snapshot vào đơn. Không lấy giá nhà cung cấp làm giá thanh toán của khách. Historical order snapshots không bị sửa khi migration cập nhật catalog.

## Luồng người dùng

1. Người dùng thấy đủ bốn thẻ gói No VPN trong catalog.
2. Khi bấm một gói yêu cầu DNS mà phiên làm việc chưa xác nhận cài đặt, wizard giữ lại gói vừa chọn và mở bước `dns_setup`.
3. Bước DNS hiển thị hướng dẫn iPhone chi tiết, nút tải `.mobileconfig`, mã QR/đường dẫn cho người đang xem bằng máy tính, và cảnh báo chỉ mở bằng Safari trên iPhone.
4. Nút tiếp tục chỉ bật sau khi người dùng đã bấm tải profile và đánh dấu xác nhận đã hoàn thành các bước trong Cài đặt. Đây là acknowledgment của người dùng, không phải xác minh kỹ thuật rằng iOS đã cài profile.
5. Wizard tiếp tục với chính gói đã chọn, tra cứu tài khoản, xác nhận hồ sơ và thanh toán như hiện tại.
6. Ngay sau khi thanh toán được ghi nhận, màn theo dõi kích hoạt hiển thị lại hướng dẫn DNS. Hướng dẫn vẫn còn sau khi LunaKey trả kết quả thành công và trong chi tiết đơn hàng.
7. Đơn thất bại, hoàn tiền hoặc bị hủy vẫn hiển thị trạng thái tiền/đơn rõ ràng; không mô tả việc cài DNS là bằng chứng kích hoạt thành công.

## Nội dung hướng dẫn DNS

### iPhone/iPad

1. Mở website bằng Safari; không mở trình duyệt nhúng trong Zalo, Facebook hoặc TikTok.
2. Nhấn **Tải cấu hình DNS** và chọn **Cho phép** khi iOS hỏi quyền tải profile.
3. Mở **Cài đặt**. Chọn **Đã tải về hồ sơ**; nếu không thấy, vào **Cài đặt chung → VPN & Quản lý thiết bị**.
4. Chọn profile Locket Gold, nhấn **Cài đặt**, nhập mật mã mở khóa máy nếu iOS yêu cầu, rồi xác nhận **Cài đặt** lần nữa.
5. Đóng hẳn và mở lại Locket sau khi kích hoạt hoàn tất.

Artifact hiện tại là profile DNS được ký và chỉ chứa payload `com.apple.dnsSettings.managed`; nó không cài CA certificate payload. Vì vậy giao diện không được bắt người dùng bật **Cài đặt tin cậy chứng chỉ** như ảnh tham khảo. Chỉ bổ sung bước tin cậy chứng chỉ trong tương lai nếu file phát hành thực sự có certificate payload và tên chứng chỉ đã được backend kiểm tra/hiển thị chính xác.

### QR và máy tính

Người dùng máy tính được cung cấp QR dẫn tới cùng luồng tải cấu hình HTTPS. QR không chứa API key, Apple ID, token phiên dài hạn hay secret NextDNS. Vé tải có thời hạn ngắn và dùng một lần.

### Thông điệp an toàn

Hiển thị cạnh nút tải và trong bước xác nhận:

> Profile này chỉ cấu hình DNS. Website không yêu cầu Apple ID, mật khẩu iCloud hoặc mã xác minh. Profile DNS không có quyền đăng xuất, đổi mật khẩu hay khóa tài khoản iCloud. Nếu màn hình yêu cầu đăng nhập Apple ID hoặc hiển thị quyền khác DNS, hãy dừng lại và liên hệ hỗ trợ.

Website không dùng từ “đảm bảo tuyệt đối”. Thay vào đó, mô tả các quyền thực tế của payload và chỉ dẫn người dùng kiểm tra tên profile/nhà phát hành.

## Mô hình dữ liệu và API nội bộ

Thêm capability `requires_dns_profile` vào `plans` và snapshot `requires_dns_profile_snapshot` vào `activation_orders`. Catalog và chi tiết đơn dùng capability này thay vì suy luận từ tên gói hoặc provider. Bốn gói No VPN được đặt `requires_dns_profile = 1`.

API plan chỉ trả capability dạng boolean. Endpoint mua Coin và tạo thanh toán QR yêu cầu `dns_acknowledged = true` khi plan yêu cầu DNS; nếu thiếu, trả lỗi ổn định `dns_acknowledgement_required` trước khi trừ tiền/tạo thanh toán. Cờ này chỉ chứng minh người dùng đã xác nhận hướng dẫn, không chứng minh iOS đã cài profile.

Thêm endpoint authenticated tạo vé tải setup trước mua, nhận `plan_id`, chỉ cấp vé khi:

- plan tồn tại, đang mở bán và hỗ trợ iOS;
- `requires_dns_profile` đang bật;
- mobileconfig thực sự tồn tại.

Endpoint tải hiện tại tiếp tục dùng vé một lần. Với đơn đã thanh toán yêu cầu DNS, endpoint cấp vé tải cho phép các trạng thái đang xử lý cũng như `completed`, để khách cài DNS trong lúc LunaKey kích hoạt. Quyền sở hữu đơn và platform iOS vẫn được kiểm tra.

## LunaKey provider contract

`KNOWN_CATEGORIES` và `CATEGORY_ALIASES` chấp nhận đúng bốn giá trị: `1month`, `3month`, `6month`, `yearly`. Client gửi nguyên category đã resolve trong payload `/api/v1/gold`; không suy luận từ `duration_days` tại thời điểm gửi.

Readiness tiếp tục fail-closed với category rỗng hoặc ngoài allowlist. Request id, idempotency và snapshot category hiện tại không thay đổi.

## Migration catalog

Thay migration đang ép mọi LunaKey plan thành `yearly/365` bằng migration idempotent theo slug ổn định. Migration cập nhật/tạo đủ bốn gói theo bảng mapping, đặt iOS + auto activation + LunaKey + DNS required, và không sửa historical order snapshots.

Migration có dry-run mặc định, `--apply` mới ghi dữ liệu, in rõ before/after nhưng không in secret. Nếu gặp slug trùng với dữ liệu không tương thích, migration dừng và báo lỗi thay vì đoán hoặc ghi đè tùy tiện.

## Frontend

Tách một component dùng chung `DnsSetupGuide` để tránh ba bản hướng dẫn lệch nhau. Component có hai chế độ:

- `prerequisite`: tải profile, checklist, acknowledgment, tiếp tục với pending plan;
- `post_payment`: trạng thái đơn, tải/cài lại, checklist kiểm tra và thông điệp an toàn.

`ActivationWizard` thêm bước `dns_setup` và giữ `pendingPlan`. `OrdersView` dùng snapshot capability để hiện guide cho LunaKey No VPN, thay toàn bộ nội dung “Không cần DNS”. Luồng legacy không yêu cầu DNS trước mua vẫn giữ hành vi cũ, nhưng có thể tái sử dụng component ở màn sau kích hoạt.

Trạng thái acknowledgment chỉ sống trong phiên wizard hoặc `sessionStorage` với version của profile; không coi local state là bằng chứng bảo mật. Khi profile/version thay đổi, xác nhận cũ bị vô hiệu hóa.

## Xử lý lỗi

- Không có mobileconfig: chặn tiếp tục trước thanh toán và báo quản trị viên cấu hình profile.
- Vé hết hạn/đã dùng: cho tạo vé mới, không tạo lại đơn hay thanh toán.
- Không phải Safari/iOS: hiển thị QR hoặc chỉ dẫn mở Safari; không giả vờ profile đã cài.
- Platform/provider trả lỗi: giữ nguyên quy tắc refund/reconciliation hiện có.
- Category ngoài allowlist: plan không được bán và không có request trả phí gửi upstream.

## Chuyển từ QR sang thanh toán Coin

Trang thanh toán không hủy QR chỉ vì người dùng bấm sang tab Coin. QR chỉ được supersede sau khi giao dịch Coin đã trừ ví và tạo activation order thành công.

Sau một lần mua bằng Coin thành công, backend tìm QR `pending` chưa ghi nhận tiền của cùng người dùng và cùng ý định mua (plan, platform, tài khoản Locket, coupon và request fingerprint). Các QR khớp được chuyển sang `cancelled` với lý do máy đọc được `superseded_by_coin` và liên kết tới activation order Coin. Thao tác nằm trong cùng transaction hoặc một bước idempotent bắt buộc ngay sau transaction mua Coin; retry không được hủy nhầm QR khác.

Danh sách thanh toán Admin mặc định không trả các QR `cancelled` có lý do `superseded_by_coin`, nên QR mà khách chỉ bấm thử sẽ biến mất khỏi màn hình vận hành. Bản ghi vẫn được giữ trong database/audit để đối soát và xử lý webhook đến muộn; không hard-delete chứng từ thanh toán. Admin có bộ lọc “Đã thay thế bởi Coin” khi cần kiểm toán.

Các trường hợp không được ẩn/hủy:

- QR đã `paid`;
- QR `underpaid` hoặc `review_needed`;
- QR có `bank_transaction_id` hoặc đã nhận webhook ngân hàng;
- mua Coin thất bại, thiếu số dư hoặc bị idempotency conflict;
- QR của plan/tài khoản/coupon khác.

Nếu webhook ngân hàng đến sau khi QR đã bị supersede, hệ thống không tạo activation thứ hai. Giao dịch được đưa vào trạng thái cần đối soát/hoàn tiền và vẫn xuất hiện cho Admin.

## Kiểm thử

### Backend

- Test allowlist và payload cho cả bốn category; category lạ fail trước network.
- Test readiness của bốn plan.
- Test migration dry-run/apply/idempotency, đủ bốn slug, đúng ngày/giá/bảo hành/DNS capability, không sửa order snapshot.
- Test endpoint setup-ticket: auth, plan active, iOS, DNS required và file availability.
- Test Coin/QR bị chặn trước khi tạo giao dịch nếu thiếu acknowledgment; hợp lệ khi có acknowledgment.
- Test post-payment ticket theo ownership, platform và trạng thái; vé vẫn một lần và hết hạn đúng hạn.
- Test chuyển tab sang Coin chưa hủy QR; Coin thất bại vẫn giữ QR pending.
- Test Coin thành công chỉ supersede đúng QR pending cùng fingerprint; paid/underpaid/review/QR khác không đổi.
- Test retry Coin idempotent không hủy thêm QR và webhook đến muộn không tạo activation thứ hai.
- Test Admin mặc định ẩn `superseded_by_coin`, nhưng bộ lọc kiểm toán vẫn xem được bản ghi.

### Frontend

- Bấm từng thẻ No VPN mở prerequisite và giữ đúng pending plan/category.
- Không thể tiếp tục nếu chưa tải + xác nhận; có thể tiếp tục khi đủ hai điều kiện.
- Hiển thị đúng bốn tên gói, 30/90/180/365 ngày, giá và bảo hành.
- Sau thanh toán/pending/completed, LunaKey order có DNS guide; không còn chữ “Không cần DNS”.
- Nội dung an toàn iCloud và hướng dẫn Safari xuất hiện ở prerequisite, completion và OrdersView.
- Các trạng thái failed/refunded/cancelled không bị spinner vô hạn và không bị mô tả thành kích hoạt thành công.
- Chuyển QR → Coin không gọi hủy ngay; sau Coin thành công QR thử nghiệm biến mất khi Admin refresh.

## Phạm vi không làm

- Không gửi Apple ID/mật khẩu/mã xác minh lên backend.
- Không cố phát hiện profile iOS bằng JavaScript vì trình duyệt không cung cấp API đáng tin cậy.
- Không gọi endpoint kích hoạt trả phí trong test hay migration.
- Không thay đổi idempotency, refund hoặc reconciliation ngoài phần cần thiết cho category/DNS gate.
