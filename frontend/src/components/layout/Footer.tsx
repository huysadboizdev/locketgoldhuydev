import React from 'react';
import { ExternalLink, Headphones, MessageCircle, Send, Shield, Smartphone, Users } from 'lucide-react';

const supportChannels = [
  {
    name: 'Facebook',
    detail: 'huygoodboizdev',
    href: 'https://www.facebook.com/huygoodboizdev/',
    icon: Users,
    iconClass: 'bg-blue-500/10 text-blue-600 dark:bg-blue-400/10 dark:text-blue-400',
  },
  {
    name: 'Zalo',
    detail: '0763 076 124',
    href: 'https://zalo.me/0763076124',
    icon: MessageCircle,
    iconClass: 'bg-sky-500/10 text-sky-600 dark:bg-sky-400/10 dark:text-sky-400',
  },
  {
    name: 'Telegram',
    detail: '@huydev204',
    href: 'https://t.me/huydev204',
    icon: Send,
    iconClass: 'bg-cyan-500/10 text-cyan-600 dark:bg-cyan-400/10 dark:text-cyan-400',
  },
];

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

        <section
          id="support"
          aria-labelledby="support-title"
          className="mt-8 scroll-mt-24 rounded-3xl border border-amber-500/20 bg-amber-50/70 p-4 shadow-sm dark:bg-amber-950/10 sm:p-5 lg:p-6"
        >
          <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
            <div>
              <h2 id="support-title" className="flex items-center gap-2 text-sm font-bold text-zinc-900 dark:text-zinc-100 sm:text-base">
                <Headphones className="h-4 w-4 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                Hỗ trợ trực tiếp
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                Chọn nền tảng thuận tiện để liên hệ với Huy Dev.
              </p>
            </div>
            <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400">Sẵn sàng hỗ trợ</span>
          </div>

          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3 sm:gap-3">
            {supportChannels.map(({ name, detail, href, icon: Icon, iconClass }) => (
              <a
                key={name}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex min-h-14 min-w-0 items-center gap-3 rounded-2xl border border-zinc-200/90 bg-white px-3.5 py-3 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-amber-400 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 dark:border-zinc-800 dark:bg-zinc-900/80 dark:hover:border-amber-500/70"
              >
                <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${iconClass}`}>
                  <Icon className="h-4.5 w-4.5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-bold text-zinc-900 dark:text-zinc-100">{name}</span>
                  <span className="block truncate text-[11px] text-zinc-500 dark:text-zinc-400">{detail}</span>
                </span>
                <ExternalLink className="h-3.5 w-3.5 shrink-0 text-zinc-400 transition-colors group-hover:text-amber-600 dark:group-hover:text-amber-400" aria-hidden="true" />
              </a>
            ))}
          </div>
        </section>

        <div className="mt-8 flex flex-col items-center justify-between gap-3 border-t border-zinc-200 pt-6 text-center text-xs text-zinc-500 dark:border-zinc-800/80 dark:text-zinc-400 sm:flex-row sm:text-left">
          <p>© {new Date().getFullYear()} Locket Gold - Huy Dev. Mọi quyền được bảo lưu.</p>
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-zinc-500 dark:text-zinc-400 sm:justify-end">
            <span>Bảo mật</span>
            <span>•</span>
            <span>Điều khoản</span>
            <span>•</span>
            <a href="/#support" className="transition-colors hover:text-amber-600 hover:underline dark:hover:text-amber-400">
              Hỗ trợ kỹ thuật
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};
