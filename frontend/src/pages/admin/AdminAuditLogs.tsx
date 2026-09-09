import React, { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw,
  AlertCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Code,
  Eye,
} from 'lucide-react';
import { Modal } from '../../components/admin/Modal';
import { fetchAdminAuditLogs } from '../../api/adminEndpoints';
import type { AdminAuditLog } from '../../types/admin';

export const AdminAuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [limit] = useState(10);
  const [actionFilter, setActionFilter] = useState('');
  const [entityFilter, setEntityFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Detail / JSON Modal
  const [selectedLog, setSelectedLog] = useState<AdminAuditLog | null>(null);

  const loadLogs = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await fetchAdminAuditLogs({
        action: actionFilter,
        entity_type: entityFilter,
        page,
        limit,
      });
      if (res.success) {
        setLogs(res.items);
        setTotal(res.pagination.total);
        const nextPages = Math.max(1, res.pagination.pages);
        setPages(nextPages);
        if (page > nextPages) setPage(nextPages);
      }
    } catch (err: any) {
      setError(err.message || 'Không thể tải nhật ký thao tác.');
    } finally {
      setIsLoading(false);
    }
  }, [actionFilter, entityFilter, page, limit]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const formatDate = (timestamp: number) => {
    if (!timestamp) return '---';
    return new Date(timestamp * 1000).toLocaleString('vi-VN');
  };

  const getActionBadge = (action: string) => {
    if (action.includes('adjust') || action.includes('wallet')) {
      return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    }
    if (action.includes('status') || action.includes('delete')) {
      return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    }
    if (action.includes('confirm') || action.includes('create') || action.includes('approve')) {
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    }
    return 'bg-zinc-800 text-zinc-300 border-zinc-700';
  };

  return (
    <div className="space-y-6">
      {/* Filters Header */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-400">Hành động:</span>
            <input
              type="text"
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
              placeholder="VD: wallet_adjust..."
              className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-400">Thực thể:</span>
            <select
              value={entityFilter}
              onChange={(e) => {
                setEntityFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
            >
              <option value="">Tất cả thực thể</option>
              <option value="user">User (Người dùng)</option>
              <option value="payment">Payment (Thanh toán)</option>
              <option value="plan">Plan (Gói dịch vụ)</option>
              <option value="review">Review (Đánh giá)</option>
              <option value="site_settings">Settings (Hệ thống)</option>
              <option value="account">Account Pool</option>
            </select>
          </div>
        </div>

        <button
          type="button"
          onClick={loadLogs}
          disabled={isLoading}
          className="flex items-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs font-semibold text-zinc-300 hover:text-white transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
          <span>Làm mới</span>
        </button>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Audit Logs Table */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 shadow-xl backdrop-blur-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/60 text-zinc-400">
                <th className="py-3 px-4 font-semibold">ID</th>
                <th className="py-3 px-4 font-semibold">Thời gian</th>
                <th className="py-3 px-4 font-semibold">Admin thực hiện</th>
                <th className="py-3 px-4 font-semibold">Hành động</th>
                <th className="py-3 px-4 font-semibold">Đối tượng</th>
                <th className="py-3 px-4 font-semibold">Mã đối tượng</th>
                <th className="py-3 px-4 font-semibold">IP / Thiết bị</th>
                <th className="py-3 px-4 font-semibold text-right">Chi tiết</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-zinc-500">
                    <Loader2 className="h-6 w-6 animate-spin text-amber-500 mx-auto mb-2" />
                    <span>Đang tải nhật ký kiểm toán...</span>
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-zinc-500">
                    Không có nhật ký nào được ghi nhận.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-zinc-800/40 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-zinc-500">#{log.id}</td>
                    <td className="py-3 px-4 text-zinc-400 whitespace-nowrap">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-bold text-white">
                        {log.admin_username || `Admin #${log.admin_user_id}`}
                      </div>
                      <div className="text-[10px] text-zinc-500">{log.admin_email}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border font-mono ${getActionBadge(log.action)}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-semibold text-zinc-300 uppercase">
                      {log.entity_type}
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-400">
                      {log.entity_id || '---'}
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-zinc-500 truncate max-w-[150px]" title={`${log.ip_address} | ${log.user_agent}`}>
                      {log.ip_address || '---'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedLog(log)}
                        className="rounded-lg border border-zinc-700 bg-zinc-800 p-1.5 text-zinc-300 hover:border-amber-500 hover:text-amber-400 transition-colors"
                        title="Xem payload JSON"
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </button>
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
            Tổng cộng: <span className="font-bold text-zinc-200">{total}</span> nhật ký (Trang {page}/{pages || 1})
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

      {/* JSON Payload Modal */}
      {selectedLog && (
        <Modal
          isOpen={Boolean(selectedLog)}
          onClose={() => setSelectedLog(null)}
          title={`Chi Tiết Nhật Ký Thao Tác #${selectedLog.id}`}
          maxWidth="lg"
        >
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-2 gap-3 rounded-2xl bg-zinc-950 border border-zinc-800 p-3">
              <div>
                <span className="text-zinc-500 block">Admin:</span>
                <span className="font-bold text-white">{selectedLog.admin_username} (#{selectedLog.admin_user_id})</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Thời gian:</span>
                <span className="text-zinc-300">{formatDate(selectedLog.created_at)}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Hành động:</span>
                <span className="font-mono text-amber-400 font-bold">{selectedLog.action}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Thực thể:</span>
                <span className="text-zinc-300">{selectedLog.entity_type} {selectedLog.entity_id ? `(${selectedLog.entity_id})` : ''}</span>
              </div>
            </div>

            <div>
              <span className="font-bold text-zinc-300 mb-1.5 block flex items-center gap-1.5">
                <Code className="h-4 w-4 text-amber-500" />
                <span>Dữ liệu chi tiết (JSON Payload - Đã Redact Secrets):</span>
              </span>
              <pre className="max-h-60 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950 p-3 font-mono text-[11px] text-zinc-300">
                {JSON.stringify(selectedLog.details, null, 2)}
              </pre>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
