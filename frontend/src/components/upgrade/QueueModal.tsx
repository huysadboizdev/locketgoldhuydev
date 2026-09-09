import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, CheckCircle2, AlertCircle, Loader2, Apple, Smartphone, Download, Sparkles, RefreshCw, Check } from 'lucide-react';
import { formatWaitTime } from '../../utils/format';
import { createMobileconfigDownloadTicket, createApkDownloadTicket, fetchSiteSettings } from '../../api/endpoints';
import type { DevicePlatform, QueueItemStatus } from '../../types/api';
import { ModalPortal } from '../common/ModalPortal';

interface QueueModalProps {
  isOpen: boolean;
  username: string;
  clientId: string | null;
  platform?: DevicePlatform | null;
  status: QueueItemStatus | 'idle';
  position: number;
  totalQueue: number;
  estimatedTime: number;
  result: { success: boolean; msg?: string; dns?: any; [key: string]: any } | null;
  error: string | null;
  onClose: () => void;
  onReset: () => void;
}

export const QueueModal: React.FC<QueueModalProps> = ({
  isOpen,
  username,
  clientId,
  platform,
  status,
  position,
  totalQueue,
  estimatedTime,
  result,
  error,
  onClose,
  onReset,
}) => {
  const [copiedDns, setCopiedDns] = useState(false);
  const [confettiFired, setConfettiFired] = useState(false);
  const [isDownloadingProfile, setIsDownloadingProfile] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [isDownloadingApk, setIsDownloadingApk] = useState(false);
  const [apkDownloadError, setApkDownloadError] = useState<string | null>(null);
  const [siteDns, setSiteDns] = useState<{
    profile_id?: string | null;
    hostname?: string | null;
    apple_url?: string | null;
  } | null>(null);

  useEffect(() => {
    if (isOpen && !siteDns) {
      fetchSiteSettings()
        .then((settings) => {
          if (settings.dns) {
            setSiteDns({
              profile_id: settings.dns.profile_id ?? settings.dns.nextdns_profile ?? null,
              hostname: settings.dns.hostname ?? settings.dns.nextdns_hostname ?? null,
              apple_url: settings.dns.apple_url ?? settings.dns.nextdns_apple_url ?? null,
            });
          } else if (settings.nextdns_hostname) {
            setSiteDns({
              profile_id: settings.nextdns_profile ?? null,
              hostname: settings.nextdns_hostname ?? null,
              apple_url: settings.nextdns_apple_url ?? null,
            });
          }
        })
        .catch(() => {});
    }
  }, [isOpen, siteDns]);

  const dnsProfile = result?.dns?.profile_id || siteDns?.profile_id || '';
  const dnsHostname = result?.dns?.hostname || result?.dns?.android_dns || siteDns?.hostname || (dnsProfile ? `${dnsProfile}.dns.nextdns.io` : '');
  const appleDnsUrl = result?.dns?.apple_url || siteDns?.apple_url || (dnsProfile ? `https://apple.nextdns.io/${dnsProfile}` : 'https://apple.nextdns.io');

  const handleCopyDns = (hostnameToCopy: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(hostnameToCopy);
      setCopiedDns(true);
      setTimeout(() => setCopiedDns(false), 2500);
    }
  };

  const handleDownloadApk = async () => {
    if (!clientId) {
      setApkDownloadError('Không tìm thấy mã yêu cầu kích hoạt (client_id).');
      return;
    }
    setApkDownloadError(null);
    setIsDownloadingApk(true);
    try {
      const res = await createApkDownloadTicket(clientId);
      if (res && res.success && res.download_url) {
        window.location.href = res.download_url;
      } else {
        setApkDownloadError(res.msg || 'Không thể tạo liên kết tải APK. Vui lòng thử lại.');
      }
    } catch (err: any) {
      setApkDownloadError(err.message || 'Lỗi khi tải bản APK.');
    } finally {
      setIsDownloadingApk(false);
    }
  };

  const handleDownloadMobileconfig = async () => {
    if (!clientId) {
      setDownloadError('Không tìm thấy mã yêu cầu kích hoạt (client_id).');
      return;
    }
    setDownloadError(null);
    setIsDownloadingProfile(true);
    try {
      const res = await createMobileconfigDownloadTicket(clientId);
      if (res && res.success && res.download_url) {
        window.location.href = res.download_url;
      } else {
        setDownloadError(res.msg || 'Không thể tạo liên kết tải cấu hình. Vui lòng thử lại.');
      }
    } catch (err: any) {
      setDownloadError(err.message || 'Lỗi khi tải cấu hình profile.');
    } finally {
      setIsDownloadingProfile(false);
    }
  };

  // Lazy load và bắn pháo hoa khi completed
  useEffect(() => {
    if (status === 'completed' && !confettiFired) {
      setConfettiFired(true);
      import('canvas-confetti').then((confettiModule) => {
        const confetti = confettiModule.default;
        confetti({
          particleCount: 70,
          spread: 60,
          origin: { y: 0.6 },
          colors: ['#ffffff', '#e4e4e7', '#a1a1aa', '#fde047'],
        });
      }).catch(() => {
        // Ignored if confetti fails to load
      });
    } else if (status !== 'completed') {
      setConfettiFired(false);
    }
  }, [status, confettiFired]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <ModalPortal
        isOpen={isOpen}
        onClose={onClose}
        dismissible={status === 'completed' || status === 'error' || status === 'not_found'}
        ariaLabelledBy="queue-modal-title"
        backdropClassName="bg-black/70 backdrop-blur-sm dark:bg-black/80"
        className="max-w-lg !overflow-hidden !rounded-3xl !border !border-zinc-200 dark:!border-zinc-800 dark:!bg-[#121216]"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.2 }}
          className="relative w-full overflow-y-auto p-5 text-zinc-900 transition-colors dark:text-zinc-100 sm:p-7"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800/80 pb-4">
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse" />
              <h3 id="queue-modal-title" className="text-sm font-bold text-zinc-900 dark:text-white tracking-wide">
                {status === 'completed'
                  ? 'KÍCH HOẠT THÀNH CÔNG'
                  : status === 'error'
                  ? 'KÍCH HOẠT THẤT BẠI'
                  : 'TIẾN TRÌNH KÍCH HOẠT GOLD'}
              </h3>
            </div>
            {(status === 'completed' || status === 'error' || status === 'not_found') && (
              <button
                onClick={onClose}
                className="rounded-xl p-1.5 text-zinc-500 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-white transition-colors"
                aria-label="Đóng"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="py-5">
            {/* Target Account Badge */}
            <div className="mb-5 flex items-center justify-between rounded-xl bg-zinc-50 dark:bg-zinc-950/80 border border-zinc-200 dark:border-zinc-800 px-4 py-2.5 text-xs">
              <span className="text-zinc-500 dark:text-zinc-400">Tài khoản đích:</span>
              <div className="text-right">
                <span className="font-bold text-zinc-900 dark:text-zinc-200">@{username}</span>
                {clientId && (
                  <span className="block text-[10px] text-zinc-400 font-mono">
                    ID: {clientId.substring(0, 8)}...
                  </span>
                )}
              </div>
            </div>

            {/* CASE 1: WAITING IN QUEUE */}
            {status === 'waiting' && (
              <div className="space-y-5 text-center py-2">
                {/* Position Ring */}
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-zinc-200 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 shadow-inner">
                  <span className="text-3xl font-black text-zinc-900 dark:text-white">#{position}</span>
                </div>

                <div>
                  <h4 className="text-base font-bold text-zinc-900 dark:text-white">Đang chờ trong hàng đợi</h4>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    {position > 1 ? `Còn ${position - 1} người phía trước bạn` : 'Bạn đang ở vị trí đầu tiên, sắp được xử lý!'}
                  </p>
                </div>

                {/* Queue Stats Bar */}
                <div className="grid grid-cols-2 gap-3 rounded-2xl border border-zinc-200 dark:border-zinc-800/80 bg-zinc-50 dark:bg-zinc-950/60 p-3 text-xs">
                  <div>
                    <span className="text-zinc-500 block">Thời gian ước tính:</span>
                    <span className="font-bold text-zinc-800 dark:text-zinc-200 mt-0.5 block">{formatWaitTime(estimatedTime)}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Tổng hàng đợi:</span>
                    <span className="font-bold text-zinc-800 dark:text-zinc-200 mt-0.5 block">{totalQueue} yêu cầu</span>
                  </div>
                </div>

                {/* Animated shimmer bar */}
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                  <div className="h-full w-1/2 rounded-full bg-gradient-to-r from-amber-500 to-amber-300 animate-[shimmer_1.5s_infinite]" />
                </div>

                <p className="text-[11px] text-zinc-500 leading-normal">
                  Vui lòng không đóng trang này. Hệ thống tự động phân phối worker xử lý theo thứ tự.
                </p>
              </div>
            )}

            {/* CASE 2: PROCESSING */}
            {status === 'processing' && (
              <div className="space-y-4 text-center py-4">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl border border-zinc-200 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900">
                  <Loader2 className="h-8 w-8 animate-spin text-zinc-700 dark:text-zinc-200" />
                </div>

                <div>
                  <h4 className="text-base font-bold text-zinc-900 dark:text-white">Đang thực hiện kích hoạt Gold...</h4>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    Đang gửi biên lai giao dịch và đăng ký Entitlement với RevenueCat.
                  </p>
                </div>

                <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-3 text-left font-mono text-[11px] text-zinc-600 dark:text-zinc-400 space-y-1">
                  <p className="text-emerald-600 dark:text-emerald-400">[*] Kết nối RevenueCat Gateway... OK</p>
                  <p className="text-zinc-800 dark:text-zinc-300">[&gt;] Đang nạp gói locket_199_1m...</p>
                  <p className="text-zinc-500">[?] Đang chờ server phản hồi xác thực...</p>
                </div>
              </div>
            )}

            {/* CASE 3: COMPLETED SUCCESS */}
            {status === 'completed' && (
              <div className="space-y-5 py-2">
                <div className="text-center space-y-2">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 dark:bg-zinc-800 border border-emerald-200 dark:border-zinc-700 text-emerald-600 dark:text-white shadow-lg">
                    <CheckCircle2 className="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <h4 className="text-lg font-extrabold text-zinc-900 dark:text-white">
                    Chúc mừng! Locket Gold Đã Được Kích Hoạt
                  </h4>
                  <p className="text-xs text-zinc-600 dark:text-zinc-400">
                    {result?.msg || `Gói Gold đã được nạp thành công vào tài khoản @${username}.`}
                  </p>
                </div>

                {/* Important Setup Step Notice */}
                <div className="rounded-2xl border border-amber-600/30 dark:border-amber-900/40 bg-amber-50 dark:bg-amber-950/20 p-3.5 text-xs text-amber-900 dark:text-amber-200/90 leading-relaxed">
                  <div className="flex items-center gap-1.5 font-bold mb-1 text-amber-700 dark:text-amber-300">
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>BƯỚC QUAN TRỌNG ĐỂ DUY TRÌ GOLD:</span>
                  </div>
                  Vui lòng thực hiện cài đặt theo thiết bị bên dưới để hoàn tất cấu hình.
                </div>

                {/* Device Platform Badge */}
                <div className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-zinc-100 dark:bg-zinc-900/80 border border-zinc-200 dark:border-zinc-800 text-xs">
                  <span className="text-zinc-500 dark:text-zinc-400 font-medium">Thiết bị áp dụng:</span>
                  {platform === 'ios' && (
                    <span className="inline-flex items-center gap-1.5 font-bold text-zinc-900 dark:text-white">
                      <Apple className="h-3.5 w-3.5 text-zinc-900 dark:text-zinc-100" />
                      <span>iPhone / iPad (iOS)</span>
                    </span>
                  )}
                  {platform === 'android' && (
                    <span className="inline-flex items-center gap-1.5 font-bold text-emerald-600 dark:text-emerald-400">
                      <Smartphone className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                      <span>Android</span>
                    </span>
                  )}
                  {!platform && (
                    <span className="inline-flex items-center gap-1.5 font-medium text-amber-600 dark:text-amber-400">
                      <span>Chưa gắn nền tảng (Yêu cầu cũ)</span>
                    </span>
                  )}
                </div>

                {/* TAB 1: IOS GUIDE (Rendered ONLY when platform === 'ios') */}
                {platform === 'ios' && (
                  <div className="space-y-3.5">
                    <button
                      type="button"
                      onClick={handleDownloadMobileconfig}
                      disabled={isDownloadingProfile}
                      className="flex w-full items-center justify-center gap-2 rounded-2xl bg-zinc-900 dark:bg-zinc-100 py-3 text-xs font-bold text-white dark:text-zinc-950 transition-all hover:bg-zinc-800 dark:hover:bg-white active:scale-[0.98] disabled:opacity-60 shadow-md cursor-pointer"
                    >
                      {isDownloadingProfile ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin text-white dark:text-zinc-950" />
                          <span>Đang tạo liên kết tải an toàn...</span>
                        </>
                      ) : (
                        <>
                          <Download className="h-4 w-4" />
                          <span>Cài Đặt Profile DNS iOS (1 Chạm)</span>
                        </>
                      )}
                    </button>

                    {downloadError && (
                      <p className="mt-1 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                        <AlertCircle className="h-3.5 w-3.5" />
                        <span>{downloadError}</span>
                      </p>
                    )}

                    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 p-4 text-xs text-zinc-700 dark:text-zinc-300 space-y-2.5">
                      <p className="font-semibold text-zinc-900 dark:text-white">3 bước hoàn tất trên iPhone / iPad:</p>
                      <ol className="list-decimal pl-4 space-y-1.5 text-zinc-600 dark:text-zinc-400 text-[11px] leading-relaxed">
                        <li>Bấm nút trên bằng trình duyệt <b>Safari</b> và chọn <b>Cho phép</b> tải hồ sơ DNS.</li>
                        <li>Mở ứng dụng <b>Cài đặt</b> trên iPhone &gt; bấm vào mục <b>Đã tải về hồ sơ</b> ở trên cùng &gt; bấm <b>Cài đặt</b>.</li>
                        <li>Tắt hẳn ứng dụng Locket trong đa nhiệm và mở lại để kiểm tra trạng thái Locket Gold.</li>
                      </ol>
                      <div className="pt-2 border-t border-zinc-200 dark:border-zinc-800 text-[11px] text-zinc-500">
                        Link cài dự phòng qua Apple: <a href={appleDnsUrl} target="_blank" rel="noreferrer" className="text-amber-500 hover:underline font-mono break-all">{appleDnsUrl}</a>
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 2: ANDROID GUIDE (Rendered ONLY when platform === 'android') */}
                {platform === 'android' && (
                  <div className="space-y-3.5">
                    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 p-4 text-xs text-zinc-700 dark:text-zinc-300 space-y-2.5">
                      <p className="font-semibold text-zinc-900 dark:text-white">Cách 1: Cài DNS Chặn Thu Hồi (Khuyên Dùng):</p>
                      <div className="flex items-center justify-between rounded-xl bg-zinc-200/70 dark:bg-zinc-900 p-2.5 font-mono text-[11px] text-zinc-800 dark:text-zinc-200 border border-zinc-300 dark:border-zinc-800">
                        <span className="font-bold select-all">{dnsHostname}</span>
                        <button
                          type="button"
                          onClick={() => handleCopyDns(dnsHostname)}
                          className={`px-2.5 py-1 text-[10px] font-bold rounded-lg transition-colors flex items-center gap-1 cursor-pointer ${
                            copiedDns
                              ? 'bg-emerald-500 text-white'
                              : 'bg-amber-500 hover:bg-amber-600 text-black'
                          }`}
                        >
                          {copiedDns ? (
                            <>
                              <Check className="h-3 w-3" />
                              <span>Đã chép!</span>
                            </>
                          ) : (
                            <span>Sao chép</span>
                          )}
                        </button>
                      </div>
                      <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                        Vào <b>Cài đặt</b> ➔ <b>Mạng &amp; Internet / Kết nối</b> ➔ <b>DNS Riêng tư (Private DNS)</b> ➔ Chọn tên máy chủ và dán hostname ở trên.
                      </p>
                    </div>

                    <div className="text-center text-xs text-zinc-400 font-medium">— HOẶC —</div>

                    <button
                      type="button"
                      onClick={handleDownloadApk}
                      disabled={isDownloadingApk}
                      className="flex w-full items-center justify-center gap-2 rounded-2xl bg-zinc-900 dark:bg-zinc-100 py-3 text-xs font-bold text-white dark:text-zinc-950 transition-all hover:bg-zinc-800 dark:hover:bg-white active:scale-[0.98] disabled:opacity-60 shadow-md cursor-pointer"
                    >
                      {isDownloadingApk ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin text-white dark:text-zinc-950" />
                          <span>Đang tạo liên kết tải an toàn...</span>
                        </>
                      ) : (
                        <>
                          <Download className="h-4 w-4" />
                          <span>Tải Bản APK Locket Tối Ưu</span>
                        </>
                      )}
                    </button>

                    {apkDownloadError && (
                      <p className="mt-1 flex items-center gap-1 text-xs text-rose-600 dark:text-rose-400">
                        <AlertCircle className="h-3.5 w-3.5" />
                        <span>{apkDownloadError}</span>
                      </p>
                    )}

                    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 p-3 text-xs text-zinc-600 dark:text-zinc-400 space-y-1 text-[11px]">
                      <p className="font-semibold text-zinc-900 dark:text-white">Lưu ý khi dùng APK:</p>
                      <p>Cài đặt đè lên ứng dụng cũ hoặc cài mới rồi đăng nhập lại tài khoản Locket của bạn.</p>
                    </div>
                  </div>
                )}

                {/* UNKNOWN / LEGACY REQUEST FALLBACK */}
                {!platform && (
                  <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-zinc-700 dark:text-zinc-300 space-y-2">
                    <p className="font-semibold text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                      <AlertCircle className="h-4 w-4" />
                      <span>Yêu cầu này chưa được gắn thông tin nền tảng</span>
                    </p>
                    <p className="text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed">
                      Đây là phiên yêu cầu cũ hoặc chưa xác định rõ iOS / Android. Để nhận hướng dẫn cấu hình chuẩn xác và tải đúng tệp được cấp phép (profile hoặc APK), vui lòng hoàn tất phiên này hoặc bắt đầu một yêu cầu mới với lựa chọn thiết bị tương ứng.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* CASE 4: ERROR */}
            {status === 'error' && (
              <div className="space-y-4 text-center py-4">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400">
                  <AlertCircle className="h-8 w-8" />
                </div>

                <div>
                  <h4 className="text-base font-bold text-zinc-900 dark:text-white">Kích hoạt không thành công</h4>
                  <p className="mt-1 text-xs text-rose-600 dark:text-rose-300">
                    {error || 'Máy chủ Locket hoặc RevenueCat từ chối yêu cầu lúc này.'}
                  </p>
                </div>

                <div className="pt-2 flex gap-3">
                  <button
                    onClick={onReset}
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800 py-3 text-xs font-semibold text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
                  >
                    <RefreshCw className="h-3.5 w-3.5" /> Thử lại
                  </button>
                  <button
                    onClick={onClose}
                    className="flex-1 rounded-2xl bg-zinc-900 dark:bg-zinc-100 py-3 text-xs font-semibold text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-white transition-colors"
                  >
                    Đóng
                  </button>
                </div>
              </div>
            )}

            {/* CASE 5: NOT FOUND */}
            {status === 'not_found' && (
              <div className="space-y-4 text-center py-4">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400">
                  <AlertCircle className="h-8 w-8" />
                </div>

                <div>
                  <h4 className="text-base font-bold text-zinc-900 dark:text-white">Phiên yêu cầu đã kết thúc</h4>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    Phiên kích hoạt không còn tồn tại trong hàng đợi hoặc đã được xử lý xong.
                  </p>
                </div>

                <button
                  onClick={onReset}
                  className="w-full rounded-2xl bg-zinc-900 dark:bg-zinc-100 py-3 text-xs font-semibold text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-white transition-colors"
                >
                  Bắt đầu yêu cầu mới
                </button>
              </div>
            )}
          </div>
        </motion.div>
      </ModalPortal>
    </AnimatePresence>
  );
};
