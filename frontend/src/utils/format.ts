/**
 * Ẩn danh username dạng h****
 */
export function maskUsername(name: string): string {
  if (!name) return '—';
  const s = String(name).trim();
  if (s.length <= 1) return s + '***';
  const stars = '*'.repeat(Math.min(4, Math.max(0, s.length - 1)));
  return s[0] + stars;
}

/**
 * Chuyển số giây thành chuỗi thời gian dễ đọc (e.g. 45s, 2p 30s)
 */
export function formatWaitTime(seconds: number): string {
  if (seconds <= 0) return '0s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}p ${s}s` : `${m}p`;
}

/**
 * Định dạng thời gian tương đối từ timestamp ISO
 */
export function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return 'Vừa xong';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSec < 60) return 'Vừa xong';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} phút trước`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} giờ trước`;
    return `${Math.floor(diffSec / 86400)} ngày trước`;
  } catch {
    return 'Vừa xong';
  }
}
