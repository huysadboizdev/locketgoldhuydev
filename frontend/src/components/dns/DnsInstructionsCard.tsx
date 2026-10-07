import React, { useState } from 'react';
import {
  Download,
  QrCode,
  AlertTriangle,
  Smartphone,
  Copy,
  Check,
} from 'lucide-react';

export const LUNAKEY_DNS_MOBILECONFIG_URL = 'https://dns.lunakey.net/dns.mobileconfig';

interface DnsInstructionsCardProps {
  className?: string;
  onAcknowledge?: () => void;
  acknowledged?: boolean;
  showAcknowledgeCheckbox?: boolean;
}

export const DnsInstructionsCard: React.FC<DnsInstructionsCardProps> = ({
  className = '',
  onAcknowledge,
  acknowledged = false,
  showAcknowledgeCheckbox = false,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyLink = () => {
    navigator.clipboard.writeText(LUNAKEY_DNS_MOBILECONFIG_URL);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&margin=10&data=${encodeURIComponent(
    LUNAKEY_DNS_MOBILECONFIG_URL
  )}`;

  return (
    <div
      className={`rounded-3xl border border-amber-500/20 bg-white/90 dark:bg-zinc-900/90 shadow-[0_20px_50px_rgba(245,158,11,0.08)] backdrop-blur-md p-4 sm:p-6 lg:p-8 space-y-6 ${className}`}
    >
      {/* Title Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-200/80 dark:border-zinc-800/80 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-600 dark:text-amber-400">
            <Smartphone className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base sm:text-lg font-extrabold text-zinc-900 dark:text-white flex items-center gap-2">
              <span>Hướng dẫn cài đặt trên iPhone</span>
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
                BẮT BUỘC ĐỂ LÊN GOLD
              </span>
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Cài đặt hồ sơ DNS và bật tin cậy chứng chỉ để kích hoạt đầy đủ tính năng Locket Gold
            </p>
          </div>
        </div>

        <a
          href={LUNAKEY_DNS_MOBILECONFIG_URL}
          download="dns.mobileconfig"
          className="gold-primary inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-xs font-bold transition-all shadow-md active:scale-95 sm:self-center"
        >
          <Download className="h-4 w-4" />
          <span>Tải Cấu Hình Ngay</span>
        </a>
      </div>

      {/* Main Grid: Left Steps + Right PC QR Box */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: 3 Steps + Warning */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-4">
          {/* Step 1 */}
          <div className="group relative rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/60 p-4 transition-all hover:border-amber-500/40">
            <div className="flex items-start gap-3.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-500/15 font-extrabold text-amber-700 dark:text-amber-400 text-sm border border-amber-500/30">
                1
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-zinc-900 dark:text-white">
                  Nhấn nút <span className="text-amber-600 dark:text-amber-400">Tải Cấu Hình</span> ở trên và bấm chọn <span className="text-emerald-600 dark:text-emerald-400">Cho phép (Allow)</span> khi hệ thống hỏi
                </h4>
                <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                  Khi có thông báo hiện lên <em>&ldquo;Trang web này đang cố gắng tải về một hồ sơ cấu hình...&rdquo;</em> ➔ bấm <strong>Cho phép</strong> ➔ bấm <strong>Đóng</strong>.
                </p>
              </div>
            </div>
          </div>

          {/* Step 2 */}
          <div className="group relative rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/60 p-4 transition-all hover:border-amber-500/40">
            <div className="flex items-start gap-3.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-500/15 font-extrabold text-amber-700 dark:text-amber-400 text-sm border border-amber-500/30">
                2
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-zinc-900 dark:text-white">
                  Mở <strong>Cài đặt (Settings)</strong> ➔ chọn <strong>Đã tải về hồ sơ</strong> (hoặc <em>Cài đặt chung ➔ Quản lý VPN &amp; Thiết bị</em>) ➔ nhấn <strong>Cài đặt (Install)</strong>
                </h4>
                <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                  Nhập mật khẩu mở khóa màn hình iPhone của bạn (nếu có yêu cầu) rồi bấm <strong>Cài đặt</strong> ở góc trên bên phải.
                </p>
              </div>
            </div>
          </div>

          {/* Step 3 - BẮT BUỘC */}
          <div className="group relative rounded-2xl border-2 border-rose-500/30 bg-rose-50/30 dark:bg-rose-950/20 p-4 transition-all hover:border-rose-500/50">
            <div className="flex items-start gap-3.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-rose-500 text-white font-extrabold text-sm shadow-md">
                3
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-extrabold text-rose-700 dark:text-rose-300">
                    Bật tin cậy chứng chỉ: Cài đặt ➔ Cài đặt chung ➔ Giới thiệu ➔ kéo xuống cuối chọn Cài đặt tin cậy chứng chỉ ➔ Gạt BẬT cho LocketGold CA
                  </h4>
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded bg-rose-600 text-white shrink-0">
                    BẮT BUỘC ⭐
                  </span>
                </div>
                <p className="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed">
                  Khi hiện bảng thông báo xác nhận chứng nhận gốc của thiết bị, hãy bấm chọn <strong>Tiếp tục (Continue)</strong>.
                </p>
              </div>
            </div>
          </div>

          {/* Important Warning Notice */}
          <div className="rounded-2xl border border-amber-300/40 bg-amber-50/80 dark:bg-amber-950/30 p-4 space-y-1.5">
            <div className="flex items-center gap-2 text-xs font-bold text-amber-800 dark:text-amber-300">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span>Lưu ý quan trọng:</span>
            </div>
            <p className="text-xs leading-relaxed text-amber-900/90 dark:text-amber-200/90">
              ⚠️ <strong>Mở trang web này bằng trình duyệt Safari</strong> (không mở từ Zalo, Facebook, TikTok hoặc Chrome). Apple chỉ cho phép trình duyệt Safari gốc tải và cài đặt hồ sơ cấu hình hệ thống.
            </p>
          </div>
        </div>

        {/* Right Column: PC QR Code Card */}
        <div className="lg:col-span-5 xl:col-span-4 flex flex-col items-center justify-center rounded-3xl border border-dashed border-amber-500/30 bg-amber-50/20 dark:bg-zinc-900/40 p-5 text-center space-y-4">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-[11px] font-bold text-amber-700 dark:text-amber-300 border border-amber-500/20">
            <QrCode className="h-3.5 w-3.5" />
            <span>DÀNH CHO NGƯỜI DÙNG MÁY TÍNH (PC)</span>
          </div>

          {/* QR Code Container */}
          <div className="relative rounded-2xl border-2 border-amber-500/30 bg-white p-3 shadow-lg group">
            <img
              src={qrImageUrl}
              alt="Mã QR tải cấu hình DNS LunaKey"
              className="h-44 w-44 object-contain rounded-lg transition-transform group-hover:scale-105"
              loading="lazy"
            />
            <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <span className="text-[11px] font-bold text-white bg-black/70 px-2.5 py-1 rounded-full">
                Quét bằng Camera
              </span>
            </div>
          </div>

          <div className="space-y-1">
            <h4 className="text-sm font-bold text-zinc-900 dark:text-white flex items-center justify-center gap-1.5">
              <span>Quét Bằng Camera iPhone</span>
            </h4>
            <p className="text-[11px] text-zinc-500 dark:text-zinc-400 leading-relaxed max-w-[260px] mx-auto">
              Mở ứng dụng <strong>Camera</strong> trên iPhone, hướng ống kính vào mã QR trên để tải trực tiếp cấu hình về máy qua Safari nhé!
            </p>
          </div>

          {/* Direct Download Button */}
          <a
            href={LUNAKEY_DNS_MOBILECONFIG_URL}
            download="dns.mobileconfig"
            className="w-full flex items-center justify-center gap-2 rounded-2xl bg-amber-100 dark:bg-amber-950/60 hover:bg-amber-200 dark:hover:bg-amber-900/60 text-amber-900 dark:text-amber-200 border border-amber-300/60 dark:border-amber-700/60 py-2.5 px-4 text-xs font-bold transition-all shadow-sm"
          >
            <Download className="h-4 w-4" />
            <span>Tải Trực Tiếp (.mobileconfig)</span>
          </a>

          {/* Copy link */}
          <div className="flex items-center justify-center gap-1.5 text-[10px] text-zinc-400 dark:text-zinc-500">
            <span>Link: dns.lunakey.net/dns.mobileconfig</span>
            <button
              type="button"
              onClick={handleCopyLink}
              title="Sao chép liên kết"
              className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
            </button>
          </div>
        </div>
      </div>

      {/* Optional Acknowledge Checkbox for purchase / wizard flow */}
      {showAcknowledgeCheckbox && (
        <div className="rounded-2xl border-2 border-amber-500/40 bg-amber-50/50 dark:bg-amber-950/30 p-4 pt-3 space-y-2">
          <label className="flex items-start gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={() => onAcknowledge?.()}
              className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-amber-600 focus:ring-amber-500 cursor-pointer"
            />
            <div className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
              Tôi xác nhận đã hoàn tất cài đặt cấu hình DNS và bật tin cậy chứng chỉ{' '}
              <span className="text-amber-600 dark:text-amber-400 font-bold">LocketGold CA</span> trên iPhone của tôi.
              <span className="block text-[11px] font-normal text-zinc-500 dark:text-zinc-400 mt-0.5">
                (Nếu chưa cài đặt cấu hình này, ứng dụng Locket sẽ không thể hiển thị và sử dụng các tính năng Locket Gold).
              </span>
            </div>
          </label>
        </div>
      )}
    </div>
  );
};
