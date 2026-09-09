import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  PlanItem,
  ActivationOrder,
} from '../types/api';
import {
  fetchPlans,
  fetchWalletBalance,
  fetchUserOrders,
} from '../api/endpoints';
import { OverviewView } from './dashboard/OverviewView';
import { ActivationWizard } from './dashboard/ActivationWizard';
import { WalletView } from './dashboard/WalletView';
import { OrdersView } from './dashboard/OrdersView';
import { FeedbackView } from './dashboard/FeedbackView';
import { ThemeToggle } from '../components/layout/ThemeToggle';
import {
  LayoutDashboard,
  Zap,
  Coins,
  ShoppingBag,
  LogOut,
  User,
  Plus,
  MessageSquareHeart,
} from 'lucide-react';

export type DashboardTab = 'overview' | 'wizard' | 'wallet' | 'orders' | 'feedback' | 'account';

const DASHBOARD_TABS: DashboardTab[] = ['overview', 'wizard', 'wallet', 'orders', 'feedback', 'account'];

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab');
  const tabParam: DashboardTab = DASHBOARD_TABS.includes(rawTab as DashboardTab)
    ? (rawTab as DashboardTab)
    : 'overview';
  const [activeTab, setActiveTab] = useState<DashboardTab>(tabParam);

  const { user, logout } = useAuth();

  // Shared state
  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [isLoadingPlans, setIsLoadingPlans] = useState(false);
  const [coinBalance, setCoinBalance] = useState<number>(0);
  const [isLoadingBalance, setIsLoadingBalance] = useState(false);
  const [orders, setOrders] = useState<ActivationOrder[]>([]);
  const [neededTopupCoins, setNeededTopupCoins] = useState<number | null>(null);

  // Sync tab with search params
  const handleTabChange = (tab: DashboardTab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const handleLogout = async () => {
    await logout();
    navigate('/', { replace: true });
  };

  useEffect(() => {
    setActiveTab(tabParam);
  }, [tabParam]);

  // Fetch plans
  const loadPlans = useCallback(async () => {
    setIsLoadingPlans(true);
    try {
      const res = await fetchPlans();
      if (res && res.success) {
        setPlans(res.plans);
      }
    } catch {}
    finally {
      setIsLoadingPlans(false);
    }
  }, []);

  // Fetch wallet balance
  const loadBalance = useCallback(async () => {
    setIsLoadingBalance(true);
    try {
      const res = await fetchWalletBalance();
      if (res && res.success) {
        setCoinBalance(res.balance_coin);
      }
    } catch {}
    finally {
      setIsLoadingBalance(false);
    }
  }, []);

  // Fetch orders summary
  const loadOrdersSummary = useCallback(async () => {
    try {
      const res = await fetchUserOrders(20, 0);
      if (res && res.success) {
        setOrders(res.items);
      }
    } catch {}
  }, []);

  useEffect(() => {
    loadPlans();
    loadBalance();
    loadOrdersSummary();
  }, [loadPlans, loadBalance, loadOrdersSummary]);

  const activeOrdersCount = orders.filter(
    (o) => o.status === 'awaiting_queue' || o.status === 'queued' || o.status === 'processing'
  ).length;

  const completedOrdersCount = orders.filter((o) => o.status === 'completed').length;

  const handleGoToTopup = (needed?: number) => {
    if (needed) setNeededTopupCoins(needed);
    handleTabChange('wallet');
  };

  return (
    <div className="gold-page min-h-[100dvh] flex flex-col bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 transition-colors">
      <div className="gold-ambient pointer-events-none" aria-hidden="true" />

      {/* Top Navbar */}
      <header className="sticky top-0 z-40 w-full border-b border-zinc-200/80 dark:border-zinc-800/80 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 sm:h-16 max-w-[1600px] 2xl:max-w-[1760px] items-center justify-between px-3 sm:px-5 lg:px-8">
          {/* Brand */}
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <Link
              to="/dashboard?tab=overview"
              onClick={() => handleTabChange('overview')}
              className="flex min-w-0 items-center gap-2 sm:gap-2.5 transition-opacity hover:opacity-90"
            >
              <img
                src="/logo-locket.png"
                alt=""
                aria-hidden="true"
                className="h-9 w-9 sm:h-10 sm:w-10 shrink-0 object-contain drop-shadow-[0_5px_10px_rgba(244,114,182,0.25)]"
              />
              <div className="flex flex-col">
                <span className="text-[11px] sm:text-sm font-extrabold tracking-tight text-zinc-900 dark:text-white whitespace-nowrap">
                  Locket Gold - Huy Dev
                </span>
                <span className="hidden sm:block text-[10px] text-zinc-500 dark:text-zinc-400">Dashboard</span>
              </div>
            </Link>

          </div>

          {/* Right Header Controls */}
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
            {/* Live Coin Balance Pill */}
            <button
              type="button"
              onClick={() => handleTabChange('wallet')}
              aria-label={`Số dư ${coinBalance} Coin. Mở ví Coin`}
              className="cursor-pointer flex min-h-10 items-center gap-1.5 sm:gap-2 rounded-2xl border border-amber-500/30 bg-amber-50 dark:bg-amber-950/40 px-2.5 sm:px-3 py-1.5 shadow-sm hover:border-amber-500/60 transition-all"
            >
              <div className="flex items-center gap-1.5 text-xs font-bold text-amber-700 dark:text-amber-300">
                <Coins className="h-3.5 w-3.5 text-amber-500" />
                <span>{isLoadingBalance ? '...' : coinBalance.toLocaleString('vi-VN')}</span>
                <span className="hidden min-[380px]:inline text-[10px] font-normal text-amber-600/80 dark:text-amber-400/80">Coin</span>
              </div>
              <span className="hidden sm:inline-block text-[10px] uppercase font-extrabold px-1.5 py-0.5 rounded bg-amber-500 text-zinc-950">
                + Nạp
              </span>
            </button>

            {/* Quick Action: New Activation */}
            <button
              type="button"
              onClick={() => handleTabChange('wizard')}
              className="hidden md:flex gold-primary rounded-xl px-3.5 py-1.5 text-xs font-bold items-center gap-1.5 transition-all active:scale-[0.98]"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Kích hoạt mới</span>
            </button>

            {/* Theme Toggle */}
            <ThemeToggle />

            {user && (
              <button
                type="button"
                onClick={() => handleTabChange('account')}
                aria-label="Mở thông tin tài khoản"
                className={`flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold sm:hidden ${
                  activeTab === 'account'
                    ? 'bg-amber-500 text-zinc-950'
                    : 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                }`}
              >
                {(user.display_name || user.username || 'U').charAt(0).toUpperCase()}
              </button>
            )}

            {/* User Profile / Logout */}
            {user && (
              <div className="hidden sm:flex items-center gap-2 pl-2 border-l border-zinc-200 dark:border-zinc-800 text-xs">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-400 font-bold text-xs">
                  {(user.display_name || user.username || 'U').charAt(0).toUpperCase()}
                </div>
                <span className="font-semibold text-zinc-800 dark:text-zinc-200 max-w-[100px] truncate">
                  {user.display_name || user.username}
                </span>
                <button
                  type="button"
                  onClick={handleLogout}
                  title="Đăng xuất"
                  className="p-1 rounded-xl text-zinc-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Dashboard Layout: Sidebar + Content */}
      <div className="mx-auto flex-1 w-full max-w-[1600px] 2xl:max-w-[1760px] px-3 sm:px-5 lg:px-8 py-3 sm:py-5 flex flex-col md:flex-row gap-4 lg:gap-5">
        {/* Desktop Left Sidebar */}
        <aside className="hidden md:flex sticky top-20 h-fit flex-col w-52 lg:w-56 xl:w-60 shrink-0 space-y-1 rounded-3xl border border-amber-500/15 bg-white/65 dark:bg-zinc-900/65 p-2.5 shadow-[0_18px_50px_rgba(141,99,7,0.06)] backdrop-blur-md">
          <button
            type="button"
            onClick={() => handleTabChange('overview')}
            className={`flex items-center justify-between rounded-2xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
              activeTab === 'overview'
                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30'
                : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <LayoutDashboard className="h-4 w-4" />
              <span>Tổng quan</span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('wizard')}
            className={`flex items-center justify-between rounded-2xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
              activeTab === 'wizard'
                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30'
                : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Zap className="h-4 w-4" />
              <span>Gói Locket Gold</span>
            </div>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-700 dark:text-amber-300 font-bold">
              HOT
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('wallet')}
            className={`flex items-center justify-between rounded-2xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
              activeTab === 'wallet'
                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30'
                : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Coins className="h-4 w-4" />
              <span>Ví Coin & Nạp</span>
            </div>
            <span className="text-[11px] font-bold text-amber-600 dark:text-amber-400 font-mono">
              {coinBalance}
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('orders')}
            className={`flex items-center justify-between rounded-2xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
              activeTab === 'orders'
                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30'
                : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <ShoppingBag className="h-4 w-4" />
              <span>Đơn kích hoạt</span>
            </div>
            {activeOrdersCount > 0 && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-sky-500 text-white font-bold text-[10px]">
                {activeOrdersCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('feedback')}
            className={`flex items-center gap-2.5 rounded-2xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
              activeTab === 'feedback'
                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30'
                : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <MessageSquareHeart className="h-4 w-4" />
            <span>Feedback & ảnh</span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('account')}
            className={`flex items-center gap-2.5 rounded-2xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
              activeTab === 'account'
                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30'
                : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <User className="h-4 w-4" />
            <span>Tài khoản</span>
          </button>

          <div className="pt-4 mt-4 border-t border-zinc-200 dark:border-zinc-800 text-[11px] text-zinc-400 px-3">
            <span>Phiên bản: VIP Huy Dev</span>
          </div>
        </aside>

        {/* Content Area */}
        <main className="flex-1 min-w-0 min-h-[calc(100dvh-5.75rem)] rounded-[26px] sm:rounded-[30px] border border-amber-500/15 bg-white/55 dark:bg-zinc-900/45 p-3.5 sm:p-5 lg:p-6 pb-20 md:pb-6 shadow-[0_22px_70px_rgba(141,99,7,0.07)] backdrop-blur-sm">
          <div key={activeTab} className="gold-rise">
          {activeTab === 'overview' && (
            <OverviewView
              userDisplayName={user?.display_name || user?.username || 'Bạn'}
              coinBalance={coinBalance}
              activeOrdersCount={activeOrdersCount}
              completedOrdersCount={completedOrdersCount}
              onGoToWizard={() => handleTabChange('wizard')}
              onGoToWallet={() => handleTabChange('wallet')}
              onGoToOrders={() => handleTabChange('orders')}
            />
          )}

          {activeTab === 'wizard' && (
            <ActivationWizard
              plans={plans}
              isLoadingPlans={isLoadingPlans}
              userCoinBalance={coinBalance}
              onRefreshWallet={loadBalance}
              onGoToTopup={handleGoToTopup}
              onOrderCreated={() => {
                loadOrdersSummary();
                loadBalance();
              }}
            />
          )}

          {activeTab === 'wallet' && (
            <WalletView
              balance={coinBalance}
              isLoadingBalance={isLoadingBalance}
              onRefreshBalance={loadBalance}
              prefilledCoin={neededTopupCoins}
            />
          )}

          {activeTab === 'orders' && (
            <OrdersView />
          )}

          {activeTab === 'feedback' && (
            <FeedbackView
              onGoToWizard={() => handleTabChange('wizard')}
              onGoToOrders={() => handleTabChange('orders')}
            />
          )}

          {activeTab === 'account' && (
            <div className="rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-5 sm:p-7 max-w-3xl space-y-5">
              <h3 className="text-base font-bold text-zinc-900 dark:text-white">
                Thông tin tài khoản
              </h3>
              <div className="space-y-3 text-xs">
                <div className="flex flex-col min-[430px]:flex-row min-[430px]:items-center justify-between gap-1 py-2 border-b border-zinc-100 dark:border-zinc-800">
                  <span className="text-zinc-500">Tên hiển thị:</span>
                  <span className="font-semibold text-zinc-800 dark:text-zinc-200">{user?.display_name}</span>
                </div>
                <div className="flex flex-col min-[430px]:flex-row min-[430px]:items-center justify-between gap-1 py-2 border-b border-zinc-100 dark:border-zinc-800">
                  <span className="text-zinc-500">Username:</span>
                  <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200">@{user?.username}</span>
                </div>
                <div className="flex flex-col min-[430px]:flex-row min-[430px]:items-center justify-between gap-1 py-2 border-b border-zinc-100 dark:border-zinc-800">
                  <span className="text-zinc-500">Email:</span>
                  <span className="break-all font-semibold text-zinc-800 dark:text-zinc-200">{user?.email}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="w-full rounded-2xl border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/20 py-3 text-xs font-bold text-rose-600 dark:text-rose-400 flex items-center justify-center gap-1.5"
              >
                <LogOut className="h-4 w-4" />
                <span>Đăng xuất khỏi tài khoản</span>
              </button>
            </div>
          )}
          </div>
        </main>
      </div>

      {/* Mobile Bottom Navigation Bar */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 border-t border-zinc-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-md pb-[env(safe-area-inset-bottom)]"
        aria-label="Thanh điều hướng di động"
      >
        <div className="grid grid-cols-5 h-14 px-1">
          <button
            type="button"
            onClick={() => handleTabChange('overview')}
            className={`flex flex-col items-center justify-center gap-0.5 text-[10px] min-h-[44px] ${
              activeTab === 'overview'
                ? 'text-amber-600 dark:text-amber-400 font-bold'
                : 'text-zinc-500'
            }`}
          >
            <LayoutDashboard className="h-4 w-4" />
            <span>Tổng quan</span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('wizard')}
            className={`flex flex-col items-center justify-center gap-0.5 text-[10px] min-h-[44px] ${
              activeTab === 'wizard'
                ? 'text-amber-600 dark:text-amber-400 font-bold'
                : 'text-zinc-500'
            }`}
          >
            <Zap className="h-4 w-4" />
            <span>Gói Gold</span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('wallet')}
            className={`flex flex-col items-center justify-center gap-0.5 text-[10px] min-h-[44px] ${
              activeTab === 'wallet'
                ? 'text-amber-600 dark:text-amber-400 font-bold'
                : 'text-zinc-500'
            }`}
          >
            <Coins className="h-4 w-4" />
            <span>Ví Coin</span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('orders')}
            className={`relative flex flex-col items-center justify-center gap-0.5 text-[10px] min-h-[44px] ${
              activeTab === 'orders'
                ? 'text-amber-600 dark:text-amber-400 font-bold'
                : 'text-zinc-500'
            }`}
          >
            <ShoppingBag className="h-4 w-4" />
            <span>Đơn hàng</span>
            {activeOrdersCount > 0 && (
              <span className="absolute top-1 right-3 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-sky-500 text-white font-bold text-[8px]">
                {activeOrdersCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('feedback')}
            className={`flex flex-col items-center justify-center gap-0.5 text-[10px] min-h-[44px] ${
              activeTab === 'feedback'
                ? 'text-amber-600 dark:text-amber-400 font-bold'
                : 'text-zinc-500'
            }`}
          >
            <MessageSquareHeart className="h-4 w-4" />
            <span>Feedback</span>
          </button>
        </div>
      </nav>
    </div>
  );
};
