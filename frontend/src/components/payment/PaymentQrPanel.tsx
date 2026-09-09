import React, { useState } from 'react';
import type { BankConfig, PaymentStatus } from '../../types/api';
import { usePaymentCountdown } from '../../hooks/usePaymentCountdown';
import {
  QrCode,
  Copy,
  Check,
  Clock,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Landmark,
  ShieldAlert,
  Loader2,
  X,
} from 'lucide-react';

export interface PaymentQrData {
  id?: number;
  payment_id?: number;
  payment_code: string;
  payment_ref?: string;
  transfer_code: string;
  amount_vnd: number;
  coin_amount: number;
  qr_url: string;
  expires_at: number;
  server_time?: number;
  status: PaymentStatus;
  bank_config?: BankConfig;
  purpose: 'wallet_topup' | 'plan_purchase';
  plan_name?: string;
  locket_username?: string;
  platform?: string;
}

interface PaymentQrPanelProps {
  payment: PaymentQrData;
  onRenew?: () => Promise<void>;
  isRenewing?: boolean;
  renewError?: string | null;
  onClose?: () => void;
  onStatusExpire?: () => void;
  title?: string;
  subtitle?: string;
}

export const PaymentQrPanel: React.FC<PaymentQrPanelProps> = ({
  payment,
  onRenew,
  isRenewing = false,
  renewError = null,
  onClose,
  onStatusExpire,
  title,
  subtitle,
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const {
    formattedTime,
    progressPercent,
    isExpired: countdownExpired,
  } = usePaymentCountdown({
    expiresAt: payment.expires_at,
    serverTime: payment.server_time,
    totalDurationSeconds: 600,
    onExpire: onStatusExpire,
  });

  const isActuallyExpired = payment.status === 'expired' || (payment.status === 'pending' && countdownExpired);
  const isPaid = payment.status === 'paid';
  const isCancelled = payment.status === 'cancelled';
  const isUnderpaid = payment.status === 'underpaid';
  const isReviewNeeded = payment.status === 'review_needed';
  const isBlocked = isActuallyExpired || isCancelled || isUnderpaid || isReviewNeeded;

  // Copy helper with feedback
  const handleCopy = (text: string, key: string) => {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(
      () => {
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2500);
      },
      () => {}
    );
  };

  const defaultTitle =
    title ||
    (payment.purpose === 'wallet_topup'
      ? `Nạp ${payment.coin_amount.toLocaleString('vi-VN')} Coin qua VietQR`
      : `Thanh toán gói ${payment.plan_name || 'Locket Gold'}`);

  const defaultSubtitle =
    subtitle ||
    (payment.purpose === 'wallet_topup'
      ? 'Quét mã VietQR trên app ngân hàng hoặc chuyển khoản chính xác nội dung bên dưới.'
      : `Kích hoạt ngay cho tài khoản @${payment.locket_username || 'Locket'} trên ${
          payment.platform?.toUpperCase() || 'thiết bị của bạn'
        }.`);

  return (
    <div
      className="w-full rounded-3xl border border-amber-500/30 bg-white dark:bg-zinc-900/90 p-4 sm:p-6 shadow-xl transition-all"
      role="region"
      aria-label="Thông tin thanh toán VietQR"
    >
      {/* Header */}
      <div className="flex items-start justify-between border-b border-zinc-100 dark:border-zinc-800 pb-4 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <QrCode className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h4 className="text-sm sm:text-base font-bold text-zinc-900 dark:text-white truncate">
              {defaultTitle}
            </h4>
            <p className="text-[11px] sm:text-xs text-zinc-500 dark:text-zinc-400 line-clamp-1">
              {defaultSubtitle}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Status Badge */}
          <div aria-live="polite">
            {isPaid ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-300 dark:border-emerald-800 px-2.5 py-1 text-[11px] font-bold text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>Đã thanh toán</span>
              </span>
            ) : isActuallyExpired ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 dark:bg-rose-950/50 border border-rose-300 dark:border-rose-800 px-2.5 py-1 text-[11px] font-bold text-rose-700 dark:text-rose-400">
                <AlertCircle className="h-3.5 w-3.5" />
                <span>Mã đã hết hạn</span>
              </span>
            ) : isCancelled ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 px-2.5 py-1 text-[11px] font-bold text-zinc-700 dark:text-zinc-300">
                <span>Đã hủy</span>
              </span>
            ) : isUnderpaid ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 dark:bg-orange-950/50 border border-orange-300 dark:border-orange-800 px-2.5 py-1 text-[11px] font-bold text-orange-700 dark:text-orange-400">
                <span>Chuyển thiếu tiền</span>
              </span>
            ) : isReviewNeeded ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 dark:bg-purple-950/50 border border-purple-300 dark:border-purple-800 px-2.5 py-1 text-[11px] font-bold text-purple-700 dark:text-purple-400">
                <span>Cần kiểm tra</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 dark:bg-amber-950/50 border border-amber-300 dark:border-amber-800 px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:text-amber-400">
                <span className="h-2 w-2 rounded-full bg-amber-500 motion-safe:animate-ping" />
                <span>Đang chờ thanh toán</span>
              </span>
            )}
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Đóng bảng thanh toán"
              className="p-1.5 rounded-xl text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Main Content Body */}
      {isPaid ? (
        /* Paid state celebration */
        <div className="py-8 text-center space-y-4">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-emerald-500 text-white shadow-xl shadow-emerald-500/20 motion-safe:animate-bounce">
            <CheckCircle2 className="h-9 w-9" />
          </div>
          <div>
            <h4 className="text-lg font-extrabold text-zinc-900 dark:text-white">
              Thanh toán thành công!
            </h4>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto">
              Hệ thống đã xác nhận giao dịch #{payment.payment_ref || payment.payment_code}.{' '}
              {payment.purpose === 'wallet_topup'
                ? `Số dư ví của bạn đã được cộng +${payment.coin_amount} Coin.`
                : 'Đơn hàng của bạn đang được xử lý kích hoạt tự động.'}
            </p>
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="gold-primary rounded-2xl px-6 py-2.5 text-xs font-bold shadow-md"
            >
              Hoàn tất
            </button>
          )}
        </div>
      ) : (
        /* Unpaid / Pending / Expired state */
        <div className="pt-4 space-y-4">
          {/* 10-Minute Countdown bar when pending */}
          {payment.status === 'pending' && !isActuallyExpired && (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.05] p-3 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 font-semibold text-amber-800 dark:text-amber-300">
                  <Clock className="h-4 w-4" />
                  <span>Thời gian hiệu lực mã:</span>
                </div>
                <span className="font-mono font-bold text-amber-700 dark:text-amber-300 text-sm">
                  {formattedTime}
                </span>
              </div>
              {/* Progress bar */}
              <div className="w-full bg-amber-200/50 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-amber-500 to-amber-400 h-2 rounded-full transition-all duration-1000 ease-linear motion-reduce:transition-none"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          )}

          {/* Grid Layout: QR Code + Transfer Details */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-center">
            {/* QR Box with Expiry Blur Overlay */}
            <div className="md:col-span-5 flex flex-col items-center justify-center">
              <div className="relative w-full max-w-[220px] aspect-square rounded-2xl border border-zinc-200 dark:border-zinc-700 bg-white p-2.5 shadow-sm overflow-hidden flex items-center justify-center">
                <img
                  src={payment.qr_url}
                  alt={`VietQR ${payment.transfer_code}`}
                  className={`w-full h-full object-contain rounded-xl transition-all duration-300 ${
                    isBlocked
                      ? 'filter blur-sm opacity-30 select-none pointer-events-none'
                      : ''
                  }`}
                />

                {/* Overlay when expired */}
                {isBlocked && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center p-3 text-center bg-zinc-950/70 text-white rounded-2xl backdrop-blur-xs space-y-2.5">
                    <ShieldAlert className="h-8 w-8 text-rose-400" />
                    <p className="text-[11px] font-semibold leading-tight text-rose-200">
                      {isUnderpaid
                        ? 'Giao dịch chuyển thiếu tiền đang chờ quản trị viên xử lý.'
                        : isReviewNeeded
                          ? 'Giao dịch đang cần quản trị viên kiểm tra trước khi xử lý.'
                          : 'Mã thanh toán đã hết hạn. Vui lòng tạo mã mới trước khi chuyển khoản.'}
                    </p>
                  </div>
                )}
              </div>

              <p className="mt-2 text-[10px] text-zinc-400 text-center">
                Mở ứng dụng ngân hàng bất kỳ để quét mã
              </p>
            </div>

            {/* Bank Transfer Details Box */}
            <div className="md:col-span-7 space-y-2.5">
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 p-3.5 sm:p-4 space-y-2.5 text-xs">
                {/* Bank Name */}
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1">
                    <Landmark className="h-3.5 w-3.5" />
                    <span>Ngân hàng:</span>
                  </span>
                  <span className="font-bold text-zinc-900 dark:text-white">
                    {payment.bank_config?.bank_id || 'TPBank'}
                  </span>
                </div>

                {/* Account Number */}
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Số tài khoản:</span>
                  <div className="flex items-center gap-1.5 font-mono font-bold text-zinc-900 dark:text-white">
                    <span>{payment.bank_config?.account_no || 'HUYDEV204'}</span>
                    <button
                      type="button"
                      onClick={() => handleCopy(payment.bank_config?.account_no || 'HUYDEV204', 'account_no')}
                      aria-label="Sao chép số tài khoản"
                      className="p-1 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors"
                    >
                      {copiedKey === 'account_no' ? (
                        <Check className="h-3.5 w-3.5 text-emerald-500" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Account Owner */}
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Chủ tài khoản:</span>
                  <span className="font-semibold text-zinc-800 dark:text-zinc-200 uppercase">
                    {payment.bank_config?.account_name || 'HA QUANG HUY'}
                  </span>
                </div>

                {/* Amount */}
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Số tiền:</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-extrabold text-amber-600 dark:text-amber-400">
                      {payment.amount_vnd.toLocaleString('vi-VN')} VNĐ
                    </span>
                    <button
                      type="button"
                      onClick={() => handleCopy(String(payment.amount_vnd), 'amount_vnd')}
                      aria-label="Sao chép số tiền"
                      className="p-1 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors"
                    >
                      {copiedKey === 'amount_vnd' ? (
                        <Check className="h-3.5 w-3.5 text-emerald-500" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Transfer Code (addInfo) - HIGHLIGHTED */}
                <div className="pt-2 border-t border-zinc-200/60 dark:border-zinc-800/80 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-zinc-500 dark:text-zinc-400 block text-[11px]">
                      Nội dung chuyển khoản:
                    </span>
                    <span className="text-[10px] text-rose-500 font-medium">
                      (Bắt buộc chuyển đúng để đối soát giao dịch)
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <code className="rounded-lg bg-amber-500/15 border border-amber-500/40 px-2 py-1 font-mono font-extrabold text-amber-700 dark:text-amber-300 text-xs sm:text-sm break-all">
                      {payment.transfer_code}
                    </code>
                    <button
                      type="button"
                      onClick={() => handleCopy(payment.transfer_code, 'transfer_code')}
                      aria-label="Sao chép nội dung chuyển khoản"
                      className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-700 dark:text-amber-300 transition-colors"
                    >
                      {copiedKey === 'transfer_code' ? (
                        <Check className="h-4 w-4 text-emerald-500" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Polling / Warning Footer */}
              {payment.status === 'pending' && !isActuallyExpired && (
                <div className="flex items-center gap-2 text-[11px] text-zinc-500 dark:text-zinc-400 px-1 py-0.5">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500 shrink-0" />
                  <span>Đang kiểm tra trạng thái với máy chủ mỗi 3 giây...</span>
                </div>
              )}

              {renewError && (
                <p className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1.5">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{renewError}</span>
                </p>
              )}

              {/* Expired Action Bar */}
              {(isActuallyExpired || isCancelled) && onRenew && (
                <div className="pt-2">
                  <button
                    type="button"
                    disabled={isRenewing}
                    onClick={onRenew}
                    className="gold-primary w-full min-h-[44px] rounded-2xl py-3 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50"
                  >
                    {isRenewing ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin text-zinc-950" />
                        <span>Đang tạo mã VietQR mới...</span>
                      </>
                    ) : (
                      <>
                        <RefreshCw className="h-4 w-4" />
                        <span>Tạo mã thanh toán mới</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
