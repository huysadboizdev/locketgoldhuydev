import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import {
  fetchCsrfToken,
  loginApi,
  registerApi,
  logoutApi,
  loginWithGoogleApi,
} from '../api/endpoints';
import {
  setAccessToken as setClientAccessToken,
  setCsrfToken as setClientCsrfToken,
  setAuthFailureHandler,
  setAuthSuccessHandler,
  getCsrfToken as getClientCsrfToken,
  requestTokenRefresh,
} from '../api/client';
import type { AuthUser } from '../types/api';

interface AuthContextType {
  user: AuthUser | null;
  accessToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  csrfToken: string | null;
  login: (identifier: string, password: string, rememberMe?: boolean) => Promise<{ success: boolean; msg?: string; error?: string }>;
  loginWithGoogle: (credential: string) => Promise<{ success: boolean; msg?: string; error?: string }>;
  register: (data: { email: string; username: string; display_name?: string; password: string }) => Promise<{ success: boolean; msg?: string; error?: string }>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface BootstrapResult {
  accessToken: string | null;
  csrfToken: string | null;
}

// React StrictMode mounts effects twice in development. Keep bootstrap at
// module scope so both effect runs share one CSRF request and one refresh-token
// rotation instead of racing and triggering replay protection.
let bootstrapPromise: Promise<BootstrapResult> | null = null;

function requestAuthBootstrap(): Promise<BootstrapResult> {
  if (bootstrapPromise) {
    return bootstrapPromise;
  }

  bootstrapPromise = (async () => {
    try {
      const csrfResponse = await fetchCsrfToken();
      if (csrfResponse?.csrf_token) {
        setClientCsrfToken(csrfResponse.csrf_token);
      }
    } catch {
      // Refresh will fail safely when the backend is unavailable.
    }

    const token = await requestTokenRefresh();
    return {
      accessToken: token,
      csrfToken: getClientCsrfToken(),
    };
  })().finally(() => {
    bootstrapPromise = null;
  });

  return bootstrapPromise;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [csrfToken, setCsrfTokenState] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  // Sync token to client module
  const updateAccessToken = useCallback((token: string | null) => {
    setAccessTokenState(token);
    setClientAccessToken(token);
  }, []);

  const updateCsrfToken = useCallback((token: string | null) => {
    setCsrfTokenState(token);
    setClientCsrfToken(token);
  }, []);

  // Hook into client auth callbacks
  useEffect(() => {
    isMountedRef.current = true;
    setAuthFailureHandler(() => {
      if (isMountedRef.current) {
        setUser(null);
        setAccessTokenState(null);
      }
    });
    setAuthSuccessHandler((token: string, refreshedUser?: any) => {
      if (isMountedRef.current) {
        setAccessTokenState(token);
        if (refreshedUser) {
          setUser(refreshedUser);
        }
      }
    });
    return () => {
      isMountedRef.current = false;
      setAuthFailureHandler(null);
      setAuthSuccessHandler(null);
    };
  }, []);

  /**
   * Bootstrap auth session on app mount or full page refresh:
   * 1. Get initial CSRF token
   * 2. Attempt silent refresh using HttpOnly cookie
   */
  const bootstrapAuth = useCallback(async () => {
    try {
      const result = await requestAuthBootstrap();
      if (result.csrfToken) {
        updateCsrfToken(result.csrfToken);
      }
      if (result.accessToken) {
        updateAccessToken(result.accessToken);
      } else {
        updateAccessToken(null);
        setUser(null);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [updateAccessToken, updateCsrfToken]);

  useEffect(() => {
    bootstrapAuth();
  }, [bootstrapAuth]);

  /**
   * Manually refresh the user session
   */
  const refreshSession = useCallback(async (): Promise<boolean> => {
    const token = await requestTokenRefresh();
    const latestCsrfToken = getClientCsrfToken();
    if (latestCsrfToken) {
      updateCsrfToken(latestCsrfToken);
    }
    if (token) {
      updateAccessToken(token);
      return true;
    }

    // requestTokenRefresh preserves auth state on transient network errors but
    // clears it through the failure callback on an explicit 401/403.
    if (!getClientCsrfToken()) {
      updateAccessToken(null);
      setUser(null);
    }
    return false;
  }, [updateAccessToken, updateCsrfToken]);

  /**
   * User login with identifier & password
   */
  const login = async (identifier: string, password: string, rememberMe: boolean = false) => {
    try {
      const res = await loginApi({ identifier, password, remember_me: rememberMe });
      if (res && res.success && res.user && res.access_token) {
        updateAccessToken(res.access_token);
        setUser(res.user);
        if (res.csrf_token) {
          updateCsrfToken(res.csrf_token);
        }
        return { success: true, msg: res.msg || 'Đăng nhập thành công!' };
      }
      return { success: false, msg: res.msg || 'Đăng nhập thất bại.', error: res.error };
    } catch (err: any) {
      return {
        success: false,
        msg: err.message || 'Lỗi kết nối máy chủ.',
        error: err.data?.error || 'login_error',
      };
    }
  };

  /**
   * User registration
   */
  const register = async (data: {
    email: string;
    username: string;
    display_name?: string;
    password: string;
  }) => {
    try {
      const res = await registerApi(data);
      if (res && res.success && res.user && res.access_token) {
        updateAccessToken(res.access_token);
        setUser(res.user);
        if (res.csrf_token) {
          updateCsrfToken(res.csrf_token);
        }
        return { success: true, msg: res.msg || 'Đăng ký tài khoản thành công!' };
      }
      return { success: false, msg: res.msg || 'Đăng ký thất bại.', error: res.error };
    } catch (err: any) {
      return {
        success: false,
        msg: err.message || 'Lỗi kết nối máy chủ.',
        error: err.data?.error || 'register_error',
      };
    }
  };

  /**
   * Google Sign-in / SSO
   */
  const loginWithGoogle = async (credential: string) => {
    try {
      const res = await loginWithGoogleApi(credential);
      if (res && res.success && res.user && res.access_token) {
        updateAccessToken(res.access_token);
        setUser(res.user);
        if (res.csrf_token) {
          updateCsrfToken(res.csrf_token);
        }
        return { success: true, msg: res.msg || 'Đăng nhập Google thành công!' };
      }
      return { success: false, msg: res.msg || 'Đăng nhập Google thất bại.', error: res.error };
    } catch (err: any) {
      return {
        success: false,
        msg: err.message || 'Lỗi kết nối máy chủ.',
        error: err.data?.error || 'google_auth_error',
      };
    }
  };

  /**
   * User logout
   */
  const logout = async () => {
    try {
      await logoutApi();
    } catch {
      // Ignore network errors on logout
    } finally {
      updateAccessToken(null);
      setUser(null);
      // Fetch fresh CSRF token for guest session
      try {
        const csrfRes = await fetchCsrfToken();
        if (csrfRes && csrfRes.csrf_token) {
          updateCsrfToken(csrfRes.csrf_token);
        }
      } catch {
        // Ignore
      }
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isLoading,
        isAuthenticated: Boolean(user && accessToken),
        csrfToken,
        login,
        loginWithGoogle,
        register,
        logout,
        refreshSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
