import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface AdminPaginationProps {
  page: number;
  pages: number;
  total: number;
  pageSize?: number;
  itemLabel?: string;
  onPageChange: (page: number) => void;
}

export const ADMIN_PAGE_SIZE = 10;

export const AdminPagination: React.FC<AdminPaginationProps> = ({
  page,
  pages,
  total,
  pageSize = ADMIN_PAGE_SIZE,
  itemLabel = 'mục',
  onPageChange,
}) => {
  const safePages = Math.max(1, pages);
  const safePage = Math.min(Math.max(1, page), safePages);
  const from = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const to = Math.min(total, safePage * pageSize);

  return (
    <div className="flex flex-col gap-3 border-t border-zinc-200 bg-zinc-50/80 px-4 py-3 text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950/30 dark:text-zinc-400 sm:flex-row sm:items-center sm:justify-between">
      <span>
        Hiển thị <strong className="text-zinc-800 dark:text-zinc-200">{from}–{to}</strong> / {total} {itemLabel}
        <span className="ml-1">(Trang {safePage}/{safePages})</span>
      </span>
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          aria-label="Trang trước"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-zinc-300 bg-white text-zinc-700 transition hover:border-amber-400 hover:text-amber-700 disabled:cursor-not-allowed disabled:opacity-35 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="flex h-9 min-w-9 items-center justify-center rounded-xl bg-amber-500 px-2 font-bold text-zinc-950">{safePage}</span>
        <button
          type="button"
          aria-label="Trang sau"
          disabled={safePage >= safePages}
          onClick={() => onPageChange(safePage + 1)}
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-zinc-300 bg-white text-zinc-700 transition hover:border-amber-400 hover:text-amber-700 disabled:cursor-not-allowed disabled:opacity-35 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
