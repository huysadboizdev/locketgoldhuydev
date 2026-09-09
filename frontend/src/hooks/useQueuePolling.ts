import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchQueueStatus, fetchMyActiveQueue } from '../api/endpoints';
import { useAuth } from './useAuth';
import type { DevicePlatform, QueueItemStatus, QueueStatusResponse } from '../types/api';

const STORAGE_KEY = 'locket_queue_session';

interface StoredSession {
  clientId: string;
  username: string;
  platform?: DevicePlatform;
  createdAt: number;
}

export function useQueuePolling() {
  const { isLoading, isAuthenticated, accessToken } = useAuth();

  const [clientId, setClientId] = useState<string | null>(null);
  const [targetUsername, setTargetUsername] = useState<string>('');
  const [platform, setPlatform] = useState<DevicePlatform | null>(null);
  const [status, setStatus] = useState<QueueItemStatus | 'idle'>('idle');
  const [position, setPosition] = useState<number>(0);
  const [totalQueue, setTotalQueue] = useState<number>(0);
  const [estimatedTime, setEstimatedTime] = useState<number>(0);
  const [result, setResult] = useState<{ success: boolean; msg?: string; [key: string]: any } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState<boolean>(false);

  const pollingTimerRef = useRef<any>(null);
  const hasLoggedPollingErrorRef = useRef<boolean>(false);

  const clearStorage = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  // Khôi phục phiên khi tải lại trang (Refresh Recovery)
  // Chỉ truy vấn /api/queue/my-active khi đã xác thực và có access token
  useEffect(() => {
    let isMounted = true;
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        const session: StoredSession = JSON.parse(raw);
        if (session && session.clientId) {
          setClientId(session.clientId);
          setTargetUsername(session.username || '');
          if (session.platform === 'ios' || session.platform === 'android') {
            setPlatform(session.platform);
          }
          setStatus('waiting');
          setIsOpen(true);
          return;
        }
      }
    } catch {
      sessionStorage.removeItem(STORAGE_KEY);
    }

    // Đợi auth bootstrap xong và xác thực hợp lệ mới gọi backend
    if (isLoading || !isAuthenticated || !accessToken) {
      return;
    }

    fetchMyActiveQueue()
      .then((res) => {
        if (!isMounted) return;
        if (res && res.success && res.active) {
          setClientId(res.active.client_id);
          setTargetUsername(res.active.username || '');
          if (res.active.platform === 'ios' || res.active.platform === 'android') {
            setPlatform(res.active.platform);
          }
          setStatus(res.active.status);
          setPosition(res.active.position || 1);
          setTotalQueue(res.active.total_queue || 1);
          setEstimatedTime(res.active.estimated_time || 5);
          setIsOpen(true);
        }
      })
      .catch(() => {
        // Bỏ qua lỗi nếu unauthenticated hoặc offline
      });

    return () => {
      isMounted = false;
    };
  }, [isLoading, isAuthenticated, accessToken]);

  // Dọn dẹp trạng thái hàng đợi khi người dùng đăng xuất
  useEffect(() => {
    if (!isAuthenticated) {
      setClientId(null);
      setPlatform(null);
      setStatus('idle');
      setPosition(0);
      setTotalQueue(0);
      setEstimatedTime(0);
      setResult(null);
      setError(null);
      setIsOpen(false);
      clearStorage();
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    }
  }, [isAuthenticated, clearStorage]);

  // Bắt đầu theo dõi một client_id mới
  const startQueue = useCallback((
    newClientId: string,
    username: string,
    newPlatform: DevicePlatform,
    initialPos: number = 1,
    initialTotal: number = 1,
    initialTime: number = 5
  ) => {
    setClientId(newClientId);
    setTargetUsername(username);
    setPlatform(newPlatform);
    setStatus('waiting');
    setPosition(initialPos);
    setTotalQueue(initialTotal);
    setEstimatedTime(initialTime);
    setResult(null);
    setError(null);
    setIsOpen(true);

    try {
      const sessionData: StoredSession = {
        clientId: newClientId,
        username,
        platform: newPlatform,
        createdAt: Date.now(),
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(sessionData));
    } catch {
      // Ignored
    }
  }, []);

  const closeQueue = useCallback(() => {
    setIsOpen(false);
  }, []);

  const resetQueue = useCallback(() => {
    setClientId(null);
    setPlatform(null);
    setStatus('idle');
    setPosition(0);
    setTotalQueue(0);
    setEstimatedTime(0);
    setResult(null);
    setError(null);
    setIsOpen(false);
    clearStorage();
  }, [clearStorage]);

  // Vòng lặp Polling: Điều chỉnh tần suất (waiting: 4s, processing: 2s) và tạm dừng khi tab ẩn
  useEffect(() => {
    if (!clientId || status === 'completed' || status === 'error' || status === 'not_found' || status === 'idle' || !isAuthenticated) {
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
      return;
    }

    let isMounted = true;
    let isPolling = false;

    const scheduleNext = () => {
      if (!isMounted) return;
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
      // Khi tab đang ẩn (document.hidden), tạm ngưng timer; visibilitychange sẽ kích hoạt lại
      if (typeof document !== 'undefined' && document.hidden) {
        return;
      }
      const delay = status === 'processing' ? 2000 : 4000;
      pollingTimerRef.current = setTimeout(poll, delay);
    };

    const poll = async () => {
      if (!isMounted || isPolling) return;
      if (typeof document !== 'undefined' && document.hidden) {
        return;
      }

      isPolling = true;
      try {
        const res: QueueStatusResponse = await fetchQueueStatus(clientId);
        if (!isMounted) return;

        setStatus(res.status);
        setPosition(res.position);
        setTotalQueue(res.total_queue);
        setEstimatedTime(res.estimated_time);

        if (res.platform === 'ios' || res.platform === 'android') {
          setPlatform(res.platform);
        }

        if (res.result) {
          setResult(res.result);
        }
        if (res.error) {
          setError(res.error);
        }

        // Dọn dẹp session khi đạt trạng thái kết thúc
        if (res.status === 'completed' || res.status === 'error' || res.status === 'not_found') {
          clearStorage();
          return;
        }
        hasLoggedPollingErrorRef.current = false;
      } catch (err: any) {
        if (!isMounted) return;
        if (err?.status === 404) {
          setStatus('not_found');
          setError(err.message || 'Yêu cầu không tồn tại hoặc không thuộc quyền sở hữu của bạn.');
          clearStorage();
          return;
        }
        if (!hasLoggedPollingErrorRef.current) {
          hasLoggedPollingErrorRef.current = true;
          console.warn('[QueuePolling] Backend tạm thời gián đoạn, tiếp tục thăm dò khi máy chủ phục hồi...');
        }
      } finally {
        isPolling = false;
        if (isMounted) {
          scheduleNext();
        }
      }
    };

    // Polling ngay lập tức lần đầu
    poll();

    // Page Visibility API: Tự động poll ngay lập tức khi người dùng quay lại tab
    const handleVisibilityChange = () => {
      if (typeof document !== 'undefined' && !document.hidden && isMounted) {
        poll();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMounted = false;
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [clientId, status, isAuthenticated, clearStorage]);

  return {
    clientId,
    targetUsername,
    platform,
    status,
    position,
    totalQueue,
    estimatedTime,
    result,
    error,
    isOpen,
    startQueue,
    closeQueue,
    resetQueue,
  };
}
