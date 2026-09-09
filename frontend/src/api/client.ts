export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  _retry?: boolean;
}

// In-memory access token storage — STRICTLY in memory, never in localStorage/sessionStorage/cookies
let inMemoryAccessToken: string | null = null;

export function setAccessToken(token: string | null) {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

// CSRF token storage
let currentCsrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  currentCsrfToken = token;
}

export function getCsrfToken(): string | null {
  return currentCsrfToken;
}

// Auth callbacks (to notify AuthContext to update or clear state)
type AuthFailureHandler = () => void;
type AuthSuccessHandler = (token: string, user?: any) => void;

let onAuthFailure: AuthFailureHandler | null = null;
let onAuthSuccess: AuthSuccessHandler | null = null;

export function setAuthFailureHandler(handler: AuthFailureHandler | null) {
  onAuthFailure = handler;
}

export function setAuthSuccessHandler(handler: AuthSuccessHandler | null) {
  onAuthSuccess = handler;
}

// Single-flight refresh token mutex (In-tab promise + Cross-tab Web Locks)
let refreshPromise: Promise<string | null> | null = null;

async function executeRefreshNetworkCall(): Promise<string | null> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
  if (currentCsrfToken) {
    headers['X-CSRF-Token'] = currentCsrfToken;
  }

  try {
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers,
      credentials: 'include',
    });

    let data: any = null;
    try {
      data = await response.json();
    } catch {
      // Non-JSON response
    }

    if (!response.ok) {
      // If 401 or 403, the session is explicitly invalid or revoked
      if (response.status === 401 || response.status === 403) {
        setAccessToken(null);
        if (onAuthFailure) {
          onAuthFailure();
        }
      }
      return null;
    }

    if (data && data.success && data.access_token) {
      setAccessToken(data.access_token);
      if (data.csrf_token) {
        setCsrfToken(data.csrf_token);
      }
      if (onAuthSuccess) {
        onAuthSuccess(data.access_token, data.user);
      }
      return data.access_token as string;
    } else {
      setAccessToken(null);
      if (onAuthFailure) {
        onAuthFailure();
      }
      return null;
    }
  } catch {
    // Network errors (offline, dropouts): DO NOT clear state as revoked
    return null;
  }
}

export async function requestTokenRefresh(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      // Cross-tab coordination via Web Locks API (if supported)
      if (typeof navigator !== 'undefined' && 'locks' in navigator && navigator.locks?.request) {
        return await navigator.locks.request('locket-auth-refresh', { mode: 'exclusive' }, async () => {
          return await executeRefreshNetworkCall();
        });
      } else {
        return await executeRefreshNetworkCall();
      }
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function apiClient<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 20000, headers = {}, method = 'GET', _retry = false, ...rest } = options;

  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);

  const isFormData = typeof FormData !== 'undefined' && rest.body instanceof FormData;

  const requestHeaders: Record<string, string> = {
    'Accept': 'application/json',
    ...(headers as Record<string, string>),
  };

  if (!isFormData && !requestHeaders['Content-Type']) {
    requestHeaders['Content-Type'] = 'application/json';
  }


  // Tự động gắn Access Token dạng Bearer nếu có trong bộ nhớ
  if (inMemoryAccessToken && !requestHeaders['Authorization']) {
    requestHeaders['Authorization'] = `Bearer ${inMemoryAccessToken}`;
  }

  // Tự động gắn CSRF token cho các request làm thay đổi dữ liệu
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method.toUpperCase())) {
    if (currentCsrfToken && !requestHeaders['X-CSRF-Token']) {
      requestHeaders['X-CSRF-Token'] = currentCsrfToken;
    }
  }

  try {
    const response = await fetch(url, {
      ...rest,
      method,
      credentials: 'include', // Đảm bảo cookie phiên HttpOnly (refresh token) được gửi kèm
      headers: requestHeaders,
      signal: controller.signal,
    });

    clearTimeout(id);

    // Xử lý status code
    let data: any = null;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      data = { raw: text };
    }

    // Tự động cập nhật CSRF token nếu server trả về trong body
    if (data && typeof data === 'object' && data.csrf_token) {
      setCsrfToken(data.csrf_token);
    }

    // Single-flight refresh token mutex khi access token hết hạn
    const isTokenExpired = response.status === 401 && data?.error === 'access_token_expired';
    const isAuthEndpoint = url.includes('/api/auth/login') ||
                           url.includes('/api/auth/register') ||
                           url.includes('/api/auth/refresh');

    if (isTokenExpired && !_retry && !isAuthEndpoint) {
      const newAccessToken = await requestTokenRefresh();
      if (newAccessToken) {
        return apiClient<T>(url, {
          ...options,
          _retry: true,
          headers: {
            ...headers,
            'Authorization': `Bearer ${newAccessToken}`,
          },
        });
      }
    }

    if (!response.ok) {
      const errorMsg = data?.msg || data?.error || `Request failed with status ${response.status}`;
      throw new ApiError(errorMsg, response.status, data);
    }

    return data as T;
  } catch (err: any) {
    clearTimeout(id);
    if (err.name === 'AbortError') {
      throw new ApiError('Yêu cầu hết thời gian chờ (Timeout). Vui lòng thử lại.', 408);
    }
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(err.message || 'Lỗi kết nối máy chủ.', 0);
  }
}
