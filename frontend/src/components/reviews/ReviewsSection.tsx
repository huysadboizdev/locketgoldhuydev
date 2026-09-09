import React, { useState } from 'react';
import { useReviews } from '../../hooks/useReviews';
import { useAuth } from '../../context/AuthContext';
import { ReviewCarousel } from './ReviewCarousel';
import { ReviewFormModal } from './ReviewFormModal';
import { ReviewLightbox } from './ReviewLightbox';
import type { ReviewImage } from '../../types/api';
import { Link } from 'react-router-dom';
import { ModalPortal } from '../common/ModalPortal';

export const ReviewsSection: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const {
    reviews,
    stats,
    loading,
    error,
    refreshPublicReviews,
    myReview,
    isEligible,
    hasReview,
    submitReview,
    updateReview,
    deleteReview,
  } = useReviews();

  // Modals state
  const [isFormModalOpen, setIsFormModalOpen] = useState<boolean>(false);
  const [lightboxState, setLightboxState] = useState<{
    isOpen: boolean;
    images: ReviewImage[];
    currentIndex: number;
  }>({
    isOpen: false,
    images: [],
    currentIndex: 0,
  });

  const [ineligibleModalOpen, setIneligibleModalOpen] = useState<boolean>(false);

  const handleOpenImage = (images: ReviewImage[], index: number) => {
    setLightboxState({
      isOpen: true,
      images,
      currentIndex: index,
    });
  };

  const handleCloseLightbox = () => {
    setLightboxState((prev) => ({ ...prev, isOpen: false }));
  };

  const handleNavigateLightbox = (index: number) => {
    setLightboxState((prev) => ({ ...prev, currentIndex: index }));
  };

  return (
    <section id="reviews" className="relative py-12 sm:py-16 overflow-hidden">
      {/* Ambient background glow */}
      <div
        className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[600px] h-[350px] bg-amber-500/10 dark:bg-amber-500/5 blur-[120px] rounded-full"
        aria-hidden="true"
      />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-8 sm:mb-12">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 mb-3 shadow-sm">
            <svg className="w-3.5 h-3.5 text-amber-500" viewBox="0 0 20 20" fill="currentColor">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            Đánh giá từ người dùng thật
          </div>

          <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-zinc-900 dark:text-white tracking-tight">
            Cộng Đồng Trải Nghiệm{' '}
            <span className="bg-gradient-to-r from-amber-500 via-amber-400 to-yellow-300 bg-clip-text text-transparent">
              Locket Gold
            </span>
          </h2>

          <p className="mt-3 text-sm sm:text-base text-zinc-600 dark:text-zinc-400">
            Minh bạch, chân thực và đã được xác minh. Mọi phản hồi đều đến từ những người dùng đã hoàn tất quy trình kích hoạt.
          </p>

          {/* Rating Summary Bar */}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-4 text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
            {stats.total > 0 ? (
              <>
                <div className="flex items-center gap-1 font-bold text-zinc-900 dark:text-zinc-100 text-base">
                  <span className="text-amber-500 text-lg">★</span>
                  <span>{stats.average_rating.toFixed(1)}</span>
                  <span className="text-xs text-zinc-400 font-normal">/ 5.0</span>
                </div>
                <span>•</span>
                <span className="font-medium text-zinc-800 dark:text-zinc-200">
                  {stats.total} đánh giá xác thực
                </span>
                <span>•</span>
              </>
            ) : null}

            <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              100% huy hiệu người dùng đã kích hoạt
            </span>
          </div>
        </div>

        {/* Reviews Carousel */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 rounded-full border-2 border-amber-500 border-t-transparent animate-spin" />
              <span className="text-xs text-zinc-500">Đang tải đánh giá...</span>
            </div>
          </div>
        ) : error ? (
          <div className="w-full max-w-md mx-auto my-8 p-6 rounded-2xl border border-red-500/20 bg-red-500/5 text-center flex flex-col items-center justify-center">
            <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center text-red-500 mb-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-xs sm:text-sm text-red-600 dark:text-red-400 font-medium">
              {error}
            </p>
            <button
              type="button"
              onClick={() => refreshPublicReviews()}
              className="mt-3 inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold bg-red-500/10 hover:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/30 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Thử lại
            </button>
          </div>
        ) : (
          <ReviewCarousel
            reviews={reviews}
            onImageClick={handleOpenImage}
            isLightboxOpen={lightboxState.isOpen}
          />
        )}

        {/* CTA Bar below Carousel */}
        <div className="mt-8 text-center">
          {!isAuthenticated ? (
            <Link
              to="/login?returnTo=%2F%23reviews"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs sm:text-sm font-semibold text-zinc-900 dark:text-zinc-100 bg-white/80 dark:bg-zinc-800/80 hover:bg-amber-500/10 dark:hover:bg-amber-500/20 border border-amber-500/30 transition-all shadow-sm"
            >
              <svg className="w-4 h-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
              </svg>
              Đăng nhập để gửi đánh giá của bạn
            </Link>
          ) : isEligible ? (
            <button
              type="button"
              onClick={() => setIsFormModalOpen(true)}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full text-xs sm:text-sm font-bold bg-gradient-to-r from-amber-400 to-amber-500 text-zinc-950 hover:brightness-105 shadow-md shadow-amber-500/20 transition-all"
            >
              <span className="text-base">★</span>
              <span>{hasReview ? 'Xem lại & Chỉnh sửa đánh giá của bạn' : 'Viết đánh giá trải nghiệm'}</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setIneligibleModalOpen(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs sm:text-sm font-medium text-zinc-500 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700 hover:border-amber-500/30 transition-all"
            >
              <svg className="w-4 h-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Hoàn tất nâng cấp tài khoản để gửi đánh giá
            </button>
          )}
        </div>
      </div>

      {/* Review Form Modal */}
      <ReviewFormModal
        isOpen={isFormModalOpen}
        onClose={() => setIsFormModalOpen(false)}
        myReview={myReview}
        onSubmit={submitReview}
        onUpdate={updateReview}
        onDelete={deleteReview}
      />

      {/* Lightbox Modal */}
      <ReviewLightbox
        isOpen={lightboxState.isOpen}
        images={lightboxState.images}
        currentIndex={lightboxState.currentIndex}
        onClose={handleCloseLightbox}
        onNavigate={handleNavigateLightbox}
      />

      {/* Ineligible Explanation Modal */}
      <ModalPortal
        isOpen={ineligibleModalOpen}
        onClose={() => setIneligibleModalOpen(false)}
        ariaLabelledBy="review-ineligible-title"
        className="max-w-md !border !border-amber-500/30"
        backdropClassName="bg-black/70 backdrop-blur-sm"
      >
          <div className="p-5 text-center sm:p-6">
            <div className="w-12 h-12 rounded-full bg-amber-500/10 text-amber-500 mx-auto flex items-center justify-center mb-3">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h4 id="review-ineligible-title" className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
              Yêu cầu hoàn tất dịch vụ
            </h4>
            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 mt-2 leading-relaxed">
              Để bảo đảm 100% đánh giá là chân thực và hữu ích cho cộng đồng, chỉ những tài khoản đã thực hiện nâng cấp Locket Gold thành công ít nhất một lần mới có thể gửi đánh giá.
            </p>
            <div className="mt-5 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => setIneligibleModalOpen(false)}
                className="min-h-11 px-4 py-2 rounded-xl text-xs font-semibold bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
              >
                Đóng
              </button>
              <a
                href="#upgrade"
                onClick={() => setIneligibleModalOpen(false)}
                className="flex min-h-11 items-center px-4 py-2 rounded-xl text-xs font-bold bg-amber-500 text-zinc-950 hover:bg-amber-400 transition-colors"
              >
                Nâng cấp ngay
              </a>
            </div>
          </div>
      </ModalPortal>
    </section>
  );
};
