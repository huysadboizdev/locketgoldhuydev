import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search,
  CheckCircle2,
  XCircle,
  RefreshCw,
  AlertCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Modal } from '../../components/admin/Modal';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { ApiError } from '../../api/client';
import {
  fetchAdminPayments,
  manuallyConfirmAdminPayment,
  rejectAdminPayment,
} from '../../api/adminEndpoints';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

export const AdminPayments: React.FC = () => {
  const [payments, setPayments] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [limit] = useState(10);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [purposeFilter, setPurposeFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Confirm Payment Modal
  const [confirmModalPayment, setConfirmModalPayment] = useState<any | null>(null);
  const [bankTxId, setBankTxId] = useState('');
  const [manualReason, setManualReason] = useState('');
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const manualReasonRef = useRef<HTMLTextAreaElement | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  // Reject Payment Modal
  const [rejectModalPayment, setRejectModalPayment] = useState<any | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [isRejecting, setIsRejecting] = useState(false);

  const loadPayments = useCallback(async (silent = false) => {
    try {
      if (!silent) {
        setIsLoading(true);
        setError(null);
      }
      const res = await fetchAdminPayments({
        q: searchQuery,
        status: statusFilter,
        purpose: purposeFilter,
        page,
        limit,
      });
      if (res.success) {
        setPayments(res.items);
        setTotal(res.pagination.total);
        const nextPages = Math.max(1, res.pagination.pages);
        setPages(nextPages);
        if (page > nextPages) setPage(nextPages);
      }
    } catch (err: any) {
      if (!silent) setError(err.message || 'Không thể tải danh sách thanh toán.');
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [searchQuery, statusFilter, purposeFilter, page, limit]);

  useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  useLiveRefresh(() => loadPayments(true), 8_000);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadPayments();
  };

  const handleConfirmAction = async () => {
    if (!confirmModalPayment) return;
    if (manualReason.trim().length < 5) {
      setConfirmError('Vui lòng nhập lý do xác nhận thủ công, tối thiểu 5 ký tự.');
      manualReasonRef.current?.focus();
      return;
    }
    try {
      setIsConfirming(true);
      setConfirmError(null);
      await manuallyConfirmAdminPayment(
        confirmModalPayment.id,
        manualReason.trim(),
        bankTxId.trim() || undefined,
      );
      setConfirmModalPayment(null);
      setBankTxId('');
      setManualReason('');
      loadPayments();
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 404) {
        setConfirmError(
          'Backend đang chạy phiên bản cũ hoặc thiếu API xác nhận thủ công. Hãy khởi động lại backend rồi thử lại.',
        );
      } else {
        setConfirmError(err.message || 'Không thể xác nhận thủ công thanh toán.');
      }
    } finally {
      setIsConfirming(false);
    }
  };

  const handleRejectAction = async () => {
    if (!rejectModalPayment) return;
    try {
      setIsRejecting(true);
      await rejectAdminPayment(rejectModalPayment.id, rejectReason.trim() || undefined);
      setRejectModalPayment(null);
      setRejectReason('');
      loadPayments();
    } catch (err: any) {
      setError(err.message || 'Không thể từ chối thanh toán.');
    } finally {
      setIsRejecting(false);
    }
  };

  const formatVnd = (amount: number = 0) => {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
  };

  const formatDate = (timestamp: number) => {
    if (!timestamp) return '---';
    return new Date(timestamp * 1000).toLocaleString('vi-VN');
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'paid':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'pending':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse';
      case 'expired':
        return 'bg-zinc-800 text-zinc-500 border-zinc-700';
      case 'underpaid':
      case 'review_needed':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
      case 'cancelled':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      default:
        return 'bg-zinc-800 text-zinc-400 border-zinc-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Search and Filters */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 backdrop-blur-md">
        <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm theo mã chuyển khoản, mã thanh toán hoặc mã ngân hàng..."
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 pl-10 pr-4 py-2.5 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
            />
          </div>
          <button
            type="submit"
            className="rounded-xl bg-amber-500 px-4 py-2.5 text-xs font-bold text-zinc-950 hover:bg-amber-400 transition-colors shrink-0"
          >
            Tìm kiếm
          </button>
        </form>

        <div className="flex items-center gap-2.5 shrink-0 overflow-x-auto">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-300 focus:outline-none focus:border-amber-500"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="paid">Đã thanh toán (Paid)</option>
            <option value="pending">Chờ thanh toán (Pending)</option>
            <option value="expired">Hết hạn (Expired)</option>
            <option value="review_needed">Cần kiểm tra (Review)</option>
            <option value="cancelled">Đã hủy (Cancelled)</option>
          </select>

          {/* Purpose Filter */}
          <select
            value={purposeFilter}
            onChange={(e) => {
              setPurposeFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-300 focus:outline-none focus:border-amber-500"
          >
            <option value="">Tất cả mục đích</option>
            <option value="wallet_topup">Nạp ví Coin</option>
            <option value="plan_purchase">Mua gói trực tiếp</option>
          </select>

          <button
            type="button"
            onClick={() => void loadPayments()}
            disabled={isLoading}
            className="rounded-xl border border-zinc-800 bg-zinc-950 p-2.5 text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors"
            title="Tải lại"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Payments Table */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 shadow-xl backdrop-blur-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/60 text-zinc-400">
                <th className="py-3.5 px-4 font-semibold">ID</th>
                <th className="py-3.5 px-4 font-semibold">Mã Chuyển Khoản</th>
                <th className="py-3.5 px-4 font-semibold">Người dùng</th>
                <th className="py-3.5 px-4 font-semibold">Số tiền (VND)</th>
                <th className="py-3.5 px-4 font-semibold">Coin</th>
                <th className="py-3.5 px-4 font-semibold">Mục đích</th>
                <th className="py-3.5 px-4 font-semibold">Trạng thái</th>
                <th className="py-3.5 px-4 font-semibold">Mã GD Ngân Hàng</th>
                <th className="py-3.5 px-4 font-semibold">Ngày tạo</th>
                <th className="py-3.5 px-4 font-semibold text-right">Xử lý</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {isLoading ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-zinc-500">
                    <Loader2 className="h-6 w-6 animate-spin text-amber-500 mx-auto mb-2" />
                    <span>Đang tải danh sách thanh toán...</span>
                  </td>
                </tr>
              ) : payments.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-zinc-500">
                    Không tìm thấy giao dịch thanh toán nào.
                  </td>
                </tr>
              ) : (
                payments.map((pm) => (
                  <tr key={pm.id} className="hover:bg-zinc-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-zinc-400">#{pm.id}</td>
                    <td className="py-3.5 px-4 font-mono font-bold text-amber-300">
                      {pm.transfer_code || pm.payment_code}
                    </td>
                    <td className="py-3.5 px-4 text-zinc-200">
                      {pm.customer_username || pm.customer_email || `User #${pm.user_id}`}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-emerald-400">
                      {formatVnd(pm.amount_vnd)}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-amber-400">
                      {pm.coin_amount ? `${pm.coin_amount} Coin` : '---'}
                    </td>
                    <td className="py-3.5 px-4 text-zinc-300">
                      {pm.purpose === 'wallet_topup' ? 'Nạp Ví Coin' : 'Mua Gói'}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${getStatusBadge(pm.status)}`}>
                        {pm.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[11px] text-zinc-400">
                      {pm.bank_transaction_id || '---'}
                    </td>
                    <td className="py-3.5 px-4 text-zinc-400 whitespace-nowrap">
                      {formatDate(pm.created_at)}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {pm.status === 'pending' || pm.status === 'expired' || pm.status === 'underpaid' || pm.status === 'review_needed' ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setConfirmModalPayment(pm);
                              setBankTxId('');
                              setManualReason('');
                              setConfirmError(null);
                            }}
                            className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-1 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                            title="Xác nhận thanh toán thủ công"
                          >
                            <CheckCircle2 className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setRejectModalPayment(pm);
                              setRejectReason('');
                            }}
                            className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-1 text-rose-400 hover:bg-rose-500/20 transition-colors"
                            title="Từ chối / Hủy giao dịch"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        </div>
                      ) : (
                        <span className="text-[11px] text-zinc-400">Đã xong</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex items-center justify-between border-t border-zinc-800 px-4 py-3 bg-zinc-950/40 text-xs text-zinc-400">
          <div>
            Tổng cộng: <span className="font-bold text-zinc-200">{total}</span> giao dịch (Trang {page}/{pages || 1})
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-2 font-bold text-zinc-200">{page}</span>
            <button
              type="button"
              disabled={page >= pages || isLoading}
              onClick={() => setPage((p) => Math.min(p + 1, pages))}
              className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Confirm Payment Modal */}
      {confirmModalPayment && (
        <Modal
          isOpen={Boolean(confirmModalPayment)}
          onClose={() => setConfirmModalPayment(null)}
          title="Xác Nhận Thanh Toán Thủ Công"
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-amber-200">
              Chỉ xác nhận sau khi bạn đã tự kiểm tra tiền thực nhận. Thao tác này không phụ thuộc SePay và có thể khôi phục giao dịch đã hết hạn.
            </div>

            {confirmError && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300">
                {confirmError}
              </div>
            )}
            <div className="rounded-xl bg-zinc-950 border border-zinc-800 p-3 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-zinc-500">Mã chuyển khoản:</span>
                <span className="font-mono font-bold text-amber-400">{confirmModalPayment.transfer_code}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Số tiền xác nhận:</span>
                <span className="font-bold text-emerald-400">{formatVnd(confirmModalPayment.amount_vnd)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Cộng Coin / Kích hoạt:</span>
                <span className="font-bold text-zinc-200">
                  {confirmModalPayment.purpose === 'wallet_topup' ? `+${confirmModalPayment.coin_amount} Coin vào ví` : 'Kích hoạt gói'}
                </span>
              </div>
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1">
                Mã giao dịch ngân hàng (tùy chọn):
              </label>
              <input
                type="text"
                value={bankTxId}
                onChange={(e) => setBankTxId(e.target.value)}
                placeholder="VD: FT24098192837..."
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1">
                Lý do xác nhận thủ công *
              </label>
              <textarea
                ref={manualReasonRef}
                value={manualReason}
                onChange={(e) => {
                  setManualReason(e.target.value);
                  if (e.target.value.trim().length >= 5) setConfirmError(null);
                }}
                maxLength={500}
                rows={3}
                placeholder="VD: Đã kiểm tra sao kê ngân hàng, SePay hết lượt API."
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
              />
              <div className="mt-1 flex justify-between text-[10px] text-zinc-500">
                <span>Tối thiểu 5 ký tự để lưu vào nhật ký kiểm toán.</span>
                <span>{manualReason.trim().length}/500</span>
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setConfirmModalPayment(null)}
                className="rounded-xl border border-zinc-700 bg-zinc-800 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-700"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleConfirmAction}
                disabled={isConfirming}
                className="flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {isConfirming && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>Xác nhận thủ công</span>
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Reject Payment Dialog */}
      {rejectModalPayment && (
        <ConfirmDialog
          isOpen={Boolean(rejectModalPayment)}
          onClose={() => setRejectModalPayment(null)}
          onConfirm={handleRejectAction}
          title="Từ Chối Giao Dịch Thanh Toán"
          message={`Hủy bỏ giao dịch mã ${rejectModalPayment.transfer_code} (${formatVnd(rejectModalPayment.amount_vnd)})?`}
          confirmText="Hủy giao dịch"
          isDanger={true}
          isLoading={isRejecting}
        />
      )}
    </div>
  );
};
