import React, { useState, useEffect, useCallback } from 'react';
import {
  DollarSign,
  PackageCheck,
  Users,
  Coins,
  Clock,
  Star,
  TrendingUp,
  RefreshCw,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { StatCard } from '../../components/admin/StatCard';
import { fetchAdminOverview } from '../../api/adminEndpoints';
import type { AdminOverviewResponse, AdminTimeRange } from '../../types/admin';

interface AdminOverviewProps {
  onNavigateTab: (tab: any) => void;
}

export const AdminOverview: React.FC<AdminOverviewProps> = ({ onNavigateTab }) => {
  const [range, setRange] = useState<AdminTimeRange>('30d');
  const [data, setData] = useState<AdminOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const loadOverview = useCallback(async (selectedRange: AdminTimeRange) => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await fetchAdminOverview(selectedRange);
      if (res.success) {
        setData(res);
      } else {
        setError('Không thể tải số liệu tổng quan.');
      }
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối máy chủ');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview(range);
  }, [range, loadOverview]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      loadOverview(range);
    }, 15000);
    return () => clearInterval(timer);
  }, [autoRefresh, range, loadOverview]);

  const formatVnd = (amount: number = 0) => {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
  };

  const formatNum = (num: number = 0) => {
    return new Intl.NumberFormat('vi-VN').format(num);
  };

  const recentOrders = data?.recent_orders ?? data?.recent?.orders ?? [];
  const recentPayments = data?.recent_payments ?? data?.recent?.payments ?? [];

  return (
    <div className="space-y-6">
      {/* Top Filter Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-400">Khoảng thời gian:</span>
          <div className="flex rounded-xl bg-zinc-950 p-1 border border-zinc-800">
            {(['7d', '30d', '90d'] as AdminTimeRange[]).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRange(r)}
                className={`rounded-lg px-3 py-1 text-xs font-bold transition-all ${
                  range === r
                    ? 'bg-amber-500 text-zinc-950 shadow'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                {r === '7d' ? '7 Ngày' : r === '30d' ? '30 Ngày' : '90 Ngày'}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-zinc-400">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500"
            />
            <span>Tự động làm mới (15s)</span>
          </label>

          <button
            type="button"
            onClick={() => loadOverview(range)}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
            <span>Làm mới</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Cards Grid */}
      {(() => {
        const c = data?.cards;
        const paidRev = c?.paid_revenue_vnd ?? c?.payments?.revenue_vnd ?? 0;
        const topupRev = c?.topup_revenue_vnd ?? c?.payments?.topup_revenue_vnd ?? 0;
        const planRev = c?.plan_purchase_revenue_vnd ?? c?.payments?.plan_purchase_revenue_vnd ?? 0;
        const completedOrders = c?.completed_orders ?? c?.activation_orders?.completed ?? 0;
        const totalOrders = c?.total_orders ?? c?.activation_orders?.total ?? 0;
        const processingOrders = c?.processing_orders ?? c?.activation_orders?.processing ?? 0;
        const totalUsers = c?.total_users ?? 0;
        const activeUsers = c?.active_users ?? 0;
        const totalCoins = c?.total_wallet_balance_coin ?? c?.total_coin_in_wallets ?? c?.wallet?.total_balance_coin ?? 0;
        const usersWithCoin = c?.users_with_coin ?? c?.wallet?.total_users_with_coin ?? 0;
        const queueWait = c?.queue_waiting ?? c?.queue?.total_waiting ?? 0;
        const queueProc = c?.queue_processing ?? c?.queue?.total_processing ?? 0;
        const queueTotalCount = (c?.queue_waiting ?? 0) + (c?.queue_processing ?? 0) || ((c?.queue?.total_waiting ?? 0) + (c?.queue?.total_processing ?? 0));
        const avgRating = c?.average_rating ?? c?.reviews?.average_rating ?? 5.0;
        const totalReviews = c?.total_reviews ?? c?.reviews?.total ?? 0;
        const revenueSeries = data?.series ?? data?.charts?.revenue_series ?? [];

        return (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <StatCard
                title={`Doanh Thu Thực Tế (${range})`}
                value={formatVnd(paidRev)}
                subtitle={`Nạp ví: ${formatVnd(topupRev)} | Mua gói: ${formatVnd(planRev)}`}
                icon={DollarSign}
                variant="gold"
              />

              <StatCard
                title="Đơn Kích Hoạt Hoàn Tất"
                value={formatNum(completedOrders)}
                subtitle={`Tổng số đơn: ${formatNum(totalOrders)} (Đang xử lý: ${processingOrders})`}
                icon={PackageCheck}
                variant="emerald"
              />

              <StatCard
                title="Người Dùng Hoạt Động"
                value={formatNum(activeUsers)}
                subtitle={`Tổng đăng ký: ${formatNum(totalUsers)}`}
                icon={Users}
                variant="blue"
              />

              <StatCard
                title="Tổng Số Dư Coin Trong Ví"
                value={`${formatNum(totalCoins)} Coin`}
                subtitle={`Phân bổ qua ${formatNum(usersWithCoin)} tài khoản`}
                icon={Coins}
                variant="purple"
              />

              <StatCard
                title="Hàng Đợi Cấp Phép"
                value={formatNum(queueTotalCount)}
                subtitle={`Chờ: ${queueWait} | Đang cấp phép: ${queueProc}`}
                icon={Clock}
                variant="rose"
              />

              <StatCard
                title="Đánh Giá Khách Hàng"
                value={`${avgRating.toFixed(1)} ★`}
                subtitle={`Tự động công khai | Tổng: ${formatNum(totalReviews)}`}
                icon={Star}
                variant="zinc"
              />
            </div>

            {/* SVG Trend Chart */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-amber-500" />
                  <h3 className="text-sm font-bold text-white">Biểu Đồ Doanh Thu & Đơn Hàng ({range})</h3>
                </div>
                <span className="text-[11px] text-zinc-400">Đã chuẩn hóa múi giờ Asia/Bangkok (UTC+7)</span>
              </div>

              {revenueSeries && revenueSeries.length > 0 ? (
                <div className="space-y-4">
                  {/* Simple responsive bar / SVG chart */}
                  <div className="h-48 w-full flex items-end gap-1.5 pt-6 pb-2 px-2 overflow-x-auto">
                    {(() => {
                      const maxRev = Math.max(...revenueSeries.map((s: any) => s.revenue_vnd || 0), 1);
                      return revenueSeries.map((item: any, idx: number) => {
                        const heightPercent = Math.max(((item.revenue_vnd || 0) / maxRev) * 100, 4);
                        return (
                          <div
                            key={idx}
                            className="flex-1 min-w-[20px] max-w-[40px] flex flex-col items-center gap-1 group relative"
                          >
                            {/* Tooltip */}
                            <div className="pointer-events-none absolute -top-12 z-20 hidden group-hover:flex flex-col items-center rounded-lg bg-zinc-950 border border-zinc-700 px-2 py-1 text-[10px] text-white shadow-xl whitespace-nowrap">
                              <span className="font-bold">{item.date}</span>
                              <span className="text-amber-400">{formatVnd(item.revenue_vnd || 0)}</span>
                              <span className="text-zinc-400">{'orders' in item ? item.orders : item.order_count} giao dịch</span>
                            </div>

                            <div
                              style={{ height: `${heightPercent}%` }}
                              className="w-full rounded-t-md bg-gradient-to-t from-amber-600/80 to-amber-400 group-hover:from-amber-500 group-hover:to-amber-300 transition-all cursor-pointer"
                            />
                            <span className="text-[9px] text-zinc-400 truncate w-full text-center">
                              {String(item.date).slice(5)}
                            </span>
                          </div>
                        );
                      });
                    })()}
                  </div>
                </div>
              ) : (
                <div className="flex h-40 items-center justify-center text-xs text-zinc-500">
                  Chưa có dữ liệu giao dịch trong khoảng thời gian này.
                </div>
              )}
            </div>
          </>
        );
      })()}

      {/* Breakdowns & Recent Activities Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Orders */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <PackageCheck className="h-4 w-4 text-emerald-400" />
              <span>Đơn Kích Hoạt Gần Đây</span>
            </h3>
            <button
              type="button"
              onClick={() => onNavigateTab('orders')}
              className="flex items-center gap-1 text-xs font-semibold text-amber-400 hover:underline"
            >
              <span>Xem tất cả</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="flex-1 overflow-x-auto">
            {recentOrders.length > 0 ? (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-400">
                    <th className="pb-2 font-semibold">User</th>
                    <th className="pb-2 font-semibold">Gói</th>
                    <th className="pb-2 font-semibold">Platform</th>
                    <th className="pb-2 font-semibold">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {recentOrders.slice(0, 5).map((ord) => (
                    <tr key={ord.id} className="hover:bg-zinc-800/40">
                      <td className="py-2.5 font-medium text-zinc-200">
                        {ord.locket_username || ord.username || `User #${ord.user_id}`}
                      </td>
                      <td className="py-2.5 text-zinc-400">{ord.plan_name_snapshot || 'Gói VIP'}</td>
                      <td className="py-2.5">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${ord.platform === 'ios' ? 'bg-zinc-800 text-zinc-300' : 'bg-emerald-950 text-emerald-300'}`}>
                          {ord.platform ? ord.platform.toUpperCase() : 'ALL'}
                        </span>
                      </td>
                      <td className="py-2.5">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            ord.status === 'completed'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : ord.status === 'failed'
                              ? 'bg-rose-500/20 text-rose-300'
                              : 'bg-amber-500/20 text-amber-300'
                          }`}
                        >
                          {ord.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="flex h-32 items-center justify-center text-xs text-zinc-500">
                Chưa có đơn hàng nào.
              </div>
            )}
          </div>
        </div>

        {/* Recent Payments */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-amber-400" />
              <span>Giao Dịch Gần Đây</span>
            </h3>
            <button
              type="button"
              onClick={() => onNavigateTab('payments')}
              className="flex items-center gap-1 text-xs font-semibold text-amber-400 hover:underline"
            >
              <span>Xem tất cả</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="flex-1 overflow-x-auto">
            {recentPayments.length > 0 ? (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-400">
                    <th className="pb-2 font-semibold">Mã GD</th>
                    <th className="pb-2 font-semibold">Số tiền</th>
                    <th className="pb-2 font-semibold">Mục đích</th>
                    <th className="pb-2 font-semibold">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {recentPayments.slice(0, 5).map((pm) => (
                    <tr key={pm.id} className="hover:bg-zinc-800/40">
                      <td className="py-2.5 font-mono text-zinc-300">{pm.transfer_code || pm.payment_code}</td>
                      <td className="py-2.5 font-bold text-amber-400">{formatVnd(pm.amount_vnd)}</td>
                      <td className="py-2.5 text-zinc-400">
                        {pm.purpose === 'wallet_topup' ? 'Nạp Coin' : 'Mua gói trực tiếp'}
                      </td>
                      <td className="py-2.5">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            pm.status === 'paid'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : pm.status === 'pending'
                              ? 'bg-amber-500/20 text-amber-300'
                              : 'bg-zinc-800 text-zinc-400'
                          }`}
                        >
                          {pm.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="flex h-32 items-center justify-center text-xs text-zinc-500">
                Chưa có giao dịch thanh toán nào.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
