import { useState, useEffect, useCallback } from 'react';
import { fetchSiteSettings } from '../api/endpoints';
import type { SiteSettingsResponse } from '../types/api';

export function useSiteSettings() {
  const [settings, setSettings] = useState<SiteSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkSettings = useCallback(async () => {
    try {
      const res = await fetchSiteSettings();
      setSettings(res);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Không thể kết nối máy chủ');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSettings();
    const interval = setInterval(checkSettings, 10000);
    return () => clearInterval(interval);
  }, [checkSettings]);

  return {
    settings,
    isMaintenance: Boolean(settings?.maintenance_active),
    maintenanceMessage: settings?.maintenance?.message || 'Hệ thống đang bảo trì để nâng cấp máy chủ.',
    loading,
    error,
    isBackendOffline: Boolean(error) || (settings === null && !loading),
    retry: checkSettings,
  };
}
