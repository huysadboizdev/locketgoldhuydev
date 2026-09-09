import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { ReviewImage, UserReview } from '../../types/api';
import { AuthenticatedReviewImage } from './AuthenticatedReviewImage';
import { ModalPortal } from '../common/ModalPortal';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { useToast } from '../../hooks/useToast';

interface ReviewFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  myReview: UserReview | null;
  onSubmit: (rating: number, content: string, images: File[]) => Promise<{ success: boolean; msg: string; error?: string }>;
  onUpdate: (rating: number, content: string, images: File[], keepImageIds?: number[]) => Promise<{ success: boolean; msg: string; error?: string }>;
  onDelete: () => Promise<{ success: boolean; msg: string; error?: string }>;
}

export const ReviewFormModal: React.FC<ReviewFormModalProps> = ({
  isOpen,
  onClose,
  myReview,
  onSubmit,
  onUpdate,
  onDelete,
}) => {
  const [rating, setRating] = useState<number>(0);
  const [hoverRating, setHoverRating] = useState<number>(0);
  const [content, setContent] = useState<string>('');
  const [existingImages, setExistingImages] = useState<ReviewImage[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);
  
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewUrlsRef = useRef<string[]>([]);

  const clearPreviewUrls = useCallback(() => {
    previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    previewUrlsRef.current = [];
    setPreviewUrls([]);
  }, []);

  useEffect(() => {
    if (isOpen) {
      clearPreviewUrls();
      if (myReview) {
        setRating(myReview.rating);
        setContent(myReview.content);
        setExistingImages(myReview.images || []);
      } else {
        setRating(0);
        setContent('');
        setExistingImages([]);
      }
      setSelectedFiles([]);
      setErrorMessage(null);
    } else {
      clearPreviewUrls();
      setSelectedFiles([]);
    }
  }, [clearPreviewUrls, isOpen, myReview]);

  useEffect(() => {
    return () => previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    setErrorMessage(null);

    const allowedTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);
    const invalidType = files.find((file) => !allowedTypes.has(file.type));
    if (invalidType) {
      setErrorMessage(`Ảnh "${invalidType.name}" không đúng định dạng. Chỉ hỗ trợ JPG, PNG hoặc WebP.`);
      e.target.value = '';
      return;
    }

    const oversizedFile = files.find((file) => file.size > 3 * 1024 * 1024);
    if (oversizedFile) {
      setErrorMessage(`Ảnh "${oversizedFile.name}" vượt quá dung lượng tối đa 3MB.`);
      e.target.value = '';
      return;
    }

    const availableSlots = Math.max(0, 3 - existingImages.length - selectedFiles.length);
    if (availableSlots <= 0) {
      setErrorMessage('Mỗi feedback chỉ được đính kèm tối đa 3 ảnh.');
      e.target.value = '';
      return;
    }

    if (files.length > availableSlots) {
      setErrorMessage(`Chỉ còn ${availableSlots} vị trí ảnh. Hệ thống đã chọn ${availableSlots} ảnh đầu tiên.`);
    }

    const addedFiles = files.slice(0, availableSlots);
    const combinedFiles = [...selectedFiles, ...addedFiles];
    setSelectedFiles(combinedFiles);

    const newPreviews = addedFiles.map((file) => URL.createObjectURL(file));
    setPreviewUrls((prev) => {
      const next = [...prev, ...newPreviews];
      previewUrlsRef.current = next;
      return next;
    });

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeSelectedFile = (index: number) => {
    const newFiles = selectedFiles.filter((_, i) => i !== index);
    setSelectedFiles(newFiles);

    if (previewUrls[index]) URL.revokeObjectURL(previewUrls[index]);
    const newPreviews = previewUrls.filter((_, i) => i !== index);
    previewUrlsRef.current = newPreviews;
    setPreviewUrls(newPreviews);
  };

  const removeExistingImage = (imageId: number) => {
    setExistingImages((prev) => prev.filter((img) => img.id !== imageId));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!rating || rating < 1 || rating > 5) {
      setErrorMessage('Vui lòng chọn số sao đánh giá (1 đến 5 sao).');
      return;
    }

    const trimmedContent = content.trim();
    if (trimmedContent.length > 1000) {
      setErrorMessage(`Nội dung đánh giá vượt quá 1000 ký tự (hiện có: ${trimmedContent.length} ký tự).`);
      return;
    }

    try {
      setIsSubmitting(true);
      let res;
      if (myReview) {
        const keepIds = existingImages.map((img) => img.id);
        res = await onUpdate(rating, trimmedContent, selectedFiles, keepIds);
      } else {
        res = await onSubmit(rating, trimmedContent, selectedFiles);
      }

      if (res.success) {
        toast.success('Thành công', res.msg);
        clearPreviewUrls();
        onClose();
      } else {
        setErrorMessage(res.msg);
      }
    } catch {
      setErrorMessage('Không thể gửi đánh giá lúc này. Vui lòng thử lại.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    try {
      setIsDeleting(true);
      setErrorMessage(null);
      const res = await onDelete();
      if (res.success) {
        toast.success('Thành công', res.msg);
        clearPreviewUrls();
        onClose();
      } else {
        setErrorMessage(res.msg);
      }
    } catch {
      setErrorMessage('Không thể xóa đánh giá lúc này. Vui lòng thử lại.');
    } finally {
      setIsDeleting(false);
      setShowConfirmDelete(false);
    }
  };

  const currentStatusText = myReview
    ? {
        pending: 'Đang đồng bộ công khai',
        approved: 'Đang hiển thị công khai',
        rejected: 'Đã bị gỡ (dữ liệu cũ)',
        hidden: 'Tạm ẩn',
      }[myReview.status] || myReview.status
    : null;

  return (
    <>
      <ModalPortal
        isOpen={isOpen}
        onClose={onClose}
        dismissible={!isSubmitting && !isDeleting && !showConfirmDelete}
        className="max-w-2xl max-h-[calc(100dvh-2rem)] sm:max-h-[90dvh]"
        ariaLabelledBy="review-modal-title"
      >
        <div className="flex flex-col h-full overflow-hidden">
          {/* Header */}
          <div className="px-4 py-4 sm:px-6 sm:py-5 border-b border-zinc-200 dark:border-zinc-800 shrink-0">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting || isDeleting || showConfirmDelete}
              className="absolute top-3 right-3 flex h-11 w-11 items-center justify-center rounded-full text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 sm:top-4 sm:right-4"
              aria-label="Đóng"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <h3 id="review-modal-title" className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 pr-8">
              <span className="text-amber-500">★</span>
              {myReview ? 'Chỉnh sửa đánh giá của bạn' : 'Viết đánh giá trải nghiệm'}
            </h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              Chia sẻ đánh giá thực tế của bạn sau khi hoàn tất nâng cấp tài khoản Locket Gold.
            </p>
          </div>

          {/* Body */}
          <div className="p-4 sm:p-6 overflow-y-auto grow">
            {myReview && (
              <div className="mb-5 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-zinc-700 dark:text-zinc-300 flex flex-col gap-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-amber-600 dark:text-amber-400">Trạng thái hiện tại:</span>
                  <span className="font-medium px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-300">
                    {currentStatusText}
                  </span>
                </div>
                {myReview.status === 'rejected' && myReview.admin_note && (
                  <div className="mt-1 text-red-600 dark:text-red-400 font-medium">
                    Lý do từ chối: {myReview.admin_note}
                  </div>
                )}
                <div className="text-[11px] text-zinc-500 dark:text-zinc-400">
                  * Thay đổi của bạn sẽ được cập nhật công khai ngay sau khi lưu.
                </div>
              </div>
            )}

            <form id="review-form" onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 dark:text-zinc-400 mb-2">
                  Mức độ hài lòng của bạn <span className="text-red-500">*</span>
                </label>
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="flex items-center gap-0.5 sm:gap-1.5" role="radiogroup" aria-label="Đánh giá số sao">
                    {[1, 2, 3, 4, 5].map((star) => {
                      const isFilled = (hoverRating || rating) >= star;
                      return (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setRating(star)}
                          onMouseEnter={() => setHoverRating(star)}
                          onMouseLeave={() => setHoverRating(0)}
                          className="p-1.5 min-w-[44px] min-h-[44px] rounded flex items-center justify-center transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-amber-400 touch-manipulation"
                          aria-label={`${star} sao`}
                          role="radio"
                          aria-checked={rating === star}
                        >
                          <svg
                            className={`w-8 h-8 transition-colors ${isFilled ? 'text-amber-400 fill-amber-400' : 'text-zinc-300 dark:text-zinc-700 fill-transparent stroke-zinc-400 dark:stroke-zinc-600 stroke-[1.5]'}`}
                            viewBox="0 0 20 20"
                            fill="currentColor"
                          >
                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                          </svg>
                        </button>
                      );
                    })}
                  </div>
                  <span className="text-sm font-semibold text-amber-500 ml-2">
                    {rating > 0 ? `${rating} / 5 sao` : 'Vui lòng chọn sao'}
                  </span>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label htmlFor="review-content" className="text-xs font-semibold uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
                    Nội dung đánh giá <span className="font-normal normal-case text-zinc-400">(tùy chọn)</span>
                  </label>
                  <span className="text-xs font-mono text-zinc-400">
                    {content.trim().length} / 1000
                  </span>
                </div>
                <textarea
                  id="review-content"
                  rows={4}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Chia sẻ chi tiết về thời gian kích hoạt, trải nghiệm sử dụng Locket Gold, các tính năng bạn yêu thích..."
                  className="w-full rounded-xl p-3 text-sm bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all"
                  maxLength={1000}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
                    Ảnh đính kèm (Tùy chọn)
                  </label>
                  <span className="text-xs font-mono text-zinc-400">
                    {existingImages.length + selectedFiles.length} / 3
                  </span>
                </div>

                <div className="flex flex-wrap gap-3">
                  {existingImages.map((img) => (
                    <div key={`existing-${img.id}`} className="relative w-20 h-20 rounded-xl overflow-hidden border border-amber-500/40 bg-zinc-100 dark:bg-zinc-800 group">
                      <AuthenticatedReviewImage
                        src={img.url}
                        alt={img.original_filename || 'Ảnh hiện tại'}
                        className="w-full h-full object-contain p-0.5"
                      />
                      <div className="absolute top-0 left-0 right-0 bg-amber-500/80 text-[9px] font-bold text-zinc-950 text-center py-0.5">
                        Ảnh cũ
                      </div>
                      <button
                        type="button"
                        onClick={() => removeExistingImage(img.id)}
                        className="absolute inset-0 bg-black/50 text-white flex items-center justify-center sm:opacity-0 sm:group-hover:opacity-100 transition-opacity min-w-[44px] min-h-[44px] touch-manipulation"
                        title="Xóa ảnh này"
                      >
                        <svg className="w-6 h-6 sm:w-5 sm:h-5 drop-shadow-md" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}

                  {previewUrls.map((url, idx) => (
                    <div key={`new-${idx}`} className="relative w-20 h-20 rounded-xl overflow-hidden border border-emerald-500/40 bg-zinc-100 dark:bg-zinc-800 group">
                      <img src={url} alt={`Ảnh mới ${idx + 1}`} className="w-full h-full object-contain p-0.5" />
                      <div className="absolute top-0 left-0 right-0 bg-emerald-500/80 text-[9px] font-bold text-zinc-950 text-center py-0.5">
                        Ảnh mới
                      </div>
                      <button
                        type="button"
                        onClick={() => removeSelectedFile(idx)}
                        className="absolute inset-0 bg-black/50 text-white flex items-center justify-center sm:opacity-0 sm:group-hover:opacity-100 transition-opacity min-w-[44px] min-h-[44px] touch-manipulation"
                        title="Xóa ảnh này"
                      >
                        <svg className="w-6 h-6 sm:w-5 sm:h-5 drop-shadow-md" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}

                  {existingImages.length + selectedFiles.length < 3 && (
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="w-20 h-20 rounded-xl border-2 border-dashed border-zinc-300 dark:border-zinc-700 hover:border-amber-500 focus:border-amber-500 flex flex-col items-center justify-center text-zinc-400 hover:text-amber-500 transition-colors min-w-[44px] min-h-[44px]"
                    >
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                      </svg>
                      <span className="text-[10px] mt-1 font-medium">Thêm ảnh</span>
                    </button>
                  )}
                  
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple
                    className="hidden"
                    onChange={handleFileChange}
                  />
                </div>
              </div>

              {errorMessage && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400 font-medium">
                  {errorMessage}
                </div>
              )}
            </form>
          </div>

          {/* Footer Actions */}
          <div className="px-4 py-4 sm:px-6 border-t border-zinc-200 dark:border-zinc-800 shrink-0 bg-zinc-50 dark:bg-zinc-900/50 flex flex-col-reverse sm:flex-row items-center justify-between gap-3">
            {myReview ? (
              <button
                type="button"
                onClick={() => setShowConfirmDelete(true)}
                disabled={isSubmitting || isDeleting}
                className="w-full sm:w-auto min-h-[44px] px-4 py-2 rounded-xl text-sm font-semibold text-red-500 hover:bg-red-500/10 border border-red-500/20 sm:border-transparent sm:hover:border-red-500/20 transition-colors disabled:opacity-50"
              >
                Xóa đánh giá
              </button>
            ) : (
              <div className="hidden sm:block" />
            )}

            <div className="flex w-full sm:w-auto gap-3">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting || isDeleting}
                className="flex-1 sm:flex-none min-h-[44px] px-5 py-2 rounded-xl text-sm font-semibold text-zinc-600 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors"
              >
                Hủy
              </button>
              <button
                type="submit"
                form="review-form"
                disabled={isSubmitting || isDeleting}
                className="flex-1 sm:flex-none min-h-[44px] px-6 py-2 rounded-xl text-sm font-bold bg-gradient-to-r from-amber-400 to-amber-500 text-zinc-950 hover:brightness-105 shadow-md shadow-amber-500/20 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <span>Đang gửi...</span>
                  </>
                ) : (
                  <span>{myReview ? 'Cập nhật' : 'Gửi đánh giá'}</span>
                )}
              </button>
            </div>
          </div>
        </div>
      </ModalPortal>

      <ConfirmDialog
        isOpen={showConfirmDelete}
        title="Xóa đánh giá"
        message="Bạn có chắc chắn muốn xóa đánh giá của mình không? Hành động này không thể hoàn tác."
        confirmText="Xóa đánh giá"
        isConfirming={isDeleting}
        onConfirm={handleDelete}
        onCancel={() => setShowConfirmDelete(false)}
      />
    </>
  );
};
