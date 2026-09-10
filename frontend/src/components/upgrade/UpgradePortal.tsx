import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  UserCheck,
  ArrowRight,
  Smartphone,
  Apple,
  AlertCircle,
  Loader2,
  Sparkles,
  RefreshCw,
  Lock,
  ShieldCheck,
  Check,
} from 'lucide-react';
import { fetchUserInfo, requestRestore, fetchGoldCheck } from '../../api/endpoints';
import { extractUsername, isValidUsername } from '../../utils/username';
import type { DevicePlatform, UserInfoData } from '../../types/api';
import { useAuth } from '../../hooks/useAuth';

interface UpgradePortalProps {
  onStartQueue: (
    clientId: string,
    username: string,
    platform: DevicePlatform,
    position?: number,
    total?: number,
    estimatedTime?: number
  ) => void;
  isBackendOffline?: boolean;
}

export const UpgradePortal: React.FC<UpgradePortalProps> = ({ onStartQueue, isBackendOffline }) => {
  const { isAuthenticated, user } = useAuth();
  const [rawInput, setRawInput] = useState('');
  const [platform, setPlatform] = useState<DevicePlatform>('ios');

  // State tra cứu user
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [userInfo, setUserInfo] = useState<UserInfoData | null>(null);

  // State gửi vào queue
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const cleanUsername = extractUsername(rawInput);

  const handleLookup = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!cleanUsername) return;

    if (!isValidUsername(cleanUsername)) {
      setLookupError('Username chỉ được chứa chữ, số, dấu chấm và gạch dưới (2-30 ký tự).');
      return;
    }

    setIsLookingUp(true);
    setLookupError(null);
    setUserInfo(null);
    setSubmitError(null);

    try {
      const res = await fetchUserInfo(cleanUsername);
      if (res.success && res.data) {
        setUserInfo(res.data);
      } else {
        setLookupError(res.msg || 'Không tìm thấy người dùng Locket này.');
      }
    } catch (err: any) {
      if (err.status === 401) {
        setLookupError('Phiên đăng nhập đã hết hạn hoặc chưa đăng nhập. Vui lòng đăng nhập lại.');
      } else if (err.status === 404) {
        setLookupError('Không tìm thấy tài khoản Locket. Hãy kiểm tra lại username chính xác nhé.');
      } else if (err.status === 503) {
        setLookupError('Máy chủ đang bận xử lý hoặc tạm thời hết tài khoản mồi. Vui lòng thử lại sau 1 phút.');
      } else {
        setLookupError(err.message || 'Lỗi kết nối máy chủ khi tra cứu.');
      }
    } finally {
      setIsLookingUp(false);
    }
  };

  const handleStartUpgrade = async () => {
    if (!userInfo?.username) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      // Precheck Gold truoc khi dua vao hang doi: chan acc da Gold / da tung dang ky.
      const gold = await fetchGoldCheck(userInfo.username);
      if (!gold.success || gold.blocked || gold.error === 'gold_check_unavailable') {
        setSubmitError(
          gold.error === 'gold_check_unavailable'
            ? 'Không kiểm tra được Gold lúc này. Vui lòng đổi gói mới.'
            : 'Tài khoản đã mua/dùng Gold — gói này chỉ cho người chưa từng đăng ký. Vui lòng đổi gói mới.'
        );
        return;
      }
      const res = await requestRestore(userInfo.username, platform);
      if (res.success && res.client_id) {
        onStartQueue(
          res.client_id,
          userInfo.username,
          platform,
          res.position || 1,
          res.total_queue || 1,
          res.estimated_time || 5
        );
      } else {
        setSubmitError(res.msg || 'Không thể đưa vào hàng đợi lúc này.');
      }
    } catch (err: any) {
      if (err.status === 401) {
        setSubmitError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
      } else if (err.status === 403) {
        setSubmitError('Yêu cầu bảo mật CSRF không hợp lệ. Vui lòng tải lại trang.');
      } else if (err.status === 409) {
        setSubmitError(err.message || 'Tài khoản đã mua/dùng Gold — gói này chỉ cho người chưa từng đăng ký. Vui lòng đổi gói mới.');
      } else if (err.status === 503) {
        setSubmitError('Hàng đợi hiện đang đầy (tối đa 500 yêu cầu). Vui lòng thử lại sau ít phút.');
      } else {
        setSubmitError(err.message || 'Lỗi khi gửi yêu cầu kích hoạt.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setRawInput('');
    setUserInfo(null);
    setLookupError(null);
    setSubmitError(null);
  };

  return (
    <div id="upgrade" className="mx-auto max-w-xl px-4 sm:px-6 py-8">
      <div className="gold-card rounded-3xl border p-6 sm:p-8 backdrop-blur-md transition-all">
        {/* Offline Warning Banner */}
        {isBackendOffline && (
          <div className="mb-5 flex items-start gap-2.5 rounded-2xl border border-amber-600/30 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/40 p-3.5 text-xs text-amber-800 dark:text-amber-200">
            <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-bold block text-amber-900 dark:text-amber-300">Máy chủ chưa sẵn sàng (Backend Offline)</span>
              <span className="text-[11px] text-amber-700 dark:text-amber-200/80 leading-normal block">
                Backend Flask (127.0.0.1:5001) đang tạm tắt hoặc đang khởi động. Các thao tác API tạm khóa cho đến khi kết nối được thiết lập lại.
              </span>
            </div>
          </div>
        )}

        {/* LOCKED STATE IF NOT AUTHENTICATED */}
        {!isAuthenticated ? (
          <div className="text-center py-4 px-2 sm:px-4 space-y-6">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 shadow-sm">
              <Lock className="h-7 w-7" />
            </div>

            <div className="space-y-2">
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                <ShieldCheck className="h-3.5 w-3.5" /> Dành riêng cho thành viên
              </span>
              <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
                Đăng nhập để kiểm tra & kích hoạt
              </h3>
              <p className="text-xs sm:text-sm text-zinc-500 dark:text-zinc-400 max-w-md mx-auto leading-relaxed">
                Để bảo vệ quyền riêng tư và theo dõi tiến trình kích hoạt Locket Gold theo phiên an toàn, bạn cần đăng nhập tài khoản trước khi tiếp tục.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              <Link
                to="/login?returnTo=%23upgrade"
                className="gold-primary flex w-full sm:w-auto items-center justify-center gap-2 rounded-2xl px-6 py-3.5 text-xs sm:text-sm font-bold transition-all active:scale-[0.98]"
              >
                <span>Đăng nhập ngay</span>
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/register?returnTo=%23upgrade"
                className="flex w-full sm:w-auto items-center justify-center gap-2 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-6 py-3.5 text-xs sm:text-sm font-semibold text-zinc-800 dark:text-zinc-200 hover:border-zinc-300 dark:hover:border-zinc-700 transition-all"
              >
                <span>Tạo tài khoản mới</span>
              </Link>
            </div>

            <div className="border-t border-zinc-100 dark:border-zinc-800/80 pt-4 mt-6 grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] text-zinc-500 dark:text-zinc-400">
              <div className="flex items-center justify-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                <span>Hoàn toàn miễn phí</span>
              </div>
              <div className="flex items-center justify-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                <span>Tiến trình thời gian thực</span>
              </div>
              <div className="flex items-center justify-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                <span>Không lộ tài khoản Locket</span>
              </div>
            </div>
          </div>
        ) : (
          /* UNLOCKED STATE WHEN AUTHENTICATED */
          <>
            {/* Step Indicator Header */}
            <div className="mb-5 flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800/80 pb-4">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800 text-xs font-bold text-zinc-800 dark:text-zinc-100">
                  {userInfo ? '2' : '1'}
                </div>
                <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                  {userInfo ? 'Xác nhận tài khoản' : 'Nhập thông tin Locket'}
                </span>
              </div>

              {userInfo && (
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" /> Đổi user
                </button>
              )}
            </div>

            {/* Active User Session Pill */}
            {user && (
              <div className="mb-5 flex items-center justify-between rounded-xl bg-zinc-50 dark:bg-zinc-950/60 border border-zinc-200/80 dark:border-zinc-800/80 px-3.5 py-2 text-xs">
                <div className="flex items-center gap-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-bold text-[10px]">
                    ✓
                  </div>
                  <span className="text-zinc-600 dark:text-zinc-300">
                    Thành viên: <strong className="text-zinc-900 dark:text-white">{user.display_name}</strong> (@{user.username})
                  </span>
                </div>
              </div>
            )}

            {/* STEP 1: FORM NHẬP USERNAME */}
            {!userInfo ? (
              <form onSubmit={handleLookup} className="space-y-4">
                <div>
                  <label
                    htmlFor="locket-username"
                    className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5"
                  >
                    Username hoặc Link Profile Locket của bạn
                  </label>
                  <div className="relative">
                    <input
                      id="locket-username"
                      type="text"
                      value={rawInput}
                      onChange={(e) => {
                        setRawInput(e.target.value);
                        if (lookupError) setLookupError(null);
                      }}
                      placeholder="Ví dụ: huy_dev hoặc https://locket.cam/..."
                      disabled={isLookingUp || isBackendOffline}
                      autoFocus
                      className="w-full rounded-2xl border border-zinc-300 dark:border-zinc-700/80 bg-zinc-50 dark:bg-zinc-950/80 px-4 py-3.5 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 transition-colors focus:border-amber-500 dark:focus:border-zinc-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 dark:focus:ring-zinc-600/30 disabled:opacity-50"
                    />
                    {cleanUsername && (
                      <div className="absolute right-3.5 top-3.5 text-[11px] font-mono text-zinc-400 dark:text-zinc-500">
                        @{cleanUsername}
                      </div>
                    )}
                  </div>
                  <p className="mt-1.5 text-[11px] text-zinc-500 dark:text-zinc-400">
                    Hệ thống tự động trích xuất username nếu bạn dán link chia sẻ từ ứng dụng Locket.
                  </p>
                </div>

                {lookupError && (
                  <div className="flex items-start gap-2.5 rounded-2xl border border-rose-600/30 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/30 p-3 text-xs text-rose-700 dark:text-rose-300 animate-in fade-in duration-150">
                    <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400 mt-0.5" />
                    <span>{lookupError}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={!cleanUsername || isLookingUp || isBackendOffline}
                  className="gold-primary flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-xs sm:text-sm font-bold transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isLookingUp ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin text-white dark:text-zinc-950" />
                      <span>Đang tìm hồ sơ Locket...</span>
                    </>
                  ) : (
                    <>
                      <Search className="h-4 w-4" />
                      <span>Kiểm tra tài khoản Locket</span>
                    </>
                  )}
                </button>
              </form>
            ) : (
              /* STEP 2: USER PREVIEW & CONFIRM UPGRADE */
              <div className="space-y-5">
                {/* User Profile Card */}
                <div className="flex items-center gap-3.5 rounded-2xl border border-zinc-200 dark:border-zinc-700/60 bg-zinc-50 dark:bg-zinc-950/70 p-4">
                  <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-full border border-zinc-300 dark:border-zinc-700 bg-zinc-200 dark:bg-zinc-800">
                    {userInfo.profile_picture_url ? (
                      <img
                        src={userInfo.profile_picture_url}
                        alt={userInfo.username}
                        className="h-full w-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center font-bold text-zinc-600 dark:text-zinc-300 text-lg">
                        {userInfo.username.charAt(0).toUpperCase()}
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate text-base font-bold text-zinc-900 dark:text-white">
                        {userInfo.first_name || userInfo.last_name
                          ? `${userInfo.first_name} ${userInfo.last_name}`.trim()
                          : userInfo.username}
                      </span>
                      <UserCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    </div>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">@{userInfo.username}</p>
                    <div className="mt-1 flex items-center gap-2 text-[11px] text-zinc-500 dark:text-zinc-400">
                      <span>UID: {userInfo.uid.substring(0, 8)}•••</span>
                      <span>•</span>
                      <span className="text-amber-600 dark:text-amber-400 font-medium">Sẵn sàng nâng Gold</span>
                    </div>
                  </div>
                </div>

                {/* Platform Selector */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-2">
                    Chọn thiết bị bạn đang sử dụng
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      disabled={isSubmitting}
                      onClick={() => setPlatform('ios')}
                      className={`flex items-center justify-center gap-2 rounded-2xl border p-3 text-xs font-semibold transition-all disabled:opacity-60 disabled:cursor-not-allowed ${
                        platform === 'ios'
                          ? 'border-zinc-900 dark:border-zinc-300 bg-zinc-900 dark:bg-zinc-800 text-white shadow-sm'
                          : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950/60 text-zinc-600 dark:text-zinc-400 hover:border-zinc-300 dark:hover:border-zinc-700'
                      }`}
                    >
                      <Apple className="h-4 w-4" />
                      <span>iPhone / iPad (iOS)</span>
                    </button>

                    <button
                      type="button"
                      disabled={isSubmitting}
                      onClick={() => setPlatform('android')}
                      className={`flex items-center justify-center gap-2 rounded-2xl border p-3 text-xs font-semibold transition-all disabled:opacity-60 disabled:cursor-not-allowed ${
                        platform === 'android'
                          ? 'border-zinc-900 dark:border-zinc-300 bg-zinc-900 dark:bg-zinc-800 text-white shadow-sm'
                          : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950/60 text-zinc-600 dark:text-zinc-400 hover:border-zinc-300 dark:hover:border-zinc-700'
                      }`}
                    >
                      <Smartphone className="h-4 w-4" />
                      <span>Android</span>
                    </button>
                  </div>
                  <p className="mt-1.5 text-[11px] text-zinc-500 dark:text-zinc-400">
                    {platform === 'ios'
                      ? 'iOS: Sau khi kích hoạt sẽ được cấp Profile DNS chống thu hồi 1 chạm.'
                      : 'Android: Sau khi kích hoạt sẽ được cấp file APK mod tối ưu.'}
                  </p>
                </div>

                {submitError && (
                  <div className="flex items-start gap-2.5 rounded-2xl border border-rose-600/30 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/30 p-3 text-xs text-rose-700 dark:text-rose-300">
                    <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400 mt-0.5" />
                    <span>{submitError}</span>
                  </div>
                )}

                {/* Confirm & Upgrade Button */}
                <button
                  type="button"
                  disabled={isSubmitting || isBackendOffline}
                  onClick={handleStartUpgrade}
                  className="gold-primary flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-bold transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin text-white dark:text-zinc-950" />
                      <span>Đang đưa vào hàng đợi...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4 text-amber-400 dark:text-amber-500" />
                      <span>
                        {platform === 'ios'
                          ? 'Kích hoạt cho iPhone / iPad'
                          : 'Kích hoạt cho Android'}
                      </span>
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
