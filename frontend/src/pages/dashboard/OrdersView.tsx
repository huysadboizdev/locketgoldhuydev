import React, { useState, useEffect, useCallback } from 'react';
import {
  ActivationOrder,
  PublicDnsConfig,
} from '../../types/api';
import {
  fetchUserOrders,
  fetchPlatformConfig,
  createMobileconfigDownloadTicket,
  createApkDownloadTicket,
} from '../../api/endpoints';
import {
  CheckCircle2,
  Clock,
  Apple,
  Smartphone,
  Copy,
  Check,
  Download,
  Loader2,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  ExternalLink,
} from 'lucide-react';
import { ModalPortal } from '../../components/common/ModalPortal';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

const ORDER_STATUS_LABELS: Record<string, string> = {
  awaiting_payment: 'Chờ thanh toán',
  paid: 'Đã thanh toán',
  awaiting_queue: 'Chờ xếp hàng',
  queued: 'Đang xếp hàng',
  processing: 'Đang xử lý',
  completed: 'Hoàn thành',
  failed: 'Thất bại',
  refunded: 'Đã hoàn Coin',
  cancelled: 'Đã hủy',
};

const maskZalo = (phone?: string | null): string => {
  if (!phone) return '—';
  const digits = phone.replace(/\D/g, '');
  if (digits.length <= 6) return phone;
  return `${digits.slice(0, 3)}***${digits.slice(-4)}`;
};

const formatAccount = (order: ActivationOrder): string => {
  if (order.fulfillment_mode_snapshot === 'manual_contact') {
    return `Zalo ${maskZalo(order.contact_zalo)}`;
  }
  if (order.fulfillment_mode_snapshot === 'apk_download') {
    return 'Tải file APK';
  }
  return order.locket_username ? `@${order.locket_username}` : '—';
};

const orderStatusLabel = (order: ActivationOrder) => {
  if (order.fulfillment_mode_snapshot === 'manual_contact') {
    if (order.status === 'paid') return 'Chờ Admin tiếp nhận';
    if (order.status === 'processing') return 'Admin đang xử lý';
  }
  if (order.fulfillment_mode_snapshot === 'apk_download' && order.status === 'completed') {
    return 'Sẵn sàng tải APK';
  }
  return ORDER_STATUS_LABELS[order.status] || order.status;
};

