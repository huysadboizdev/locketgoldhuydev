import React from 'react';
import type { PublicReview, ReviewImage } from '../../types/api';

interface ReviewCardProps {
  review: PublicReview;
  onImageClick?: (images: ReviewImage[], index: number) => void;
}

export const ReviewCard: React.FC<ReviewCardProps> = ({ review, onImageClick }) => {
  const authorInitial = (review.display_name || 'U').charAt(0).toUpperCase();

  const formattedDate = React.useMemo(() => {
    if (!review.created_at) return '';
    try {
      const d = new Date(review.created_at * 1000);
      return d.toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      });
    } catch {
      return '';
    }
  }, [review.created_at]);

  return (
    <div className="group relative flex flex-col h-full rounded-2xl p-5 sm:p-6 transition-all duration-300 bg-white/80 dark:bg-zinc-900/70 backdrop-blur-xl border border-amber-500/20 shadow-lg hover:shadow-xl hover:border-amber-500/40 hover:-translate-y-0.5">
      {/* Ambient background highlight */}
      <div
        className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-amber-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        aria-hidden="true"
      />

      {/* Header: User Info + Rating */}
      <div className="relative flex items-start justify-between gap-3 mb-3.5">
        <div className="flex items-center gap-3 min-w-0">
          {/* Avatar Circle */}
          <div
            className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center font-bold text-base text-zinc-950 bg-gradient-to-tr from-amber-400 via-amber-300 to-yellow-200 shadow-md shadow-amber-500/20"
            aria-hidden="true"
          >
            {authorInitial}
          </div>

          <div className="min-w-0 flex flex-col">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-semibold text-sm sm:text-base text-zinc-900 dark:text-zinc-100 truncate">
                {review.display_name}
              </span>
              {/* Verified Badge */}
              {review.is_verified && (
                <span
                  title="Tài khoản đã hoàn tất kích hoạt Locket Gold thực tế"
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                >
                  <svg className="w-3 h-3 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Đã nâng cấp
                </span>
              )}
            </div>

            {/* Date & Masked Username */}
            <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
              {review.masked_username && <span>@{review.masked_username}</span>}
              {review.masked_username && formattedDate && <span>•</span>}
              {formattedDate && <span>{formattedDate}</span>}
            </div>
          </div>
        </div>

        {/* Stars */}
        <div className="flex items-center gap-0.5 text-amber-400 flex-shrink-0" aria-label={`Đánh giá ${review.rating} trên 5 sao`}>
          {[1, 2, 3, 4, 5].map((star) => (
            <svg
              key={star}
              className={`w-4 h-4 ${star <= review.rating ? 'text-amber-400 fill-amber-400' : 'text-zinc-300 dark:text-zinc-700 fill-zinc-300 dark:fill-zinc-700'}`}
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          ))}
        </div>
      </div>

      {/* Review Content - Strict plain text (No innerHTML) */}
      {review.content ? (
        <p className="relative flex-1 text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap break-words line-clamp-6 select-text">
          {review.content}
        </p>
      ) : (
        <p className="relative flex-1 text-sm italic text-zinc-400 dark:text-zinc-500">
          Người dùng đánh giá bằng số sao.
        </p>
      )}

      {/* Attached Images */}
      {review.images && review.images.length > 0 && (
        <div className="relative mt-3.5 pt-3 border-t border-zinc-200/50 dark:border-zinc-800/60 flex items-center gap-2">
          {review.images.map((img, idx) => (
            <button
              key={img.id || idx}
              type="button"
              onClick={() => onImageClick && onImageClick(review.images, idx)}
              className="group/img relative w-14 h-14 rounded-lg overflow-hidden border border-amber-500/20 hover:border-amber-400 transition-all focus:outline-none focus:ring-2 focus:ring-amber-400"
              aria-label={`Xem ảnh ${idx + 1}`}
            >
              <img
                src={img.url}
                alt="Ảnh đính kèm"
                className="w-full h-full object-contain bg-zinc-100 dark:bg-zinc-800/80 transition-transform duration-200"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-black/0 group-hover/img:bg-black/20 transition-colors flex items-center justify-center">
                <svg className="w-4 h-4 text-white opacity-0 group-hover/img:opacity-100 transition-opacity drop-shadow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
                </svg>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
