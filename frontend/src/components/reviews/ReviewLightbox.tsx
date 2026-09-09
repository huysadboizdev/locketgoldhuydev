import React, { useCallback, useEffect } from 'react';
import type { ReviewImage } from '../../types/api';
import { AuthenticatedReviewImage } from './AuthenticatedReviewImage';
import { ModalPortal } from '../common/ModalPortal';

interface ReviewLightboxProps {
  isOpen: boolean;
  images: ReviewImage[];
  currentIndex: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}

export const ReviewLightbox: React.FC<ReviewLightboxProps> = ({
  isOpen,
  images,
  currentIndex,
  onClose,
  onNavigate,
}) => {
  const hasImages = images.length > 0;
  const currentImage = hasImages ? images[currentIndex] || images[0] : null;

  const handleArrowKey = useCallback(
    (event: KeyboardEvent) => {
      if (!isOpen || images.length < 2) return;
      if (event.key === 'ArrowRight') onNavigate((currentIndex + 1) % images.length);
      if (event.key === 'ArrowLeft') onNavigate((currentIndex - 1 + images.length) % images.length);
    },
    [currentIndex, images.length, isOpen, onNavigate]
  );

  useEffect(() => {
    if (!isOpen) return;
    window.addEventListener('keydown', handleArrowKey);
    return () => window.removeEventListener('keydown', handleArrowKey);
  }, [handleArrowKey, isOpen]);

  if (!currentImage) return null;

  return (
    <ModalPortal
      isOpen={isOpen}
      onClose={onClose}
      ariaLabel="Xem ảnh đánh giá"
      backdropClassName="bg-black/95 backdrop-blur-md"
      className="max-w-5xl !overflow-visible !rounded-none !bg-transparent !shadow-none dark:!bg-transparent"
    >
      <div className="relative flex max-h-[calc(100dvh-5.5rem)] select-none flex-col items-center justify-center">
        <div className="absolute -top-12 left-0 right-0 flex h-11 items-center justify-between px-1 text-white/80">
          <span className="text-sm font-medium tracking-wide">
            {images.length > 1 ? `${currentIndex + 1} / ${images.length}` : 'Ảnh đánh giá'}
          </span>
          <button
            type="button"
            onClick={onClose}
            data-autofocus="true"
            className="flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-amber-400"
            aria-label="Đóng"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="relative flex items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-zinc-950 shadow-2xl">
          <AuthenticatedReviewImage
            src={currentImage.url}
            alt={currentImage.original_filename || 'Ảnh đánh giá từ người dùng'}
            className="max-h-[calc(100dvh-6rem)] max-w-[calc(100vw-2rem)] object-contain sm:max-w-[90vw]"
            loading="eager"
          />
        </div>

        {images.length > 1 && (
          <>
            <button
              type="button"
              onClick={() => onNavigate((currentIndex - 1 + images.length) % images.length)}
              className="absolute left-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-white/10 bg-black/60 text-white transition hover:bg-black/90 focus:outline-none focus:ring-2 focus:ring-amber-400 sm:-left-14"
              aria-label="Ảnh trước đó"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => onNavigate((currentIndex + 1) % images.length)}
              className="absolute right-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-white/10 bg-black/60 text-white transition hover:bg-black/90 focus:outline-none focus:ring-2 focus:ring-amber-400 sm:-right-14"
              aria-label="Ảnh kế tiếp"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </>
        )}
      </div>
    </ModalPortal>
  );
};
