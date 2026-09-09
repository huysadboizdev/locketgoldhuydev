import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

interface GoogleAuthButtonProps {
  mode?: 'signin' | 'signup';
  onSuccess?: () => void;
  onError?: (errorMsg: string) => void;
  disabled?: boolean;
}

interface GoogleCredentialResponse {
  credential: string;
  select_by?: string;
}

const GOOGLE_SCRIPT_ID = 'google-identity-services-script';
const GOOGLE_SCRIPT_URL = 'https://accounts.google.com/gsi/client';

let googleScriptPromise: Promise<void> | null = null;
let initializedClientId: string | null = null;
let activeCredentialHandler: ((response: GoogleCredentialResponse) => void) | null = null;

function loadGoogleIdentityServices(): Promise<void> {
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }
  if (googleScriptPromise) {
    return googleScriptPromise;
  }

  googleScriptPromise = new Promise<void>((resolve, reject) => {
    let script = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    let shouldAppend = false;
    if (!script) {
      script = document.createElement('script');
      script.id = GOOGLE_SCRIPT_ID;
      script.src = GOOGLE_SCRIPT_URL;
      script.async = true;
      script.defer = true;
      shouldAppend = true;
    }

    const handleLoad = () => {
      cleanup();
      if (window.google?.accounts?.id) {
        resolve();
      } else {
        reject(new Error('Google Identity Services không khả dụng.'));
      }
    };
    const handleError = () => {
      cleanup();
      reject(new Error('Không tải được Google Identity Services.'));
    };
    const cleanup = () => {
      script?.removeEventListener('load', handleLoad);
      script?.removeEventListener('error', handleError);
    };

    script.addEventListener('load', handleLoad, { once: true });
    script.addEventListener('error', handleError, { once: true });
    if (shouldAppend) {
      document.head.appendChild(script);
    }
  }).catch((error) => {
    googleScriptPromise = null;
    throw error;
  });

  return googleScriptPromise;
}

export const GoogleAuthButton: React.FC<GoogleAuthButtonProps> = ({
  mode = 'signin',
  onSuccess,
  onError,
  disabled = false,
}) => {
  const { loginWithGoogle } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'));
  const clientId = ((import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) || '').trim();

  const handleCredential = useCallback(async (response: GoogleCredentialResponse) => {
    if (!response?.credential) {
      onError?.('Không nhận được mã xác thực từ Google.');
      return;
    }

    setIsAuthenticating(true);
    try {
      const result = await loginWithGoogle(response.credential);
      if (result.success) {
        onSuccess?.();
      } else {
        onError?.(result.msg || 'Đăng nhập Google không thành công.');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Lỗi kết nối khi xác thực Google.';
      onError?.(message);
    } finally {
      setIsAuthenticating(false);
    }
  }, [loginWithGoogle, onError, onSuccess]);

  useEffect(() => {
    activeCredentialHandler = handleCredential;
    return () => {
      if (activeCredentialHandler === handleCredential) {
        activeCredentialHandler = null;
      }
    };
  }, [handleCredential]);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains('dark'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!clientId) {
      setScriptReady(false);
      return;
    }

    let cancelled = false;
    loadGoogleIdentityServices()
      .then(() => {
        if (!cancelled) {
          setScriptError(null);
          setScriptReady(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setScriptReady(false);
          setScriptError('Không tải được nút đăng nhập Google.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  useEffect(() => {
    const googleId = window.google?.accounts?.id;
    const container = containerRef.current;
    if (!scriptReady || !clientId || !googleId || !container) {
      return;
    }

    if (initializedClientId !== clientId) {
      googleId.initialize({
        client_id: clientId,
        callback: (response) => activeCredentialHandler?.(response),
        auto_select: false,
        cancel_on_tap_outside: true,
      });
      initializedClientId = clientId;
    }

    container.innerHTML = '';
    googleId.renderButton(container, {
      theme: isDark ? 'filled_black' : 'outline',
      size: 'large',
      type: 'standard',
      shape: 'pill',
      text: mode === 'signup' ? 'signup_with' : 'continue_with',
      logo_alignment: 'left',
      width: Math.max(240, Math.min(container.clientWidth || 320, 400)),
    });
  }, [clientId, isDark, mode, scriptReady]);

  if (!clientId) {
    return (
      <div className="flex min-h-11 w-full items-center justify-center gap-2 rounded-full border border-amber-300/70 bg-amber-50 px-4 text-xs font-semibold text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        Google Sign-In chưa được cấu hình
      </div>
    );
  }

  if (scriptError) {
    return (
      <div className="flex min-h-11 w-full items-center justify-center gap-2 rounded-full border border-red-300/70 bg-red-50 px-4 text-xs font-semibold text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        {scriptError}
      </div>
    );
  }

  return (
    <div className="relative w-full" aria-busy={isAuthenticating}>
      {(!scriptReady || isAuthenticating) && (
        <div className="mb-2 flex items-center justify-center gap-2 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs font-semibold text-amber-700 dark:text-amber-300">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {isAuthenticating ? 'Đang xác thực tài khoản Google...' : 'Đang tải Google Sign-In...'}
        </div>
      )}
      <div
        ref={containerRef}
        className={`flex min-h-11 w-full items-center justify-center overflow-hidden transition-opacity ${
          disabled || isAuthenticating ? 'pointer-events-none opacity-50' : ''
        }`}
      />
    </div>
  );
};
