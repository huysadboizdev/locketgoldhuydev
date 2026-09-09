# 🚀 Locket Gold Frontend — Huy Dev Edition

Giao diện Web nâng cấp Locket Gold hiện đại, tối giản đơn sắc (monochrome), tối ưu hiệu năng cho VPS Ubuntu 2 CPU - 2GB RAM.

---

## 🛠️ Công nghệ sử dụng
- **React 19 + TypeScript**: Đảm bảo an toàn kiểu dữ liệu và kiến trúc component rõ ràng.
- **Vite 6**: Tốc độ đóng gói siêu nhanh (< 6s).
- **Tailwind CSS v4**: `@tailwindcss/vite` tinh gọn, không cần cấu hình v3 rườm rà.
- **Lucide React**: 100% icon đơn sắc đen/trắng, không màu mè.
- **Motion (`motion/react`)**: Hiệu ứng chuyển động mượt mà, hỗ trợ `prefers-reduced-motion`.
- **Canvas Confetti**: Lazy-loaded, chỉ nạp khi kích hoạt thành công.

---

## 📊 Ngân sách Hiệu năng Thực tế
- **Initial JavaScript Gzip**: `~133 kB` (Mục tiêu: < 250 kB — Đạt chuẩn).
- **Initial CSS Gzip**: `~7 kB`.
- **Dung lượng build tĩnh**: `~470 kB` không nén, `~145 kB` sau khi nén Gzip.
- **Mức tiêu thụ RAM khi chạy Nginx trên VPS**: `~15 - 20 MB RAM` (An toàn tuyệt đối cho VPS 2GB RAM).

---

## 💻 Hướng dẫn Phát triển (Local Development)

### 1. Cài đặt thư viện
```bash
npm.cmd install
```

### 2. Chạy Dev Server
```bash
npm.cmd run dev
```
Dev server sẽ chạy tại `http://localhost:3000` và tự động proxy các request `/api/*` sang backend Flask tại `http://127.0.0.1:5001`.

### 3. Đóng gói cho Production
```bash
npm.cmd run build
```
Kết quả sinh ra tại thư mục `dist/`.

---

## 🌐 Triển khai lên VPS Ubuntu (Nginx)

1. Sao chép toàn bộ thư mục `dist/` lên VPS tại `/var/www/locket-frontend/dist`.
2. Cấu hình Nginx phân phối tĩnh thư mục này và proxy `/api/*` + `/admin/*` về Gunicorn (127.0.0.1:5001) theo tài liệu kế hoạch `plan_frontend_architecture.md`.
