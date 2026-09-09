# Locket Gold VIP - Huy Dev Edition

Dự án toàn diện tích hợp Backend Flask API và Frontend React hiện đại cho giải pháp kích hoạt Locket Gold.

---

## 📁 Cấu Trúc Dự Án Thống Nhất

```
D:\toolvip\locketgold\Locket_Gold_Huy_Dev\
├── backend\                     # Flask API backend & worker pool
│   ├── locket\                  # Core package (public, admin, user auth, db, queue)
│   ├── wsgi.py                  # Entrypoint Flask WSGI server
│   ├── gunicorn.conf.py         # Cấu hình production Gunicorn
│   ├── requirements.txt         # Python dependencies
│   ├── locket.db                # SQLite database (WAL mode)
│   └── tests\                   # Automated test suite
├── frontend\                    # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── src\                     # UI components, pages, context, hooks
│   ├── public\                  # Public static assets
│   ├── package.json             # NPM dependencies & scripts
│   └── vite.config.ts           # Cấu hình Vite & API reverse proxy
├── scripts\
│   └── start_dev.ps1            # Script khởi động đồng thời cả Backend & Frontend
└── README.md                    # Tài liệu hướng dẫn sử dụng
```

---

## 🚀 Hướng Dẫn Khởi Chạy Local

### 1. Cách chạy đồng thời cả Backend & Frontend (Khuyên dùng)

Mở PowerShell tại thư mục gốc dự án:

```powershell
cd D:\toolvip\locketgold\Locket_Gold_Huy_Dev
powershell -ExecutionPolicy Bypass -File .\scripts\start_dev.ps1
```

- Script tự động kiểm tra `backend\wsgi.py` và `frontend\package.json`.
- Tự động khởi động Backend tại `http://127.0.0.1:5001`.
- Kiểm tra sức khỏe (Health Check) API trước khi bật Frontend.
- Khởi động Frontend Vite tại `http://localhost:3000`.
- Khi nhấn `Ctrl + C`, script tự động tắt sạch sẽ các tiến trình do script tạo ra.

---

### 2. Cách chạy Backend riêng biệt

```powershell
cd D:\toolvip\locketgold\Locket_Gold_Huy_Dev\backend
python wsgi.py
```

- API lắng nghe tại: `http://127.0.0.1:5001`
- Admin Dashboard: `http://127.0.0.1:5001/admin/`

---

### 3. Cách chạy Frontend riêng biệt

```powershell
cd D:\toolvip\locketgold\Locket_Gold_Huy_Dev\frontend
npm.cmd run dev
```

- Giao diện người dùng: `http://localhost:3000`
- Các request `/api/*` sẽ được Vite tự động proxy tới `http://127.0.0.1:5001`.

---

### 4. Kiểm tra Build Frontend

```powershell
cd D:\toolvip\locketgold\Locket_Gold_Huy_Dev\frontend
npm.cmd run build
```

---

### 5. Chạy Kiểm Thử Backend Tự Động

```powershell
cd D:\toolvip\locketgold\Locket_Gold_Huy_Dev\backend
python tests\test_user_auth.py
```
