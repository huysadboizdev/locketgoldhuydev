import React, { useState } from 'react';
import {
  Camera,
  CheckCircle2,
  Clock3,
  EyeOff,
  LockKeyhole,
  MessageSquareHeart,
  Pencil,
  ShieldCheck,
  Star,
  XCircle,
  Zap,
} from 'lucide-react';
import { ReviewFormModal } from '../../components/reviews/ReviewFormModal';
import { ReviewLightbox } from '../../components/reviews/ReviewLightbox';
import { AuthenticatedReviewImage } from '../../components/reviews/AuthenticatedReviewImage';
import { useReviews } from '../../hooks/useReviews';
import type { UserReview } from '../../types/api';

interface FeedbackViewProps {
  onGoToWizard: () => void;
  onGoToOrders: () => void;
}

const STATUS_META: Record<
  UserReview['status'],
  { label: string; description: string; className: string; icon: React.ReactNode }
> = {
  pending: {
    label: 'Đang đồng bộ công khai',
    description: 'Đây là dữ liệu cũ đang được hệ thống chuyển sang trạng thái công khai.',
    className: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    icon: <Clock3 className="h-3.5 w-3.5" />,
  },
  approved: {
    label: 'Đã công khai',
    description: 'Đánh giá đang hiển thị công khai trong khu vực phản hồi khách hàng.',
    className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
  },
  rejected: {
    label: 'Đã bị gỡ',
    description: 'Đây là trạng thái cũ. Bạn có thể chỉnh sửa để đánh giá được công khai lại ngay.',
    className: 'border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300',
    icon: <XCircle className="h-3.5 w-3.5" />,
  },
  hidden: {
    label: 'Đang tạm ẩn',
    description: 'Đánh giá hiện không được hiển thị công khai trên landing page.',
    className: 'border-zinc-400/30 bg-zinc-500/10 text-zinc-700 dark:text-zinc-300',
    icon: <EyeOff className="h-3.5 w-3.5" />,
  },
};

const formatReviewDate = (timestamp: number) =>
  new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(timestamp * 1000));

