import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ShieldCheck, Construction, Clock, Home } from 'lucide-react';
import { Navbar } from '../layout/Navbar';
import { Footer } from '../layout/Footer';

interface TrackOrderPageProps {
  isBackendOffline?: boolean;
}

export const TrackOrderPage: React.FC<TrackOrderPageProps> = ({ isBackendOffline }) => {
  return (
    <div className="gold-page flex min-h-screen flex-col text-zinc-900 dark:text-zinc-100 transition-colors">
      <Navbar isBackendOffline={isBackendOffline} />

      <main className="flex-1 py-12 sm:py-16">
        <div className="mx-auto max-w-xl px-4 sm:px-6">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors mb-6"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Quay lại trang chủ</span>
          </Link>

          <div className="gold-card rounded-3xl border p-6 sm:p-8 backdrop-blur-md">
            {/* Header with Construction badge */}
            <div className="mb-6 space-y-2">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-600/30 bg-amber-50 dark:bg-amber-950/40 px-3 py-1 text-xs font-semibold text-amber-700 dark:text-amber-300">
                <Construction className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                <span>Tính năng đang được phát triển</span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-white tracking-tight">
                Tra Cứu Tiến Trình Kích Hoạt
              </h1>
              <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                Cổng tra cứu lịch sử đơn hàng theo mã định danh cá nhân đang được hoàn thiện đồng bộ cùng hệ thống tài khoản người dùng.
              </p>
            </div>

            {/* Explanation card */}
            <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 p-5 space-y-4">
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-zinc-200 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
                  <Clock className="h-4 w-4" />
                </div>
                <div className="space-y-1">
                  <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-200">
                    Theo dõi tiến trình hiện tại ở đâu?
                  </h2>
                  <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                    Hệ thống backend lưu trữ và quản lý hàng đợi tập trung qua cơ sở dữ liệu SQLite. Khi bạn thực hiện yêu cầu kích hoạt tại Trang chủ, tiến trình sẽ được cập nhật trực tiếp theo thời gian thực trên modal phiên làm việc.
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/80 p-3.5 text-xs text-zinc-600 dark:text-zinc-400 space-y-1.5">
                <p className="font-semibold text-zinc-800 dark:text-zinc-200">Hướng dẫn nhanh:</p>
                <ul className="list-disc list-inside space-y-1 text-[11px]">
                  <li>Để kích hoạt mới hoặc kiểm tra tài khoản, vui lòng thực hiện tại <strong>Trang chủ</strong>.</li>
                  <li>Nếu phiên kích hoạt đang chạy, hãy giữ tab trình duyệt mở để nhận kết quả ngay khi hoàn tất.</li>
                  <li>Xem bảng "Lịch sử kích hoạt gần nhất" trên trang chủ để tra cứu các lượt thành công mới nhất.</li>
                </ul>
              </div>

              <div className="pt-2">
                <Link
                  to="/"
                  className="gold-primary flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-xs sm:text-sm font-bold transition-all active:scale-[0.98]"
                >
                  <Home className="h-4 w-4" />
                  <span>Về Trang chủ kiểm tra tài khoản</span>
                </Link>
              </div>
            </div>

            {/* Privacy & Security Note (Correctly reflecting DB storage without in-memory error) */}
            <div className="mt-6 rounded-2xl border border-zinc-200 dark:border-zinc-800/80 bg-zinc-50 dark:bg-zinc-950/40 p-3.5 text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-zinc-800 dark:text-zinc-300">
                <ShieldCheck className="h-3.5 w-3.5 text-zinc-600 dark:text-zinc-400" />
                <span>Chính sách bảo mật dữ liệu</span>
              </div>
              <p>
                Hệ thống bảo vệ tối đa dữ liệu người dùng: không lưu trữ mật khẩu, không yêu cầu mã đăng nhập Locket. Mọi yêu cầu được ghi nhận an toàn vào hàng đợi của hệ thống.
              </p>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
};
