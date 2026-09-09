import { useState, useEffect, useCallback } from 'react';
import {
  fetchPublicReviews,
  fetchMyReview,
  submitReviewApi,
  updateMyReviewApi,
  deleteMyReviewApi,
} from '../api/endpoints';
import type { PublicReview, ReviewStats, UserReview } from '../types/api';
import { useAuth } from '../context/AuthContext';

export interface UseReviewsReturn {
  reviews: PublicReview[];
  stats: ReviewStats;
  loading: boolean;
  error: string | null;
  refreshPublicReviews: () => Promise<void>;

  // User's own review & eligibility
  myReview: UserReview | null;
  isEligible: boolean;
  hasReview: boolean;
  myReviewLoading: boolean;
  refreshMyReview: () => Promise<void>;

  // Actions
  submitReview: (rating: number, content: string, images: File[]) => Promise<{ success: boolean; msg: string; error?: string }>;
  updateReview: (rating: number, content: string, images: File[], keepImageIds?: number[]) => Promise<{ success: boolean; msg: string; error?: string }>;
  deleteReview: () => Promise<{ success: boolean; msg: string; error?: string }>;
}

const DEFAULT_STATS: ReviewStats = {
  total: 0,
  average_rating: 0,
  distribution: { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 },
};

interface UseReviewsOptions {
  loadPublic?: boolean;
}

export function useReviews({ loadPublic = true }: UseReviewsOptions = {}): UseReviewsReturn {
  const { isAuthenticated } = useAuth();

  const [reviews, setReviews] = useState<PublicReview[]>([]);
  const [stats, setStats] = useState<ReviewStats>(DEFAULT_STATS);
  const [loading, setLoading] = useState<boolean>(loadPublic);
  const [error, setError] = useState<string | null>(null);

  const [myReview, setMyReview] = useState<UserReview | null>(null);
  const [isEligible, setIsEligible] = useState<boolean>(false);
  const [hasReview, setHasReview] = useState<boolean>(false);
  const [myReviewLoading, setMyReviewLoading] = useState<boolean>(false);

  // Fetch approved reviews for public carousel
  const refreshPublicReviews = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPublicReviews();
      if (data && data.success) {
        setReviews(data.reviews || []);
        setStats(data.stats || DEFAULT_STATS);
      }
    } catch (err: any) {
      setError(err.message || 'Không thể tải danh sách đánh giá.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch authenticated user's own review
  const refreshMyReview = useCallback(async () => {
    if (!isAuthenticated) {
      setMyReview(null);
      setIsEligible(false);
      setHasReview(false);
      return;
    }
    try {
      setMyReviewLoading(true);
      const data = await fetchMyReview();
      if (data && data.success) {
        setIsEligible(Boolean(data.eligible));
        setHasReview(Boolean(data.has_review));
        setMyReview(data.review || null);
      }
    } catch (err: any) {
      // Non-critical, fail silently for me endpoint
    } finally {
      setMyReviewLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (loadPublic) {
      refreshPublicReviews();
    }
  }, [loadPublic, refreshPublicReviews]);

  useEffect(() => {
    refreshMyReview();
  }, [refreshMyReview]);

  // Submit new review
  const submitReview = async (
    rating: number,
    content: string,
    images: File[]
  ): Promise<{ success: boolean; msg: string; error?: string }> => {
    try {
      const formData = new FormData();
      formData.append('rating', rating.toString());
      formData.append('content', content.trim());
      images.forEach((file) => {
        formData.append('images', file);
      });

      const res = await submitReviewApi(formData);
      await refreshMyReview();
      await refreshPublicReviews();
      return { success: true, msg: res.msg || 'Đánh giá đã được gửi thành công.' };
    } catch (err: any) {
      return {
        success: false,
        msg: err.message || 'Gửi đánh giá không thành công. Vui lòng thử lại.',
        error: err.data?.error || err.message,
      };
    }
  };

  // Update existing review
  const updateReview = async (
    rating: number,
    content: string,
    images: File[],
    keepImageIds?: number[]
  ): Promise<{ success: boolean; msg: string; error?: string }> => {
    try {
      const formData = new FormData();
      formData.append('rating', rating.toString());
      formData.append('content', content.trim());
      images.forEach((file) => {
        formData.append('images', file);
      });
      if (keepImageIds && keepImageIds.length > 0) {
        keepImageIds.forEach((id) => {
          formData.append('keep_image_ids', id.toString());
        });
      }

      const res = await updateMyReviewApi(formData);
      await refreshMyReview();
      await refreshPublicReviews();
      return { success: true, msg: res.msg || 'Đánh giá đã được cập nhật thành công.' };
    } catch (err: any) {
      return {
        success: false,
        msg: err.message || 'Cập nhật đánh giá không thành công. Vui lòng thử lại.',
        error: err.data?.error || err.message,
      };
    }
  };

  // Delete own review
  const deleteReview = async (): Promise<{ success: boolean; msg: string; error?: string }> => {
    try {
      const res = await deleteMyReviewApi();
      await refreshMyReview();
      await refreshPublicReviews();
      return { success: true, msg: res.msg || 'Đánh giá của bạn đã được xóa thành công.' };
    } catch (err: any) {
      return {
        success: false,
        msg: err.message || 'Xóa đánh giá không thành công.',
        error: err.data?.error || err.message,
      };
    }
  };

  return {
    reviews,
    stats,
    loading,
    error,
    refreshPublicReviews,
    myReview,
    isEligible,
    hasReview,
    myReviewLoading,
    refreshMyReview,
    submitReview,
    updateReview,
    deleteReview,
  };
}
