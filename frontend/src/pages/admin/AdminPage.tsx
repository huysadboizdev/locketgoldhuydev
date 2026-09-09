import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AdminLayout } from '../../components/admin/AdminLayout';
import type { AdminTab } from '../../components/admin/AdminSidebar';
import { AdminOverview } from './AdminOverview';
import { AdminUsers } from './AdminUsers';
import { AdminOrders } from './AdminOrders';
import { AdminPayments } from './AdminPayments';
import { AdminPlans } from './AdminPlans';
import { AdminCoupons } from './AdminCoupons';
import { AdminQueue } from './AdminQueue';
import { AdminReviews } from './AdminReviews';
import { AdminCreators } from './AdminCreators';
import { AdminSystem } from './AdminSystem';
import { AdminAuditLogs } from './AdminAuditLogs';
import { fetchAdminOverview } from '../../api/adminEndpoints';

export const AdminPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = (searchParams.get('tab') || 'overview') as AdminTab;
  const validTabs: AdminTab[] = [
    'overview',
    'users',
    'orders',
    'payments',
    'plans',
    'coupons',
    'queue',
    'reviews',
    'creators',
    'system',
    'audit-logs',
  ];
  const activeTab: AdminTab = validTabs.includes(rawTab) ? rawTab : 'overview';

  const [pendingPayments, setPendingPayments] = useState(0);
  const [queueTotal, setQueueTotal] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Tab metadata
  const tabMeta: Record<AdminTab, { title: string; subtitle: string }> = {
    overview: {
      title: 'Bảng Điều Khiển Tổng Quan',
      subtitle: 'Theo dõi doanh thu thực, người dùng và hoạt động thời gian thực',
    },
    users: {
      title: 'Quản Lý Người Dùng & Ví Coin',
      subtitle: 'Tìm kiếm, xem hồ sơ, khóa/mở khóa tài khoản và điều chỉnh số dư ví',
    },
    orders: {
      title: 'Danh Sách Đơn Kích Hoạt',
      subtitle: 'Quản lý các đơn cấp phép Locket Gold trên iOS và Android',
    },
    payments: {
      title: 'Giao Dịch Nạp Tiền & Thanh Toán',
      subtitle: 'Duyệt chuyển khoản VietQR, đối soát và xử lý nạp ví',
    },
    plans: {
      title: 'Danh Mục Gói Dịch Vụ',
      subtitle: 'Thiết lập biểu giá VND, Coin và thời hạn các gói Locket Gold',
    },
    coupons: {
      title: 'Quản Lý Mã Giảm Giá (Coupons)',
      subtitle: 'Thiết lập mã khuyến mãi cho gói dịch vụ theo % hoặc tiền cố định VND',
    },
    queue: {
      title: 'Hàng Đợi Kích Hoạt Tự Động',
      subtitle: 'Giám sát tiến trình cấp phép tài khoản theo thời gian thực',
    },
    reviews: {
      title: 'Đánh Giá Khách Hàng',
      subtitle: 'Xem các feedback đã tự động công khai và xóa nội dung không phù hợp',
    },
    creators: {
      title: 'TikToker / KOL Đã Xác Thực',
      subtitle: 'Nâng đúng email thành KOL, quản lý TikTok và khung nổi bật trên landing page',
    },
    system: {
      title: 'Cấu Hình Hệ Thống & Máy Chủ',
      subtitle: 'Quản lý pool tài khoản Locket, proxy, mobileconfig và chế độ bảo trì',
    },
    'audit-logs': {
      title: 'Nhật Ký Thao Tác (Audit Trail)',
      subtitle: 'Theo dõi toàn bộ các hoạt động quản trị với chi tiết thay đổi an toàn',
    },
  };

  const loadBadges = useCallback(async () => {
    try {
      const res = await fetchAdminOverview('7d');
      if (res.success && res.cards) {
        const pPay = res.cards.pending_payments ?? res.cards.payments?.pending ?? 0;
        const qTot =
          (res.cards.queue_waiting ?? 0) + (res.cards.queue_processing ?? 0) ||
          (res.cards.queue?.total_waiting ?? 0) + (res.cards.queue?.total_processing ?? 0);
        setPendingPayments(pPay);
        setQueueTotal(qTot);
      }
    } catch {
      // Background badge fetch failure non-blocking
    }
  }, []);

  useEffect(() => {
    loadBadges();
    const interval = setInterval(loadBadges, 30000);
    return () => clearInterval(interval);
  }, [loadBadges]);

  const handleSelectTab = (tab: AdminTab) => {
    setSearchParams({ tab });
  };

  const handleGlobalRefresh = async () => {
    setIsRefreshing(true);
    await loadBadges();
    // Dispatch custom event to tell active subtab to refresh if desired
    window.dispatchEvent(new CustomEvent('admin-refresh'));
    setTimeout(() => setIsRefreshing(false), 500);
  };

  return (
    <AdminLayout
      activeTab={activeTab}
      onSelectTab={handleSelectTab}
      title={tabMeta[activeTab].title}
      subtitle={tabMeta[activeTab].subtitle}
      pendingPaymentsCount={pendingPayments}
      queueCount={queueTotal}
      onRefresh={handleGlobalRefresh}
      isRefreshing={isRefreshing}
    >
      {activeTab === 'overview' && <AdminOverview onNavigateTab={handleSelectTab} />}
      {activeTab === 'users' && <AdminUsers />}
      {activeTab === 'orders' && <AdminOrders />}
      {activeTab === 'payments' && <AdminPayments />}
      {activeTab === 'plans' && <AdminPlans />}
      {activeTab === 'coupons' && <AdminCoupons />}
      {activeTab === 'queue' && <AdminQueue />}
      {activeTab === 'reviews' && <AdminReviews />}
      {activeTab === 'creators' && <AdminCreators />}
      {activeTab === 'system' && <AdminSystem />}
      {activeTab === 'audit-logs' && <AdminAuditLogs />}
    </AdminLayout>
  );
};
