import React from 'react';
import {
  LayoutDashboard,
  Users,
  PackageCheck,
  CreditCard,
  Tag,
  Ticket,
  Clock,
  Star,
  BadgeCheck,
  Settings,
  History,
  ShieldCheck,
  Sparkles,
  ExternalLink,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export type AdminTab =
  | 'overview'
  | 'users'
  | 'orders'
  | 'payments'
  | 'plans'
  | 'coupons'
  | 'queue'
  | 'reviews'
  | 'creators'
  | 'system'
  | 'audit-logs';

interface AdminSidebarProps {
  activeTab: AdminTab;
  onSelectTab: (tab: AdminTab) => void;
  pendingPaymentsCount?: number;
  queueCount?: number;
  onCloseMobile?: () => void;
}

export const AdminSidebar: React.FC<AdminSidebarProps> = ({
  activeTab,
  onSelectTab,
  pendingPaymentsCount = 0,
  queueCount = 0,
  onCloseMobile,
}) => {
  const menuItems = [
    {
      id: 'overview' as AdminTab,
      label: 'Tổng quan',
      icon: LayoutDashboard,
    },
    {
      id: 'users' as AdminTab,
      label: 'Người dùng',
      icon: Users,
    },
    {
      id: 'orders' as AdminTab,
      label: 'Đơn kích hoạt',
      icon: PackageCheck,
    },
    {
      id: 'payments' as AdminTab,
      label: 'Giao dịch',
      icon: CreditCard,
      badge: pendingPaymentsCount > 0 ? pendingPaymentsCount : undefined,
      badgeVariant: 'amber',
    },
    {
      id: 'plans' as AdminTab,
      label: 'Gói dịch vụ',
      icon: Tag,
    },
    {
      id: 'coupons' as AdminTab,
      label: 'Mã giảm giá',
      icon: Ticket,
    },
    {
      id: 'queue' as AdminTab,
      label: 'Hàng đợi',
      icon: Clock,
      badge: queueCount > 0 ? queueCount : undefined,
      badgeVariant: 'blue',
    },
    {
      id: 'reviews' as AdminTab,
      label: 'Đánh giá',
      icon: Star,
    },
    {
      id: 'creators' as AdminTab,
      label: 'TikToker / KOL',
      icon: BadgeCheck,
    },
    {
      id: 'system' as AdminTab,
      label: 'Hệ thống',
      icon: Settings,
    },
    {
      id: 'audit-logs' as AdminTab,
      label: 'Nhật ký thao tác',
      icon: History,
    },
  ];

  return (
    <aside className="flex h-full flex-col bg-zinc-950 border-r border-zinc-800/80 w-64 select-none">
      {/* Brand Header */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-zinc-800/80">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 text-zinc-950 shadow-lg shadow-amber-500/20 font-black">
          <Sparkles className="h-5 w-5 fill-current" />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <span className="font-extrabold text-sm tracking-tight text-white">Locket Gold</span>
            <span className="rounded-md bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 text-[10px] font-bold text-amber-400 uppercase">
              Admin
            </span>
          </div>
          <p className="text-[11px] text-zinc-500">Quản trị hệ thống tập trung</p>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1.5">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
          Phân Hệ Quản Lý
        </div>

        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                onSelectTab(item.id);
                if (onCloseMobile) onCloseMobile();
              }}
              className={`flex w-full items-center justify-between rounded-xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
                isActive
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30 shadow-sm'
                  : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 border border-transparent'
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon className={`h-4 w-4 ${isActive ? 'text-amber-400' : 'text-zinc-400'}`} />
                <span>{item.label}</span>
              </div>

              {item.badge !== undefined && (
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    item.badgeVariant === 'amber'
                      ? 'bg-amber-500/20 text-amber-300'
                      : 'bg-sky-500/20 text-sky-300'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer / Quick Links */}
      <div className="p-3 border-t border-zinc-800/80 space-y-2">
        <Link
          to="/dashboard"
          className="flex w-full items-center justify-between rounded-xl bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-800 px-3.5 py-2.5 text-xs font-semibold text-zinc-300 hover:text-white transition-colors"
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>Về Dashboard User</span>
          </div>
          <ExternalLink className="h-3.5 w-3.5 text-zinc-400" />
        </Link>
      </div>
    </aside>
  );
};
