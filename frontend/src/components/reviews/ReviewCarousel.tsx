import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import type { PublicReview, ReviewImage } from '../../types/api';
import { ReviewCard } from './ReviewCard';

interface ReviewCarouselProps {
  reviews: PublicReview[];
  onImageClick: (images: ReviewImage[], index: number) => void;
  isLightboxOpen?: boolean;
}

export const ReviewCarousel: React.FC<ReviewCarouselProps> = ({
  reviews,
  onImageClick,
  isLightboxOpen = false,
}) => {
  const totalReviews = reviews.length;

  // Determine items per page based on window size
  const [itemsPerPage, setItemsPerPage] = useState<number>(3);

  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width < 640) {
        setItemsPerPage(1); // Mobile
      } else if (width < 1024) {
        setItemsPerPage(2); // Tablet
      } else {
        setItemsPerPage(3); // Desktop
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const shouldLoop = totalReviews > itemsPerPage;

  // Tripled items for infinite loop without rewind
  const displayItems = useMemo(() => {
    if (!shouldLoop) return reviews;
    return [...reviews, ...reviews, ...reviews];
  }, [reviews, shouldLoop]);

  // currentIndex starts at totalReviews (the middle segment)
  const [currentIndex, setCurrentIndex] = useState<number>(shouldLoop ? totalReviews : 0);
  const [withTransition, setWithTransition] = useState<boolean>(true);

  // Sync index if totalReviews changes
  useEffect(() => {
    if (shouldLoop) {
      setCurrentIndex(totalReviews);
      setWithTransition(false);
    } else {
      setCurrentIndex(0);
    }
  }, [totalReviews, shouldLoop]);

  // Turn transition back on after instant reset
  useEffect(() => {
    if (!withTransition) {
      const frame = requestAnimationFrame(() => {
        setWithTransition(true);
      });
      return () => cancelAnimationFrame(frame);
    }
  }, [withTransition]);

  const [isHovered, setIsHovered] = useState<boolean>(false);
  const [isFocused, setIsFocused] = useState<boolean>(false);
  const [isTabHidden, setIsTabHidden] = useState<boolean>(false);

  // Touch / Drag tracking with X and Y
  const touchStartX = useRef<number>(0);
  const touchEndX = useRef<number>(0);
  const touchStartY = useRef<number>(0);
  const touchEndY = useRef<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  // Listen to document visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsTabHidden(document.hidden);
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // Check prefers-reduced-motion
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(false);
  useEffect(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      setPrefersReducedMotion(mediaQuery.matches);
      const listener = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
      mediaQuery.addEventListener('change', listener);
      return () => mediaQuery.removeEventListener('change', listener);
    }
  }, []);

  const nextSlide = useCallback(() => {
    if (!shouldLoop) return;
    setWithTransition(true);
    setCurrentIndex((prev) => prev + 1);
  }, [shouldLoop]);

  const prevSlide = useCallback(() => {
    if (!shouldLoop) return;
    setWithTransition(true);
    setCurrentIndex((prev) => prev - 1);
  }, [shouldLoop]);

  const handleTransitionEnd = () => {
    if (!shouldLoop) return;
    if (currentIndex >= 2 * totalReviews) {
      setWithTransition(false);
      setCurrentIndex(currentIndex - totalReviews);
    } else if (currentIndex < totalReviews) {
      setWithTransition(false);
      setCurrentIndex(currentIndex + totalReviews);
    }
  };

  // Autoplay interval
  useEffect(() => {
    if (
      !shouldLoop ||
      isHovered ||
      isFocused ||
      isTabHidden ||
      isLightboxOpen ||
      isDragging ||
      prefersReducedMotion
    ) {
      return;
    }

    const interval = setInterval(() => {
      nextSlide();
    }, 5000);

    return () => clearInterval(interval);
  }, [
    shouldLoop,
    isHovered,
    isFocused,
    isTabHidden,
    isLightboxOpen,
    isDragging,
    prefersReducedMotion,
    nextSlide,
  ]);

  // Touch Handlers with proper coordinate initialization
  const handleTouchStart = (e: React.TouchEvent) => {
    const touch = e.targetTouches[0];
    touchStartX.current = touch.clientX;
    touchEndX.current = touch.clientX;
    touchStartY.current = touch.clientY;
    touchEndY.current = touch.clientY;
    setIsDragging(true);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    const touch = e.targetTouches[0];
    touchEndX.current = touch.clientX;
    touchEndY.current = touch.clientY;
  };

  const handleTouchEnd = () => {
    setIsDragging(false);
    const diffX = touchStartX.current - touchEndX.current;
    const diffY = touchStartY.current - touchEndY.current;

    // Only swipe if horizontal move is significant and greater than vertical scroll
    if (Math.abs(diffX) > 50 && Math.abs(diffX) > Math.abs(diffY)) {
      if (diffX > 0) {
        nextSlide();
      } else {
        prevSlide();
      }
    }
  };

  // Case 0 reviews: Honest empty state
  if (totalReviews === 0) {
    return (
      <div className="w-full max-w-2xl mx-auto my-6 p-8 rounded-2xl border border-dashed border-amber-500/20 bg-amber-500/5 text-center flex flex-col items-center justify-center">
        <div className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center text-amber-500 mb-3">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <h4 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          Chưa có đánh giá nào được công khai
        </h4>
        <p className="text-xs sm:text-sm text-zinc-500 dark:text-zinc-400 mt-1 max-w-md">
          Mỗi đánh giá hiển thị tại đây đều từ các tài khoản đã hoàn tất kích hoạt Locket Gold thực tế. Hãy là người đầu tiên nâng cấp và chia sẻ trải nghiệm của bạn!
        </p>
      </div>
    );
  }

  // Case 1 or 2 reviews when itemsPerPage is larger: Centered flex/grid without awkward carousel scroll
  if (!shouldLoop) {
    return (
      <div className="w-full max-w-4xl mx-auto flex flex-wrap justify-center gap-6 my-6 px-4">
        {reviews.map((review) => (
          <div key={review.id} className="w-full sm:w-[360px]">
            <ReviewCard review={review} onImageClick={onImageClick} />
          </div>
        ))}
      </div>
    );
  }

  const activeDotIndex = ((currentIndex % totalReviews) + totalReviews) % totalReviews;

  return (
    <div
      className="relative w-full max-w-6xl mx-auto my-6 px-2 sm:px-4 select-none"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Slider Viewport */}
      <div className="overflow-hidden rounded-2xl py-2">
        <div
          onTransitionEnd={handleTransitionEnd}
          className={`flex ${withTransition && !prefersReducedMotion ? 'transition-transform duration-500 ease-out' : ''}`}
          style={{
            transform: `translateX(-${currentIndex * (100 / itemsPerPage)}%)`,
          }}
        >
          {displayItems.map((review, idx) => (
            <div
              key={`${review.id}-item-${idx}`}
              className="flex-shrink-0 px-2 sm:px-3"
              style={{ width: `${100 / itemsPerPage}%` }}
            >
              <ReviewCard review={review} onImageClick={onImageClick} />
            </div>
          ))}
        </div>
      </div>

      {/* Navigation Arrows */}
      {shouldLoop && (
        <>
          <button
            type="button"
            onClick={prevSlide}
            aria-label="Đánh giá trước đó"
            className="absolute left-[-4px] sm:left-[-12px] top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/90 dark:bg-zinc-800/90 text-zinc-700 dark:text-zinc-200 border border-amber-500/30 shadow-md flex items-center justify-center hover:bg-amber-400 hover:text-zinc-950 transition-all focus:outline-none focus:ring-2 focus:ring-amber-400 z-10"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <button
            type="button"
            onClick={nextSlide}
            aria-label="Đánh giá kế tiếp"
            className="absolute right-[-4px] sm:right-[-12px] top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/90 dark:bg-zinc-800/90 text-zinc-700 dark:text-zinc-200 border border-amber-500/30 shadow-md flex items-center justify-center hover:bg-amber-400 hover:text-zinc-950 transition-all focus:outline-none focus:ring-2 focus:ring-amber-400 z-10"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </>
      )}

      {/* Carousel Dots Indicators */}
      {shouldLoop && (
        <div className="flex justify-center items-center gap-1.5 mt-4">
          {reviews.map((_, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setWithTransition(true);
                setCurrentIndex(totalReviews + idx);
              }}
              aria-label={`Chuyển đến đánh giá ${idx + 1}`}
              className={`h-1.5 rounded-full transition-all duration-300 ${activeDotIndex === idx ? 'w-6 bg-amber-400 shadow-sm shadow-amber-400/50' : 'w-1.5 bg-zinc-300 dark:bg-zinc-700 hover:bg-amber-400/50'}`}
            />
          ))}
        </div>
      )}
    </div>
  );
};
