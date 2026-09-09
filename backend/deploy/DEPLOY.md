# VPS Deployment Guide (Ubuntu 2 CPU – 2GB RAM – 30GB SSD)

Hướng dẫn triển khai chuẩn production hệ thống Locket Gold VIP bao gồm:
- **Backend**: Flask + Gunicorn (1 worker, 4 threads) chạy systemd tại `/opt/locket-gold/backend`
- **Frontend**: React 18 + Vite SPA tĩnh phục vụ qua Nginx tại `/var/www/locket-gold`
- **Database**: SQLite WAL mode tại `/var/lib/locket-gold/locket.db`
- **Bảo mật**: Access Token (JWT) + Refresh Token (HttpOnly cookie) + Replay detection + Rate Limiting + Let's Encrypt TLS / Cloudflare

---

## 1. Tối ưu hệ thống VPS (2 CPU - 2GB RAM - 30GB SSD)

### 1.1 Thiết lập Swap 2GB (Khuyến nghị cho VPS 2GB RAM)
Giúp hệ thống không bị OOM (Out-of-Memory) khi tải đột biến:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 1.2 Cài đặt gói hệ điều hành
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx ufw fail2ban sqlite3
```

---

## 2. Tạo User & Cấu trúc thư mục chuẩn

```bash
# Tạo user hệ thống không có password login
sudo adduser --system --group --shell /bin/bash --home /opt/locket-gold locket

# Tạo thư mục dữ liệu database, downloads và ảnh đánh giá người dùng
sudo mkdir -p /var/lib/locket-gold /var/lib/locket-gold/downloads /var/lib/locket-gold/reviews /var/lib/locket-gold/creators
sudo chown -R locket:www-data /var/lib/locket-gold
sudo chmod 750 /var/lib/locket-gold
sudo chmod 750 /var/lib/locket-gold/downloads /var/lib/locket-gold/reviews /var/lib/locket-gold/creators

sudo mkdir -p /var/www/locket-gold
sudo chown -R www-data:www-data /var/www/locket-gold

```

---

## 3. Triển khai Backend

### 3.1 Sao chép mã nguồn & tạo Virtualenv
```bash
# Copy thư mục backend vào /opt/locket-gold/backend
sudo mkdir -p /opt/locket-gold/backend
# (Copy các file từ máy local hoặc git clone)
sudo chown -R locket:locket /opt/locket-gold

sudo -u locket -i
cd /opt/locket-gold/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
exit
```

### 3.2 Cấu hình Environment `/etc/locket-gold.env`
```bash
sudo nano /etc/locket-gold.env
```

Điền nội dung sau:
```env
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ThayBangMatKhauAdminSieuKho16KyTu!
ADMIN_DISPLAY_NAME=Administrator
ADMIN_ALLOW_GOOGLE_LOGIN=0
FLASK_SECRET_KEY=ThayBangHex64TuSinhBangOpenSSL
BEHIND_HTTPS=1
LOCKET_DB=/var/lib/locket-gold/locket.db

# JWT & Refresh Token Security
JWT_SECRET=ThayBangHex64JWTSecret
REFRESH_TOKEN_PEPPER=ThayBangHex64Pepper
JWT_ISSUER=locket-gold
JWT_AUDIENCE=locket-gold-web
ACCESS_TOKEN_TTL_SECONDS=600
REFRESH_TOKEN_TTL_SECONDS=2592000
REFRESH_COOKIE_NAME=locket_refresh

# VietQR + SePay automatic settlement
VIETQR_BANK_ID=TPB
VIETQR_ACCOUNT_NO=<bank_alias_or_account_used_to_generate_qr>
VIETQR_ACCOUNT_NAME=<bank_account_holder_name>
VIETQR_TEMPLATE=compact2
# Exact accountNumber returned in SePay's webhook payload. If SePay can return
# more than one identifier, separate them with commas.
SEPAY_WEBHOOK_ACCOUNT_NUMBERS=<real_numeric_account_returned_by_sepay>
PAYMENT_TRANSFER_PREFIX=LOCKETGOLDHUYDEV
PAYMENT_TRANSFER_DIGITS=3
PAYMENT_TTL_SECONDS=600
PAYMENT_CODE_REUSE_DELAY_SECONDS=86400
PAYMENT_WEBHOOK_ENABLED=1
SEPAY_WEBHOOK_SECRET=<same_hmac_secret_configured_in_sepay>
SEPAY_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS=300
SEPAY_TRANSACTION_CLOCK_SKEW_SECONDS=300

