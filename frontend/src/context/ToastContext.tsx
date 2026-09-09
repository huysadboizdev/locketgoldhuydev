import React, { createContext, useCallback, useMemo, useState } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';
export type ToastChannel = 'general' | 'auth';

export interface ToastOptions {
  duration?: number;
  dedupeKey?: string;
  channel?: ToastChannel;
}

export interface ToastMessage extends ToastOptions {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

type ToastInput = Omit<ToastMessage, 'id'> & { id?: string };

export interface ToastContextValue {
  toasts: ToastMessage[];
  hasAuthToast: boolean;
  showToast: (toast: ToastInput) => string;
  dismissToast: (id: string) => void;
  success: (title: string, message?: string, options?: ToastOptions) => string;
  error: (title: string, message?: string, options?: ToastOptions) => string;
  warning: (title: string, message?: string, options?: ToastOptions) => string;
  info: (title: string, message?: string, options?: ToastOptions) => string;
}

export const ToastContext = createContext<ToastContextValue | null>(null);

const MAX_QUEUED_TOASTS = 20;

export const ToastProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback((toast: ToastInput): string => {
    const id = toast.id || `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const nextToast: ToastMessage = {
      channel: 'general',
      duration: 4000,
      ...toast,
      id,
    };

    setToasts((current) => {
      const duplicate = current.some(
        (item) =>
          item.id === id ||
          (Boolean(nextToast.dedupeKey) && item.dedupeKey === nextToast.dedupeKey)
      );
      if (duplicate) return current;
      return [...current, nextToast].slice(-MAX_QUEUED_TOASTS);
    });
    return id;
  }, []);

  const createTypedHelper = useCallback(
    (type: ToastType, title: string, message?: string, options?: ToastOptions) =>
      showToast({ type, title, message, ...options }),
    [showToast]
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      toasts,
      hasAuthToast: toasts.some((toast) => toast.channel === 'auth'),
      showToast,
      dismissToast,
      success: (title, message, options) => createTypedHelper('success', title, message, options),
      error: (title, message, options) => createTypedHelper('error', title, message, options),
      warning: (title, message, options) => createTypedHelper('warning', title, message, options),
      info: (title, message, options) => createTypedHelper('info', title, message, options),
    }),
    [createTypedHelper, dismissToast, showToast, toasts]
  );

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
};
