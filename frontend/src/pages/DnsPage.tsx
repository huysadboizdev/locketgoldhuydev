import React from 'react';
import { Navbar } from '../components/layout/Navbar';
import { Footer } from '../components/layout/Footer';
import { DnsInstructionsCard } from '../components/dns/DnsInstructionsCard';
import { ShieldCheck, HelpCircle, CheckCircle, Apple, Smartphone } from 'lucide-react';

interface DnsPageProps {
  isBackendOffline?: boolean;
}

export const DnsPage: React.FC<DnsPageProps> = ({ isBackendOffline = false }) => {
  return (
    <div className="gold-page flex min-h-screen flex-col text-zinc-900 dark:text-zinc-100 transition-colors">
      <div className="gold-ambient" aria-hidden="true" />

      {/* Navbar */}
      <Navbar isBackendOffline={isBackendOffline} />

      <main className="relative flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-8 sm:space-y-12">
        {/* Hero Header */}
        <div className="text-center space-y-3 max-w-2xl mx-auto gold-rise">
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-50 dark:bg-amber-950/40 px-3.5 py-1 text-xs font-bold text-amber-700 dark:text-amber-300">
            <Apple className="h-3.5 w-3.5" />
            <span>Hồ Sơ Cấu Hình iOS Chính Thức</span>
          </div>

          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-zinc-900 dark:text-white leading-tight">
            Cài Đặt Cấu Hình DNS <br />
            <span className="text-amber-600 dark:text-amber-400">Kích Hoạt Locket Gold</span>
          </h1>

          <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
            Hồ sơ DNS No-VPN giúp thiết bị iPhone của bạn kết nối an toàn với máy chủ cấp phép,
            cho phép hiển thị huy hiệu Gold, quay video, đổi biểu tượng và tùy biến camera không giới hạn.
          </p>
        </div>

        {/* Main Instruction Card */}
        <section aria-label="Hướng dẫn cài đặt">
          <DnsInstructionsCard />
        </section>

        {/* FAQ Section */}
        <section className="rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/60 p-6 sm:p-8 space-y-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-2.5 border-b border-zinc-200/80 dark:border-zinc-800/80 pb-4">
            <HelpCircle className="h-5 w-5 text-amber-500" />
            <h2 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-white">
              Câu hỏi thường gặp về DNS Profile
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="rounded-2xl border border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/40 p-4 space-y-1.5">
              <h3 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0" />
                <span>Tại sao phải cài đặt hồ sơ DNS này?</span>
              </h3>
              <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
                Hồ sơ DNS giúp xác thực quyền sở hữu gói Gold trên thiết bị của bạn mà không cần bật VPN làm chậm mạng hay hao pin điện thoại.
              </p>
            </div>

            <div className="rounded-2xl border border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/40 p-4 space-y-1.5">
              <h3 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0" />
                <span>Hồ sơ này có an toàn cho iPhone không?</span>
              </h3>
              <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
                Hoàn toàn an toàn. Hồ sơ chỉ định tuyến truy vấn tới máy chủ kích hoạt Locket Gold, không can thiệp vào dữ liệu cá nhân, ảnh hay danh bạ của bạn.
              </p>
            </div>

            <div className="rounded-2xl border border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/40 p-4 space-y-1.5">
              <h3 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                <Smartphone className="h-4 w-4 text-amber-500 shrink-0" />
                <span>Tại sao Safari báo tải hồ sơ nhưng không thấy?</span>
              </h3>
              <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
                Sau khi bấm Cho phép, bạn hãy vào ứng dụng <strong>Cài đặt (Settings)</strong> trên iPhone, chọn mục <strong>Đã tải về hồ sơ</strong> ở ngay trên đầu để bấm Cài đặt.
              </p>
            </div>

            <div className="rounded-2xl border border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/40 p-4 space-y-1.5">
              <h3 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4 text-amber-500 shrink-0" />
                <span>Tôi có thể gỡ hồ sơ khi không dùng nữa không?</span>
              </h3>
              <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
                Có. Bạn chỉ cần vào <em>Cài đặt ➔ Cài đặt chung ➔ Quản lý VPN &amp; Thiết bị ➔ Chọn hồ sơ ➔ Xóa hồ sơ</em> bất kỳ lúc nào.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};
