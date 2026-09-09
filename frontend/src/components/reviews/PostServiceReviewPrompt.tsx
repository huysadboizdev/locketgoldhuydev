import React, { useEffect, useId, useState } from 'react';
import { CheckCircle2, HeartHandshake, Star } from 'lucide-react';
import type { ActivationOrder, UserReview } from '../../types/api';
import { ModalPortal } from '../common/ModalPortal';
import { ReviewFormModal } from './ReviewFormModal';

type ReviewActionResult = Promise<{ success: boolean; msg: string; error?: string }>;

interface PostServiceReviewPromptProps {
  isOpen: boolean;
  order: ActivationOrder | null;
  myReview: UserReview | null;
  onClose: () => void;
  onSubmit: (rating: number, content: string, images: File[]) => ReviewActionResult;
  onUpdate: (rating: number, content: string, images: File[], keepImageIds?: number[]) => ReviewActionResult;
  onDelete: () => ReviewActionResult;
}

export const PostServiceReviewPrompt: React.FC<PostServiceReviewPromptProps> = ({
  isOpen,
  order,
  myReview,
  onClose,
  onSubmit,
  onUpdate,
  onDelete,
}) => {
  const [showReviewForm, setShowReviewForm] = useState(false);
  const reactId = useId().replace(/:/g, '');
  const titleId = `post-service-title-${reactId}`;
  const descriptionId = `post-service-description-${reactId}`;

  useEffect(() => {
    setShowReviewForm(false);
  }, [order?.id]);

  if (!order) return null;

  return (
    <>
      <ModalPortal
        isOpen={isOpen && !showReviewForm}
        onClose={onClose}
        ariaLabelledBy={titleId}
        ariaDescribedBy={descriptionId}
        backdropClassName="bg-zinc-950/45 backdrop-blur-[2px]"
        className="max-w-lg overflow-hidden !rounded-[28px] !border !border-amber-300/70 !bg-white dark:!border-amber-500/25 dark:!bg-zinc-900"
      >
        <div className="relative overflow-hidden px-5 py-6 sm:px-8 sm:py-8">
          <div className="pointer-events-none absolute -right-20 -top-24 h-52 w-52 rounded-full bg-amber-300/25 blur-3xl dark:bg-amber-500/10" />
          <div className="pointer-events-none absolute -bottom-24 -left-20 h-48 w-48 rounded-full bg-pink-200/30 blur-3xl dark:bg-pink-500/10" />

          <div className="relative text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-br from-amber-300 via-amber-400 to-orange-500 text-zinc-950 shadow-lg shadow-amber-500/20 ring-4 ring-amber-100 dark:ring-amber-500/10">
              <HeartHandshake className="h-8 w-8" aria-hidden="true" />
            </div>

            <div className="mt-5 inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-bold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
              Dịch vụ đã hoàn tất
            </div>

            <h2 id={titleId} className="mt-3 text-2xl font-black tracking-tight text-zinc-950 dark:text-white sm:text-3xl">
              Cảm ơn bạn đã tin tưởng!
            </h2>
            <p id={descriptionId} className="mx-auto mt-3 max-w-md text-sm leading-6 text-zinc-600 dark:text-zinc-300">
              Gói <strong className="text-zinc-900 dark:text-white">{order.plan_name_snapshot}</strong> đã hoàn tất.
              Một đánh giá ngắn của bạn sẽ giúp Locket Gold phục vụ tốt hơn mỗi ngày.
            </p>

            <div className="mt-6 grid grid-cols-1 gap-2.5 min-[430px]:grid-cols-2">
              <button
                type="button"
                onClick={onClose}
                className="order-2 min-h-11 rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm font-semibold text-zinc-600 transition hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-amber-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 min-[430px]:order-1"
              >
                Để sau
              </button>
              <button
                type="button"
                onClick={() => setShowReviewForm(true)}
                className="order-1 inline-flex min-h-11 items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 px-4 py-3 text-sm font-black text-zinc-950 shadow-lg shadow-amber-500/20 transition hover:brightness-105 active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-amber-400 min-[430px]:order-2"
              >
                <Star className="h-4 w-4 fill-current" aria-hidden="true" />
                Đánh giá trải nghiệm
              </button>
            </div>

            <p className="mt-4 text-[11px] leading-5 text-zinc-400 dark:text-zinc-500">
              Nội dung và ảnh đều không bắt buộc — bạn chỉ cần chọn số sao.
            </p>
          </div>
        </div>
      </ModalPortal>

      <ReviewFormModal
        isOpen={isOpen && showReviewForm}
        onClose={onClose}
        myReview={myReview}
        onSubmit={onSubmit}
        onUpdate={onUpdate}
        onDelete={onDelete}
      />
    </>
  );
};
