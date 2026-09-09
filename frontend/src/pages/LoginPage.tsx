import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Eye, EyeOff, Lock, User, AlertCircle, ArrowLeft, Info, CheckCircle2, Loader2 } from 'lucide-react';
import { Navbar } from '../components/layout/Navbar';
import { Footer } from '../components/layout/Footer';
import { GoogleAuthButton } from '../components/auth/GoogleAuthButton';
import { useAuth } from '../hooks/useAuth';
import { getPostLoginReturnTo } from '../utils/url';
import { useToast } from '../hooks/useToast';

interface LoginPageProps {
  isBackendOffline?: boolean;
}

export const LoginPage: React.FC<LoginPageProps> = ({ isBackendOffline }) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const { login, user, isAuthenticated } = useAuth();
  const toast = useToast();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const [errors, setErrors] = useState<{ identifier?: string; password?: string }>({});
  const [statusNotice, setStatusNotice] = useState<{ type: 'error' | 'success' | 'info'; msg: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect
  useEffect(() => {
    if (isAuthenticated && user) {
      const target = getPostLoginReturnTo(user.role, searchParams.get('returnTo'));
      navigate(target, { replace: true });
    }
  }, [isAuthenticated, user, navigate, searchParams]);

  const validate = () => {
    const errs: { identifier?: string; password?: string } = {};
    if (!identifier.trim()) {
      errs.identifier = 'Vui lòng nhập Email hoặc Username.';
    }
    if (!password) {
      errs.password = 'Vui lòng nhập mật khẩu.';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusNotice(null);

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await login(identifier, password, rememberMe);
      if (res.success) {
        toast.success('Đăng nhập thành công', 'Chào mừng bạn quay lại Locket Gold.', {
          channel: 'auth',
          dedupeKey: 'auth-login-success',
        });
      } else {
        setStatusNotice({
          type: 'error',
          msg: res.msg || 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.',
        });
      }
    } catch (err: any) {
      setStatusNotice({
        type: 'error',
        msg: err.message || 'Lỗi kết nối máy chủ.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="gold-page flex min-h-screen flex-col text-zinc-900 dark:text-zinc-100 transition-colors">
      <Navbar isBackendOffline={isBackendOffline} />

      <main className="flex-1 flex items-center justify-center py-12 px-4 sm:px-6">
        <div className="w-full max-w-md">
          {/* Back link */}
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors mb-6"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Quay lại trang chủ</span>
          </Link>

          {/* Login Card */}
          <div className="gold-card gold-rise rounded-3xl border p-6 sm:p-8 backdrop-blur-md">
            <div className="mb-6 space-y-1 text-center sm:text-left">
              <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
                Đăng Nhập
              </h1>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Truy cập cổng quản lý và kích hoạt Locket Gold của bạn.
              </p>
            </div>

            {/* Thông báo trạng thái */}
            {statusNotice && (
              <div
                role="status"
                aria-live="polite"
                className={`mb-5 flex items-start gap-2.5 rounded-2xl border p-3.5 text-xs ${
                  statusNotice.type === 'error'
                    ? 'border-rose-600/30 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200'
                    : statusNotice.type === 'success'
                    ? 'border-emerald-600/30 dark:border-emerald-900/60 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200'
                    : 'border-amber-600/30 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-200'
                }`}
              >
                {statusNotice.type === 'error' ? (
                  <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400 mt-0.5" />
                ) : statusNotice.type === 'success' ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
                ) : (
                  <Info className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                )}
                <span>{statusNotice.msg}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              {/* Identifier field */}
              <div>
                <label
                  htmlFor="login-identifier"
                  className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5"
                >
                  Email hoặc Username
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-zinc-400 dark:text-zinc-500">
                    <User className="h-4 w-4" />
                  </div>
                  <input
                    id="login-identifier"
                    type="text"
                    name="username"
                    autoComplete="username"
                    value={identifier}
                    onChange={(e) => {
                      setIdentifier(e.target.value);
                      if (errors.identifier) setErrors((prev) => ({ ...prev, identifier: undefined }));
                    }}
                    placeholder="name@example.com hoặc username"
                    aria-describedby={errors.identifier ? 'identifier-error' : undefined}
                    aria-invalid={Boolean(errors.identifier)}
                    disabled={isSubmitting}
                    required
                    className={`w-full rounded-2xl border bg-zinc-50 dark:bg-zinc-950/80 pl-10 pr-4 py-3 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 transition-colors focus:outline-none focus:ring-2 ${
                      errors.identifier
                        ? 'border-rose-500 focus:border-rose-500 focus:ring-rose-500/20'
                        : 'border-zinc-300 dark:border-zinc-700/80 focus:border-amber-500 dark:focus:border-zinc-500 focus:ring-amber-500/20 dark:focus:ring-zinc-600/30'
                    }`}
                  />
                </div>
                {errors.identifier && (
                  <p id="identifier-error" className="mt-1.5 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errors.identifier}</span>
                  </p>
                )}
              </div>

              {/* Password field */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="login-password"
                    className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300"
                  >
                    Mật khẩu
                  </label>
                  <button
                    type="button"
                    onClick={() => setStatusNotice({ type: 'info', msg: 'Tính năng khôi phục mật khẩu qua email đang được xây dựng.' })}
                    className="text-xs text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
                  >
                    Quên mật khẩu?
                  </button>
                </div>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-zinc-400 dark:text-zinc-500">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    id="login-password"
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                    }}
                    placeholder="••••••••••••"
                    aria-describedby={errors.password ? 'password-error' : undefined}
                    aria-invalid={Boolean(errors.password)}
                    disabled={isSubmitting}
                    required
                    className={`w-full rounded-2xl border bg-zinc-50 dark:bg-zinc-950/80 pl-10 pr-11 py-3 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 transition-colors focus:outline-none focus:ring-2 ${
                      errors.password
                        ? 'border-rose-500 focus:border-rose-500 focus:ring-rose-500/20'
                        : 'border-zinc-300 dark:border-zinc-700/80 focus:border-amber-500 dark:focus:border-zinc-500 focus:ring-amber-500/20 dark:focus:ring-zinc-600/30'
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-pressed={showPassword}
                    aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p id="password-error" className="mt-1.5 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errors.password}</span>
                  </p>
                )}
              </div>

              {/* Remember me */}
              <div className="flex items-center">
                <input
                  id="remember-me"
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="h-4 w-4 rounded border-zinc-300 dark:border-zinc-700 text-amber-500 focus:ring-amber-500"
                />
                <label htmlFor="remember-me" className="ml-2 text-xs text-zinc-600 dark:text-zinc-400 select-none">
                  Ghi nhớ đăng nhập
                </label>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="gold-primary flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-xs sm:text-sm font-bold transition-all active:scale-[0.98] disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-white dark:text-zinc-950" />
                    <span>Đang xác thực...</span>
                  </>
                ) : (
                  <span>Đăng nhập</span>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-zinc-200 dark:border-zinc-800" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-white dark:bg-zinc-900 px-3 text-zinc-400 dark:text-zinc-500 text-[10px] font-semibold">
                  Hoặc
                </span>
              </div>
            </div>

            {/* Google Sign-In */}
            <div className="space-y-2">
              <GoogleAuthButton
                mode="signin"
                disabled={isSubmitting}
                onSuccess={() => {
                  toast.success('Đăng nhập Google thành công', 'Chào mừng bạn quay lại Locket Gold.', {
                    channel: 'auth',
                    dedupeKey: 'auth-google-login-success',
                  });
                }}
                onError={(errMsg) => {
                  setStatusNotice({
                    type: 'error',
                    msg: errMsg,
                  });
                }}
              />
            </div>

            {/* Link to Register */}
            <div className="mt-6 pt-4 border-t border-zinc-100 dark:border-zinc-800 text-center text-xs text-zinc-500 dark:text-zinc-400">
              <span>Chưa có tài khoản? </span>
              <Link
                to={searchParams.get('returnTo') ? `/register?returnTo=${encodeURIComponent(searchParams.get('returnTo') || '')}` : '/register'}
                className="font-semibold text-zinc-900 hover:underline dark:text-white"
              >
                Đăng ký ngay
              </Link>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
};
