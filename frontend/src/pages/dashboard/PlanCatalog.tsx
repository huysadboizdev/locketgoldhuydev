import React, { useState } from 'react';
import { PlanItem } from '../../types/api';
import {
  Apple,
  Smartphone,
  Sparkles,
  Check,
  AlertCircle,
  Coins,
  ArrowRight,
  Info,
} from 'lucide-react';
import {
  PlanDetailsModal,
  formatVND,
  formatCoin,
  formatDuration,
} from './PlanDetailsModal';

interface PlanCatalogProps {
  plans: PlanItem[];
  isLoading: boolean;
  selectedPlanId?: number | null;
  onSelectPlan: (plan: PlanItem) => void;
}

export const PlanCatalog: React.FC<PlanCatalogProps> = ({
  plans,
  isLoading,
  selectedPlanId,
  onSelectPlan,
}) => {
  const [activeModalPlan, setActiveModalPlan] = useState<PlanItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleOpenPlanDetails = (plan: PlanItem) => {
    setActiveModalPlan(plan);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handleConfirmSelect = (plan: PlanItem) => {
    onSelectPlan(plan);
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-3 sm:gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="animate-pulse rounded-2xl sm:rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white/60 dark:bg-zinc-900/60 p-4 sm:p-5 flex flex-col justify-between space-y-3 min-h-[260px]"
          >
            <div className="flex items-center justify-between">
              <div className="h-4 w-20 bg-zinc-200 dark:bg-zinc-800 rounded-full" />
              <div className="h-4 w-16 bg-zinc-200 dark:bg-zinc-800 rounded-full" />
            </div>
            <div className="space-y-2">
              <div className="h-5 w-36 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
              <div className="h-3 w-48 bg-zinc-200 dark:bg-zinc-800 rounded-md" />
            </div>
            <div className="py-2 border-y border-zinc-100 dark:border-zinc-800/80 space-y-1.5">
              <div className="h-6 w-28 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
              <div className="h-3.5 w-36 bg-zinc-200 dark:bg-zinc-800 rounded-md" />
            </div>
            <div className="space-y-1.5">
              <div className="h-3 w-full bg-zinc-200 dark:bg-zinc-800 rounded" />
              <div className="h-3 w-4/5 bg-zinc-200 dark:bg-zinc-800 rounded" />
            </div>
            <div className="h-4 w-28 bg-zinc-200 dark:bg-zinc-800 rounded self-end" />
          </div>
        ))}
      </div>
    );
  }

  if (!plans || plans.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-zinc-300 dark:border-zinc-800 p-7 sm:p-10 text-center bg-white/60 dark:bg-zinc-900/40">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400 mb-4">
          <AlertCircle className="h-7 w-7" />
        </div>
        <h3 className="text-base font-bold text-zinc-900 dark:text-white">
          Hiện chưa có gói Locket Gold khả dụng.
        </h3>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400 max-w-sm mx-auto">
          Quản trị viên đang cập nhật bảng giá và gói dịch vụ mới. Vui lòng quay lại sau ít phút.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-3 sm:gap-4 items-stretch">
        {plans.map((plan) => {
          const isSelected = selectedPlanId === plan.id;
          const isOutOfStock = plan.inventory_status === 'out_of_stock';
          const isPopular = Boolean(plan.is_popular);
          const features = Array.isArray(plan.features) ? plan.features : [];
          const previewFeatures = features.slice(0, 2);
          const remainingCount = Math.max(0, features.length - 2);

          return (
            <div
              key={plan.id}
              role="button"
              tabIndex={0}
              aria-label={`Xem chi tiết gói ${plan.name} - ${formatVND(plan.price_vnd)}`}
              onClick={() => handleOpenPlanDetails(plan)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleOpenPlanDetails(plan);
                }
              }}
              className={`group relative flex flex-col justify-between rounded-2xl sm:rounded-3xl border p-4 sm:p-5 transition-all duration-200 text-left cursor-pointer outline-none select-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-zinc-950 ${
                isOutOfStock
                  ? 'border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/50 opacity-75 grayscale-[20%]'
                  : isSelected
                  ? 'border-amber-500 bg-amber-500/[0.04] dark:bg-amber-400/[0.04] shadow-md ring-2 ring-amber-500/30'
                  : isPopular
                  ? 'border-amber-400/70 dark:border-amber-500/60 bg-gradient-to-b from-amber-500/[0.04] to-white dark:to-zinc-900/70 shadow-sm hover:border-amber-500 hover:shadow-md hover:-translate-y-0.5'
                  : 'border-zinc-200/90 dark:border-zinc-800 bg-white dark:bg-zinc-900/70 shadow-sm hover:border-amber-500/50 hover:shadow-md hover:-translate-y-0.5'
              }`}
            >
              {/* Top Section: Badges */}
              <div>
                <div className="flex items-center justify-between gap-1.5 mb-3 min-h-[24px]">
                  {/* Platform Badge */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {plan.supported_platforms === 'all' && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-zinc-200 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 text-[10px] font-semibold text-zinc-700 dark:text-zinc-300">
                        <Apple className="h-3 w-3" />
                        <span>+</span>
                        <Smartphone className="h-3 w-3" />
                        <span>iOS & Android</span>
                      </span>
                    )}
                    {plan.supported_platforms === 'ios' && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 dark:border-sky-900/60 bg-sky-50 dark:bg-sky-950/40 px-2 py-0.5 text-[10px] font-semibold text-sky-700 dark:text-sky-300">
                        <Apple className="h-3 w-3" />
                        <span>Chỉ iOS</span>
                      </span>
                    )}
                    {plan.supported_platforms === 'android' && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
                        <Smartphone className="h-3 w-3" />
                        <span>Chỉ Android</span>
                      </span>
                    )}
                  </div>

                  {/* Status / Popular Badge */}
                  <div className="flex items-center gap-1 shrink-0">
                    {isOutOfStock ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-600 dark:text-rose-400 px-2 py-0.5 text-[10px] font-bold">
                        <AlertCircle className="h-2.5 w-2.5" />
                        <span>Hết hàng</span>
                      </span>
                    ) : isPopular ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500 text-zinc-950 px-2 py-0.5 text-[10px] font-bold shadow-sm">
                        <Sparkles className="h-2.5 w-2.5 fill-current" />
                        <span>Được chọn nhiều</span>
                      </span>
                    ) : isSelected ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-300 px-2 py-0.5 text-[10px] font-bold">
                        <Check className="h-2.5 w-2.5" />
                        <span>Đang chọn</span>
                      </span>
                    ) : null}
                  </div>
                </div>

                {/* Plan Name & Short Description */}
                <div>
                  <h4 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-white tracking-tight line-clamp-1 group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors">
                    {plan.name}
                  </h4>
                  {plan.short_description ? (
                    <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400 line-clamp-2 leading-relaxed min-h-[32px]">
                      {plan.short_description}
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500 italic line-clamp-2 leading-relaxed min-h-[32px]">
                      Gói Locket Gold chính hãng kèm bảo hành.
                    </p>
                  )}
                </div>

                {/* Price & Duration Block */}
                <div className="my-3 pt-2.5 pb-2 border-y border-zinc-100 dark:border-zinc-800/80">
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-xl sm:text-2xl font-black text-amber-600 dark:text-amber-400 tracking-tight">
                      {formatVND(plan.price_vnd)}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-400 flex-wrap">
                    <span>hoặc</span>
                    <span className="inline-flex items-center gap-1 font-bold text-zinc-800 dark:text-zinc-200">
                      <Coins className="h-3.5 w-3.5 text-amber-500" />
                      <span>{formatCoin(plan.price_coin)}</span>
                    </span>
                    <span className="text-zinc-400">·</span>
                    <span className="text-zinc-500 dark:text-zinc-400 font-medium">
                      {formatDuration(plan.duration_days)}
                    </span>
                  </div>
                </div>

                {/* Maximum 2 Features Preview */}
                <div className="space-y-1.5 mb-3">
                  {previewFeatures.length > 0 ? (
                    previewFeatures.map((feat, idx) => (
                      <div key={idx} className="flex items-start gap-1.5 text-xs text-zinc-700 dark:text-zinc-300">
                        <Check className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
                        <span className="truncate">{feat}</span>
                      </div>
                    ))
                  ) : (
                    <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
                      <Check className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                      <span>Đầy đủ đặc quyền Locket Gold VIP</span>
                    </div>
                  )}

                  {remainingCount > 0 && (
                    <div className="text-[11px] font-semibold text-amber-600 dark:text-amber-400/90 pl-5">
                      +{remainingCount} quyền lợi khác
                    </div>
                  )}
                </div>
              </div>

              {/* Bottom Action Hint */}
              <div className="pt-2.5 mt-auto border-t border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400 group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors">
                <span className="font-semibold flex items-center gap-1">
                  <Info className="h-3 w-3" />
                  <span>Bấm để xem chi tiết</span>
                </span>
                <span className="flex items-center gap-0.5 font-bold group-hover:translate-x-1 transition-transform">
                  <ArrowRight className="h-3.5 w-3.5 text-amber-500" />
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Plan Details & Selection Modal */}
      <PlanDetailsModal
        plan={activeModalPlan}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        onSelect={handleConfirmSelect}
        isSelected={activeModalPlan ? selectedPlanId === activeModalPlan.id : false}
      />
    </>
  );
};
