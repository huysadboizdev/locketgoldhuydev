import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useSiteSettings } from '../../hooks/useSiteSettings';
import { useAuth } from '../../hooks/useAuth';
import type { AnnouncementPopup } from '../../types/api';
import { AnnouncementDialog } from './AnnouncementDialog';
import { useToast } from '../../hooks/useToast';
import { useOverlay } from '../../context/OverlayContext';

const POPUP_STORAGE_PREFIX = 'locket_popup_dismissed_v';
const POPUP_SNOOZE_PREFIX = 'locket_popup_snoozed_until_v';
const TWO_HOURS_MS = 2 * 60 * 60 * 1000;

// Safe route matcher supporting exact match, wildcards, and path prefixes
function matchesRoute(currentPath: string, routes?: string[]): boolean {
  if (!routes || routes.length === 0 || routes.includes('*')) {
    return true;
  }
  return routes.some((routePattern) => {
    const p = routePattern.trim();
    if (!p || p === '*') return true;
    if (p === currentPath) return true;
    if (p.endsWith('/*')) {
      const base = p.slice(0, -2);
      return currentPath === base || currentPath.startsWith(base + '/');
    }
    if (p.endsWith('*')) {
      const base = p.slice(0, -1);
      return currentPath.startsWith(base);
    }
    return currentPath === p;
  });
}

export const GlobalAnnouncementPopup: React.FC = () => {
  const { settings } = useSiteSettings();
  const { isAuthenticated } = useAuth();
  const { hasAuthToast } = useToast();
  const { hasBlockingDialog } = useOverlay();
  const location = useLocation();

  const popup = settings?.popup as AnnouncementPopup | undefined;
  const [isDismissedInSession, setIsDismissedInSession] = useState(false);
  const [readyToShow, setReadyToShow] = useState(false);
  const [snoozedUntil, setSnoozedUntil] = useState(0);

  const versionKey = useMemo(() => {
    const version = popup?.version || 1;
    return `${POPUP_STORAGE_PREFIX}${version}`;
  }, [popup?.version]);

  const snoozeKey = useMemo(() => {
    const version = popup?.version || 1;
    return `${POPUP_SNOOZE_PREFIX}${version}`;
  }, [popup?.version]);

  useEffect(() => {
    setIsDismissedInSession(false);
  }, [versionKey]);

  useEffect(() => {
    try {
      const storedValue = Number(localStorage.getItem(snoozeKey) || 0);
      const activeUntil = Number.isFinite(storedValue) && storedValue > Date.now() ? storedValue : 0;
      setSnoozedUntil(activeUntil);
      if (!activeUntil) localStorage.removeItem(snoozeKey);
    } catch {
      setSnoozedUntil(0);
    }
  }, [snoozeKey]);

  useEffect(() => {
    if (!snoozedUntil) return;
    const remaining = snoozedUntil - Date.now();
    if (remaining <= 0) {
      setSnoozedUntil(0);
      try { localStorage.removeItem(snoozeKey); } catch { /* Ignore unavailable storage. */ }
      return;
    }
    const timer = window.setTimeout(() => {
      setSnoozedUntil(0);
      try { localStorage.removeItem(snoozeKey); } catch { /* Ignore unavailable storage. */ }
    }, remaining);
    return () => window.clearTimeout(timer);
  }, [snoozeKey, snoozedUntil]);

  useEffect(() => {
    if (popup?.display_mode === 'every_visit') {
      setIsDismissedInSession(false);
    }
  }, [location.pathname, popup?.display_mode]);

  // Check if popup should be shown based on all criteria
  const isVisible = useMemo(() => {
    if (!popup || !popup.enabled) {
      return false;
    }

    if (popup.active === false) {
      return false;
    }

    if (snoozedUntil > Date.now()) {
      return false;
    }

    const now = Date.now();
    if (popup.start_at) {
      const startMs = new Date(popup.start_at).getTime();
      if (!isNaN(startMs) && now < startMs) return false;
    }
    if (popup.end_at) {
      const endMs = new Date(popup.end_at).getTime();
      if (!isNaN(endMs) && now > endMs) return false;
    }

    const audience = popup.audience || 'all';
    if (audience === 'guests' && isAuthenticated) {
      return false;
    }
    if (audience === 'logged_in' && !isAuthenticated) {
      return false;
    }

    if (!matchesRoute(location.pathname, popup.routes)) {
      return false;
    }

    const mode = popup.display_mode || 'once_per_session';
    if (mode === 'once_per_version') {
      try {
        if (localStorage.getItem(versionKey) === 'true') {
          return false;
        }
      } catch (e) {}
    } else if (mode === 'once_per_session') {
      try {
        if (sessionStorage.getItem(versionKey) === 'true') {
          return false;
        }
      } catch (e) {}
    }

    if (isDismissedInSession) {
      return false;
    }

    return true;
  }, [popup, isAuthenticated, location.pathname, versionKey, isDismissedInSession, snoozedUntil]);

  // Auth feedback and transactional dialogs always have priority over announcements.
  useEffect(() => {
    if (isVisible && !hasAuthToast && !hasBlockingDialog) {
      const timer = setTimeout(() => {
        setReadyToShow(true);
      }, 250);
      return () => clearTimeout(timer);
    } else {
      setReadyToShow(false);
    }
  }, [hasAuthToast, hasBlockingDialog, isVisible]);

  const handleDismiss = useCallback(() => {
    if (!popup || popup.dismissible === false) return;

    setIsDismissedInSession(true);
    const mode = popup.display_mode || 'once_per_session';

    try {
      if (mode === 'once_per_version') {
        localStorage.setItem(versionKey, 'true');
      } else if (mode === 'once_per_session') {
        sessionStorage.setItem(versionKey, 'true');
      }
    } catch (e) {}
  }, [popup, versionKey]);

  const handleSnooze = useCallback(() => {
    const until = Date.now() + TWO_HOURS_MS;
    setSnoozedUntil(until);
    setReadyToShow(false);
    try {
      localStorage.setItem(snoozeKey, String(until));
    } catch {
      // State still keeps the popup hidden for this page lifetime.
    }
  }, [snoozeKey]);

  if (!readyToShow || !isVisible || !popup) {
    return null;
  }

  return (
    <AnnouncementDialog
      isOpen={true}
      onClose={handleDismiss}
      title={popup.title}
      message={popup.message || popup.content || ''}
      icon={popup.icon}
      buttonText={popup.button_text}
      buttonUrl={popup.button_url || popup.button_link}
      dismissible={popup.dismissible !== false}
      layerKind="announcement"
      onSnooze={popup.dismissible !== false ? handleSnooze : undefined}
    />
  );
};
