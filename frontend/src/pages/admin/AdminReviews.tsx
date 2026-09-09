import React, { useState, useEffect, useCallback } from 'react';
import {
  Star,
  Pin,
  Trash2,
  Image as ImageIcon,
  RefreshCw,
  AlertCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Modal } from '../../components/admin/Modal';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { AuthenticatedReviewImage } from '../../components/reviews/AuthenticatedReviewImage';
import {
  fetchAdminReviews,
  deleteAdminReview,
} from '../../api/adminEndpoints';
import type { AdminReviewItem } from '../../types/admin';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

export const AdminReviews: React.FC = () => {
  const [reviews, setReviews] = useState<AdminReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [limit] = useState(10);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Zoom Image Modal
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null);

  // Delete Dialog
  const [deletingReview, setDeletingReview] = useState<AdminReviewItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadReviews = useCallback(async (silent = false) => {
    try {
      if (!silent) {
        setIsLoading(true);
        setError(null);
      }
      const res = await fetchAdminReviews({
        status: '',
        page,
        limit,
      });
      if (res.success) {
        setReviews(res.items);
        setTotal(res.pagination.total);
        const nextPages = Math.max(1, res.pagination.pages);
        setPages(nextPages);
        if (page > nextPages) setPage(nextPages);
      }
    } catch (err: any) {
      if (!silent) setError(err.message || 'Không thể tải danh sách đánh giá.');
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [page, limit]);

  useEffect(() => {
    loadReviews();
  }, [loadReviews]);

  useLiveRefresh(() => loadReviews(true), 8_000);

  const handleDeleteConfirm = async () => {
    if (!deletingReview) return;
    try {
      setIsDeleting(true);
      await deleteAdminReview(deletingReview.id);
      setDeletingReview(null);
      loadReviews();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa đánh giá.');
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDate = (timestamp: number) => {
    if (!timestamp) return '---';
    return new Date(timestamp * 1000).toLocaleString('vi-VN');
  };

  return (
    <div className="space-y-6">
      {/* Filters Header */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 backdrop-blur-md">
        <div>
          <p className="text-sm font-bold text-zinc-100">Feedback tự động công khai</p>
          <p className="mt-0.5 text-xs text-zinc-400">Admin xem danh sách và xóa feedback không phù hợp.</p>
        </div>

        <button
          type="button"
          onClick={() => void loadReviews()}
          disabled={isLoading}
          className="flex items-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs font-semibold text-zinc-300 hover:text-white transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
          <span>Làm mới</span>
        </button>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Reviews Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {isLoading ? (
          <div className="col-span-full py-12 text-center text-zinc-500">
            <Loader2 className="h-6 w-6 animate-spin text-amber-500 mx-auto mb-2" />
            <span>Đang tải danh sách đánh giá...</span>
          </div>
        ) : reviews.length === 0 ? (
          <div className="col-span-full py-12 text-center text-zinc-500">
            Không có đánh giá nào phù hợp với bộ lọc.
          </div>
        ) : (
          reviews.map((rev) => (
            <div
              key={rev.id}
              className="relative flex flex-col justify-between rounded-3xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md"
            >
              <div>
                {/* Header */}
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div>
                    <div className="font-bold text-sm text-white flex items-center gap-1.5">
                      <span>{rev.display_name || rev.username}</span>
                      {rev.is_pinned ? (
                        <Pin className="h-3.5 w-3.5 text-amber-400 fill-current" />
                      ) : null}
                    </div>
                    <div className="text-[11px] text-zinc-400">@{rev.username} • {rev.email}</div>
                  </div>

                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${
                    rev.status === 'approved'
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                      : 'border-zinc-700 bg-zinc-800 text-zinc-400'
                  }`}>
                    {rev.status === 'approved' ? 'Công khai' : `Dữ liệu cũ: ${rev.status}`}
                  </span>
                </div>

                {/* Rating stars */}
                <div className="flex items-center gap-1 mb-3">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <Star
                      key={s}
                      className={`h-4 w-4 ${
                        s <= rev.rating ? 'text-amber-400 fill-amber-400' : 'text-zinc-700'
                      }`}
                    />
                  ))}
                  <span className="ml-1.5 text-xs font-bold text-zinc-300">{rev.rating}/5</span>
                </div>

                {/* Content */}
                <p className="text-xs text-zinc-300 leading-relaxed mb-4 whitespace-pre-line">
                  {rev.content ? `"${rev.content}"` : 'Người dùng chỉ đánh giá bằng số sao.'}
                </p>

                {/* Attached Images */}
                {rev.images && rev.images.length > 0 && (
                  <div className="mb-4">
                    <span className="text-[10px] font-semibold text-zinc-400 block mb-1.5 flex items-center gap-1">
                      <ImageIcon className="h-3 w-3" />
                      <span>Ảnh đính kèm ({rev.images.length}):</span>
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {rev.images.map((img) => (
                        <button
                          key={img.id}
                          type="button"
                          onClick={() => setZoomImageUrl(img.url)}
                          className="h-14 w-14 rounded-xl overflow-hidden border border-zinc-700 hover:border-amber-400 transition-all cursor-pointer"
                        >
                          <AuthenticatedReviewImage
                            src={img.url}
                            alt="Review proof"
                            className="h-full w-full object-cover"
                          />
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Staff Note */}
                {rev.staff_note && (
                  <div className="rounded-xl bg-zinc-950 border border-zinc-800/80 p-2.5 mb-3 text-[11px] text-zinc-400">
                    <span className="font-bold text-amber-400 block mb-0.5">Ghi chú nội bộ cũ:</span>
                    <span>{rev.staff_note}</span>
                  </div>
                )}
              </div>

              {/* Card Footer: feedback is auto-published; Admin only removes abuse/spam. */}
              <div className="flex items-center justify-between pt-3 border-t border-zinc-800/80 mt-2">
                <span className="text-[11px] text-zinc-400">{formatDate(rev.created_at)}</span>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setDeletingReview(rev)}
                    className="flex min-h-11 items-center gap-1.5 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 text-xs font-semibold text-rose-400 transition hover:bg-rose-500/20"
                    title="Xóa đánh giá"
                  >
                    <Trash2 className="h-4 w-4" />
                    <span>Xóa</span>
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination Footer */}
      <div className="flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/60 px-4 py-3 text-xs text-zinc-400">
        <div>
          Tổng cộng: <span className="font-bold text-zinc-200">{total}</span> đánh giá (Trang {page}/{pages || 1})
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            disabled={page <= 1 || isLoading}
            onClick={() => setPage((p) => Math.max(p - 1, 1))}
            className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="px-2 font-bold text-zinc-200">{page}</span>
          <button
            type="button"
            disabled={page >= pages || isLoading}
            onClick={() => setPage((p) => Math.min(p + 1, pages))}
            className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Image Zoom Modal */}
      {zoomImageUrl && (
        <Modal
          isOpen={Boolean(zoomImageUrl)}
          onClose={() => setZoomImageUrl(null)}
          title="Xem Ảnh Đính Kèm"
          maxWidth="2xl"
        >
          <div className="flex justify-center p-2">
            <AuthenticatedReviewImage
              src={zoomImageUrl}
              alt="Zoomed review proof"
              className="max-h-[70vh] rounded-2xl object-contain border border-zinc-800"
            />
          </div>
        </Modal>
      )}

      {/* Delete Confirmation */}
      {deletingReview && (
        <ConfirmDialog
          isOpen={Boolean(deletingReview)}
          onClose={() => setDeletingReview(null)}
          onConfirm={handleDeleteConfirm}
          title="Xóa Đánh Giá Khách Hàng"
          message={`Bạn có chắc chắn muốn xóa vĩnh viễn đánh giá #${deletingReview.id} của @${deletingReview.username}?`}
          confirmText="Xác nhận xóa"
          isDanger={true}
          isLoading={isDeleting}
        />
      )}
    </div>
  );
};
