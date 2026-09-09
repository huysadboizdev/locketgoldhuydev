import React, { useCallback, useEffect, useState } from 'react';
import { Clock, CheckCircle2, AlertCircle, WifiOff } from 'lucide-react';
import { fetchRecentHistory } from '../../api/endpoints';
import { formatRelativeTime } from '../../utils/format';
import type { HistoryItem } from '../../types/api';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

export const RecentHistorySection: React.FC = () => {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetchRecentHistory();
      if (res.success) {
        setItems(res.items || []);
        setIsOffline(false);
      }
    } catch {
      setIsOffline(true);
    } finally {
      setLoading(false);
      setHasLoaded(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useLiveRefresh(load, 8_000, hasLoaded);

  return (
    <section className="mx-auto max-w-4xl px-4 sm:px-6 py-10">
      <div className="gold-card rounded-3xl border p-6 sm:p-7 backdrop-blur-sm transition-colors">
        <div className="flex items-center justify-between mb-5 border-b border-zinc-200 dark:border-zinc-800 pb-3.5">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
            <h3 className="text-sm font-bold text-zinc-900 dark:text-white tracking-wide">
              LỊCH SỬ KÍCH HOẠT GẦN NHẤT
            </h3>
          </div>
          <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
            <span className="relative flex h-2 w-2" aria-hidden="true">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Cập nhật trực tiếp
          </span>
        </div>

        {/* Loading Skeletons */}
        {loading && items.length === 0 && !isOffline && (
          <div className="space-y-2.5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 w-full animate-pulse rounded-xl bg-zinc-100 dark:bg-zinc-800/50" />
            ))}
          </div>
        )}

        {/* Offline State (distinguished from empty!) */}
        {isOffline && items.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center text-xs space-y-2 text-zinc-500 dark:text-zinc-400">
            <WifiOff className="h-5 w-5 text-amber-500" />
            <p className="font-medium text-zinc-700 dark:text-zinc-300">
              Máy chủ chưa sẵn sàng tải lịch sử kích hoạt
            </p>
            <p className="text-[11px] text-zinc-500">
              Dữ liệu sẽ tự động hiển thị khi kết nối backend được thiết lập.
            </p>
          </div>
        )}

        {/* Empty State (valid response from server, but 0 items) */}
        {!loading && !isOffline && items.length === 0 && (
          <div className="py-8 text-center text-xs text-zinc-500 dark:text-zinc-400">
            Chưa có lượt kích hoạt nào được ghi nhận trong 24 giờ qua.
          </div>
        )}

        {/* History List */}
        {items.length > 0 && (
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800/60 overflow-hidden">
            {items.slice(0, 8).map((item, idx) => (
              <div key={idx} className="flex items-center justify-between py-2.5 text-xs">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-mono text-[10px]">
                    {idx + 1}
                  </div>
                  <span className="font-medium text-zinc-900 dark:text-zinc-200 font-mono">
                    @{item.username}
                  </span>
                </div>

                <div className="flex items-center gap-3 text-zinc-500 dark:text-zinc-400">
                  {item.duration !== null && (
                    <span className="hidden sm:inline text-[11px] text-zinc-500">
                      {Math.round(item.duration)}s
                    </span>
                  )}
                  <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                    {formatRelativeTime(item.completed_at)}
                  </span>
                  <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold border ${
                    item.status === 'completed'
                      ? 'border-emerald-700/30 dark:border-emerald-800/50 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300'
                      : 'border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400'
                  }`}>
                    {item.status === 'completed' ? (
                      <>
                        <CheckCircle2 className="h-2.5 w-2.5 text-emerald-600 dark:text-emerald-400" />
                        <span>Thành công</span>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="h-2.5 w-2.5 text-zinc-500 dark:text-zinc-400" />
                        <span>{item.status}</span>
                      </>
                    )}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};
