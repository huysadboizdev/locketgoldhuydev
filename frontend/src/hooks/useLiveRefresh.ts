import { useEffect, useRef } from 'react';

/**
 * Runs a quiet refresh while the page is visible and immediately catches up
 * after the tab regains focus or the browser comes back online.
 */
export function useLiveRefresh(
  refresh: () => void | Promise<void>,
  intervalMs = 10_000,
  enabled = true
) {
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;

    let inFlight = false;
    const run = async () => {
      if (
        inFlight ||
        document.visibilityState !== 'visible' ||
        (typeof navigator !== 'undefined' && navigator.onLine === false)
      ) {
        return;
      }

      inFlight = true;
      try {
        await refreshRef.current();
      } catch {
        // Background refresh failures are non-blocking; the next tick retries.
      } finally {
        inFlight = false;
      }
    };

    const intervalId = window.setInterval(() => void run(), intervalMs);
    const handleVisible = () => {
      if (document.visibilityState === 'visible') void run();
    };
    const handleFocus = () => void run();

    document.addEventListener('visibilitychange', handleVisible);
    window.addEventListener('focus', handleFocus);
    window.addEventListener('online', handleFocus);

    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisible);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('online', handleFocus);
    };
  }, [enabled, intervalMs]);
}
