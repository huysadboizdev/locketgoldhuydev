import React from 'react';
import { Sparkles, ArrowRight, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

export const BottomCtaSection: React.FC = () => {
  const { isAuthenticated } = useAuth();

  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 py-12 sm:py-16">
      <div className="gold-card relative overflow-hidden rounded-3xl border p-8 sm:p-12 text-center">
        {/* Subtle glow */}
        <div className="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center">
          <div className="h-48 w-48 rounded-full bg-amber-500/10 dark:bg-amber-500/15 blur-2xl" />
        </div>

        <div className="inline-flex items-center gap-2 rounded-full border border-amber-600/30 bg-amber-50 dark:bg-amber-950/40 px-3.5 py-1 text-xs font-semibold text-amber-700 dark:text-amber-300 mb-4">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Sẵn Sàng Bắt Đầu</span>
        </div>

        <h2 className="text-2xl sm:text-4xl font-extrabold text-zinc-900 dark:text-white tracking-tight max-w-xl mx-auto">
          Trải Nghiệm Đầy Đủ Tính Năng Locket Gold Hôm Nay
        </h2>

        <p className="mt-3 text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 max-w-lg mx-auto leading-relaxed">
          Đăng nhập ngay để lựa chọn gói dịch vụ, nạp Coin và bắt đầu kích hoạt tự động với hướng dẫn chi tiết theo nền tảng.
        </p>

        <div className="mt-7 flex flex-col sm:flex-row items-center justify-center gap-3 max-w-md mx-auto">
          <Link
            to={isAuthenticated ? '/dashboard' : '/login?returnTo=/dashboard'}
            className="gold-primary flex w-full sm:w-auto items-center justify-center gap-2 rounded-2xl px-6 py-3.5 text-xs sm:text-sm font-bold transition-all active:scale-[0.98]"
          >
            <span>Trải nghiệm ngay</span>
            <ArrowRight className="h-4 w-4" />
          </Link>

          <Link
            to="/track"
            className="gold-secondary flex w-full sm:w-auto items-center justify-center gap-2 rounded-2xl border px-5 py-3.5 text-xs sm:text-sm font-semibold transition-all"
          >
            <Search className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
            <span>Tra cứu tiến trình</span>
          </Link>
        </div>
      </div>
    </section>
  );
};
