import React, { useState, useEffect, useCallback } from 'react';
import {
  Clock,
  Cpu,
  RefreshCw,
  AlertCircle,
  Loader2,
  Activity,
  Layers,
} from 'lucide-react';
import { fetchAdminQueue } from '../../api/adminEndpoints';
import type { AdminQueueItem } from '../../types/admin';
import { AdminPagination, ADMIN_PAGE_SIZE } from '../../components/admin/AdminPagination';

export const AdminQueue: React.FC = () => {
  const [items, setItems] = useState<AdminQueueItem[]>([]);
  const [page, setPage] = useState(1);
  const [activeWorkers, setActiveWorkers] = useState(0);
  const [totalInQueue, setTotalInQueue] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadQueue = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await fetchAdminQueue();
      if (res.success) {
        const queueItems = res.items || res.snapshot?.items || [];
        const workers = res.active_workers ?? res.snapshot?.active_workers ?? 0;
        const totalQ = res.total_in_queue ?? res.snapshot?.total_in_queue ?? queueItems.length;
        setItems(queueItems);
        setActiveWorkers(workers);
        setTotalInQueue(totalQ);
      }
    } catch (err: any) {
      setError(err.message || 'Không thể lấy thông tin hàng đợi.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadQueue();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadQueue]);

  const pages = Math.max(1, Math.ceil(items.length / ADMIN_PAGE_SIZE));
  const visibleItems = items.slice((page - 1) * ADMIN_PAGE_SIZE, page * ADMIN_PAGE_SIZE);

  useEffect(() => {
    setPage((current) => Math.min(current, pages));
  }, [pages]);

  const formatDate = (timestamp: number) => {
    if (!timestamp) return '---';
    return new Date(timestamp * 1000).toLocaleTimeString('vi-VN');
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'processing':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/30 animate-pulse';
      case 'waiting':
      case 'queued':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'completed':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'error':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      default:
        return 'bg-zinc-800 text-zinc-400 border-zinc-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-zinc-400">Luồng Xử Lý (Workers)</span>
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
              <Cpu className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-white">
            {activeWorkers} <span className="text-xs font-normal text-zinc-400">luồng hoạt động</span>
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-zinc-400">Yêu Cầu Trong Hàng Đợi</span>
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
              <Clock className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-amber-400">
            {totalInQueue} <span className="text-xs font-normal text-zinc-400">yêu cầu chờ xử lý</span>
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-zinc-400">Tần Suất Cập Nhật</span>
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-300 font-semibold">Tự động làm mới mỗi 5s</span>
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500"
              />
            </label>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Queue Table */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 shadow-xl backdrop-blur-md overflow-hidden">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4 bg-zinc-950/40">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Layers className="h-4 w-4 text-amber-400" />
            <span>Danh Sách Yêu Cầu Cấp Phép Hiện Tại</span>
          </h3>
          <button
            type="button"
            onClick={loadQueue}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-700"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
            <span>Làm mới</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400 bg-zinc-950/60">
                <th className="py-3 px-4 font-semibold">Vị trí</th>
                <th className="py-3 px-4 font-semibold">Locket Username</th>
                <th className="py-3 px-4 font-semibold">Client ID</th>
                <th className="py-3 px-4 font-semibold">Nền tảng</th>
                <th className="py-3 px-4 font-semibold">Trạng thái</th>
                <th className="py-3 px-4 font-semibold">Thời gian ước tính</th>
                <th className="py-3 px-4 font-semibold">Đưa vào hàng</th>
                <th className="py-3 px-4 font-semibold">Lần thử</th>
                <th className="py-3 px-4 font-semibold">Lỗi / Ghi chú</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {isLoading && items.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-zinc-500">
                    <Loader2 className="h-6 w-6 animate-spin text-amber-500 mx-auto mb-2" />
                    <span>Đang kiểm tra hàng đợi...</span>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-zinc-500">
                    Hàng đợi hiện đang trống (Không có tác vụ nào đang chờ).
                  </td>
                </tr>
              ) : (
                visibleItems.map((item, idx) => (
                  <tr key={item.client_id || idx} className="hover:bg-zinc-800/40 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-amber-400">
                      #{item.position || (page - 1) * ADMIN_PAGE_SIZE + idx + 1}
                    </td>
                    <td className="py-3 px-4 font-bold text-white">
                      {item.username}
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-zinc-400 truncate max-w-[140px]" title={item.client_id}>
                      {item.client_id}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${item.platform === 'ios' ? 'bg-zinc-800 text-zinc-300 border border-zinc-700' : 'bg-emerald-950 text-emerald-300 border border-emerald-800'}`}>
                        {item.platform ? item.platform.toUpperCase() : 'IOS'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${getStatusBadge(item.status)}`}>
                        {item.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-zinc-300">
                      {item.estimated_time ? `~${item.estimated_time}s` : '---'}
                    </td>
                    <td className="py-3 px-4 text-zinc-400 whitespace-nowrap">
                      {formatDate(item.created_at)}
                    </td>
                    <td className="py-3 px-4 text-zinc-400">
                      {item.attempts || 0}
                    </td>
                    <td className="py-3 px-4 font-mono text-rose-400 text-[11px] truncate max-w-[180px]" title={item.error || ''}>
                      {item.error || '---'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <AdminPagination page={page} pages={pages} total={items.length} itemLabel="yêu cầu" onPageChange={setPage} />
      </div>
    </div>
  );
};
