import React, { useState } from 'react';
import { AdminSidebar, AdminTab } from './AdminSidebar';
import { useAuth } from '../../hooks/useAuth';
import { useTheme } from '../../context/ThemeContext';
import {
  Menu,
  X,
  LogOut,
  User,
  Globe,
  RefreshCw,
  Sun,
  Moon,
} from 'lucide-react';

interface AdminLayoutProps {
  activeTab: AdminTab;
  onSelectTab: (tab: AdminTab) => void;
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  pendingPaymentsCount?: number;
  queueCount?: number;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const AdminLayout: React.FC<AdminLayoutProps> = ({
  activeTab,
  onSelectTab,
  children,
  title,
  subtitle,
  pendingPaymentsCount = 0,
  queueCount = 0,
  onRefresh,
  isRefreshing = false,
}) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="admin-shell flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 antialiased font-sans transition-colors duration-200">
      {/* Desktop Sidebar */}
      <div className="hidden lg:flex lg:flex-shrink-0">
        <AdminSidebar
          activeTab={activeTab}
          onSelectTab={onSelectTab}
          pendingPaymentsCount={pendingPaymentsCount}
          queueCount={queueCount}
        />
      </div>

      {/* Mobile Sidebar Overlay / Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative flex w-full max-w-xs flex-1 flex-col bg-zinc-950 shadow-2xl">
            <div className="absolute top-3 right-3 z-10">
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-xl p-2 text-zinc-400 hover:text-white hover:bg-zinc-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <AdminSidebar
              activeTab={activeTab}
              onSelectTab={onSelectTab}
              pendingPaymentsCount={pendingPaymentsCount}
              queueCount={queueCount}
              onCloseMobile={() => setMobileOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Main Column */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Header */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-zinc-800/80 bg-zinc-900/60 px-4 sm:px-8 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="lg:hidden rounded-xl p-2 text-zinc-400 hover:bg-zinc-800 hover:text-white"
              aria-label="Mở menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-base sm:text-lg font-bold text-white tracking-tight flex items-center gap-2">
                {title}
              </h1>
              {subtitle && (
                <p className="hidden sm:block text-xs text-zinc-400">
                  {subtitle}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3">
            {/* Timezone Badge */}
            <div className="hidden md:flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900 px-3 py-1 text-[11px] font-medium text-zinc-400">
              <Globe className="h-3.5 w-3.5 text-amber-500" />
              <span>Asia/Bangkok (UTC+7)</span>
            </div>

            {/* Light / dark appearance */}
            <button
              type="button"
              onClick={toggleTheme}
              title={theme === 'dark' ? 'Chuyển sang nền sáng' : 'Chuyển sang nền tối'}
              aria-label={theme === 'dark' ? 'Chuyển sang nền sáng' : 'Chuyển sang nền tối'}
              aria-pressed={theme === 'light'}
              className="rounded-xl border border-zinc-800 bg-zinc-900 p-2 text-zinc-400 hover:border-amber-500/50 hover:text-amber-500 transition-colors"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>

            {/* Refresh Button */}
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                disabled={isRefreshing}
                title="Làm mới dữ liệu"
                className="rounded-xl border border-zinc-800 bg-zinc-900 p-2 text-zinc-400 hover:border-zinc-700 hover:text-amber-400 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin text-amber-400' : ''}`} />
              </button>
            )}

            {/* Admin Profile & Logout */}
            <div className="flex items-center gap-2 pl-2 sm:pl-3 border-l border-zinc-800">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 font-bold text-xs">
                  {user?.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt={user.display_name}
                      className="h-full w-full rounded-xl object-cover"
                    />
                  ) : (
                    <User className="h-4 w-4" />
                  )}
                </div>
                <div className="hidden xl:block text-left leading-tight">
                  <div className="text-xs font-bold text-zinc-200">
                    {user?.display_name || user?.username}
                  </div>
                  <div className="text-[10px] text-amber-400 font-medium">
                    Quản trị viên
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => logout()}
                title="Đăng xuất"
                className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-2 text-zinc-400 hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Tab Body */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-8 bg-zinc-950">
          <div className="mx-auto max-w-7xl space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
