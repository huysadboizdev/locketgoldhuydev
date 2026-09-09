import React, { useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import { useToast } from '../../hooks/useToast';
import type { ToastMessage, ToastType } from '../../context/ToastContext';

const MAX_VISIBLE_TOASTS = 3;

const variants: Record<ToastType, { card: string; icon: string; Icon: typeof Info }> = {
  success: {
    card: 'border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-50',
    icon: 'text-emerald-600 dark:text-emerald-400',
    Icon: CheckCircle2,
  },
  error: {
    card: 'border-red-200 bg-red-50 text-red-950 dark:border-red-800 dark:bg-red-950 dark:text-red-50',
    icon: 'text-red-600 dark:text-red-400',
    Icon: AlertCircle,
  },
  warning: {
    card: 'border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-50',
    icon: 'text-amber-600 dark:text-amber-400',
    Icon: AlertTriangle,
  },
  info: {
    card: 'border-sky-200 bg-sky-50 text-sky-950 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-50',
    icon: 'text-sky-600 dark:text-sky-400',
    Icon: Info,
  },
};

const ToastItem: React.FC<{ toast: ToastMessage; dismiss: (id: string) => void }> = ({
  toast,
  dismiss,
}) => {
  const duration = toast.duration ?? 4000;
  const remainingMs = useRef(duration);
  const startedAt = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const paused = useRef(false);

  const clearTimer = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const startTimer = useCallback(() => {
    if (duration === 0 || paused.current || remainingMs.current <= 0) return;
    clearTimer();
    startedAt.current = Date.now();
    timer.current = setTimeout(() => dismiss(toast.id), remainingMs.current);
  }, [clearTimer, dismiss, duration, toast.id]);

  const pauseTimer = useCallback(() => {
    if (duration === 0 || paused.current) return;
    paused.current = true;
    if (timer.current) {
      remainingMs.current = Math.max(0, remainingMs.current - (Date.now() - startedAt.current));
    }
    clearTimer();
  }, [clearTimer, duration]);

  const resumeTimer = useCallback(() => {
    if (!paused.current) return;
    paused.current = false;
    startTimer();
  }, [startTimer]);

  useEffect(() => {
    remainingMs.current = duration;
    startTimer();
    return clearTimer;
  }, [clearTimer, duration, startTimer]);

  const variant = variants[toast.type];
  const Icon = variant.Icon;

  return (
    <div
      role={toast.type === 'error' ? 'alert' : 'status'}
      data-toast-type={toast.type}
      onMouseEnter={pauseTimer}
      onMouseLeave={resumeTimer}
      onFocusCapture={pauseTimer}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) resumeTimer();
      }}
      className={`pointer-events-auto flex w-full items-start gap-3 rounded-2xl border p-3.5 shadow-xl sm:p-4 ${variant.card}`}
    >
      <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${variant.icon}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="break-words text-sm font-bold leading-5">{toast.title}</p>
        {toast.message && (
          <p className="mt-0.5 line-clamp-3 break-words text-sm leading-5 opacity-80">
            {toast.message}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={() => dismiss(toast.id)}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl opacity-60 transition hover:bg-black/5 hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-current dark:hover:bg-white/10"
        aria-label="Đóng thông báo"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
};

export const ToastViewport: React.FC = () => {
  const { toasts, dismissToast } = useToast();
  if (toasts.length === 0 || typeof document === 'undefined') return null;

  return createPortal(
    <div
      aria-live="polite"
      aria-relevant="additions removals"
      className="pointer-events-none fixed inset-x-3 top-3 z-[3000] flex flex-col gap-2 sm:inset-x-auto sm:right-4 sm:top-4 sm:w-[min(28rem,calc(100vw-2rem))]"
      style={{ marginTop: 'env(safe-area-inset-top)' }}
    >
      {toasts.slice(0, MAX_VISIBLE_TOASTS).map((toast) => (
        <ToastItem key={toast.id} toast={toast} dismiss={dismissToast} />
      ))}
    </div>,
    document.body
  );
};
