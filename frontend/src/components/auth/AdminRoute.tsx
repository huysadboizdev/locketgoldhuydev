import React, { useState } from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useSiteSettings } from '../../hooks/useSiteSettings';
import { Loader2, ShieldAlert, ArrowLeft } from 'lucide-react';
import { updateAdminSettings } from '../../api/adminEndpoints';

interface AdminRouteProps {
  children: React.ReactNode;
}

export const AdminRoute: React.FC<AdminRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const { isMaintenance, maintenanceMessage, settings } = useSiteSettings();
  const location = useLocation();
  const [isRecovering, setIsRecovering] = useState(false);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);

  const allowAdmin = settings?.maintenance?.allow_admin !== false;

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 text-zinc-400">
        <div className="flex items-center gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/80 px-6 py-4 shadow-xl backdrop-blur-md">
          <Loader2 className="h-5 w-5 animate-spin text-amber-500" />
          <span className="text-xs sm:text-sm font-medium text-zinc-300">Đang xác thực quyền quản trị...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?returnTo=${returnTo}`} replace />;
  }

  if (user?.role !== 'admin') {
    return (
      <div className="gold-page flex min-h-screen flex-col items-center justify-center p-4 text-center bg-zinc-950 text-zinc-100">
        <div className="max-w-md w-full rounded-3xl border border-rose-500/20 bg-zinc-900/90 p-8 shadow-2xl backdrop-blur-md">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-500 mb-4 border border-rose-500/20">
            <ShieldAlert className="h-7 w-7" />
          </div>
          <h2 className="text-xl font-bold text-zinc-100 mb-2">Truy Cập Bị Từ Chối (403)</h2>
          <p className="text-xs text-zinc-400 mb-6 leading-relaxed">
            Tài khoản <span className="font-semibold text-zinc-200">"{user?.email || user?.username}"</span> không có quyền quản trị viên (Admin) để truy cập khu vực này.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-3">
            <Link
              to="/dashboard"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-amber-500 hover:bg-amber-400 px-5 py-2.5 text-xs font-bold text-zinc-950 transition-colors shadow-lg shadow-amber-500/10"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Về Trang Khách Hàng</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // A total maintenance lock must still be recoverable by an authenticated
  // admin. The backend exposes only the protected settings endpoints here.
  if (isMaintenance && !allowAdmin) {
    const disableMaintenance = async () => {
      setIsRecovering(true);
      setRecoveryError(null);
      try {
        await updateAdminSettings({
          maintenance: {
            ...settings?.maintenance,
            enabled: false,
          },
        });
        window.location.reload();
      } catch (err: any) {
        setRecoveryError(err?.message || 'Khong the tat che do bao tri.');
      } finally {
        setIsRecovering(false);
      }
    };

    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 p-4 text-zinc-100">
        <div className="w-full max-w-md rounded-3xl border border-amber-500/25 bg-zinc-900 p-8 text-center shadow-2xl">
          <ShieldAlert className="mx-auto mb-4 h-10 w-10 text-amber-400" />
          <h2 className="mb-2 text-xl font-bold">He thong dang bao tri</h2>
          <p className="mb-5 text-sm text-zinc-400">{maintenanceMessage}</p>
          {recoveryError && <p className="mb-4 text-xs text-rose-400">{recoveryError}</p>}
          <button
            type="button"
            onClick={disableMaintenance}
            disabled={isRecovering}
            className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50"
          >
            {isRecovering && <Loader2 className="h-4 w-4 animate-spin" />}
            Tat che do bao tri
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
