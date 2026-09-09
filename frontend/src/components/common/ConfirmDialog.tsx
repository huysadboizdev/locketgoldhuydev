import React, { useId } from 'react';
import { ModalPortal } from './ModalPortal';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isConfirming?: boolean;
  isLoading?: boolean;
  isDanger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmText = 'Xác nhận',
  cancelText = 'Hủy',
  isConfirming = false,
  isLoading = false,
  isDanger = false,
  onConfirm,
  onCancel,
}) => {
  const loading = isConfirming || isLoading;
  const uniqueId = useId().replace(/:/g, '');
  const titleId = `confirm-dialog-title-${uniqueId}`;
  const messageId = `confirm-dialog-message-${uniqueId}`;
  return (
    <ModalPortal
      isOpen={isOpen}
      onClose={onCancel}
      dismissible={!loading}
      className="max-w-md"
      ariaLabelledBy={titleId}
      ariaDescribedBy={messageId}
    >
      <div className="p-6">
        <h3 id={titleId} className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-2">
          {title}
        </h3>
        <p id={messageId} className="text-sm text-zinc-600 dark:text-zinc-400 mb-6">
          {message}
        </p>
        <div className="flex flex-col-reverse justify-end gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="min-h-11 px-4 py-2 text-sm font-semibold text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-xl transition-colors disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`min-h-11 px-4 py-2 text-sm font-semibold text-white rounded-xl transition-colors disabled:opacity-50 flex items-center justify-center gap-2 ${isDanger ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-500 hover:bg-amber-600'}`}
          >
            {loading && (
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
            {confirmText}
          </button>
        </div>
      </div>
    </ModalPortal>
  );
};
