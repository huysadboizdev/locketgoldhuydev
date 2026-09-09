import React from 'react';
import {
  Coins,
  Sparkles,
  Clock,
  CheckCircle2,
  Plus,
} from 'lucide-react';

interface OverviewViewProps {
  userDisplayName: string;
  coinBalance: number;
  activeOrdersCount: number;
  completedOrdersCount: number;
  onGoToWizard: () => void;
  onGoToWallet: () => void;
  onGoToOrders: () => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  userDisplayName,
  coinBalance,
  activeOrdersCount,
  completedOrdersCount,
  onGoToWizard,
  onGoToWallet,
  onGoToOrders,
}) => {
  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-3xl border border-amber-500/30 bg-gradient-to-br from-amber-500/15 via-amber-500/[0.06] to-white/30 dark:to-transparent p-5 sm:p-6 lg:p-7 shadow-[0_16px_45px_rgba(210,145,15,0.08)]">
        <div className="max-w-xl space-y-3">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/20 px-3 py-1 text-xs font-bold text-amber-700 dark:text-amber-300">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Locket Gold VIP · Huy Dev</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight text-zinc-900 dark:text-white">
            Xin chào, {userDisplayName}!
          </h2>
          <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
            Chào mừng bạn đến với Cổng quản lý Locket Gold. Kích hoạt tính năng, nạp Coin hoặc theo dõi đơn hàng của bạn ngay bên dưới.
          </p>
          <div className="pt-1 flex flex-col min-[420px]:flex-row flex-wrap gap-2.5">
            <button
              type="button"
              onClick={onGoToWizard}
              className="gold-primary min-h-11 justify-center rounded-2xl px-5 py-2.5 text-xs sm:text-sm font-bold flex items-center gap-2 transition-all active:scale-[0.98]"
            >
              <Plus className="h-4 w-4" />
              <span>Kích hoạt gói mới</span>
            </button>
            <button
              type="button"
              onClick={onGoToWallet}
              className="gold-secondary min-h-11 justify-center rounded-2xl border px-4 py-2.5 text-xs sm:text-sm font-semibold flex items-center gap-2 transition-all"
            >
              <Coins className="h-4 w-4 text-amber-500" />
              <span>Nạp Coin</span>
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 min-[520px]:grid-cols-3 gap-3 sm:gap-4">
        {/* Card 1: Coin Balance */}
        <div
          onClick={onGoToWallet}
          className="cursor-pointer rounded-2xl sm:rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-4 sm:p-5 hover:-translate-y-0.5 hover:border-amber-500/40 hover:shadow-md transition-all"
        >
          <div className="flex items-center justify-between text-zinc-500 mb-3">
            <span className="text-xs font-medium">Số dư Coin</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Coins className="h-4 w-4" />
            </div>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl sm:text-3xl font-extrabold text-zinc-900 dark:text-white">
              {coinBalance.toLocaleString('vi-VN')}
            </span>
            <span className="text-xs font-bold text-amber-600 dark:text-amber-400">Coin</span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-400">
            ≈ {(coinBalance * 1000).toLocaleString('vi-VN')} VNĐ
          </p>
        </div>

        {/* Card 2: Active Orders */}
        <div
          onClick={onGoToOrders}
          className="cursor-pointer rounded-2xl sm:rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-4 sm:p-5 hover:-translate-y-0.5 hover:border-amber-500/40 hover:shadow-md transition-all"
        >
          <div className="flex items-center justify-between text-zinc-500 mb-3">
            <span className="text-xs font-medium">Đơn đang kích hoạt</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400">
              <Clock className="h-4 w-4" />
            </div>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl sm:text-3xl font-extrabold text-zinc-900 dark:text-white">
              {activeOrdersCount}
            </span>
            <span className="text-xs text-zinc-400 font-medium">đơn hàng</span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-400">
            Đang xếp hàng hoặc xử lý
          </p>
        </div>

        {/* Card 3: Completed Orders */}
        <div
          onClick={onGoToOrders}
          className="cursor-pointer rounded-2xl sm:rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-4 sm:p-5 hover:-translate-y-0.5 hover:border-amber-500/40 hover:shadow-md transition-all"
        >
          <div className="flex items-center justify-between text-zinc-500 mb-3">
            <span className="text-xs font-medium">Đã hoàn thành</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
            </div>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl sm:text-3xl font-extrabold text-zinc-900 dark:text-white">
              {completedOrdersCount}
            </span>
            <span className="text-xs text-zinc-400 font-medium">lần kích hoạt</span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-400">
            Có cấu hình DNS & vé tải
          </p>
        </div>
      </div>
    </div>
  );
};