export const OrdersView: React.FC = () => {
  const [orders, setOrders] = useState<ActivationOrder[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [totalOrders, setTotalOrders] = useState(0);
  const limit = 10;

  // Detail Modal State
  const [selectedOrder, setSelectedOrder] = useState<ActivationOrder | null>(null);
  const [platformConfig, setPlatformConfig] = useState<PublicDnsConfig | null>(null);
  const [copiedLabel, setCopiedLabel] = useState<string | null>(null);
  const [isCreatingTicket, setIsCreatingTicket] = useState(false);
  const [ticketError, setTicketError] = useState<string | null>(null);

  const loadOrders = useCallback(async (p: number, silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const res = await fetchUserOrders(limit, p * limit);
      if (res && res.success) {
        setOrders(res.items);
        setTotalOrders(res.pagination.total);
      }
    } catch {}
    finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOrders(page);
  }, [page, loadOrders]);

  useLiveRefresh(() => loadOrders(page, true), 8_000);

  useEffect(() => {
    fetchPlatformConfig()
      .then((res) => {
        if (res && res.success) {
          setPlatformConfig(res.dns);
        }
      })
      .catch(() => {});
  }, []);

  const handleCopy = (text: string, label: string) => {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(
      () => {
        setCopiedLabel(label);
        setTimeout(() => setCopiedLabel(null), 2500);
      },
      () => {}
    );
  };

  const handleDownloadTicket = async (order: ActivationOrder) => {
    setIsCreatingTicket(true);
    setTicketError(null);
    try {
      const param = { activationOrderId: order.id, clientId: order.queue_client_id || undefined };
      let res;
      if (order.platform === 'ios') {
        res = await createMobileconfigDownloadTicket(param);
      } else {
        res = await createApkDownloadTicket(param);
      }

      if (res && res.success && res.download_url) {
        window.location.href = res.download_url;
      } else {
        setTicketError(res.msg || 'Không thể tạo vé tải.');
      }
    } catch (err: any) {
      setTicketError(err.message || 'Lỗi khi yêu cầu vé tải.');
    } finally {
      setIsCreatingTicket(false);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-zinc-900 dark:text-white">
            Đơn kích hoạt Locket Gold
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Theo dõi trạng thái, tiến trình kích hoạt và lấy hướng dẫn theo thiết bị.
          </p>
        </div>
        <button
          type="button"
          onClick={() => loadOrders(page)}
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Làm mới</span>
        </button>
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-xs text-zinc-400">
          <Loader2 className="h-5 w-5 animate-spin text-amber-500 mx-auto mb-2" />
          <span>Đang tải danh sách đơn...</span>
        </div>
      ) : orders.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-zinc-300 dark:border-zinc-800 p-7 sm:p-10 text-center bg-white/60 dark:bg-zinc-900/40">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Bạn chưa có đơn kích hoạt Locket Gold nào.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60">
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800 md:hidden">
            {orders.map((ord) => (
              <article key={ord.id} className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[10px] font-mono font-bold text-zinc-400">ĐƠN #{ord.id}</p>
                    <h4 className="mt-0.5 truncate text-sm font-bold text-zinc-900 dark:text-white">{ord.plan_name_snapshot}</h4>
                    <p className="text-[11px] text-zinc-500">
                      {ord.duration_days_snapshot} ngày · {formatAccount(ord)}
                    </p>
                  </div>
                  <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${
                    ord.status === 'completed'
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                      : ord.status === 'failed' || ord.status === 'cancelled'
                      ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                      : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
                  }`}>
                    {orderStatusLabel(ord)}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 rounded-2xl bg-zinc-50 dark:bg-zinc-950/50 p-3 text-[11px]">
                  <div>
                    <span className="block text-zinc-400">Thiết bị</span>
                    <span className="mt-0.5 flex items-center gap-1 font-semibold text-zinc-700 dark:text-zinc-300">
                      {ord.platform === 'ios' ? <Apple className="h-3 w-3" /> : <Smartphone className="h-3 w-3" />}
                      {ord.platform === 'ios' ? 'iPhone/iPad' : 'Android'}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="block text-zinc-400">Thanh toán</span>
                    <span className="mt-0.5 block font-semibold text-zinc-700 dark:text-zinc-300">
                      {ord.payment_method === 'coin'
                        ? `${new Intl.NumberFormat('vi-VN').format(ord.price_coin_snapshot)} Coin`
                        : `${new Intl.NumberFormat('vi-VN').format(ord.price_vnd_snapshot)} đ`}
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedOrder(ord)}
                  className="flex min-h-11 w-full items-center justify-center gap-1.5 rounded-2xl border border-zinc-200 dark:border-zinc-700 text-xs font-bold text-zinc-700 dark:text-zinc-200"
                >
                  <Eye className="h-3.5 w-3.5" />
                  Xem chi tiết
                </button>
              </article>
            ))}
          </div>

          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/40 text-zinc-500 font-semibold">
                <tr>
                  <th className="py-3 px-4">Mã đơn</th>
                  <th className="py-3 px-4">Gói dịch vụ</th>
                  <th className="py-3 px-4">Tài khoản</th>
                  <th className="py-3 px-4">Thiết bị</th>
                  <th className="py-3 px-4">Thanh toán</th>
                  <th className="py-3 px-4">Trạng thái</th>
                  <th className="py-3 px-4 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {orders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30">
                    <td className="py-3.5 px-4 font-mono font-bold text-zinc-900 dark:text-white">
                      #{ord.id}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-semibold text-zinc-800 dark:text-zinc-200">{ord.plan_name_snapshot}</span>
                      <span className="block text-[10px] text-zinc-400">{ord.duration_days_snapshot} ngày</span>
                    </td>
                    <td className="py-3.5 px-4 font-mono font-bold text-amber-600 dark:text-amber-400">
                      {formatAccount(ord)}
                    </td>
                    <td className="py-3.5 px-4">
                      {ord.platform === 'ios' ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 px-2 py-0.5 text-[10px] font-bold text-sky-700 dark:text-sky-300">
                          <Apple className="h-3 w-3" />
                          <span>iOS</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                          <Smartphone className="h-3 w-3" />
                          <span>Android</span>
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-[11px] font-medium text-zinc-600 dark:text-zinc-400">
                        {ord.payment_method === 'coin'
                          ? `${new Intl.NumberFormat('vi-VN').format(ord.price_coin_snapshot)} Coin`
                          : `${new Intl.NumberFormat('vi-VN').format(ord.price_vnd_snapshot)} đ`}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      {ord.status === 'completed' && (
                        <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-bold text-[11px]">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          <span>{orderStatusLabel(ord)}</span>
                        </span>
                      )}
                      {ord.status === 'processing' && (
                        <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400 font-semibold text-[11px]">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          <span>{orderStatusLabel(ord)}</span>
                        </span>
                      )}
                      {ord.status === 'queued' && (
                        <span className="inline-flex items-center gap-1 text-sky-600 dark:text-sky-400 font-semibold text-[11px]">
                          <Clock className="h-3.5 w-3.5" />
                          <span>Đang xếp hàng</span>
                        </span>
                      )}
                      {ord.status === 'awaiting_payment' && (
                        <span className="text-zinc-500 font-medium text-[11px]">
                          Chờ thanh toán
                        </span>
                      )}
                      {ord.status === 'paid' && (
                        <span className="text-amber-600 dark:text-amber-400 font-semibold text-[11px]">
                          {orderStatusLabel(ord)}
                        </span>
                      )}
                      {ord.status === 'failed' && (
                        <span className="text-rose-600 dark:text-rose-400 font-bold text-[11px]">
                          Thất bại
                        </span>
                      )}
                      {ord.status === 'refunded' && (
                        <span className="text-purple-600 dark:text-purple-400 font-semibold text-[11px]">
                          Đã hoàn Coin
                        </span>
                      )}
                      {ord.status === 'cancelled' && (
                        <span className="text-zinc-500 font-semibold text-[11px]">
                          Đã hủy
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedOrder(ord)}
                        className="inline-flex items-center gap-1 rounded-xl border border-zinc-200 dark:border-zinc-700 px-3 py-1.5 text-xs font-semibold text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        <span>Xem</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalOrders > limit && (
            <div className="flex items-center justify-between p-3 border-t border-zinc-100 dark:border-zinc-800 text-xs">
              <span className="text-zinc-500">
                Hiển thị {page * limit + 1} - {Math.min((page + 1) * limit, totalOrders)} trên {totalOrders} đơn
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
                  {page + 1} / {Math.ceil(totalOrders / limit)}
                </span>
                <button
                  type="button"
                  disabled={(page + 1) * limit >= totalOrders}
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

      {/* Detail Modal */}
      {selectedOrder && (
        <ModalPortal
          isOpen
          onClose={() => setSelectedOrder(null)}
          ariaLabelledBy="user-order-detail-title"
          className="max-w-lg !rounded-3xl !border !border-zinc-200 dark:!border-zinc-800"
          backdropClassName="bg-black/50 backdrop-blur-sm"
        >
          <div className="space-y-5 p-5 sm:p-7">
            <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
              <div>
                <h4 id="user-order-detail-title" className="text-base font-bold text-zinc-900 dark:text-white">
                  Chi tiết đơn #{selectedOrder.id}
                </h4>
                <p className="text-xs text-zinc-500">
                  Thời gian tạo: {new Date(selectedOrder.created_at * 1000).toLocaleString('vi-VN')}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                className="flex h-11 w-11 items-center justify-center rounded-xl hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-400 hover:text-zinc-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Order snapshot summary */}
            <div className="rounded-2xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 p-4 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-zinc-500">Gói dịch vụ:</span>
                <span className="font-bold text-zinc-900 dark:text-white">{selectedOrder.plan_name_snapshot} ({selectedOrder.duration_days_snapshot} ngày)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Thông tin tài khoản:</span>
                <span className="font-mono font-bold text-amber-600 dark:text-amber-400">
                  {formatAccount(selectedOrder)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Thiết bị:</span>
                <span className="font-semibold text-zinc-800 dark:text-zinc-200 uppercase">
                  {selectedOrder.platform === 'ios' ? 'iPhone/iPad (iOS)' : 'Android'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Giá thanh toán:</span>
                <span className="font-bold text-zinc-900 dark:text-white">
                  {new Intl.NumberFormat('vi-VN').format(selectedOrder.price_vnd_snapshot)} đ ({new Intl.NumberFormat('vi-VN').format(selectedOrder.price_coin_snapshot)} Coin)
                </span>
              </div>
              <div className="flex justify-between pt-1 border-t border-zinc-200/50 dark:border-zinc-800">
                <span className="text-zinc-500">Trạng thái:</span>
                <span className="font-bold text-amber-600 dark:text-amber-400 uppercase">
                  {orderStatusLabel(selectedOrder)}
                </span>
              </div>
            </div>

            {/* Fulfillment Specific Guides */}
            {selectedOrder.fulfillment_mode_snapshot === 'manual_contact' ? (
              <div className="rounded-2xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/40 dark:bg-amber-950/20 p-4 space-y-3">
                <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300 font-bold text-xs">
                  <CheckCircle2 className="h-4 w-4" /> Đơn do Admin xử lý
                </div>
                <p className="text-xs text-zinc-600 dark:text-zinc-300">
                  Admin sẽ chủ động liên hệ qua số Zalo <strong>{maskZalo(selectedOrder.contact_zalo)}</strong> hoặc liên kết Facebook bạn đã cung cấp để hỗ trợ kích hoạt.
                </p>
                {selectedOrder.contact_facebook && (
                  <a href={selectedOrder.contact_facebook} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-xs font-bold text-sky-600 dark:text-sky-400 hover:underline">
                    <span>Mở liên kết Facebook đã gửi</span>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
                {selectedOrder.admin_note && (
                  <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-3 text-xs">
                    <span className="font-semibold text-zinc-700 dark:text-zinc-300">Ghi chú từ Admin:</span>
                    <p className="mt-1 text-zinc-600 dark:text-zinc-400">{selectedOrder.admin_note}</p>
                  </div>
                )}
              </div>
            ) : selectedOrder.fulfillment_mode_snapshot === 'apk_download' ? (
              /* APK DOWNLOAD VIEW - No DNS hostname, only APK download & install warning */
              <div className="rounded-2xl border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/40 dark:bg-emerald-950/20 p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-emerald-200/50 dark:border-emerald-900/40 pb-2">
                  <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300 font-bold text-xs">
                    <Smartphone className="h-4 w-4" />
                    <span>Cài đặt ứng dụng Android (APK)</span>
                  </div>
                  <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">Không cần DNS</span>
                </div>

                <p className="text-xs text-zinc-600 dark:text-zinc-300">
                  Gói dịch vụ đã sẵn sàng. Tải tệp APK bên dưới và bật quyền <strong>Cho phép cài đặt từ nguồn không xác định</strong> trong cài đặt thiết bị để cài đặt ứng dụng.
                </p>

                {selectedOrder.status === 'completed' && (
                  <button
                    type="button"
                    disabled={isCreatingTicket}
                    onClick={() => handleDownloadTicket(selectedOrder)}
                    className="gold-primary w-full rounded-xl py-2.5 text-xs font-bold flex items-center justify-center gap-1.5 transition-all"
                  >
                    {isCreatingTicket ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                    <span>Tải ứng dụng Locket Gold APK</span>
                  </button>
                )}

                <div className="rounded-xl border border-amber-300/40 bg-amber-50/60 dark:bg-amber-950/30 p-2.5 text-[11px] text-amber-700 dark:text-amber-400">
                  Lưu ý: Nếu đã cài Locket từ Google Play Store, hãy gỡ cài đặt trước khi cài đặt tệp APK này.
                </div>
              </div>
            ) : selectedOrder.platform === 'ios' ? (
              /* iOS DNS GUIDE (auto_activation) */
              <div className="rounded-2xl border border-sky-200 dark:border-sky-900/60 bg-sky-50/40 dark:bg-sky-950/20 p-4 space-y-3">
                <div className="flex items-center gap-2 text-sky-700 dark:text-sky-300 font-bold text-xs">
                  <Apple className="h-4 w-4" />
                  <span>Cài đặt cho iPhone / iPad (iOS)</span>
                </div>

                <div className="space-y-1">
                  <span className="text-[11px] text-zinc-500 font-medium">Hostname DNS NextDNS:</span>
                  <div className="flex items-center gap-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-1.5">
                    <code className="text-xs font-mono font-bold text-sky-700 dark:text-sky-300 flex-1">
                      {platformConfig?.hostname || 'Chưa cấu hình DNS'}
                    </code>
                    {platformConfig?.hostname && (
                      <button
                        type="button"
                        onClick={() => handleCopy(platformConfig.hostname!, 'modal_ios')}
                        className="p-1 rounded text-zinc-400 hover:text-zinc-700"
                      >
                        {copiedLabel === 'modal_ios' ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    )}
                  </div>
                </div>

                {selectedOrder.status === 'completed' && (
                  <button
                    type="button"
                    disabled={isCreatingTicket}
                    onClick={() => handleDownloadTicket(selectedOrder)}
                    className="gold-primary w-full rounded-xl py-2.5 text-xs font-bold flex items-center justify-center gap-1.5 transition-all"
                  >
                    {isCreatingTicket ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                    <span>Cài đặt Profile DNS NextDNS</span>
                  </button>
                )}
              </div>
            ) : (
              /* Android DNS GUIDE (auto_activation) */
              <div className="rounded-2xl border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/40 dark:bg-emerald-950/20 p-4 space-y-3">
                <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300 font-bold text-xs">
                  <Smartphone className="h-4 w-4" />
                  <span>Cài đặt Private DNS cho Android</span>
                </div>

                <div className="space-y-1">
                  <span className="text-[11px] text-zinc-500 font-medium">Tên máy chủ Private DNS:</span>
                  <div className="flex items-center gap-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-1.5">
                    <code className="text-xs font-mono font-bold text-emerald-700 dark:text-emerald-300 flex-1">
                      {platformConfig?.hostname || 'Chưa cấu hình DNS'}
                    </code>
                    {platformConfig?.hostname && (
                      <button
                        type="button"
                        onClick={() => handleCopy(platformConfig.hostname!, 'modal_and')}
                        className="p-1 rounded text-zinc-400 hover:text-zinc-700"
                      >
                        {copiedLabel === 'modal_and' ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {ticketError && (
              <p className="text-xs text-rose-500">{ticketError}</p>
            )}

            <button
              type="button"
              onClick={() => setSelectedOrder(null)}
              className="gold-secondary w-full rounded-2xl border py-2.5 text-xs font-bold"
            >
              Đóng
            </button>
          </div>
        </ModalPortal>
      )}
    </div>
  );
};
