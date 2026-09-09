import { useEffect, useRef, useState, useCallback } from 'react';
import { fetchPaymentStatus } from '../api/endpoints';
import type { PaymentOrder, PaymentStatus, ActivationOrder } from '../types/api';

interface UsePaymentPollingOptions {
  paymentCode?: string | null;
  paymentRef?: string | null;
  currentStatus?: PaymentStatus;
  enabled?: boolean;
  onSuccess?: (payment: PaymentOrder, activationOrder?: ActivationOrder | null) => void;
  onStatusChange?: (status: PaymentStatus, payment: PaymentOrder, activationOrder?: ActivationOrder | null) => void;
  onError?: (err: any) => void;
}

export function usePaymentPolling({
  paymentCode,
  paymentRef,
  currentStatus = 'pending',
  enabled = true,
  onSuccess,
  onStatusChange,
  onError,
}: UsePaymentPollingOptions) {
  const code = paymentRef || paymentCode;
  const [status, setStatus] = useState<PaymentStatus>(currentStatus);
  const isFetchingRef = useRef<boolean>(false);
  const onStatusChangeRef = useRef(onStatusChange);
  onStatusChangeRef.current = onStatusChange;
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  useEffect(() => {
    setStatus(currentStatus);
  }, [code, currentStatus]);

  const checkStatus = useCallback(async (): Promise<PaymentStatus | null> => {
    if (!code || isFetchingRef.current) return null;
    isFetchingRef.current = true;

    try {
      const res = await fetchPaymentStatus(code);
      if (res && res.success && res.payment) {
        const newStatus = res.payment.status;
        setStatus(newStatus);
        if (onStatusChangeRef.current) {
          onStatusChangeRef.current(newStatus, res.payment, res.activation_order);
        }
        if (newStatus === 'paid' && onSuccessRef.current) {
          onSuccessRef.current(res.payment, res.activation_order);
        }
        return newStatus;
      }
    } catch (err) {
      if (onErrorRef.current) {
        onErrorRef.current(err);
      }
    } finally {
      isFetchingRef.current = false;
    }
    return null;
  }, [code]);

  useEffect(() => {
    if (!enabled || !code || status !== 'pending') {
      return;
    }

    if (document.visibilityState === 'visible') {
      void checkStatus();
    }

    const intervalMs = 3000;
    const intervalId = setInterval(() => {
      if (document.visibilityState === 'visible') {
        checkStatus();
      }
    }, intervalMs);

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        checkStatus();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [enabled, code, status, checkStatus]);

  return {
    status,
    refetchStatus: checkStatus,
  };
}
