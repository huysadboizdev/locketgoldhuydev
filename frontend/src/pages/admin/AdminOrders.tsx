import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  RefreshCw,
  AlertCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Play,
  CheckCircle2,
  ExternalLink,
  Ban,
  RotateCcw,
  Eye,
  X,
  Apple,
  Smartphone,
  Info,
  Clock,
} from 'lucide-react';
import {
  fetchAdminOrders,
  startManualAdminOrder,
  completeManualAdminOrder,
  cancelManualAdminOrder,
  refundManualAdminOrder,
} from '../../api/adminEndpoints';
import { AdminActivationOrder } from '../../types/admin';
import { ModalPortal } from '../../components/common/ModalPortal';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

export const AdminOrders: React.FC = () => {
  const [orders, setOrders] = useState<AdminActivationOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [limit] = useState(10);
  const [manualPendingCount, setManualPendingCount] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [platformFilter, setPlatformFilter] = useState('');
  const [fulfillmentFilter, setFulfillmentFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Detail Modal
  const [detailOrder, setDetailOrder] = useState<AdminActivationOrder | null>(null);

  // Action Modals State
  const [actionType, setActionType] = useState<'start' | 'complete' | 'cancel' | 'refund' | null>(null);
  const [targetOrder, setTargetOrder] = useState<AdminActivationOrder | null>(null);
  const [actionNote, setActionNote] = useState('');
  const [actionReason, setActionReason] = useState('');
  const [confirmedExternal, setConfirmedExternal] = useState(false);
  const [refundRef, setRefundRef] = useState('');
  const [isSubmittingAction, setIsSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadOrders = useCallback(async (silent = false) => {
    try {
      if (!silent) {
        setIsLoading(true);
        setError(null);
      }
      const res = await fetchAdminOrders({
        q: searchQuery,
        status: statusFilter,
        platform: platformFilter,
        fulfillment_mode: fulfillmentFilter,
        page,
        limit,
      });
      if (res.success) {
        setOrders(res.items);
        setTotal(res.pagination.total);
        const nextPages = Math.max(1, res.pagination.pages);
        setPages(nextPages);
        if (page > nextPages) setPage(nextPages);
        if (typeof res.manual_pending_count === 'number') {
          setManualPendingCount(res.manual_pending_count);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Không thể tải danh sách đơn kích hoạt.';
      if (!silent) setError(msg);
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [searchQuery, statusFilter, platformFilter, fulfillmentFilter, page, limit]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  useLiveRefresh(() => loadOrders(true), 8_000);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadOrders();
  };

  const handleQuickFilterManualPending = () => {
    setFulfillmentFilter('manual_contact');
    setStatusFilter('paid');
    setPage(1);
  };

  const formatDate = (timestamp?: number | null) => {
    if (!timestamp) return '—';
    return new Date(timestamp * 1000).toLocaleString('vi-VN');
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'processing':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/30 animate-pulse';
      case 'queued':
      case 'awaiting_queue':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'paid':
        return 'bg-amber-500/15 text-amber-300 border-amber-500/40 font-bold';
      case 'awaiting_payment':
        return 'bg-zinc-800 text-zinc-400 border-zinc-700';
      case 'failed':
      case 'cancelled':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      case 'refunded':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
      default:
        return 'bg-zinc-800 text-zinc-400 border-zinc-700';
    }
  };

  const openActionModal = (order: AdminActivationOrder, type: 'start' | 'complete' | 'cancel' | 'refund') => {
    setTargetOrder(order);
    setActionType(type);
    setActionNote('');
    setActionReason('');
    setConfirmedExternal(false);
    setRefundRef('');
    setActionError(null);
  };

  const closeActionModal = () => {
    setActionType(null);
    setTargetOrder(null);
    setActionError(null);
    setIsSubmittingAction(false);
  };

  const handleSubmitAction = async () => {
    if (!targetOrder || !actionType) return;
    setIsSubmittingAction(true);
    setActionError(null);

    try {
      if (actionType === 'start') {
        await startManualAdminOrder(targetOrder.id, actionNote.trim() || undefined);
      } else if (actionType === 'complete') {
        await completeManualAdminOrder(targetOrder.id, actionNote.trim() || undefined);
      } else if (actionType === 'cancel') {
        if (!actionReason.trim() || actionReason.trim().length < 5) {
          setActionError('Vui lòng nhập lý do hủy đơn chi tiết (tối thiểu 5 ký tự).');
          setIsSubmittingAction(false);
          return;
        }
        await cancelManualAdminOrder(targetOrder.id, actionReason.trim());
      } else if (actionType === 'refund') {
        if (!actionReason.trim() || actionReason.trim().length < 5) {
          setActionError('Vui lòng nhập lý do hoàn tiền (tối thiểu 5 ký tự).');
          setIsSubmittingAction(false);
          return;
        }
        if (targetOrder.payment_method === 'qr' && !confirmedExternal) {
          setActionError('Vui lòng tích xác nhận đã chuyển khoản hoàn tiền bên ngoài cho khách.');
          setIsSubmittingAction(false);
          return;
        }
        if (targetOrder.payment_method === 'qr' && refundRef.trim().length < 3) {
          setActionError('Vui lòng nhập mã tham chiếu giao dịch hoàn tiền (tối thiểu 3 ký tự).');
          setIsSubmittingAction(false);
          return;
        }
        await refundManualAdminOrder(
          targetOrder.id,
          actionReason.trim(),
          confirmedExternal,
          refundRef.trim() || undefined
        );
      }

      closeActionModal();
      await loadOrders();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Thao tác thất bại.';
      if (msg.includes('invalid_state_transition') || msg.includes('409') || msg.includes('Conflict')) {
        setActionError('Trạng thái đơn hàng đã bị thay đổi bởi quản trị viên khác. Hệ thống sẽ làm mới danh sách.');
        setTimeout(() => {
          closeActionModal();
          loadOrders();
        }, 2000);
      } else {
        setActionError(msg);
      }
    } finally {
      setIsSubmittingAction(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Manual Pending Alert Banner */}
      {manualPendingCount > 0 && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
              <Clock className="h-5 w-5 animate-pulse" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-amber-300">
                Có {manualPendingCount} đơn thủ công đang chờ xử lý!
              </h4>
              <p className="text-xs text-amber-400/80">
                Các đơn này đã thanh toán và đang chờ Quản trị viên liên hệ qua Zalo / Facebook để kích hoạt.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleQuickFilterManualPending}
            className="rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 hover:bg-amber-400 transition-colors shrink-0 shadow-sm"
          >
            Lọc đơn cần xử lý ngay
          </button>
        </div>
      )}

      {/* Search and Filters */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 backdrop-blur-md">
        <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm theo Locket Username, Zalo hoặc Client ID..."
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
            <option value="paid">Chờ xử lý (Paid)</option>
            <option value="processing">Đang kích hoạt (Processing)</option>
            <option value="completed">Hoàn tất (Completed)</option>
            <option value="queued">Trong hàng đợi (Queued)</option>
            <option value="awaiting_payment">Chờ thanh toán</option>
            <option value="failed">Thất bại (Failed)</option>
            <option value="refunded">Đã hoàn tiền (Refunded)</option>
            <option value="cancelled">Đã hủy (Cancelled)</option>
          </select>

          {/* Fulfillment Filter */}
          <select
            value={fulfillmentFilter}
            onChange={(e) => {
              setFulfillmentFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-300 focus:outline-none focus:border-amber-500"
          >
            <option value="">Tất cả hình thức</option>
            <option value="manual_contact">Admin xử lý thủ công</option>
            <option value="auto_activation">Kích hoạt tự động</option>
            <option value="apk_download">Tải tệp APK Android</option>
          </select>

          {/* Platform Filter */}
          <select
            value={platformFilter}
            onChange={(e) => {
              setPlatformFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-300 focus:outline-none focus:border-amber-500"
          >
            <option value="">Tất cả nền tảng</option>
            <option value="ios">iOS</option>
            <option value="android">Android</option>
          </select>

          <button
            type="button"
            onClick={() => void loadOrders()}
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

      {/* Orders Table */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 shadow-xl backdrop-blur-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/60 text-zinc-400">
                <th className="py-3.5 px-4 font-semibold">Mã Đơn</th>
                <th className="py-3.5 px-4 font-semibold">Tài Khoản KH</th>
                <th className="py-3.5 px-4 font-semibold">Đích xử lý / Liên hệ</th>
                <th className="py-3.5 px-4 font-semibold">Gói Dịch Vụ</th>
                <th className="py-3.5 px-4 font-semibold">Hình thức</th>
                <th className="py-3.5 px-4 font-semibold">Thanh toán</th>
                <th className="py-3.5 px-4 font-semibold">Trạng thái</th>
                <th className="py-3.5 px-4 font-semibold">Thời gian tạo</th>
                <th className="py-3.5 px-4 font-semibold text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-zinc-500">
                    <Loader2 className="h-6 w-6 animate-spin text-amber-500 mx-auto mb-2" />
                    <span>Đang tải danh sách đơn kích hoạt...</span>
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-zinc-500">
                    Không tìm thấy đơn kích hoạt nào.
                  </td>
                </tr>
              ) : (
                orders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-zinc-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-zinc-300">#{ord.id}</td>
                    <td className="py-3.5 px-4 font-medium text-zinc-200">
                      {ord.user_username || ord.user_email || `User #${ord.user_id}`}
                    </td>
                    <td className="py-3.5 px-4 text-[11px]">
                      {ord.fulfillment_mode_snapshot === 'manual_contact' ? (
                        <div className="space-y-1">
                          <a className="block font-bold text-amber-300 hover:underline" href={`tel:${ord.contact_zalo}`}>
                            Zalo: {ord.contact_zalo || '—'}
                          </a>
                          {ord.contact_facebook && (
                            <a
                              className="inline-flex items-center gap-1 text-sky-400 hover:underline"
                              href={ord.contact_facebook}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Facebook <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      ) : ord.fulfillment_mode_snapshot === 'apk_download' ? (
                        <span className="font-bold text-emerald-300">Cấp quyền tải APK</span>
                      ) : (
                        <span className="font-mono font-bold text-amber-300">
                          {ord.locket_username ? `@${ord.locket_username}` : '—'}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-zinc-200">
                      <div className="font-semibold">{ord.plan_name_snapshot}</div>
                      <div className="text-[10px] text-zinc-500">{ord.duration_days_snapshot} ngày</div>
                    </td>
                    <td className="py-3.5 px-4">
                      {ord.fulfillment_mode_snapshot === 'manual_contact' ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 text-[10px] font-bold text-amber-300">
                          Admin xử lý
                        </span>
                      ) : ord.fulfillment_mode_snapshot === 'apk_download' ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                          Tải APK
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 border border-sky-500/30 px-2 py-0.5 text-[10px] font-bold text-sky-300">
                          Tự động
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-zinc-200">
                        {ord.payment_method === 'coin'
                          ? `${ord.price_coin_snapshot} Coin`
                          : `${new Intl.NumberFormat('vi-VN').format(ord.price_vnd_snapshot)} đ`}
                      </div>
                      <div className="text-[10px] text-zinc-500 uppercase">{ord.payment_method}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${getStatusBadge(ord.status)}`}>
                        {ord.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-zinc-400 whitespace-nowrap">
                      {formatDate(ord.created_at)}
                    </td>
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => setDetailOrder(ord)}
                          className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors"
                          title="Xem chi tiết"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>

                        {/* Admin Start Action */}
                        {ord.fulfillment_mode_snapshot === 'manual_contact' && ord.status === 'paid' && (
                          <button
                            type="button"
                            onClick={() => openActionModal(ord, 'start')}
                            className="inline-flex items-center gap-1 rounded-lg bg-sky-500/20 border border-sky-500/40 px-2 py-1 text-[11px] font-bold text-sky-300 hover:bg-sky-500/30 transition-colors"
                            title="Nhận xử lý đơn"
                          >
                            <Play className="h-3 w-3" />
                            <span>Nhận</span>
                          </button>
                        )}

                        {/* Admin Complete Action */}
                        {ord.fulfillment_mode_snapshot === 'manual_contact' && ord.status === 'processing' && (
                          <button
                            type="button"
                            onClick={() => openActionModal(ord, 'complete')}
                            className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/20 border border-emerald-500/40 px-2 py-1 text-[11px] font-bold text-emerald-300 hover:bg-emerald-500/30 transition-colors"
                            title="Xác nhận hoàn tất"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            <span>Hoàn tất</span>
                          </button>
                        )}

                        {/* Admin Cancel Action */}
                        {ord.fulfillment_mode_snapshot === 'manual_contact'
                          && (ord.status === 'paid' || ord.status === 'processing') && (
                          <button
                            type="button"
                            onClick={() => openActionModal(ord, 'cancel')}
                            className="p-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition-colors"
                            title="Hủy đơn hàng"
                          >
                            <Ban className="h-3.5 w-3.5" />
                          </button>
                        )}

                        {/* Admin Refund Action */}
                        {(ord.status === 'paid' || ord.status === 'processing' || ord.status === 'failed' || ord.status === 'cancelled') && (
                          <button
                            type="button"
                            onClick={() => openActionModal(ord, 'refund')}
                            className="p-1.5 rounded-lg border border-purple-500/30 bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 transition-colors"
                            title="Hoàn tiền đơn hàng"
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
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
            Tổng cộng: <span className="font-bold text-zinc-200">{total}</span> đơn (Trang {page}/{pages || 1})
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

      {/* Order Detail Modal */}
      {detailOrder && (
        <ModalPortal
          isOpen
          onClose={() => setDetailOrder(null)}
          ariaLabelledBy="admin-order-detail-title"
          className="max-w-xl !rounded-3xl !border !border-zinc-800 !bg-zinc-900 !text-zinc-100"
          backdropClassName="bg-black/70 backdrop-blur-sm"
        >
          <div className="space-y-5 p-5 sm:p-6">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-3">
                <h4 id="admin-order-detail-title" className="text-base font-bold text-white">
                  Chi tiết đơn #{detailOrder.id}
                </h4>
                <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${getStatusBadge(detailOrder.status)}`}>
                  {detailOrder.status}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setDetailOrder(null)}
                className="flex h-11 w-11 items-center justify-center rounded-xl text-zinc-400 hover:text-white hover:bg-zinc-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-4 space-y-2">
                <span className="font-bold text-amber-400 uppercase tracking-wider text-[10px] block">Khách hàng</span>
                <div>
                  <span className="text-zinc-500">Username: </span>
                  <span className="font-semibold text-zinc-200">{detailOrder.user_username || '—'}</span>
                </div>
                <div>
                  <span className="text-zinc-500">Email: </span>
                  <span className="font-semibold text-zinc-200">{detailOrder.user_email || '—'}</span>
                </div>
                <div>
                  <span className="text-zinc-500">User ID: </span>
                  <span className="font-mono text-zinc-300">#{detailOrder.user_id}</span>
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-4 space-y-2">
                <span className="font-bold text-amber-400 uppercase tracking-wider text-[10px] block">Gói & Nền tảng</span>
                <div>
                  <span className="text-zinc-500">Gói: </span>
                  <span className="font-semibold text-zinc-200">{detailOrder.plan_name_snapshot} ({detailOrder.duration_days_snapshot} ngày)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-zinc-500">Thiết bị: </span>
                  <span className="inline-flex items-center gap-1 font-semibold text-zinc-300">
                    {detailOrder.platform === 'ios' ? <Apple className="h-3 w-3" /> : <Smartphone className="h-3 w-3" />}
                    {detailOrder.platform ? detailOrder.platform.toUpperCase() : 'ALL'}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500">Hình thức: </span>
                  <span className="font-semibold text-zinc-300 uppercase">{detailOrder.fulfillment_mode_snapshot}</span>
                </div>
              </div>
            </div>

            {/* Contact / Delivery Specifics */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-4 space-y-2 text-xs">
              <span className="font-bold text-amber-400 uppercase tracking-wider text-[10px] block">Thông tin kích hoạt</span>
              {detailOrder.fulfillment_mode_snapshot === 'manual_contact' ? (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-500">Số Zalo: </span>
                    <a className="font-bold text-amber-300 hover:underline" href={`tel:${detailOrder.contact_zalo}`}>
                      {detailOrder.contact_zalo || '—'}
                    </a>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-500">Link Facebook: </span>
                    {detailOrder.contact_facebook ? (
                      <a
                        className="inline-flex items-center gap-1 text-sky-400 hover:underline"
                        href={detailOrder.contact_facebook}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {detailOrder.contact_facebook} <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : (
                      <span className="text-zinc-500">—</span>
                    )}
                  </div>
                </div>
              ) : detailOrder.fulfillment_mode_snapshot === 'apk_download' ? (
                <div className="space-y-1">
                  <p className="text-emerald-400 font-semibold">Đơn hàng cung cấp file cài đặt APK Android.</p>
                  {detailOrder.download_accessed_at && (
                    <p className="text-zinc-400 text-[11px]">Đã tải lần cuối: {formatDate(detailOrder.download_accessed_at)}</p>
                  )}
                </div>
              ) : (
                <div className="space-y-1">
                  <div>
                    <span className="text-zinc-500">Tài khoản Locket: </span>
                    <span className="font-mono font-bold text-amber-300">
                      {detailOrder.locket_username ? `@${detailOrder.locket_username}` : '—'}
                    </span>
                  </div>
                  {detailOrder.queue_client_id && (
                    <div>
                      <span className="text-zinc-500">Queue Client ID: </span>
                      <span className="font-mono text-zinc-400">{detailOrder.queue_client_id}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Payment Snapshot */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-4 space-y-2 text-xs">
              <span className="font-bold text-amber-400 uppercase tracking-wider text-[10px] block">Thanh toán</span>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-zinc-500">Phương thức: </span>
                  <span className="font-semibold text-zinc-200 uppercase">{detailOrder.payment_method}</span>
                </div>
                <div>
                  <span className="text-zinc-500">Giá: </span>
                  <span className="font-bold text-zinc-200">
                    {detailOrder.payment_method === 'coin'
                      ? `${detailOrder.price_coin_snapshot} Coin`
                      : `${new Intl.NumberFormat('vi-VN').format(detailOrder.price_vnd_snapshot)} đ`}
                  </span>
                </div>
                {detailOrder.payment_code && (
                  <div>
                    <span className="text-zinc-500">Mã thanh toán: </span>
                    <span className="font-mono text-zinc-300">{detailOrder.payment_code}</span>
                  </div>
                )}
                {detailOrder.transfer_code && (
                  <div>
                    <span className="text-zinc-500">Mã chuyển khoản: </span>
                    <span className="font-mono text-zinc-300">{detailOrder.transfer_code}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Timestamps & Admin Info */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-950 p-4 space-y-1 text-[11px] text-zinc-400">
              <div>Tạo lúc: <span className="text-zinc-300">{formatDate(detailOrder.created_at)}</span></div>
              {detailOrder.updated_at && <div>Cập nhật lúc: <span className="text-zinc-300">{formatDate(detailOrder.updated_at)}</span></div>}
              {detailOrder.handled_at && <div>Admin xử lý lúc: <span className="text-zinc-300">{formatDate(detailOrder.handled_at)}</span> (Admin ID: #{detailOrder.handled_by_admin_id})</div>}
              {detailOrder.admin_note && (
                <div className="pt-2 border-t border-zinc-800 mt-2">
                  <span className="font-semibold text-zinc-300">Ghi chú Admin: </span>
                  <span className="text-amber-300">{detailOrder.admin_note}</span>
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setDetailOrder(null)}
                className="rounded-xl border border-zinc-800 bg-zinc-800 px-5 py-2.5 text-xs font-bold text-zinc-200 hover:bg-zinc-700 transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </ModalPortal>
      )}

      {/* Action Modals (Start, Complete, Cancel, Refund) */}
      {actionType && targetOrder && (
        <ModalPortal
          isOpen
          onClose={closeActionModal}
          dismissible={!isSubmittingAction}
          ariaLabelledBy="admin-order-action-title"
          className="max-w-md !rounded-3xl !border !border-zinc-800 !bg-zinc-900 !text-zinc-100"
          backdropClassName="bg-black/75 backdrop-blur-sm"
        >
          <div className="space-y-4 p-5 sm:p-6">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h4 id="admin-order-action-title" className="text-base font-bold text-white">
                {actionType === 'start' && `Nhận xử lý đơn #${targetOrder.id}`}
                {actionType === 'complete' && `Hoàn tất đơn #${targetOrder.id}`}
                {actionType === 'cancel' && `Hủy đơn #${targetOrder.id}`}
                {actionType === 'refund' && `Hoàn tiền đơn #${targetOrder.id}`}
              </h4>
              <button
                type="button"
                onClick={closeActionModal}
                disabled={isSubmittingAction}
                className="flex h-11 w-11 items-center justify-center rounded-xl text-zinc-400 hover:text-white disabled:opacity-50"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {actionError && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                <span>{actionError}</span>
              </div>
            )}

            {/* Start Action Body */}
            {actionType === 'start' && (
              <div className="space-y-3 text-xs">
                <p className="text-zinc-300">
                  Xác nhận chuyển đơn sang trạng thái <strong className="text-blue-400">Đang kích hoạt (Processing)</strong>?
                </p>
                <div>
                  <label className="block text-zinc-400 mb-1">Ghi chú quản trị viên (tùy chọn):</label>
                  <input
                    type="text"
                    value={actionNote}
                    onChange={(e) => setActionNote(e.target.value)}
                    placeholder="VD: Đã nhắn tin Zalo cho khách"
                    className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>
            )}

            {/* Complete Action Body */}
            {actionType === 'complete' && (
              <div className="space-y-3 text-xs">
                <p className="text-zinc-300">
                  Xác nhận đơn hàng đã được kích hoạt thành công và chuyển sang <strong className="text-emerald-400">Hoàn thành (Completed)</strong>?
                </p>
                <div>
                  <label className="block text-zinc-400 mb-1">Ghi chú quản trị viên (tùy chọn):</label>
                  <input
                    type="text"
                    value={actionNote}
                    onChange={(e) => setActionNote(e.target.value)}
                    placeholder="VD: Khách đã xác nhận Locket Gold hoạt động tốt"
                    className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>
            )}

            {/* Cancel Action Body */}
            {actionType === 'cancel' && (
              <div className="space-y-3 text-xs">
                <p className="text-rose-300">
                  ⚠️ Đơn hàng sẽ được chuyển sang trạng thái <strong>Đã hủy (Cancelled)</strong>. Vui lòng nhập lý do hủy đơn.
                </p>
                <div>
                  <label className="block text-zinc-400 mb-1">Lý do hủy đơn * (tối thiểu 5 ký tự):</label>
                  <textarea
                    rows={3}
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                    placeholder="VD: Không liên hệ được khách hàng qua số điện thoại Zalo..."
                    className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-rose-500"
                  />
                </div>
              </div>
            )}

            {/* Refund Action Body */}
            {actionType === 'refund' && (
              <div className="space-y-3 text-xs">
                <div className="rounded-xl border border-purple-500/30 bg-purple-500/10 p-3 text-purple-300 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold">
                    <Info className="h-4 w-4" />
                    <span>Quy trình hoàn tiền</span>
                  </div>
                  {targetOrder.payment_method === 'coin' ? (
                    <p>
                      Đơn thanh toán bằng <strong>Ví Coin</strong> ({targetOrder.price_coin_snapshot} Coin). Hệ thống sẽ tự động cộng hoàn số Coin này vào ví của khách hàng.
                    </p>
                  ) : (
                    <p>
                      Đơn thanh toán qua <strong>VietQR</strong> ({new Intl.NumberFormat('vi-VN').format(targetOrder.price_vnd_snapshot)} đ). Quản trị viên cần thực hiện chuyển khoản hoàn tiền thủ công trước khi xác nhận trên hệ thống.
                    </p>
                  )}
                </div>

                {targetOrder.payment_method === 'qr' && (
                  <div className="space-y-2 pt-1">
                    <label className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={confirmedExternal}
                        onChange={(e) => setConfirmedExternal(e.target.checked)}
                        className="mt-0.5 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-0"
                      />
                      <span className="text-zinc-200 font-semibold">
                        Tôi xác nhận đã chuyển khoản ngân hàng hoàn tiền thành công cho khách hàng *
                      </span>
                    </label>

                    <div>
                      <label className="block text-zinc-400 mb-1">Mã tham chiếu ngân hàng / FT *:</label>
                      <input
                        type="text"
                        value={refundRef}
                        onChange={(e) => setRefundRef(e.target.value)}
                        placeholder="VD: FT24090812345678"
                        className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-purple-500"
                      />
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-zinc-400 mb-1">Lý do hoàn tiền * (tối thiểu 5 ký tự):</label>
                  <textarea
                    rows={2}
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                    placeholder="VD: Khách hàng yêu cầu hủy đơn do không tương thích thiết bị..."
                    className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800">
              <button
                type="button"
                onClick={closeActionModal}
                disabled={isSubmittingAction}
                className="rounded-xl border border-zinc-800 bg-zinc-800 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleSubmitAction}
                disabled={
                  isSubmittingAction
                  || (actionType === 'cancel' && actionReason.trim().length < 5)
                  || (actionType === 'refund' && actionReason.trim().length < 5)
                  || (
                    actionType === 'refund'
                    && targetOrder.payment_method === 'qr'
                    && (!confirmedExternal || refundRef.trim().length < 3)
                  )
                }
                className={`rounded-xl px-4 py-2 text-xs font-bold text-white flex items-center gap-1.5 disabled:opacity-50 ${
                  actionType === 'start'
                    ? 'bg-sky-500 hover:bg-sky-400 text-zinc-950'
                    : actionType === 'complete'
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-zinc-950'
                    : actionType === 'cancel'
                    ? 'bg-rose-500 hover:bg-rose-400'
                    : 'bg-purple-600 hover:bg-purple-500'
                }`}
              >
                {isSubmittingAction ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Đang xử lý...</span>
                  </>
                ) : (
                  <span>
                    {actionType === 'start' && 'Xác nhận nhận xử lý'}
                    {actionType === 'complete' && 'Xác nhận hoàn tất'}
                    {actionType === 'cancel' && 'Xác nhận hủy đơn'}
                    {actionType === 'refund' && 'Xác nhận hoàn tiền'}
                  </span>
                )}
              </button>
            </div>
          </div>
        </ModalPortal>
      )}
    </div>
  );
};
