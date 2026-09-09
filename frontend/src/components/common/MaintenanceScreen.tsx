import React from 'react';
import { Wrench, Shield } from 'lucide-react';

interface MaintenanceScreenProps {
  message?: string;
  endAt?: string | null;
}

export const MaintenanceScreen: React.FC<MaintenanceScreenProps> = ({ message, endAt }) => {
  return (
    <div className="gold-page flex min-h-screen flex-col items-center justify-center p-6 text-center text-zinc-900 dark:text-zinc-100 transition-colors">
      <div className="mx-auto max-w-md space-y-6">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-2xl">
          <Wrench className="h-10 w-10 text-amber-500 dark:text-amber-300 animate-pulse" />
        </div>

        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-1 text-xs font-semibold text-zinc-700 dark:text-zinc-300">
            <Shield className="h-3 w-3 text-zinc-500 dark:text-zinc-400" />
            <span>BẢO TRÌ NÂNG CẤP HỆ THỐNG</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-zinc-900 dark:text-white">
            Hệ Thống Đang Được Tối Ưu
          </h1>
          <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
            {message || 'Chúng tôi đang tiến hành cập nhật cụm máy chủ để đảm bảo tính ổn định cao nhất.'}
          </p>
        </div>

        {endAt && (
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/80 p-3 text-xs text-zinc-700 dark:text-zinc-300">
            Dự kiến hoàn tất lúc: <span className="font-bold text-zinc-950 dark:text-white">{new Date(endAt).toLocaleString('vi-VN')}</span>
          </div>
        )}

        <div className="pt-2 text-xs text-zinc-500">
          Vui lòng quay lại sau ít phút hoặc theo dõi thông báo từ ban quản trị.
        </div>
      </div>
    </div>
  );
};