# Locket Accounts (optional seed)
EMAIL=
PASSWORD=
gist_token_url=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Review/KOL images on Cloudinary (credentials stay backend-only)
REVIEW_STORAGE_PROVIDER=cloudinary
CLOUDINARY_CLOUD_NAME=<cloud_name>
CLOUDINARY_API_KEY=<api_key>
CLOUDINARY_API_SECRET=<api_secret>
CLOUDINARY_FOLDER=locket-gold/reviews
CLOUDINARY_CREATOR_FOLDER=locket-gold/creators
ENABLE_ACCEL_REDIRECT=0

# Local-storage alternative only:
# REVIEW_STORAGE_PROVIDER=local
# REVIEW_STORAGE_ROOT=/var/lib/locket-gold/reviews
# CREATOR_STORAGE_ROOT=/var/lib/locket-gold/creators
# ENABLE_ACCEL_REDIRECT=1

```

Cloudinary API key requirements:

- Prefer the product-environment root API key for this private backend. A
  restricted key must be assigned permission to create/upload assets in both
  `locket-gold/reviews` and `locket-gold/creators`.
- Grant delete/destroy permission as well so deleting a review or KOL removes
  its remote asset. Do not expose the API secret to Vite or the browser.
- An Admin API `ping` only validates credentials and read access; deployment
  acceptance must include one real upload followed by deletion.

Configure SePay to send HMAC-SHA256 webhooks directly to
`https://locketgoldhuy.io.vn/api/payment/webhook`. Do not use the `http://`
URL and do not put any SePay or bank secret in the frontend environment.

> **Cách sinh khoá bí mật an toàn trên terminal:**
> `openssl rand -hex 32` (chạy riêng cho `FLASK_SECRET_KEY`, `JWT_SECRET`, và `REFRESH_TOKEN_PEPPER`)

Khoá quyền bảo mật file env:
```bash
sudo chown root:locket /etc/locket-gold.env
sudo chmod 640 /etc/locket-gold.env
```

### 3.3 Cài đặt systemd service
```bash
sudo cp /opt/locket-gold/backend/deploy/locket.service /etc/systemd/system/locket.service
sudo systemctl daemon-reload
sudo systemctl enable --now locket
sudo systemctl status locket
```

Kết quả mong đợi: `Active: active (running)`. Logs:
```bash
sudo journalctl -u locket -f
```

---

## 4. Triển khai Frontend (React SPA)

> **Lưu ý tối ưu:** Đối với VPS 2 CPU / 2GB RAM, chạy `npm run build` trực tiếp trên server có thể ngốn RAM và kích hoạt OOM killer. Khuyến nghị chạy `npm run build` trên máy local/CI rồi copy thư mục `dist/` lên VPS:

```bash
# Trên máy Local (PowerShell):
cd D:\toolvip\locketgold\Locket_Gold_Huy_Dev\frontend
npm run build

# Copy thư mục dist lên VPS (sử dụng SCP hoặc Rsync):
scp -r dist/* root@YOUR_VPS_IP:/var/www/locket-gold/

# Trên VPS: Phân quyền cho Nginx đọc file tĩnh
sudo chown -R www-data:www-data /var/www/locket-gold
sudo chmod -R 755 /var/www/locket-gold
```

---

## 5. Cấu hình Nginx & HTTPS

### 5.1 Chuẩn bị thư mục tải xuống và file cấu hình
```bash
sudo mkdir -p /var/lib/locket-gold/downloads
sudo chown -R locket:locket /var/lib/locket-gold/downloads
sudo chmod 750 /var/lib/locket-gold/downloads

# Đặt file profile iOS và APK tối ưu vào thư mục downloads
sudo cp /opt/locket-gold/backend/locket/static/locket.mobileconfig /var/lib/locket-gold/downloads/
# (Copy file APK Locket_v1.200.0-gocmod.com.apk vào /var/lib/locket-gold/downloads/)
sudo chown -R locket:locket /var/lib/locket-gold/downloads/
```

