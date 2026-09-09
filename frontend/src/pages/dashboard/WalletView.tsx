import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  WalletTransaction,
  TopupPaymentResponse,
} from '../../types/api';
import {
  fetchWalletTransactions,
  createTopupPayment,
  renewPayment,
} from '../../api/endpoints';
import { PaymentQrPanel } from '../../components/payment/PaymentQrPanel';
import { usePaymentPolling } from '../../hooks/usePaymentPolling';
import {
  Coins,
  ArrowUpRight,
  ArrowDownLeft,
  RefreshCw,
  QrCode,
  AlertCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Landmark,
  ShieldCheck,
  BadgeCheck,
} from 'lucide-react';

interface WalletViewProps {
  balance: number;
  isLoadingBalance: boolean;
  onRefreshBalance: () => void;
  prefilledCoin?: number | null;
}

const QUICK_OPTIONS = [20, 50, 100, 200];

const TRANSACTION_LABELS: Record<string, string> = {
  topup: 'Nạp Coin',
  purchase: 'Mua gói',
  refund: 'Hoàn Coin',
  adjustment: 'Điều chỉnh',
};

export const WalletView: React.FC<WalletViewProps> = ({
  balance,
  isLoadingBalance,
  onRefreshBalance,
  prefilledCoin,
}) => {
  const [selectedCoin, setSelectedCoin] = useState<number>(prefilledCoin || 50);
  const [customCoinInput, setCustomCoinInput] = useState<string>('');
  const [isCustom, setIsCustom] = useState<boolean>(false);

  // Top-up QR state
  const [topupOrder, setTopupOrder] = useState<TopupPaymentResponse | null>(null);
  const [isCreatingTopup, setIsCreatingTopup] = useState(false);
  const [topupError, setTopupError] = useState<string | null>(null);
  const [isRenewingTopup, setIsRenewingTopup] = useState(false);
  const [renewError, setRenewError] = useState<string | null>(null);
  const topupAttemptRef = useRef<{ key: string; amountVnd: number } | null>(null);

  // Transactions state
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [isLoadingTxs, setIsLoadingTxs] = useState(false);
  const [page, setPage] = useState(0);
  const [totalTxs, setTotalTxs] = useState(0);
  const limit = 10;

  // Load transactions
  const loadTransactions = useCallback(async (p: number) => {
    setIsLoadingTxs(true);
    try {
      const res = await fetchWalletTransactions(limit, p * limit);
      if (res && res.success) {
        setTransactions(res.items);
        setTotalTxs(res.pagination.total);
      }
    } catch {}
    finally {
      setIsLoadingTxs(false);
    }
  }, []);

  useEffect(() => {
    loadTransactions(page);
  }, [page, loadTransactions]);

  useEffect(() => {
    if (prefilledCoin && prefilledCoin > 0) {
      if (QUICK_OPTIONS.includes(prefilledCoin)) {
        setSelectedCoin(prefilledCoin);
        setIsCustom(false);
      } else {
        setIsCustom(true);
        setSelectedCoin(prefilledCoin);
        setCustomCoinInput(String(prefilledCoin));
      }
    }
  }, [prefilledCoin]);

  const activeCoinAmount = isCustom ? (parseInt(customCoinInput) || 0) : selectedCoin;
  const activeVndAmount = activeCoinAmount * 1000;

  // Create Topup with Idempotency Key
  const handleCreateTopup = async () => {
    if (activeCoinAmount <= 0) {
      setTopupError('Số lượng Coin phải lớn hơn 0.');
      return;
    }
    setIsCreatingTopup(true);
    setTopupError(null);
    setRenewError(null);

    try {
      const previousAttempt = topupAttemptRef.current;
      const idempotencyKey =
        previousAttempt?.amountVnd === activeVndAmount
          ? previousAttempt.key
          : crypto.randomUUID();
      topupAttemptRef.current = { key: idempotencyKey, amountVnd: activeVndAmount };
      const res = await createTopupPayment(activeVndAmount, idempotencyKey);
      if (res && res.success) {
        setTopupOrder({
          ...res,
          status: 'pending',
        });
      } else {
        setTopupError(res.msg || 'Không thể tạo đơn nạp Coin.');
      }
    } catch (err: any) {
      setTopupError(err.message || 'Lỗi máy chủ khi tạo mã thanh toán.');
    } finally {
      setIsCreatingTopup(false);
    }
  };

  // Renew Topup
  const handleRenewTopup = async () => {
    if (!topupOrder) return;
    setIsRenewingTopup(true);
    setRenewError(null);
    try {
      const refToRenew = topupOrder.payment_ref || topupOrder.payment_code;
      const res = await renewPayment(refToRenew);
      if (res && res.success && res.payment) {
        setTopupOrder((prev) => ({
          ...prev!,
          payment_id: res.payment.id,
          payment_code: res.payment.payment_code,
          payment_ref: res.payment.payment_ref || res.payment.payment_code,
          transfer_code: res.payment.transfer_code,
          qr_url: res.payment.qr_url || prev!.qr_url,
          status: res.payment.status,
          expires_at: res.payment.expires_at,
          server_time: res.server_time || res.payment.server_time,
          bank_config: res.payment.bank_config || prev!.bank_config,
        }));
      } else {
        setRenewError(res.msg || 'Không thể tạo lại mã thanh toán mới.');
      }
    } catch (err: any) {
      setRenewError(err.message || 'Lỗi kết nối khi làm mới mã thanh toán.');
    } finally {
      setIsRenewingTopup(false);
    }
  };

  // One polling loop is shared by the QR panel and wallet refresh flow.
  const { status: topupStatus, refetchStatus: refetchTopupStatus } = usePaymentPolling({
    paymentRef: topupOrder?.payment_ref || topupOrder?.payment_code,
    currentStatus: topupOrder?.status || 'pending',
    enabled: !!topupOrder && (topupOrder.status === 'pending' || !topupOrder.status),
    onStatusChange: (status, pay) => {
      setTopupOrder((prev) =>
        prev
          ? {
              ...prev,
              status,
              payment_id: pay.id,
              payment_code: pay.payment_code,
              payment_ref: pay.payment_ref || pay.payment_code,
              transfer_code: pay.transfer_code || prev.transfer_code,
              qr_url: pay.qr_url || prev.qr_url,
              expires_at: pay.expires_at,
              server_time: pay.server_time,
            }
          : null
      );
      if (status === 'paid') {
        onRefreshBalance();
        loadTransactions(0);
      }
    },
  });

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Top Section: Balance Card & Top-Up Trigger */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 sm:gap-5 items-start">
        {/* Balance Card */}
        <div className="xl:col-span-4 rounded-3xl border border-amber-500/30 bg-gradient-to-br from-amber-500/15 via-amber-500/[0.06] to-white/30 dark:to-transparent p-5 sm:p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-amber-700 dark:text-amber-400">
              <Coins className="h-4 w-4" />
              <span>Ví Coin của tôi</span>
            </div>
            <button
              type="button"
              onClick={onRefreshBalance}
              title="Làm mới số dư"
              className="p-1.5 rounded-xl hover:bg-amber-500/20 text-amber-700 dark:text-amber-400 transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoadingBalance ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Số dư khả dụng:</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-3xl sm:text-4xl font-extrabold text-zinc-900 dark:text-white tracking-tight">
                {isLoadingBalance ? '...' : balance.toLocaleString('vi-VN')}
              </span>
              <span className="text-sm font-bold text-amber-600 dark:text-amber-400">Coin</span>
            </div>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              Tương đương {(balance * 1000).toLocaleString('vi-VN')} VNĐ (1 Coin = 1.000 VNĐ)
            </p>
          </div>

          <div className="pt-2 border-t border-amber-500/20 text-[11px] text-zinc-600 dark:text-zinc-400">
            <span>Dùng Coin để kích hoạt các gói Locket Gold ngay lập tức mà không cần chờ duyệt thủ công.</span>
          </div>
        </div>

        {/* Top-Up Form */}
        <div className="xl:col-span-8 rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-5 sm:p-6 space-y-4">
          <div>
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">
              Nạp Coin vào Ví
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Chọn gói nạp Coin tiện lợi hoặc nhập số lượng tùy ý (tối thiểu 10 Coin).
            </p>
          </div>

          {/* Quick options */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {QUICK_OPTIONS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => {
                  setSelectedCoin(c);
                  setIsCustom(false);
                }}
                className={`flex flex-col items-center justify-center rounded-2xl border py-3 px-2 text-center transition-all ${
                  !isCustom && selectedCoin === c
                    ? 'border-amber-500 bg-amber-500/10 shadow-sm ring-2 ring-amber-500/20'
                    : 'border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 hover:border-amber-500/30'
                }`}
              >
                <span className="text-sm font-bold text-zinc-900 dark:text-white">{c} Coin</span>
                <span className="text-[10px] text-zinc-500">{(c * 1000).toLocaleString('vi-VN')} đ</span>
              </button>
            ))}
          </div>

          {/* Custom option toggle */}
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setIsCustom(!isCustom)}
              className="text-xs font-semibold text-amber-600 dark:text-amber-400 hover:underline"
            >
              {isCustom ? 'Chọn lại các mức có sẵn' : '+ Nhập số lượng khác'}
            </button>

            {isCustom && (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={customCoinInput}
                  onChange={(e) => setCustomCoinInput(e.target.value)}
                  placeholder="Nhập số Coin (VD: 75)"
                  className="w-full rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-950 px-4 py-2.5 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                />
              </div>
            )}
          </div>

          {/* Calculation row */}
          <div className="rounded-2xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50/60 dark:bg-zinc-950/40 p-4 flex items-center justify-between text-xs">
            <span className="text-zinc-500">Số tiền thanh toán:</span>
            <div className="text-right">
              <span className="text-base font-extrabold text-amber-600 dark:text-amber-400">
                {activeVndAmount.toLocaleString('vi-VN')} VNĐ
              </span>
              <span className="ml-1 text-[11px] text-zinc-400">({activeCoinAmount} Coin)</span>
            </div>
          </div>

          {topupError && (
            <p className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{topupError}</span>
            </p>
          )}

          <button
            type="button"
            disabled={isCreatingTopup || activeCoinAmount <= 0}
            onClick={handleCreateTopup}
            className="gold-primary w-full rounded-2xl py-3.5 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50"
          >
            {isCreatingTopup ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-zinc-950" />
                <span>Đang tạo mã VietQR...</span>
              </>
            ) : (
              <>
                <QrCode className="h-4 w-4" />
                <span>Nạp ngay {activeCoinAmount} Coin</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Top-up VietQR Modal / Inline View if generated */}
      {topupOrder && (
        <PaymentQrPanel
          payment={{
            ...topupOrder,
            status: topupStatus,
            transfer_code: topupOrder.transfer_code || topupOrder.payment_code,
            qr_url: topupOrder.qr_url || '',
            amount_vnd: topupOrder.amount_vnd,
            coin_amount: topupOrder.coin_amount,
            purpose: 'wallet_topup',
          }}
          onRenew={handleRenewTopup}
          isRenewing={isRenewingTopup}
          renewError={renewError}
          onClose={() => {
            setTopupOrder(null);
            topupAttemptRef.current = null;
          }}
          onStatusExpire={() => {
            // Ask the server once more before settling on expired. This avoids
            // missing an Admin confirmation that arrived at the countdown edge.
            void refetchTopupStatus();
          }}
        />
      )}

      {/* Bottom Section: Transaction Ledger */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">
              Lịch sử giao dịch Ví Coin
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Sổ cái minh bạch mọi biến động số dư nạp, mua gói, hoàn tiền hoặc điều chỉnh.
            </p>
          </div>
          <button
            type="button"
            onClick={() => loadTransactions(page)}
            className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoadingTxs ? 'animate-spin' : ''}`} />
            <span>Làm mới</span>
          </button>
        </div>

        {isLoadingTxs ? (
          <div className="py-8 text-center text-xs text-zinc-400">
            <Loader2 className="h-5 w-5 animate-spin text-amber-500 mx-auto mb-2" />
            <span>Đang tải sổ cái giao dịch...</span>
          </div>
        ) : transactions.length === 0 ? (
          <div className="rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white/75 dark:bg-zinc-900/55 p-4 sm:p-5">
            <div className="text-center">
              <div className="mx-auto mb-2.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <Coins className="h-5 w-5" />
              </div>
              <p className="text-sm font-bold text-zinc-900 dark:text-white">Ví của bạn chưa có giao dịch</p>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Giao dịch đầu tiên sẽ xuất hiện tại đây sau khi được xác nhận.</p>
            </div>
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-950/40 p-3.5">
                <Landmark className="mb-2 h-4 w-4 text-amber-600 dark:text-amber-400" />
                <p className="text-xs font-bold text-zinc-800 dark:text-zinc-200">1. Tạo mã VietQR</p>
                <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">Chọn số Coin cần nạp và tạo mã thanh toán riêng.</p>
              </div>
              <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-950/40 p-3.5">
                <ShieldCheck className="mb-2 h-4 w-4 text-sky-600 dark:text-sky-400" />
                <p className="text-xs font-bold text-zinc-800 dark:text-zinc-200">2. Chuyển khoản chính xác</p>
                <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">Giữ nguyên số tiền và nội dung chuyển khoản được cung cấp.</p>
              </div>
              <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-950/40 p-3.5">
                <BadgeCheck className="mb-2 h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                <p className="text-xs font-bold text-zinc-800 dark:text-zinc-200">3. Nhận Coin sau xác nhận</p>
                <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">Số dư chỉ cập nhật khi giao dịch đã được hệ thống xác nhận.</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="overflow-hidden rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60">
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800 sm:hidden">
              {transactions.map((tx) => {
                const isPositive = tx.amount_coin > 0;
                return (
                  <article key={tx.id} className="p-4 space-y-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold text-zinc-800 dark:text-zinc-200">{TRANSACTION_LABELS[tx.type] || tx.type}</p>
                        <p className="mt-0.5 text-[10px] font-mono text-zinc-400">{new Date(tx.created_at * 1000).toLocaleString('vi-VN')}</p>
                      </div>
                      <span className={`text-sm font-extrabold font-mono ${isPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-zinc-900 dark:text-white'}`}>
                        {isPositive ? `+${tx.amount_coin}` : tx.amount_coin} Coin
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl bg-zinc-50 dark:bg-zinc-950/50 px-3 py-2 text-[11px]">
                      <span className="min-w-0 truncate text-zinc-500">{tx.description || tx.reference_id || 'Không có mô tả'}</span>
                      <span className="shrink-0 font-semibold text-zinc-700 dark:text-zinc-300">Còn {tx.balance_after} Coin</span>
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="hidden overflow-x-auto sm:block">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/40 text-zinc-500 font-semibold">
                  <tr>
                    <th className="py-3 px-4">Thời gian</th>
                    <th className="py-3 px-4">Loại giao dịch</th>
                    <th className="py-3 px-4">Số lượng</th>
                    <th className="py-3 px-4">Số dư sau</th>
                    <th className="py-3 px-4">Mô tả / Tham chiếu</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {transactions.map((tx) => {
                    const isPositive = tx.amount_coin > 0;
                    return (
                      <tr key={tx.id} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30">
                        <td className="py-3 px-4 text-zinc-500 font-mono text-[11px]">
                          {new Date(tx.created_at * 1000).toLocaleString('vi-VN')}
                        </td>
                        <td className="py-3 px-4">
                          {tx.type === 'topup' && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-400">
                              <ArrowDownLeft className="h-3 w-3" />
                              <span>Nạp Coin</span>
                            </span>
                          )}
                          {tx.type === 'purchase' && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 px-2 py-0.5 text-[10px] font-bold text-amber-700 dark:text-amber-400">
                              <ArrowUpRight className="h-3 w-3" />
                              <span>Mua gói</span>
                            </span>
                          )}
                          {tx.type === 'refund' && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 px-2 py-0.5 text-[10px] font-bold text-sky-700 dark:text-sky-400">
                              <RefreshCw className="h-3 w-3" />
                              <span>Hoàn Coin</span>
                            </span>
                          )}
                          {tx.type === 'adjustment' && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 px-2 py-0.5 text-[10px] font-bold text-purple-700 dark:text-purple-400">
                              <span>Admin chỉnh</span>
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-bold font-mono">
                          <span className={isPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-zinc-900 dark:text-zinc-100'}>
                            {isPositive ? `+${tx.amount_coin}` : tx.amount_coin} Coin
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-zinc-600 dark:text-zinc-400">
                          {tx.balance_after} Coin
                        </td>
                        <td className="py-3 px-4 text-zinc-600 dark:text-zinc-300 max-w-xs truncate">
                          {tx.description || tx.reference_id || '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalTxs > limit && (
              <div className="flex items-center justify-between p-3 border-t border-zinc-100 dark:border-zinc-800 text-xs">
                <span className="text-zinc-500">
                  Hiển thị {page * limit + 1} - {Math.min((page + 1) * limit, totalTxs)} trên tổng {totalTxs} giao dịch
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    disabled={page === 0}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    className="p-1 rounded-lg border border-zinc-200 dark:border-zinc-700 disabled:opacity-40"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="px-2 font-semibold text-zinc-800 dark:text-zinc-200">
                    Trang {page + 1} / {Math.ceil(totalTxs / limit)}
                  </span>
                  <button
                    type="button"
                    disabled={(page + 1) * limit >= totalTxs}
                    onClick={() => setPage((p) => p + 1)}
                    className="p-1 rounded-lg border border-zinc-200 dark:border-zinc-700 disabled:opacity-40"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
