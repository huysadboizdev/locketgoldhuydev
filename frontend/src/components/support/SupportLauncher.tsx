import React, { useEffect, useState } from 'react';
import { ExternalLink, Headphones, MessageCircle, Send, Users, X } from 'lucide-react';

const channels = [
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

export const SupportLauncher: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsOpen(false);
    };

    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [isOpen]);

  return (
    <>
      {isOpen && (
        <section
          id="dashboard-support-panel"
          role="dialog"
          aria-labelledby="dashboard-support-title"
          className="fixed bottom-[calc(8.25rem+env(safe-area-inset-bottom))] left-3 right-3 z-50 max-h-[min(70dvh,28rem)] overflow-y-auto rounded-3xl border border-amber-500/25 bg-white p-4 shadow-[0_24px_70px_rgba(24,24,27,0.24)] dark:bg-zinc-900 sm:left-auto sm:w-96 sm:p-5 md:bottom-20 md:right-6"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 id="dashboard-support-title" className="flex items-center gap-2 text-base font-extrabold text-zinc-900 dark:text-white">
                <Headphones className="h-5 w-5 shrink-0 text-amber-500" aria-hidden="true" />
                Hỗ trợ trực tiếp
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                Chọn nền tảng thuận tiện để liên hệ với Huy Dev.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              aria-label="Đóng hỗ trợ"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 dark:hover:bg-zinc-800 dark:hover:text-white"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>

          <div className="mt-4 space-y-2.5">
            {channels.map(({ name, detail, href, icon: Icon, iconClass }) => (
              <a
                key={name}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex min-h-14 min-w-0 items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 px-3.5 py-3 transition-all hover:border-amber-400 hover:bg-amber-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 dark:border-zinc-800 dark:bg-zinc-950/70 dark:hover:border-amber-500/70 dark:hover:bg-amber-950/20"
              >
                <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconClass}`}>
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-bold text-zinc-900 dark:text-white">{name}</span>
                  <span className="block truncate text-xs text-zinc-500 dark:text-zinc-400">{detail}</span>
                </span>
                <ExternalLink className="h-4 w-4 shrink-0 text-zinc-400 transition-colors group-hover:text-amber-600 dark:group-hover:text-amber-400" aria-hidden="true" />
              </a>
            ))}
          </div>

          <p className="mt-3 text-center text-[11px] text-emerald-600 dark:text-emerald-400">
            Sẵn sàng hỗ trợ bạn
          </p>
        </section>
      )}

      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-label={isOpen ? 'Đóng hỗ trợ' : 'Mở hỗ trợ'}
        aria-expanded={isOpen}
        aria-controls="dashboard-support-panel"
        className="fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom))] right-3 z-50 flex min-h-12 items-center gap-2 rounded-full border border-amber-300 bg-amber-500 px-4 py-2.5 text-xs font-extrabold text-zinc-950 shadow-[0_12px_35px_rgba(245,158,11,0.35)] transition-all hover:-translate-y-0.5 hover:bg-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 active:translate-y-0 md:bottom-6 md:right-6"
      >
        {isOpen ? <X className="h-5 w-5" aria-hidden="true" /> : <Headphones className="h-5 w-5" aria-hidden="true" />}
        <span>{isOpen ? 'Đóng' : 'Hỗ trợ'}</span>
      </button>
    </>
  );
};