export const FeedbackView: React.FC<FeedbackViewProps> = ({ onGoToWizard, onGoToOrders }) => {
  const {
    myReview,
    isEligible,
    myReviewLoading,
    submitReview,
    updateReview,
    deleteReview,
  } = useReviews({ loadPublic: false });
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const statusMeta = myReview ? STATUS_META[myReview.status] : null;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 sm:space-y-5">
      <section className="relative overflow-hidden rounded-3xl border border-amber-500/25 bg-gradient-to-br from-amber-500/15 via-white/70 to-white/30 p-5 shadow-[0_16px_45px_rgba(210,145,15,0.08)] dark:via-zinc-900/70 dark:to-zinc-900/30 sm:p-6">
        <div className="pointer-events-none absolute -right-10 -top-14 h-44 w-44 rounded-full bg-amber-400/15 blur-3xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-amber-500/25 bg-amber-500/15 text-amber-600 dark:text-amber-300">
              <MessageSquareHeart className="h-5 w-5" />
            </div>
            <div>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-extrabold tracking-tight text-zinc-950 dark:text-white sm:text-2xl">
                  Feedback của bạn
                </h2>
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                  <ShieldCheck className="h-3 w-3" />
                  Người dùng thật
                </span>
              </div>
              <p className="max-w-2xl text-xs leading-relaxed text-zinc-600 dark:text-zinc-400 sm:text-sm">
                Chấm từ 1–5 sao, chia sẻ trải nghiệm và tải ảnh nếu muốn. Feedback sẽ được hiển thị công khai ngay sau khi gửi.
              </p>
            </div>
          </div>
          {isEligible && !myReviewLoading && (
            <button
              type="button"
              onClick={() => setIsFormOpen(true)}
              className="gold-primary inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-2xl px-5 py-2.5 text-xs font-bold transition-all active:scale-[0.98]"
            >
              {myReview ? <Pencil className="h-4 w-4" /> : <MessageSquareHeart className="h-4 w-4" />}
              {myReview ? 'Chỉnh sửa feedback' : 'Viết feedback'}
            </button>
          )}
        </div>
      </section>

      {myReviewLoading ? (
        <section className="animate-pulse rounded-3xl border border-zinc-200 bg-white/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70 sm:p-6">
          <div className="h-5 w-44 rounded-lg bg-zinc-200 dark:bg-zinc-800" />
          <div className="mt-4 h-4 w-full max-w-xl rounded-lg bg-zinc-100 dark:bg-zinc-800/70" />
          <div className="mt-2 h-4 w-3/4 rounded-lg bg-zinc-100 dark:bg-zinc-800/70" />
        </section>
      ) : !isEligible ? (
        <section className="grid gap-4 rounded-3xl border border-zinc-200 bg-white/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70 sm:grid-cols-[1fr_auto] sm:items-center sm:p-6">
          <div className="flex items-start gap-3.5">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
              <LockKeyhole className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-zinc-900 dark:text-white">Hoàn tất một lần kích hoạt để mở feedback</h3>
              <p className="mt-1 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                Hệ thống nhận đánh giá từ tài khoản đã có đơn hoàn thành hoặc TikToker/KOL được Admin xác thực.
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 min-[420px]:flex-row sm:flex-col lg:flex-row">
            <button
              type="button"
              onClick={onGoToOrders}
              className="gold-secondary inline-flex min-h-10 items-center justify-center rounded-xl border px-4 py-2 text-xs font-semibold"
            >
              Xem đơn hàng
            </button>
            <button
              type="button"
              onClick={onGoToWizard}
              className="gold-primary inline-flex min-h-10 items-center justify-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold"
            >
              <Zap className="h-3.5 w-3.5" />
              Chọn gói Gold
            </button>
          </div>
        </section>
      ) : myReview ? (
        <section className="rounded-3xl border border-zinc-200 bg-white/85 p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/70 sm:p-6">
          <div className="flex flex-col gap-3 border-b border-zinc-100 pb-4 dark:border-zinc-800 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-1" aria-label={`${myReview.rating} trên 5 sao`}>
                {[1, 2, 3, 4, 5].map((star) => (
                  <Star
                    key={star}
                    className={`h-5 w-5 ${star <= myReview.rating ? 'fill-amber-400 text-amber-400' : 'text-zinc-300 dark:text-zinc-700'}`}
                  />
                ))}
                <span className="ml-2 text-xs font-bold text-zinc-700 dark:text-zinc-300">{myReview.rating}/5</span>
              </div>
              <p className="mt-1.5 text-[11px] text-zinc-400">Gửi ngày {formatReviewDate(myReview.created_at)}</p>
            </div>
            {statusMeta && (
              <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-bold ${statusMeta.className}`}>
                {statusMeta.icon}
                {statusMeta.label}
              </span>
            )}
          </div>

          <div className="pt-4">
            <p className="whitespace-pre-wrap text-sm leading-7 text-zinc-700 dark:text-zinc-300">{myReview.content}</p>

            {myReview.images.length > 0 && (
              <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {myReview.images.map((image, index) => (
                  <button
                    key={image.id}
                    type="button"
                    onClick={() => setLightboxIndex(index)}
                    className="group relative aspect-[4/3] overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-amber-500 dark:border-zinc-800 dark:bg-zinc-950"
                    aria-label={`Xem ảnh feedback ${index + 1}`}
                  >
                    <AuthenticatedReviewImage
                      src={image.url}
                      alt={image.original_filename || `Ảnh feedback ${index + 1}`}
                      className="h-full w-full object-contain p-1 transition-transform duration-300 group-hover:scale-[1.03]"
                      loading="lazy"
                    />
                    <span className="absolute bottom-2 right-2 inline-flex items-center gap-1 rounded-lg bg-black/65 px-2 py-1 text-[10px] font-medium text-white opacity-0 backdrop-blur-sm transition-opacity group-hover:opacity-100 group-focus:opacity-100">
                      <Camera className="h-3 w-3" /> Xem ảnh
                    </span>
                  </button>
                ))}
              </div>
            )}

            {statusMeta && (
              <div className={`mt-4 rounded-2xl border p-3.5 text-xs ${statusMeta.className}`}>
                <p className="font-semibold">{statusMeta.description}</p>
                {myReview.status === 'rejected' && myReview.admin_note && (
                  <p className="mt-1.5 border-t border-current/15 pt-1.5">
                    <span className="font-bold">Ghi chú quản trị viên:</span> {myReview.admin_note}
                  </p>
                )}
              </div>
            )}
          </div>
        </section>
      ) : (
        <section className="grid gap-4 rounded-3xl border border-amber-500/20 bg-white/85 p-5 dark:bg-zinc-900/70 sm:p-6 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex items-center gap-1" aria-hidden="true">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star key={star} className="h-5 w-5 fill-amber-400 text-amber-400" />
              ))}
            </div>
            <h3 className="mt-3 text-base font-bold text-zinc-900 dark:text-white">Bạn đã đủ điều kiện gửi feedback</h3>
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
              Mỗi tài khoản có một feedback và có thể chỉnh sửa. Bạn được tải tối đa 3 ảnh JPG, PNG hoặc WebP, mỗi ảnh không quá 3MB.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsFormOpen(true)}
            className="gold-primary inline-flex min-h-11 items-center justify-center gap-2 rounded-2xl px-5 py-2.5 text-xs font-bold"
          >
            <Camera className="h-4 w-4" />
            Viết feedback & tải ảnh
          </button>
        </section>
      )}

      <ReviewFormModal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        myReview={myReview}
        onSubmit={submitReview}
        onUpdate={updateReview}
        onDelete={deleteReview}
      />

      <ReviewLightbox
        isOpen={lightboxIndex !== null}
        images={myReview?.images || []}
        currentIndex={lightboxIndex || 0}
        onClose={() => setLightboxIndex(null)}
        onNavigate={setLightboxIndex}
      />
    </div>
  );
};
