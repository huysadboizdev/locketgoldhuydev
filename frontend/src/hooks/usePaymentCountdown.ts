import { useState, useEffect, useRef, useCallback } from 'react';

interface UsePaymentCountdownOptions {
  expiresAt?: number | null;
  serverTime?: number | null;
  totalDurationSeconds?: number;
  onExpire?: () => void;
}

interface UsePaymentCountdownResult {
  secondsLeft: number;
  formattedTime: string;
  progressPercent: number;
  isExpired: boolean;
}

export function usePaymentCountdown({
  expiresAt,
  serverTime,
  totalDurationSeconds = 600,
  onExpire,
}: UsePaymentCountdownOptions): UsePaymentCountdownResult {
  // Compute skew between server time and local device clock
  const skewMsRef = useRef<number>(0);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    if (serverTime && serverTime > 0) {
      // serverTime is in seconds, Date.now() is ms
      skewMsRef.current = serverTime * 1000 - Date.now();
    } else {
      skewMsRef.current = 0;
    }
  }, [serverTime]);

  const computeRemaining = useCallback((): number => {
    if (!expiresAt || expiresAt <= 0) return 0;
    const nowSynced = Date.now() + skewMsRef.current;
    const remainingMs = expiresAt * 1000 - nowSynced;
    return Math.max(0, Math.floor(remainingMs / 1000));
  }, [expiresAt]);

  const [secondsLeft, setSecondsLeft] = useState<number>(() => computeRemaining());
  const hasTriggeredExpireRef = useRef<boolean>(false);

  // Reset trigger flag when expiresAt changes
  useEffect(() => {
    hasTriggeredExpireRef.current = false;
    setSecondsLeft(computeRemaining());
  }, [expiresAt, computeRemaining]);

  useEffect(() => {
    if (!expiresAt || expiresAt <= 0) {
      setSecondsLeft(0);
      return;
    }

    const tick = () => {
      const rem = computeRemaining();
      setSecondsLeft(rem);
      if (rem <= 0 && !hasTriggeredExpireRef.current) {
        hasTriggeredExpireRef.current = true;
        if (onExpireRef.current) {
          onExpireRef.current();
        }
      }
    };

    // Initial check
    tick();

    const interval = setInterval(tick, 1000);

    // Sync on tab visibility change (foreground wakeup)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        tick();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [expiresAt, computeRemaining]);

  const minutes = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;
  const formattedTime = `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  const progressPercent = Math.min(100, Math.max(0, (secondsLeft / totalDurationSeconds) * 100));
  const isExpired = secondsLeft <= 0;

  return {
    secondsLeft,
    formattedTime,
    progressPercent,
    isExpired,
  };
}
