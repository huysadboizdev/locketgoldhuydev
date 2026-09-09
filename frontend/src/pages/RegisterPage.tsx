import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Eye, EyeOff, Lock, Mail, User, AlertCircle, ArrowLeft, CheckCircle2, Loader2, Sparkles } from 'lucide-react';
import { Navbar } from '../components/layout/Navbar';
import { Footer } from '../components/layout/Footer';
import { GoogleAuthButton } from '../components/auth/GoogleAuthButton';
import { useAuth } from '../hooks/useAuth';
import { getDashboardReturnTo, getPostLoginReturnTo } from '../utils/url';
import { useToast } from '../hooks/useToast';

interface RegisterPageProps {
  isBackendOffline?: boolean;
}

interface FormErrors {
  displayName?: string;
  email?: string;
  username?: string;
  password?: string;
  confirmPassword?: string;
  agreeTerms?: string;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({ isBackendOffline }) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const rawReturnTo = searchParams.get('returnTo');
  const returnTo = getDashboardReturnTo(rawReturnTo);

  const { register, user, isAuthenticated } = useAuth();
  const toast = useToast();

  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [statusNotice, setStatusNotice] = useState<{ type: 'error' | 'success' | 'info'; msg: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect
  useEffect(() => {
    if (isAuthenticated && user) {
      navigate(getPostLoginReturnTo(user.role, rawReturnTo), { replace: true });
    }
  }, [isAuthenticated, user, navigate, rawReturnTo]);

  const validate = (): boolean => {
    const errs: FormErrors = {};

    if (!displayName.trim()) {
      errs.displayName = 'Vui lòng nhập tên hiển thị.';
    }

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim()) {
      errs.email = 'Vui lòng nhập địa chỉ email.';
    } else if (!emailPattern.test(email)) {
      errs.email = 'Địa chỉ email không đúng định dạng.';
    }

    if (!username.trim()) {
      errs.username = 'Vui lòng nhập username.';
    } else if (!/^[a-zA-Z0-9_]{3,20}$/.test(username)) {
      errs.username = 'Username từ 3-20 ký tự, chỉ gồm chữ cái, số và gạch dưới.';
    }

    if (!password) {
      errs.password = 'Vui lòng nhập mật khẩu.';
    } else if (password.length < 10 || password.length > 128) {
      errs.password = 'Mật khẩu phải có độ dài từ 10 đến 128 ký tự.';
    }

    if (!confirmPassword) {
      errs.confirmPassword = 'Vui lòng xác nhận mật khẩu.';
    } else if (password !== confirmPassword) {
      errs.confirmPassword = 'Mật khẩu xác nhận không khớp.';
    }

    if (!agreeTerms) {
      errs.agreeTerms = 'Bạn cần đồng ý với Điều khoản dịch vụ.';
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
      const res = await register({
        email: email.trim().toLowerCase(),
        username: username.trim().toLowerCase(),
        display_name: displayName.trim(),
        password,
      });

      if (res.success) {
        toast.success('Đăng ký thành công', 'Tài khoản của bạn đã được tạo. Chào mừng đến với Locket Gold!', {
          channel: 'auth',
          dedupeKey: 'auth-register-success',
        });
      } else {
        setStatusNotice({
          type: 'error',
          msg: res.msg || 'Đăng ký thất bại. Vui lòng kiểm tra lại.',
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
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors mb-6"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Quay lại trang chủ</span>
          </Link>

          <div className="gold-card gold-rise rounded-3xl border p-6 sm:p-8 backdrop-blur-md">
            <div className="mb-6 space-y-1 text-center sm:text-left">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
                  Đăng Ký Tài Khoản
                </h1>
                <Sparkles className="h-4 w-4 text-amber-500" />
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Tạo tài khoản thành viên để kiểm tra và gửi yêu cầu kích hoạt Locket Gold.
              </p>
            </div>

            {statusNotice && (
              <div
                role="status"
                aria-live="polite"
                className={`mb-5 flex items-start gap-2.5 rounded-2xl border p-3.5 text-xs ${
                  statusNotice.type === 'error'
                    ? 'border-rose-600/30 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200'
                    : 'border-emerald-600/30 dark:border-emerald-900/60 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200'
                }`}
              >
                {statusNotice.type === 'error' ? (
                  <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400 mt-0.5" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
                )}
                <span>{statusNotice.msg}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              {/* Display Name */}
              <div>
                <label
                  htmlFor="register-display-name"
                  className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5"
                >
                  Tên hiển thị
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-zinc-400 dark:text-zinc-500">
                    <User className="h-4 w-4" />
                  </div>
                  <input
                    id="register-display-name"
                    type="text"
                    name="name"
                    autoComplete="name"
                    value={displayName}
                    onChange={(e) => {
                      setDisplayName(e.target.value);
                      if (errors.displayName) setErrors((prev) => ({ ...prev, displayName: undefined }));
                    }}
                    placeholder="Nguyễn Văn A"
                    disabled={isSubmitting}
                    required
                    className={`w-full rounded-2xl border bg-zinc-50 dark:bg-zinc-950/80 pl-10 pr-4 py-3 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 transition-colors focus:outline-none focus:ring-2 ${
                      errors.displayName
                        ? 'border-rose-500 focus:border-rose-500 focus:ring-rose-500/20'
                        : 'border-zinc-300 dark:border-zinc-700/80 focus:border-amber-500 dark:focus:border-zinc-500 focus:ring-amber-500/20 dark:focus:ring-zinc-600/30'
                    }`}
                  />
                </div>
                {errors.displayName && (
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errors.displayName}</span>
                  </p>
                )}
              </div>

              {/* Email */}
              <div>
                <label
                  htmlFor="register-email"
                  className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5"
                >
                  Địa chỉ Email
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-zinc-400 dark:text-zinc-500">
                    <Mail className="h-4 w-4" />
                  </div>
                  <input
                    id="register-email"
                    type="email"
                    name="email"
                    autoComplete="email"
                    inputMode="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
                    }}
                    placeholder="name@example.com"
                    disabled={isSubmitting}
                    required
                    className={`w-full rounded-2xl border bg-zinc-50 dark:bg-zinc-950/80 pl-10 pr-4 py-3 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 transition-colors focus:outline-none focus:ring-2 ${
                      errors.email
                        ? 'border-rose-500 focus:border-rose-500 focus:ring-rose-500/20'
                        : 'border-zinc-300 dark:border-zinc-700/80 focus:border-amber-500 dark:focus:border-zinc-500 focus:ring-amber-500/20 dark:focus:ring-zinc-600/30'
                    }`}
                  />
                </div>
                {errors.email && (
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errors.email}</span>
                  </p>
                )}
              </div>

              {/* Username */}
              <div>
                <label
                  htmlFor="register-username"
                  className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5"
                >
                  Tên tài khoản (Username)
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-zinc-400 dark:text-zinc-500">
                    <User className="h-4 w-4" />
                  </div>
                  <input
                    id="register-username"
                    type="text"
                    name="username"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      if (errors.username) setErrors((prev) => ({ ...prev, username: undefined }));
                    }}
                    placeholder="huy_dev (3-20 ký tự)"
                    disabled={isSubmitting}
                    required
                    className={`w-full rounded-2xl border bg-zinc-50 dark:bg-zinc-950/80 pl-10 pr-4 py-3 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 transition-colors focus:outline-none focus:ring-2 ${
                      errors.username
                        ? 'border-rose-500 focus:border-rose-500 focus:ring-rose-500/20'
                        : 'border-zinc-300 dark:border-zinc-700/80 focus:border-amber-500 dark:focus:border-zinc-500 focus:ring-amber-500/20 dark:focus:ring-zinc-600/30'
                    }`}
                  />
                </div>
                {errors.username && (
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errors.username}</span>
                  </p>
                )}
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="register-password"
                  className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5"
                >
                  Mật khẩu (tối thiểu 10 ký tự)
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-zinc-400 dark:text-zinc-500">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    id="register-password"
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                    }}
                    placeholder="••••••••••••"
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
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errors.password}</span>
                  </p>
                )}
              </div>

              {/* Confirm Password */}
              <div>
                <label
                  htmlFor="register-confirm-password"
                  className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5"
                >
                  Xác nhận mật khẩu
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-zinc-400 dark:text-zinc-500">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    id="register-confirm-password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    name="confirm-password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      if (errors.confirmPassword) setErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                    }}
                    placeholder="••••••••••••"
                    disabled={isSubmitting}
                    required
                    className={`w-full rounded-2xl border bg-zinc-50 dark:bg-zinc-950/80 pl-10 pr-11 py-3 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 transition-colors focus:outline-none focus:ring-2 ${
                      errors.confirmPassword
                        ? 'border-rose-500 focus:border-rose-500 focus:ring-rose-500/20'
                        : 'border-zinc-300 dark:border-zinc-700/80 focus:border-amber-500 dark:focus:border-zinc-500 focus:ring-amber-500/20 dark:focus:ring-zinc-600/30'
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    aria-pressed={showConfirmPassword}
                    aria-label={showConfirmPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                  >
                    {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errors.confirmPassword}</span>
                  </p>
                )}
              </div>

              {/* Terms Checkbox */}
              <div className="pt-1">
                <div className="flex items-start">
                  <input
                    id="agree-terms"
                    type="checkbox"
                    checked={agreeTerms}
                    onChange={(e) => {
                      setAgreeTerms(e.target.checked);
                      if (errors.agreeTerms) setErrors((prev) => ({ ...prev, agreeTerms: undefined }));
                    }}
                    className="mt-0.5 h-4 w-4 rounded border-zinc-300 dark:border-zinc-700 text-amber-500 focus:ring-amber-500"
                  />
                  <label htmlFor="agree-terms" className="ml-2 text-xs text-zinc-600 dark:text-zinc-400 select-none">
                    Tôi đồng ý với Điều khoản dịch vụ và Chính sách kích hoạt an toàn của Locket Gold VIP.
                  </label>
                </div>
                {errors.agreeTerms && (
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errors.agreeTerms}</span>
                  </p>
                )}
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
                    <span>Đang tạo tài khoản...</span>
                  </>
                ) : (
                  <span>Đăng ký ngay</span>
                )}
              </button>
            </form>

            {/* Google Sign-in */}
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

            <div className="space-y-2">
              <GoogleAuthButton
                mode="signup"
                disabled={isSubmitting}
                onSuccess={() => {
                  toast.success('Đăng nhập Google thành công', 'Chào mừng bạn đến với Locket Gold.', {
                    channel: 'auth',
                    dedupeKey: 'auth-google-register-success',
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

            {/* Back to login */}
            <div className="mt-6 pt-4 border-t border-zinc-100 dark:border-zinc-800 text-center text-xs text-zinc-500 dark:text-zinc-400">
              <span>Đã có tài khoản? </span>
              <Link
                to={`/login?returnTo=${encodeURIComponent(returnTo)}`}
                className="font-semibold text-zinc-900 hover:underline dark:text-white"
              >
                Đăng nhập ngay
              </Link>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
};