### 5.2 Phương án A: Dùng Cloudflare Origin Certificate (Khuyên dùng — Ổn định nhất)
1. Trên Cloudflare Dashboard: **SSL/TLS** -> **Origin Server** -> **Create Certificate** (chọn RSA 2048 hoặc ECC, thời hạn 15 năm).
2. Lưu chứng chỉ và private key trên VPS:
   ```bash
   sudo mkdir -p /etc/ssl/certs /etc/ssl/private
   sudo nano /etc/ssl/certs/cloudflare_origin.pem     # Dán Origin Certificate
   sudo nano /etc/ssl/private/cloudflare_origin.key   # Dán Private Key
   sudo chmod 644 /etc/ssl/certs/cloudflare_origin.pem
   sudo chmod 600 /etc/ssl/private/cloudflare_origin.key
   ```
3. Cài đặt file cấu hình `nginx-cloudflare.conf`:
   ```bash
   sudo cp /opt/locket-gold/backend/deploy/nginx-cloudflare.conf /etc/nginx/sites-available/locket-gold
   sudo sed -i 's/YOUR_DOMAIN/locketgold.me/g' /etc/nginx/sites-available/locket-gold
   sudo ln -sf /etc/nginx/sites-available/locket-gold /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t && sudo systemctl reload nginx
   ```
4. Trên Cloudflare: Chuyển chế độ SSL sang **Full (strict)**.

### 5.3 Phương án B: Cấp chứng chỉ Let's Encrypt theo 2 giai đoạn an toàn
*Tránh lỗi Nginx không thể khởi động do thiếu file chứng chỉ SSL trong file cấu hình:*

**Giai đoạn 1: Cấp chứng chỉ qua ACME webroot hoặc standalone trên Port 80**
```bash
sudo apt install -y certbot python3-certbot-nginx

# Tạm dừng Nginx nếu đang chiếm cổng 80 để cấp cert sạch
sudo systemctl stop nginx
sudo certbot certonly --standalone -d locketgold.me --non-interactive --agree-tos -m admin@locketgold.me

# Hoặc nếu Nginx đang chạy webroot:
# sudo certbot certonly --webroot -w /var/www/html -d locketgold.me
```

**Giai đoạn 2: Kích hoạt cấu hình HTTPS sau khi đã có chứng chỉ**
```bash
sudo cp /opt/locket-gold/backend/deploy/nginx.conf /etc/nginx/sites-available/locket-gold
sudo sed -i 's/YOUR_DOMAIN/locketgold.me/g' /etc/nginx/sites-available/locket-gold
sudo ln -sf /etc/nginx/sites-available/locket-gold /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl start nginx
sudo systemctl reload nginx
```

---

## 6. Thiết lập Firewall (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```
*Port 5001 được đóng hoàn toàn khỏi Internet, chỉ lắng nghe nội bộ 127.0.0.1.*

---

## 7. Vận hành & Sao lưu dữ liệu

| Thao tác | Lệnh trên VPS |
|---|---|
| Xem logs Backend thời gian thực | `sudo journalctl -u locket -f` |
| Khởi động lại Backend API | `sudo systemctl restart locket` |
| Kiểm tra trạng thái Backend | `sudo systemctl status locket` |
| Kiểm tra cấu hình & reload Nginx | `sudo nginx -t && sudo systemctl reload nginx` |
| Sao lưu thủ công cơ sở dữ liệu SQLite | `sudo -u locket sqlite3 /var/lib/locket-gold/locket.db ".backup /var/lib/locket-gold/backup-$(date +%F).db"` |

### Lịch tự động sao lưu SQLite (Cron)
Chạy `sudo crontab -e` dưới quyền root:
```cron
0 3 * * * sudo -u locket sqlite3 /var/lib/locket-gold/locket.db ".backup /var/lib/locket-gold/backup-$(date +\%F).db"
```
*Lệnh `.backup` sử dụng SQLite Online Backup API an toàn tuyệt đối khi hệ thống đang ghi dữ liệu.*
