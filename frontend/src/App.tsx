import React, { Suspense, lazy } from 'react';
import { Navigate, Routes, Route } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { MaintenanceScreen } from './components/common/MaintenanceScreen';
import { useSiteSettings } from './hooks/useSiteSettings';
import { Loader2 } from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { AdminRoute } from './components/auth/AdminRoute';
import { GlobalAnnouncementPopup } from './components/common/GlobalAnnouncementPopup';

const TrackOrderPage = lazy(() =>
  import('./components/track/TrackOrderPage').then((m) => ({ default: m.TrackOrderPage }))
);
const LoginPage = lazy(() =>
  import('./pages/LoginPage').then((m) => ({ default: m.LoginPage }))
);
const RegisterPage = lazy(() =>
  import('./pages/RegisterPage').then((m) => ({ default: m.RegisterPage }))
);
const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage }))
);
const AdminPage = lazy(() =>
  import('./pages/admin/AdminPage').then((m) => ({ default: m.AdminPage }))
);
const NotFoundPage = lazy(() =>
  import('./pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage }))
);

const PageLoader: React.FC = () => (
  <div className="gold-page flex min-h-screen items-center justify-center bg-zinc-950">
    <div className="flex items-center gap-2.5 rounded-2xl border border-zinc-800 bg-zinc-900/80 px-5 py-3 text-xs text-zinc-400 shadow-xl backdrop-blur-md">
      <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
      <span>Đang tải trang...</span>
    </div>
  </div>
);

const LandingEntry: React.FC<{ isBackendOffline: boolean }> = ({ isBackendOffline }) => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <PageLoader />;
  }

  if (isAuthenticated) {
    return <Navigate to={user?.role === 'admin' ? '/admin' : '/dashboard'} replace />;
  }

  return <HomePage isBackendOffline={isBackendOffline} />;
};

const MaintenanceRouteWrapper: React.FC<{
  children: React.ReactNode;
  isMaintenance: boolean;
  message?: string;
  allowAdmin?: boolean;
}> = ({ children, isMaintenance, message, allowAdmin = true }) => {
  const { user } = useAuth();
  if (isMaintenance) {
    if (allowAdmin && user?.role === 'admin') {
      return <>{children}</>;
    }
    return <MaintenanceScreen message={message} />;
  }
  return <>{children}</>;
};

export function App() {
  const { isMaintenance, maintenanceMessage, isBackendOffline, settings } = useSiteSettings();
  const allowAdmin = settings?.maintenance?.allow_admin !== false;

  return (
    <>
      <GlobalAnnouncementPopup />
      <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route
          path="/"
          element={
            <MaintenanceRouteWrapper
              isMaintenance={isMaintenance}
              message={maintenanceMessage}
              allowAdmin={allowAdmin}
            >
              <LandingEntry isBackendOffline={isBackendOffline} />
            </MaintenanceRouteWrapper>
          }
        />
        <Route
          path="/dashboard/*"
          element={
            <MaintenanceRouteWrapper
              isMaintenance={isMaintenance}
              message={maintenanceMessage}
              allowAdmin={allowAdmin}
            >
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            </MaintenanceRouteWrapper>
          }
        />
        <Route
          path="/dashboard"
          element={
            <MaintenanceRouteWrapper
              isMaintenance={isMaintenance}
              message={maintenanceMessage}
              allowAdmin={allowAdmin}
            >
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            </MaintenanceRouteWrapper>
          }
        />
        <Route
          path="/track"
          element={
            <MaintenanceRouteWrapper
              isMaintenance={isMaintenance}
              message={maintenanceMessage}
              allowAdmin={allowAdmin}
            >
              <TrackOrderPage isBackendOffline={isBackendOffline} />
            </MaintenanceRouteWrapper>
          }
        />

        {/* /login is always accessible so admin can sign in during maintenance */}
        <Route path="/login" element={<LoginPage isBackendOffline={isBackendOffline} />} />

        {/* /register is blocked during maintenance mode */}
        <Route
          path="/register"
          element={
            <MaintenanceRouteWrapper
              isMaintenance={isMaintenance}
              message={maintenanceMessage}
              allowAdmin={allowAdmin}
            >
              <RegisterPage isBackendOffline={isBackendOffline} />
            </MaintenanceRouteWrapper>
          }
        />

        {/* Admin SPA routes: protected by AdminRoute, accessible during maintenance by admin */}
        <Route
          path="/admin/*"
          element={
            <AdminRoute>
              <AdminPage />
            </AdminRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminPage />
            </AdminRoute>
          }
        />

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
    </>
  );
}

export default App;
