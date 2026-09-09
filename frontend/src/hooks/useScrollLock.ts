import { useEffect, useRef } from 'react';

const activeLocks = new Set<symbol>();
let originalOverflow = '';
let originalPaddingRight = '';

/** Locks body scrolling without losing track when dialogs are nested. */
export function useScrollLock(lock: boolean): void {
  const lockId = useRef(Symbol('scroll-lock'));

  useEffect(() => {
    if (!lock || typeof document === 'undefined') return;

    const id = lockId.current;
    if (activeLocks.has(id)) return;

    if (activeLocks.size === 0) {
      originalOverflow = document.body.style.overflow;
      originalPaddingRight = document.body.style.paddingRight;
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
      document.body.style.overflow = 'hidden';
      if (scrollbarWidth > 0) document.body.style.paddingRight = `${scrollbarWidth}px`;
      document.body.dataset.scrollLocked = 'true';
    }

    activeLocks.add(id);

    return () => {
      activeLocks.delete(id);
      if (activeLocks.size === 0) {
        document.body.style.overflow = originalOverflow;
        document.body.style.paddingRight = originalPaddingRight;
        delete document.body.dataset.scrollLocked;
      }
    };
  }, [lock]);
}
