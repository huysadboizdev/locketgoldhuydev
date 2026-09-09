import React, { useId } from 'react';
import { X } from 'lucide-react';
import { ModalPortal } from '../common/ModalPortal';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '4xl';
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = 'lg',
}) => {
  const titleId = `admin-modal-${useId().replace(/:/g, '')}`;
  const maxWidthClass = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '4xl': 'max-w-4xl',
  }[maxWidth];

  return (
    <ModalPortal
      isOpen={isOpen}
      onClose={onClose}
      ariaLabelledBy={titleId}
      overlayClassName="admin-shell"
      backdropClassName="bg-zinc-950/55 backdrop-blur-sm dark:bg-black/70"
      className={`${maxWidthClass} !rounded-3xl !border !border-zinc-200 !bg-white/98 !text-zinc-900 shadow-2xl backdrop-blur-md dark:!border-zinc-800 dark:!bg-zinc-900/95 dark:!text-zinc-100`}
    >
      <div className="flex min-h-0 flex-col p-4 sm:p-6">
        <div className="mb-4 flex shrink-0 items-center justify-between border-b border-zinc-200 pb-4 dark:border-zinc-800">
          <h3 id={titleId} className="text-base font-bold text-zinc-950 dark:text-zinc-100 sm:text-lg">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="flex h-11 w-11 items-center justify-center rounded-xl text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-950 focus:outline-none focus:ring-2 focus:ring-amber-500 dark:text-zinc-400 dark:hover:bg-zinc-800/80 dark:hover:text-zinc-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="min-h-0 overflow-y-auto pr-1">{children}</div>
      </div>
    </ModalPortal>
  );
};
