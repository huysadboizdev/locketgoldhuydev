import React from 'react';
import { Shield, Smartphone } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="gold-footer border-t py-12 text-zinc-600 dark:text-zinc-400 transition-colors">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
          {/* Col 1: About */}
          <div className="space-y-3">
            <span className="text-sm font-semibold tracking-wide text-zinc-900 dark:text-zinc-100">
              Locket Gold - Huy Dev
            </span>
            <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
              Nền tảng hỗ trợ kích hoạt và hướng dẫn cấu hình Locket Gold tự động, đơn giản và an toàn cho người dùng iOS và Android.
            </p>
          </div>

          {/* Col 2: Security & Disclaimer */}
          <div className="space-y-3">
            <span className="text-sm font-semibold tracking-wide text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
              <Shield className="h-4 w-4 text-zinc-700 dark:text-zinc-300" /> Miễn trừ trách nhiệm
            </span>
            <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
              Locket Widget và RevenueCat là nhãn hiệu đã được đăng ký của các chủ sở hữu tương ứng. Nền tảng được tạo nhằm mục đích nghiên cứu và hỗ trợ kỹ thuật cá nhân.
            </p>
          </div>

          {/* Col 3: Support & Platform info */}
          <div className="space-y-3">
            <span className="text-sm font-semibold tracking-wide text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
              <Smartphone className="h-4 w-4 text-zinc-700 dark:text-zinc-300" /> Tương thích
            </span>
            <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
              Hỗ trợ đầy đủ các dòng máy iPhone/iPad (thông qua Profile DNS) và điện thoại Android (thông qua gói cài đặt APK tối ưu).
            </p>
          </div>
        </div>

        <div className="mt-8 border-t border-zinc-200 dark:border-zinc-800/80 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-zinc-500 dark:text-zinc-400">
          <p>© {new Date().getFullYear()} Locket Gold - Huy Dev. Mọi quyền được bảo lưu.</p>
          <div className="flex items-center gap-4 text-zinc-500 dark:text-zinc-400">
            <span>Bảo mật</span>
            <span>•</span>
            <span>Điều khoản</span>
            <span>•</span>
            <span>Hỗ trợ kỹ thuật</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
