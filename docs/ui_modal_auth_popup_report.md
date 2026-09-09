# Báo cáo nghiệm thu UI Modal, Toast xác thực và Popup toàn trang

Ngày kiểm tra: 08/09/2026 (Asia/Bangkok)

## Kết quả đã sửa

- Tạo `OverlayProvider` quản lý một stack dùng chung cho dialog nghiệp vụ và popup thông báo. Chỉ lớp trên cùng được bắt phím Escape, giữ focus và nhận click backdrop.
- Chuẩn hóa các modal thực tế về `ModalPortal`: feedback, lightbox ảnh, chi tiết gói, tiến trình kích hoạt, chi tiết đơn user, chi tiết/thao tác đơn admin, modal admin dùng chung và cảnh báo chưa đủ điều kiện feedback.
- Body scroll lock dùng token riêng cho từng modal, có bù chiều rộng scrollbar và chỉ mở khóa sau khi lớp cuối cùng đóng.
- Focus trap hoạt động cả khi modal không có control, chặn focus thoát ra ngoài và trả focus về vị trí trước đó khi đóng.
- Sửa vòng đời URL preview ảnh feedback: không thu hồi URL còn đang hiển thị; thu hồi đúng lúc xóa ảnh, gửi thành công, đóng modal hoặc unmount.
- Toast toàn cục có 4 kiểu riêng: success, error, warning, info; tối đa 3 toast hiển thị, phần còn lại xếp hàng. Bộ đếm tự đóng chỉ bắt đầu khi toast xuất hiện và tạm dừng khi hover/focus.
- Toast đăng nhập/đăng ký được gắn kênh `auth`, chống lặp bằng `dedupeKey` và vẫn tồn tại qua chuyển route.
- Popup admin không dùng delay cố định. Popup chỉ xuất hiện sau khi toàn bộ auth toast và modal nghiệp vụ đã kết thúc, rồi chờ chuyển tiếp 250ms.
- Backdrop popup không còn làm mờ nền và giảm còn 50% độ tối. Người dùng có thể chọn `Tắt trong 2 tiếng`; mốc hết hạn được lưu theo từng phiên bản popup và có hiệu lực qua tải lại/chuyển route.
- Live Preview dùng chính `AnnouncementDialog` thật nhưng vô hiệu điều hướng CTA; liên kết nội bộ của popup runtime dùng React Router thay vì tải lại toàn trang.
- Điều hướng sau đăng ký cũng xét role: admin vào `/admin`, user vào `/dashboard`; `returnTo` chỉ được giữ khi nằm trong đúng vùng quyền.
- Cấu hình popup hiện tại trong database đã được bật. API công khai trả `enabled: true`, `active: true` tại thời điểm nghiệm thu.

## Responsive và accessibility

- Khung modal giới hạn theo `100dvh`, có khoảng đệm safe-area và vùng nội dung cuộn độc lập.
- Nút thao tác chính/đóng có vùng chạm tối thiểu 44px; Confirm Dialog xếp nút dọc trên mobile.
- Mỗi dialog có `role="dialog"`, `aria-modal`, label/description ID riêng; backdrop không thể đóng được dùng phần tử không tương tác.
- Toast dùng `aria-live`, lỗi dùng `role="alert"`, các trạng thái khác dùng `role="status"`.

## Kiểm thử thực tế

- Frontend production build: PASS, 1.681 modules, không lỗi TypeScript.
- Frontend Vitest + React Testing Library: PASS 17/17 tests trong 6 test files.
- Backend regression: PASS 227/227 tests.
- API `/api/site-settings`: popup `enabled=true`, `active=true`.

Test hồi quy bao phủ: nested modal/Escape, scroll lock, focus ban đầu, 4 biến thể toast, hàng đợi 3 toast, tự đóng và pause, auth-toast/popup coordination, modal/popup coordination, CTA nội bộ, preview CTA không điều hướng, tắt popup 2 giờ qua remount rồi tự hết hạn, role redirect và vòng đời Blob URL của ảnh feedback.

## Giới hạn xác minh

Môi trường hiện tại không có browser automation/chụp ảnh đa viewport. Responsive được kiểm tra ở mức cấu trúc CSS, build và DOM behavior tests; không ghi nhận giả rằng đã chụp 12 viewport như báo cáo cũ.
