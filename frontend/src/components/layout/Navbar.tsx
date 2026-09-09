import React, { useEffect, useState, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, Loader2, LogOut, LayoutDashboard } from 'lucide-react';
import { fetchGlobalQueueStatus } from '../../api/endpoints';
import type { GlobalQueueStatusResponse } from '../../types/api';
import { ThemeToggle } from './ThemeToggle';
import { useAuth } from '../../hooks/useAuth';

interface NavbarProps {
  isBackendOffline?: boolean;
}

type BackendStatus = 'checking' | 'online' | 'queue_active' | 'offline';

export const Navbar: React.FC<NavbarProps> = ({ isBackendOffline }) => {
  const location = useLocation();
  const { user, isAuthenticated, logout } = useAuth();
  const [globalStatus, setGlobalStatus] = useState<GlobalQueueStatusResponse | null>(null);
  const [status, setStatus] = useState<BackendStatus>('checking');
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetchGlobalQueueStatus();
      if (res && res.success) {
        setGlobalStatus(res);
        setStatus(res.total_queue > 0 ? 'queue_active' : 'online');
      } else {
        setStatus('offline');
      }
    } catch {
      setStatus('offline');
      setGlobalStatus(null);
    }
  }, []);

  useEffect(() => {
    checkStatus();
    const timer = setInterval(checkStatus, 10000);
    return () => clearInterval(timer);
  }, [checkStatus]);

  const currentStatus: BackendStatus = isBackendOffline ? 'offline' : status;

  // Handle ESC key to close mobile menu
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsMenuOpen(false);
      }
    };
    if (isMenuOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMenuOpen]);

  // Close menu on route change
  useEffect(() => {
    setIsMenuOpen(false);
  }, [location.pathname]);

  const handleScrollSection = (sectionId: string) => (e: React.MouseEvent) => {
    if (location.pathname === '/') {
      e.preventDefault();
      const elem = document.getElementById(sectionId);
      if (elem) {
        elem.scrollIntoView({ behavior: 'smooth' });
      }
      setIsMenuOpen(false);
    }
  };

  return (
    <header className="gold-nav sticky top-0 z-40 w-full border-b backdrop-blur-md transition-colors">
      <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between gap-3 px-3 sm:px-5 lg:px-8">
        {/* Brand Logo */}
        <Link to="/" className="flex shrink-0 items-center gap-2.5 transition-opacity hover:opacity-90">
          <img
            src="/logo-locket.png"
            alt=""
            aria-hidden="true"
            className="h-10 w-10 shrink-0 object-contain drop-shadow-[0_5px_10px_rgba(244,114,182,0.28)]"
          />
          <div className="flex flex-col">
            <span className="text-xs sm:text-sm font-extrabold tracking-tight text-zinc-900 dark:text-white whitespace-nowrap">
              Locket Gold - Huy Dev
            </span>
            <span className="text-[10px] sm:text-[11px] text-zinc-500 dark:text-zinc-400 font-medium">Official</span>
          </div>
        </Link>

        {/* Desktop Nav Links */}
        <nav className="hidden shrink-0 items-center gap-0.5 whitespace-nowrap text-xs font-semibold text-zinc-600 dark:text-zinc-300 2xl:flex" aria-label="Menu chính">
          <Link to="/" className="rounded-lg px-2.5 py-2 transition-colors hover:text-zinc-900 dark:hover:text-white">
            Trang chủ
          </Link>
          <a href="/#features" onClick={handleScrollSection('features')} className="rounded-lg px-2.5 py-2 transition-colors hover:text-zinc-900 dark:hover:text-white">
            Tính năng
          </a>
          <a href="/#creators" onClick={handleScrollSection('creators')} className="rounded-lg px-2.5 py-2 transition-colors hover:text-zinc-900 dark:hover:text-white">
            TikToker/KOL
          </a>
          <a href="/#process" onClick={handleScrollSection('process')} className="rounded-lg px-2.5 py-2 transition-colors hover:text-zinc-900 dark:hover:text-white">
            Quy trình
          </a>
          <a href="/#support" onClick={handleScrollSection('support')} className="mx-0.5 rounded-xl border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-amber-700 transition-colors hover:border-amber-500/50 hover:bg-amber-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60 dark:text-amber-300">
            Hỗ trợ
          </a>
          <Link to={isAuthenticated ? '/dashboard' : '/login?returnTo=/dashboard'} className="rounded-lg px-2.5 py-2 transition-colors hover:text-zinc-900 dark:hover:text-white">
            Gói dịch vụ
          </Link>
          <Link to="/track" className="flex items-center gap-1 rounded-lg px-2.5 py-2 text-zinc-500 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
            <span>Tra cứu</span>
            <span className="h-1.5 w-1.5 rounded-full bg-zinc-300 dark:bg-zinc-600" aria-label="Sắp ra mắt" title="Sắp ra mắt" />
          </Link>
        </nav>

        {/* Global status & actions */}
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {/* Server status pill */}
          <div className={`hidden lg:flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors ${
            currentStatus === 'offline'
              ? 'border-amber-700/30 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300'
              : currentStatus === 'checking'
                ? 'border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/90 text-zinc-500 dark:text-zinc-400'
                : currentStatus === 'queue_active'
                  ? 'border-amber-500/40 bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300'
                  : 'border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/90 text-zinc-700 dark:text-zinc-300'
          }`}>
            <span className="relative flex h-2 w-2">
              {currentStatus === 'checking' ? (
                <Loader2 className="h-2 w-2 animate-spin text-zinc-400" />
              ) : currentStatus === 'offline' ? (
                <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500"></span>
              ) : (
                <>
                  <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${currentStatus === 'queue_active' ? 'bg-amber-400' : 'bg-emerald-400'}`}></span>
                  <span className={`relative inline-flex h-2 w-2 rounded-full ${currentStatus === 'queue_active' ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
                </>
              )}
            </span>
            <span className="text-[11px] font-medium">
              {currentStatus === 'checking'
                ? 'Đang kết nối...'
                : currentStatus === 'offline'
                  ? 'Máy chủ ngoại tuyến'
                  : currentStatus === 'queue_active'
                    ? `Hàng đợi: ${globalStatus?.total_queue}`
                    : 'Sẵn sàng'}
            </span>
          </div>

          {/* Theme Toggle */}
          <ThemeToggle />

          {/* User Auth or Actions */}
          {isAuthenticated && user ? (
            <div className="hidden sm:flex items-center gap-2">
              <Link
                to="/dashboard"
                className="flex items-center gap-1.5 rounded-2xl border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:text-amber-400 transition-colors shadow-sm"
              >
                <LayoutDashboard className="h-3.5 w-3.5" />
                <span>Bảng điều khiển</span>
              </Link>
              <div className="flex items-center gap-2 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/90 pl-2.5 pr-1.5 py-1 text-xs shadow-sm">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-400 font-bold text-[11px]">
                  {(user.display_name || user.username || 'U').charAt(0).toUpperCase()}
                </div>
                <span className="font-semibold text-zinc-800 dark:text-zinc-200 max-w-[100px] truncate">
                  {user.display_name || user.username}
                </span>
                <button
                  type="button"
                  onClick={() => logout()}
                  title="Đăng xuất"
                  className="ml-1 p-1 rounded-xl hover:bg-zinc-200/60 dark:hover:bg-zinc-800 text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
                  aria-label="Đăng xuất"
                >
                  <LogOut className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <div className="hidden sm:flex items-center gap-1.5">
              <Link
                to="/login?returnTo=/dashboard"
                className="px-3 py-1.5 text-xs font-semibold text-zinc-700 dark:text-zinc-300 hover:text-zinc-950 dark:hover:text-white transition-colors"
              >
                Đăng nhập
              </Link>
              <Link
                to="/register?returnTo=/dashboard"
                className="gold-primary rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all"
              >
                Đăng ký
              </Link>
            </div>
          )}

          {/* Mobile Menu Toggle Button */}
          <button
            type="button"
            onClick={() => setIsMenuOpen((prev) => !prev)}
            aria-expanded={isMenuOpen}
            aria-controls="mobile-navigation"
            aria-label={isMenuOpen ? 'Đóng menu' : 'Mở menu'}
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-200 bg-white text-zinc-700 focus-visible:ring-2 focus-visible:ring-amber-500 dark:border-zinc-800 dark:bg-zinc-900/80 dark:text-zinc-200 2xl:hidden"
          >
            {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Navigation */}
      {isMenuOpen && (
        <div
          id="mobile-navigation"
          className="gold-nav border-t px-4 py-5 shadow-xl backdrop-blur-md animate-in slide-in-from-top-2 duration-150 2xl:hidden"
        >
          <div className="flex flex-col space-y-3">
            {/* User card if logged in */}
            {isAuthenticated && user && (
              <div className="flex items-center justify-between rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 p-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-400 font-bold text-xs">
                    {(user.display_name || user.username || 'U').charAt(0).toUpperCase()}
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs font-bold text-zinc-900 dark:text-white">
                      {user.display_name}
                    </span>
                    <span className="text-[10px] text-zinc-500 dark:text-zinc-400">
                      @{user.username}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    setIsMenuOpen(false);
                  }}
                  className="flex items-center gap-1 text-xs font-semibold text-rose-600 dark:text-rose-400 px-2.5 py-1.5 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/30"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>Đăng xuất</span>
                </button>
              </div>
            )}

            {/* Mobile Status Indicator */}
            <div className="flex lg:hidden items-center justify-between rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 p-3 text-xs">
              <span className="text-zinc-500 dark:text-zinc-400">Trạng thái máy chủ:</span>
              <span className="font-semibold text-zinc-800 dark:text-zinc-200">
                {currentStatus === 'checking'
                  ? 'Đang kết nối...'
                  : currentStatus === 'offline'
                    ? 'Máy chủ ngoại tuyến'
                    : currentStatus === 'queue_active'
                      ? `Hàng đợi: ${globalStatus?.total_queue} yêu cầu`
                      : 'Sẵn sàng'}
              </span>
            </div>

            {/* Navigation Links */}
            {isAuthenticated && (
              <Link
                to="/dashboard"
                onClick={() => setIsMenuOpen(false)}
                className="flex items-center justify-between py-2.5 px-3 rounded-xl bg-amber-500/10 text-amber-800 dark:text-amber-300 font-bold text-sm border border-amber-500/20 mb-1"
              >
                <div className="flex items-center gap-2">
                  <LayoutDashboard className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  <span>Bảng điều khiển dịch vụ</span>
                </div>
                <span className="text-xs">→</span>
              </Link>
            )}

            <Link
              to="/"
              onClick={() => setIsMenuOpen(false)}
              className="flex items-center justify-between py-2 text-sm font-medium text-zinc-800 dark:text-zinc-200 border-b border-zinc-100 dark:border-zinc-800/60"
            >
              <span>Trang chủ</span>
            </Link>

            <a
              href="/#features"
              onClick={handleScrollSection('features')}
              className="flex items-center justify-between py-2 text-sm font-medium text-zinc-800 dark:text-zinc-200 border-b border-zinc-100 dark:border-zinc-800/60"
            >
              <span>Tính năng</span>
            </a>

            <a
              href="/#process"
              onClick={handleScrollSection('process')}
              className="flex items-center justify-between py-2 text-sm font-medium text-zinc-800 dark:text-zinc-200 border-b border-zinc-100 dark:border-zinc-800/60"
            >
              <span>Quy trình</span>
            </a>

            <a
              href="/#creators"
              onClick={handleScrollSection('creators')}
              className="flex items-center justify-between py-2 text-sm font-medium text-zinc-800 dark:text-zinc-200 border-b border-zinc-100 dark:border-zinc-800/60"
            >
              <span>TikToker/KOL</span>
            </a>

            <a
              href="/#support"
              onClick={handleScrollSection('support')}
              className="flex items-center justify-between py-2 text-sm font-medium text-zinc-800 dark:text-zinc-200 border-b border-zinc-100 dark:border-zinc-800/60"
            >
              <span>Hỗ trợ</span>
            </a>

            <Link
              to={isAuthenticated ? '/dashboard' : '/login?returnTo=/dashboard'}
              onClick={() => setIsMenuOpen(false)}
              className="flex items-center justify-between py-2 text-sm font-medium text-zinc-800 dark:text-zinc-200 border-b border-zinc-100 dark:border-zinc-800/60"
            >
              <span>Gói dịch vụ</span>
            </Link>

            <Link
              to="/track"
              onClick={() => setIsMenuOpen(false)}
              className="flex items-center justify-between py-2 text-sm font-medium text-zinc-800 dark:text-zinc-200 border-b border-zinc-100 dark:border-zinc-800/60"
            >
              <span>Tra cứu tiến trình</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-200/70 dark:bg-zinc-800 text-zinc-500 font-normal">Sắp ra mắt</span>
            </Link>

            {/* Auth Links if not logged in */}
            {!isAuthenticated && (
              <div className="pt-2 grid grid-cols-2 gap-2 text-center text-xs">
                <Link
                  to="/login?returnTo=/dashboard"
                  onClick={() => setIsMenuOpen(false)}
                  className="py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-200 font-semibold bg-white dark:bg-zinc-900"
                >
                  Đăng nhập
                </Link>
                <Link
                  to="/register?returnTo=/dashboard"
                  onClick={() => setIsMenuOpen(false)}
                  className="gold-primary py-2.5 rounded-xl font-bold"
                >
                  Đăng ký
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
