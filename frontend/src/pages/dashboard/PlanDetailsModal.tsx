import React, { useRef, useState } from 'react';
import { PlanItem } from '../../types/api';
import { ModalPortal } from '../../components/common/ModalPortal';
import {
  Apple,
  Smartphone,
  Sparkles,
  Check,
  X,
  Coins,
  Calendar,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';

interface PlanDetailsModalProps {
  plan: PlanItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSelect: (plan: PlanItem) => void;
  isSelected?: boolean;
}

export const formatVND = (price: number): string => {
  return `${new Intl.NumberFormat('vi-VN').format(price || 0)} VNĐ`;
};

export const formatCoin = (coin: number): string => {
  return `${new Intl.NumberFormat('vi-VN').format(coin || 0)} Coin`;
};

export const formatDuration = (days: number): string => {
  if (!days || days <= 0) return 'Không giới hạn';
  if (days >= 3650) return 'Vĩnh viễn';
  return `${new Intl.NumberFormat('vi-VN').format(days)} ngày`;
};

export const PlanDetailsModal: React.FC<PlanDetailsModalProps> = ({
  plan,
  isOpen,
  onClose,
  onSelect,
  isSelected = false,
}) => {
  const primaryButtonRef = useRef<HTMLButtonElement>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const isOutOfStock = plan?.inventory_status === 'out_of_stock';
  const isPopular = Boolean(plan?.is_popular);

  if (!isOpen || !plan) {
    return null;
  }

  const handleSelect = () => {
    if (isOutOfStock || isProcessing) return;
    setIsProcessing(true);
    try {
      onSelect(plan);
      onClose();
    } finally {
      setIsProcessing(false);
    }
  };

  const features = Array.isArray(plan.features) ? plan.features : [];

  return (
    <ModalPortal
      isOpen={isOpen}
      onClose={onClose}
      ariaLabelledBy="plan-details-title"
      ariaDescribedBy="plan-details-desc"
      className="max-w-xl !overflow-hidden !rounded-3xl !border !border-amber-500/25 dark:!border-zinc-800"
    >
      <div className="relative flex min-h-0 w-full flex-col overflow-hidden">
        {/* Decorative Top Accent Bar */}
        <div
          className={`h-1.5 w-full ${
            isPopular
              ? 'bg-gradient-to-r from-amber-400 via-amber-500 to-amber-300'
              : 'bg-gradient-to-r from-zinc-200 via-amber-400/50 to-zinc-200 dark:from-zinc-800 dark:via-amber-500/40 dark:to-zinc-800'
          }`}
        />

        {/* Modal Header */}
        <div className="p-4 sm:p-6 pb-3 border-b border-zinc-100 dark:border-zinc-800/80">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
              {/* Platform Badge */}
              {plan.supported_platforms === 'all' && (
                <span className="inline-flex items-center gap-1 rounded-full border border-zinc-200 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800/90 px-2.5 py-0.5 text-[11px] font-semibold text-zinc-700 dark:text-zinc-300">
                  <Apple className="h-3.5 w-3.5" />
                  <span>+</span>
                  <Smartphone className="h-3.5 w-3.5" />
                  <span>iOS & Android</span>
                </span>
              )}
              {plan.supported_platforms === 'ios' && (
                <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 dark:border-sky-900/60 bg-sky-50 dark:bg-sky-950/40 px-2.5 py-0.5 text-[11px] font-semibold text-sky-700 dark:text-sky-300">
                  <Apple className="h-3.5 w-3.5" />
                  <span>Chỉ iOS</span>
                </span>
              )}
              {plan.supported_platforms === 'android' && (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50 dark:bg-emerald-950/40 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                  <Smartphone className="h-3.5 w-3.5" />
                  <span>Chỉ Android</span>
                </span>
              )}

              {/* Popular Badge */}
              {isPopular && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-500 text-zinc-950 px-2.5 py-0.5 text-[11px] font-bold shadow-sm">
                  <Sparkles className="h-3 w-3 fill-current" />
                  <span>Được chọn nhiều</span>
                </span>
              )}

              {/* Out of Stock Badge */}
              {isOutOfStock && (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-600 dark:text-rose-400 px-2.5 py-0.5 text-[11px] font-bold">
                  <AlertCircle className="h-3 w-3" />
                  <span>Tạm hết hàng</span>
                </span>
              )}
            </div>

            {/* Close X Button */}
            <button
              type="button"
              onClick={onClose}
              aria-label="Đóng cửa sổ chi tiết gói"
              className="p-1.5 -mr-1 -mt-1 rounded-full text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:outline-none"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Plan Name & Description */}
          <div className="mt-3">
            <h2
              id="plan-details-title"
              className="text-xl sm:text-2xl font-black text-zinc-900 dark:text-white tracking-tight break-words"
            >
              {plan.name}
            </h2>
            {plan.short_description && (
              <p
                id="plan-details-desc"
                className="mt-1.5 text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed break-words"
              >
                {plan.short_description}
              </p>
            )}
          </div>
        </div>

        {/* Modal Body - Scrollable */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 sm:space-y-5">
          {/* Price & Term Highlight Card */}
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] dark:bg-amber-500/[0.07] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider block">
                Giá thanh toán
              </span>
              <div className="flex items-baseline gap-2 mt-0.5">
                <span className="text-2xl sm:text-3xl font-black text-amber-600 dark:text-amber-400 tracking-tight">
                  {formatVND(plan.price_vnd)}
                </span>
              </div>
            </div>

            <div className="sm:text-right border-t sm:border-t-0 border-amber-500/15 pt-2 sm:pt-0">
              <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider block">
                Tương đương ví Coin & Thời hạn
              </span>
              <div className="flex items-center sm:justify-end gap-2 mt-0.5">
                <span className="inline-flex items-center gap-1 font-bold text-sm sm:text-base text-zinc-800 dark:text-zinc-200">
                  <Coins className="h-4 w-4 text-amber-500" />
                  <span>{formatCoin(plan.price_coin)}</span>
                </span>
                <span className="text-zinc-400">·</span>
                <span className="inline-flex items-center gap-1 text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 font-medium">
                  <Calendar className="h-3.5 w-3.5 text-zinc-400" />
                  <span>{formatDuration(plan.duration_days)}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Full Benefits & Features Section */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs sm:text-sm font-bold text-zinc-900 dark:text-white uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-amber-500" />
                <span>Toàn bộ quyền lợi gói cước ({features.length})</span>
              </h3>
              <span className="text-[11px] text-zinc-400">Kích hoạt trực tiếp</span>
            </div>

            {features.length > 0 ? (
              <ul className="space-y-2" aria-label="Danh sách quyền lợi">
                {features.map((feature, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-3 rounded-xl border border-zinc-100 dark:border-zinc-800/80 bg-zinc-50/70 dark:bg-zinc-800/30 p-2.5 sm:p-3 text-xs sm:text-sm text-zinc-800 dark:text-zinc-200"
                  >
                    <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 mt-0.5">
                      <Check className="h-3.5 w-3.5" />
                    </div>
                    <span className="break-words leading-relaxed">{feature}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 p-4 text-center text-xs text-zinc-500 dark:text-zinc-400">
                Gói dịch vụ đã bao gồm toàn bộ quyền lợi VIP Locket Gold cao cấp.
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 sm:p-5 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/90 flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs sm:text-sm font-semibold text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-750 transition-colors focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:outline-none text-center"
          >
            Để sau
          </button>

          <button
            ref={primaryButtonRef}
            data-autofocus={!isOutOfStock ? 'true' : undefined}
            type="button"
            disabled={isOutOfStock || isProcessing}
            onClick={handleSelect}
            className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all shadow-md focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:outline-none ${
              isOutOfStock
                ? 'bg-zinc-200 dark:bg-zinc-800 text-zinc-400 cursor-not-allowed border border-transparent shadow-none'
                : 'gold-primary active:scale-[0.98]'
            }`}
          >
            {isOutOfStock ? (
              <>
                <AlertCircle className="h-4 w-4" />
                <span>Tạm hết hàng</span>
              </>
            ) : (
              <>
                <span>{isSelected ? 'Xác nhận chọn gói này' : 'Chọn gói này'}</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </ModalPortal>
  );
};
