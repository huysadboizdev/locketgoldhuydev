import React, { useState, useEffect, useCallback } from 'react';
import {
  Ticket,
  Plus,
  Search,
  RefreshCw,
  Edit2,
  Trash2,
  BarChart3,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Percent,
  Coins,
  Tag,
} from 'lucide-react';
import { Modal } from '../../components/admin/Modal';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import {
  fetchAdminCoupons,
  createAdminCoupon,
  updateAdminCoupon,
  toggleAdminCoupon,
  deleteAdminCoupon,
  fetchAdminCouponStats,
  fetchAdminPlans,
} from '../../api/adminEndpoints';
import type {
  AdminCoupon,
  AdminCouponStats,
  AdminPlanItem,
} from '../../types/admin';

const formatVND = (num?: number | null) =>
  new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(num || 0);

const formatDate = (timestamp?: number | null) => {
  if (!timestamp) return '—';
  return new Date(timestamp * 1000).toLocaleString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
};

export const AdminCoupons: React.FC = () => {
  const [coupons, setCoupons] = useState<AdminCoupon[]>([]);
  const [availablePlans, setAvailablePlans] = useState<AdminPlanItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive' | 'exhausted'>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCoupons, setTotalCoupons] = useState(0);

  // Create / Edit Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCoupon, setEditingCoupon] = useState<AdminCoupon | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form Fields
  const [formCode, setFormCode] = useState('');
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formDiscountType, setFormDiscountType] = useState<'percent' | 'fixed_vnd'>('percent');
  const [formDiscountValue, setFormDiscountValue] = useState<number>(10);
  const [formMaxDiscountVnd, setFormMaxDiscountVnd] = useState<string>('');
  const [formMinOrderVnd, setFormMinOrderVnd] = useState<number>(1000);
  const [formUsageLimitTotal, setFormUsageLimitTotal] = useState<string>('');
  const [formUsageLimitPerUser, setFormUsageLimitPerUser] = useState<string>('1');
  const [formStartsAt, setFormStartsAt] = useState<string>('');
  const [formEndsAt, setFormEndsAt] = useState<string>('');
  const [formIsActive, setFormIsActive] = useState<boolean>(true);
  const [formPlanIds, setFormPlanIds] = useState<number[]>([]);

  // Stats Modal states
  const [statsModalCoupon, setStatsModalCoupon] = useState<AdminCoupon | null>(null);
  const [couponStats, setCouponStats] = useState<AdminCouponStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  // Delete Dialog states
  const [deleteTarget, setDeleteTarget] = useState<AdminCoupon | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Load available plans once
  useEffect(() => {
    fetchAdminPlans()
      .then((res) => {
        if (res.success && res.plans) {
          setAvailablePlans(res.plans);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch Coupons with filtering
  const loadCoupons = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await fetchAdminCoupons({
        search: searchQuery.trim() || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        page: currentPage,
        limit: 10,
      });

      if (res.success) {
        setCoupons(res.items || res.coupons || []);
        const nextPages = Math.max(1, res.pagination?.pages || res.pages || 1);
        setTotalPages(nextPages);
        if (currentPage > nextPages) setCurrentPage(nextPages);
        setTotalCoupons(res.pagination?.total || res.total || 0);
      }
    } catch (err: any) {
      setError(err.message || 'Lỗi khi tải danh sách mã giảm giá.');
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, statusFilter, currentPage]);

  useEffect(() => {
    loadCoupons();
  }, [loadCoupons]);

  // Handle open create modal
  const handleOpenCreate = () => {
    setEditingCoupon(null);
    setFormCode('');
    setFormName('');
    setFormDescription('');
    setFormDiscountType('percent');
    setFormDiscountValue(10);
    setFormMaxDiscountVnd('');
    setFormMinOrderVnd(1000);
    setFormUsageLimitTotal('');
    setFormUsageLimitPerUser('1');
    setFormStartsAt('');
    setFormEndsAt('');
    setFormIsActive(true);
    setFormPlanIds([]);
    setFormError(null);
    setIsModalOpen(true);
  };

  // Handle open edit modal
  const handleOpenEdit = (coupon: AdminCoupon) => {
    setEditingCoupon(coupon);
    setFormCode(coupon.code);
    setFormName(coupon.name);
    setFormDescription(coupon.description || '');
    setFormDiscountType(coupon.discount_type === 'fixed' ? 'fixed_vnd' : coupon.discount_type);
    setFormDiscountValue(coupon.discount_value);
    setFormMaxDiscountVnd(coupon.max_discount_vnd ? String(coupon.max_discount_vnd) : '');
    setFormMinOrderVnd(coupon.min_order_vnd || 1000);
    setFormUsageLimitTotal(coupon.usage_limit_total ? String(coupon.usage_limit_total) : '');
    setFormUsageLimitPerUser(coupon.usage_limit_per_user ? String(coupon.usage_limit_per_user) : '');
    setFormStartsAt(
      coupon.starts_at ? new Date(coupon.starts_at * 1000).toISOString().slice(0, 16) : ''
    );
    setFormEndsAt(
      coupon.ends_at ? new Date(coupon.ends_at * 1000).toISOString().slice(0, 16) : ''
    );
    setFormIsActive(Boolean(coupon.is_active));
    setFormPlanIds(coupon.applicable_plan_ids || []);
    setFormError(null);
    setIsModalOpen(true);
  };

  // Handle Save Coupon (Create or Update)
  const handleSaveCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const cleanCode = formCode.trim().toUpperCase();
    if (!cleanCode) {
      setFormError('Vui lòng nhập mã giảm giá.');
      return;
    }

    if (!formName.trim()) {
      setFormError('Vui lòng nhập tên chương trình giảm giá.');
      return;
    }

    // Integer & business rule validations
    if (formDiscountType === 'percent') {
      if (formDiscountValue < 1 || formDiscountValue > 99 || !Number.isInteger(formDiscountValue)) {
        setFormError('Tỷ lệ giảm phần trăm phải là số nguyên từ 1% đến 99%.');
        return;
      }
    } else {
      if (
        formDiscountValue < 1000 ||
        formDiscountValue % 1000 !== 0 ||
        !Number.isInteger(formDiscountValue)
      ) {
        setFormError('Số tiền giảm cố định phải là bội số của 1.000 VNĐ (tối thiểu 1.000 VNĐ).');
        return;
      }
    }

    let parsedMaxDiscount: number | null = null;
    if (formMaxDiscountVnd.trim()) {
      const parsed = Number(formMaxDiscountVnd.trim());
      if (isNaN(parsed) || parsed < 1000 || parsed % 1000 !== 0 || !Number.isInteger(parsed)) {
        setFormError('Mức giảm tối đa phải là số nguyên bội số của 1.000 VNĐ.');
        return;
      }
      parsedMaxDiscount = parsed;
    }

    if (formMinOrderVnd < 1000 || formMinOrderVnd % 1000 !== 0 || !Number.isInteger(formMinOrderVnd)) {
      setFormError('Giá trị đơn hàng tối thiểu phải là bội số của 1.000 VNĐ (tối thiểu 1.000 VNĐ).');
      return;
    }

    let parsedLimitTotal: number | null = null;
    if (formUsageLimitTotal.trim()) {
      const parsed = Number(formUsageLimitTotal.trim());
      if (isNaN(parsed) || parsed < 1 || !Number.isInteger(parsed)) {
        setFormError('Tổng lượt sử dụng phải là số nguyên lớn hơn 0.');
        return;
      }
      parsedLimitTotal = parsed;
    }

    let parsedLimitPerUser: number | null = null;
    if (formUsageLimitPerUser.trim()) {
      const parsed = Number(formUsageLimitPerUser.trim());
      if (isNaN(parsed) || parsed < 1 || !Number.isInteger(parsed)) {
        setFormError('Lượt sử dụng mỗi người phải là số nguyên lớn hơn 0.');
        return;
      }
      parsedLimitPerUser = parsed;
    }

    try {
      setIsSaving(true);
      const payload: any = {
        code: cleanCode,
        name: formName.trim(),
        description: formDescription.trim(),
        discount_type: formDiscountType,
        discount_value: formDiscountValue,
        max_discount_vnd: formDiscountType === 'percent' ? parsedMaxDiscount : null,
        min_order_vnd: formMinOrderVnd,
        usage_limit_total: parsedLimitTotal,
        usage_limit_per_user: parsedLimitPerUser,
        starts_at: formStartsAt ? Math.floor(new Date(formStartsAt).getTime() / 1000) : null,
        ends_at: formEndsAt ? Math.floor(new Date(formEndsAt).getTime() / 1000) : null,
        is_active: formIsActive,
        plan_ids: formPlanIds,
      };

      if (editingCoupon) {
        await updateAdminCoupon(editingCoupon.id, payload);
        setNotice(`Đã cập nhật mã giảm giá "${cleanCode}" thành công!`);
      } else {
        await createAdminCoupon(payload);
        setNotice(`Đã tạo mã giảm giá mới "${cleanCode}" thành công!`);
      }

      setIsModalOpen(false);
      setTimeout(() => setNotice(null), 3000);
      loadCoupons();
    } catch (err: any) {
      setFormError(err.message || 'Lỗi khi lưu mã giảm giá.');
    } finally {
      setIsSaving(false);
    }
  };

  // Toggle active status directly from table
  const handleToggleActive = async (coupon: AdminCoupon) => {
    try {
      const newStatus = !coupon.is_active;
      await toggleAdminCoupon(coupon.id, newStatus);
      setCoupons((prev) =>
        prev.map((c) => (c.id === coupon.id ? { ...c, is_active: newStatus } : c))
      );
      setNotice(`Đã ${newStatus ? 'kích hoạt' : 'tạm dừng'} mã "${coupon.code}"!`);
      setTimeout(() => setNotice(null), 2500);
    } catch (err: any) {
      setError(err.message || 'Lỗi khi thay đổi trạng thái.');
    }
  };

  // Open Stats Modal
  const handleOpenStats = async (coupon: AdminCoupon) => {
    setStatsModalCoupon(coupon);
    setCouponStats(null);
    setIsLoadingStats(true);
    try {
      const res = await fetchAdminCouponStats(coupon.id);
      if (res.success && res.stats) {
        setCouponStats(res.stats);
      }
    } catch (err: any) {
      setError(err.message || 'Lỗi khi lấy dữ liệu thống kê mã giảm giá.');
    } finally {
      setIsLoadingStats(false);
    }
  };

  // Confirm Delete
  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      setIsDeleting(true);
      await deleteAdminCoupon(deleteTarget.id);
      setDeleteTarget(null);
      setNotice(`Đã xóa mã giảm giá "${deleteTarget.code}" thành công!`);
      setTimeout(() => setNotice(null), 3000);
      loadCoupons();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa mã giảm giá.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Alert Notices */}
      {notice && (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-xs text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Top Header & Action Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Ticket className="h-5 w-5 text-amber-500" />
            <span>Quản Lý Mã Giảm Giá (Coupons)</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Tổng cộng <span className="font-bold text-amber-400">{totalCoupons}</span> mã giảm giá áp dụng cho gói kích hoạt Locket Gold qua Coin và VietQR.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadCoupons}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-900/80 px-3.5 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-800 hover:text-white transition disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Làm mới</span>
          </button>

          <button
            type="button"
            onClick={handleOpenCreate}
            className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 hover:bg-amber-400 transition shadow-lg shadow-amber-500/15"
          >
            <Plus className="h-4 w-4" />
            <span>Thêm mã mới</span>
          </button>
        </div>
      </div>

      {/* Search & Status Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1.5 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-1.5 backdrop-blur-md overflow-x-auto">
          {[
            { id: 'all', label: 'Tất cả' },
            { id: 'active', label: 'Đang hoạt động' },
            { id: 'inactive', label: 'Tạm dừng' },
            { id: 'exhausted', label: 'Đã hết lượt' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                setStatusFilter(tab.id as any);
                setCurrentPage(1);
              }}
              className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all whitespace-nowrap ${
                statusFilter === tab.id
                  ? 'bg-amber-500 text-zinc-950 shadow-md'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative min-w-[240px] sm:w-72">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Tìm theo mã hoặc tên..."
            className="w-full rounded-2xl border border-zinc-800 bg-zinc-900/80 pl-9 pr-3.5 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
          />
        </div>
      </div>

      {/* Coupons Table */}
      <div className="rounded-3xl border border-zinc-800 bg-zinc-900/80 shadow-xl overflow-hidden backdrop-blur-md">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/60 text-zinc-400 font-semibold">
                <th className="py-3.5 px-4">Mã Coupon & Tên</th>
                <th className="py-3.5 px-4">Mức Giảm Giá</th>
                <th className="py-3.5 px-4">Đơn Tối Thiểu</th>
                <th className="py-3.5 px-4">Lượt Đã Dùng</th>
                <th className="py-3.5 px-4">Gói Áp Dụng</th>
                <th className="py-3.5 px-4 text-center">Trạng Thái</th>
                <th className="py-3.5 px-4 text-right">Hành Động</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-amber-500 mb-2" />
                    <span>Đang tải danh sách mã giảm giá...</span>
                  </td>
                </tr>
              ) : coupons.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500">
                    Không tìm thấy mã giảm giá nào phù hợp.
                  </td>
                </tr>
              ) : (
                coupons.map((coupon) => {
                  const isPercent = coupon.discount_type === 'percent';
                  const isExhausted = Boolean(coupon.is_exhausted);
                  const isCurrentlyActive = Boolean(coupon.is_active);

                  return (
                    <tr key={coupon.id} className="hover:bg-zinc-800/30 transition-colors">
                      {/* Code & Name */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <span className="rounded-lg bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 font-mono font-black text-amber-400 text-xs">
                            {coupon.code}
                          </span>
                          {coupon.description && (
                            <span
                              className="text-zinc-500 hover:text-zinc-300 cursor-help"
                              title={coupon.description}
                            >
                              <Tag className="h-3.5 w-3.5" />
                            </span>
                          )}
                        </div>
                        <div className="font-semibold text-white mt-1">{coupon.name}</div>
                      </td>

                      {/* Discount Value */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-amber-400 flex items-center gap-1">
                          {isPercent ? (
                            <>
                              <Percent className="h-3.5 w-3.5" />
                              <span>Giảm {coupon.discount_value}%</span>
                            </>
                          ) : (
                            <>
                              <Coins className="h-3.5 w-3.5" />
                              <span>Giảm {formatVND(coupon.discount_value)}</span>
                            </>
                          )}
                        </div>
                        {isPercent && coupon.max_discount_vnd ? (
                          <div className="text-[11px] text-zinc-400 mt-0.5">
                            Tối đa {formatVND(coupon.max_discount_vnd)}
                          </div>
                        ) : null}
                      </td>

                      {/* Min Order */}
                      <td className="py-3.5 px-4">
                        <span className="font-mono text-zinc-300">
                          {formatVND(coupon.min_order_vnd)}
                        </span>
                      </td>

                      {/* Usage */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-white font-mono">
                            {coupon.redeemed_count ?? 0}
                          </span>
                          <span className="text-zinc-500">/</span>
                          <span className="text-zinc-400 font-mono">
                            {coupon.usage_limit_total ? coupon.usage_limit_total : '∞'}
                          </span>
                        </div>
                        {coupon.usage_limit_per_user && (
                          <div className="text-[10px] text-zinc-500 mt-0.5">
                            Tối đa {coupon.usage_limit_per_user} lần/khách
                          </div>
                        )}
                      </td>

                      {/* Applicable Plans */}
                      <td className="py-3.5 px-4">
                        {coupon.applicable_plan_ids && coupon.applicable_plan_ids.length > 0 ? (
                          <div className="flex flex-wrap gap-1 max-w-[180px]">
                            {coupon.applicable_plan_ids.map((pid) => {
                              const plan = availablePlans.find((p) => p.id === pid);
                              return (
                                <span
                                  key={pid}
                                  className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300 font-medium"
                                >
                                  {plan ? plan.name : `Gói #${pid}`}
                                </span>
                              );
                            })}
                          </div>
                        ) : (
                          <span className="text-emerald-400 font-medium text-[11px]">
                            Tất cả các gói
                          </span>
                        )}
                      </td>

                      {/* Status Toggle */}
                      <td className="py-3.5 px-4 text-center">
                        <button
                          type="button"
                          onClick={() => handleToggleActive(coupon)}
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold border transition ${
                            isExhausted
                              ? 'bg-zinc-800 text-zinc-400 border-zinc-700'
                              : isCurrentlyActive
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20 hover:bg-rose-500/20'
                          }`}
                          title="Bấm để bật / tắt mã"
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              isExhausted
                                ? 'bg-zinc-500'
                                : isCurrentlyActive
                                ? 'bg-emerald-500 animate-pulse'
                                : 'bg-rose-500'
                            }`}
                          />
                          <span>
                            {isExhausted
                              ? 'Hết lượt'
                              : isCurrentlyActive
                              ? 'Hoạt động'
                              : 'Tạm dừng'}
                          </span>
                        </button>
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => handleOpenStats(coupon)}
                            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-amber-400 transition"
                            title="Thống kê chi tiết"
                          >
                            <BarChart3 className="h-4 w-4" />
                          </button>

                          <button
                            type="button"
                            onClick={() => handleOpenEdit(coupon)}
                            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-white transition"
                            title="Chỉnh sửa"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>

                          <button
                            type="button"
                            onClick={() => setDeleteTarget(coupon)}
                            className="rounded-lg p-2 text-zinc-400 hover:bg-rose-500/10 hover:text-rose-400 transition"
                            title="Xóa mã"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-zinc-800 px-5 py-3.5 bg-zinc-950/40 text-xs">
            <span className="text-zinc-400">
              Trang <span className="font-bold text-white">{currentPage}</span> / {totalPages}
            </span>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-zinc-300 hover:bg-zinc-800 disabled:opacity-40"
              >
                Trước
              </button>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
                className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-zinc-300 hover:bg-zinc-800 disabled:opacity-40"
              >
                Sau
              </button>
            </div>
          </div>
        )}
      </div>

      {/* CREATE / EDIT COUPON MODAL */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingCoupon ? `Chỉnh Sửa Mã: ${editingCoupon.code}` : 'Tạo Mã Giảm Giá Mới'}
        maxWidth="2xl"
      >
        <form onSubmit={handleSaveCoupon} className="space-y-4 text-xs">
          {formError && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{formError}</span>
            </div>
          )}

          {/* Row 1: Code & Name */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Mã giảm giá (Code) <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={formCode}
                onChange={(e) => setFormCode(e.target.value.toUpperCase())}
                placeholder="VD: GOLDVIP, SALE50"
                required
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 font-mono font-bold text-amber-400 uppercase placeholder-zinc-600 focus:outline-none focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Tên chương trình <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="VD: Giảm giá hè 2026"
                required
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block font-bold text-zinc-300 mb-1">Mô tả chi tiết</label>
            <textarea
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              rows={2}
              placeholder="Thông tin thêm về điều kiện áp dụng..."
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-amber-500"
            />
          </div>

          {/* Row 2: Discount Type & Value */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-zinc-300 mb-1">Loại chiết khấu</label>
              <select
                value={formDiscountType}
                onChange={(e) => {
                  const type = e.target.value as 'percent' | 'fixed_vnd';
                  setFormDiscountType(type);
                  if (type === 'percent') {
                    setFormDiscountValue(10);
                  } else {
                    setFormDiscountValue(10000);
                  }
                }}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-zinc-100 focus:outline-none focus:border-amber-500"
              >
                <option value="percent">Theo phần trăm (%)</option>
                <option value="fixed_vnd">Số tiền cố định (VNĐ)</option>
              </select>
            </div>

            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Mức giảm {formDiscountType === 'percent' ? '(1% - 99%)' : '(Bội số 1.000 VNĐ)'}{' '}
                <span className="text-rose-400">*</span>
              </label>
              <input
                type="number"
                value={formDiscountValue}
                onChange={(e) => setFormDiscountValue(Math.max(0, parseInt(e.target.value) || 0))}
                step={formDiscountType === 'percent' ? 1 : 1000}
                min={formDiscountType === 'percent' ? 1 : 1000}
                max={formDiscountType === 'percent' ? 99 : undefined}
                required
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 font-mono font-bold text-amber-400 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          {/* Row 3: Max Discount (for percent) & Min Order VND */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Giảm tối đa (VNĐ) {formDiscountType === 'percent' ? '(Tùy chọn)' : '(Không áp dụng)'}
              </label>
              <input
                type="number"
                value={formMaxDiscountVnd}
                onChange={(e) => setFormMaxDiscountVnd(e.target.value)}
                disabled={formDiscountType !== 'percent'}
                placeholder={formDiscountType === 'percent' ? 'VD: 50000 (Để trống nếu không giới hạn)' : '—'}
                step={1000}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-amber-500 disabled:opacity-40"
              />
            </div>

            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Đơn hàng tối thiểu (VNĐ) <span className="text-rose-400">*</span>
              </label>
              <input
                type="number"
                value={formMinOrderVnd}
                onChange={(e) => setFormMinOrderVnd(Math.max(1000, parseInt(e.target.value) || 1000))}
                step={1000}
                min={1000}
                required
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 font-mono text-zinc-100 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          {/* Row 4: Total Limit & Per-User Limit */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Tổng lượt sử dụng toàn sàn
              </label>
              <input
                type="number"
                value={formUsageLimitTotal}
                onChange={(e) => setFormUsageLimitTotal(e.target.value)}
                placeholder="Để trống nếu không giới hạn"
                min={1}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Lượt sử dụng tối đa mỗi khách
              </label>
              <input
                type="number"
                value={formUsageLimitPerUser}
                onChange={(e) => setFormUsageLimitPerUser(e.target.value)}
                placeholder="Mặc định: 1 lượt/khách"
                min={1}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          {/* Row 5: Schedule window */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Thời gian bắt đầu (Tùy chọn)
              </label>
              <input
                type="datetime-local"
                value={formStartsAt}
                onChange={(e) => setFormStartsAt(e.target.value)}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-zinc-100 focus:outline-none focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block font-bold text-zinc-300 mb-1">
                Thời gian kết thúc (Tùy chọn)
              </label>
              <input
                type="datetime-local"
                value={formEndsAt}
                onChange={(e) => setFormEndsAt(e.target.value)}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-zinc-100 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          {/* Row 6: Applicable Plans Multiselect */}
          <div>
            <label className="block font-bold text-zinc-300 mb-1">
              Gói dịch vụ được áp dụng (Không chọn = Áp dụng tất cả các gói)
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-36 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
              {availablePlans.map((plan) => {
                const isChecked = formPlanIds.includes(plan.id);
                return (
                  <label
                    key={plan.id}
                    className="flex items-center gap-2 cursor-pointer select-none text-[11px] text-zinc-300 hover:text-white"
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormPlanIds([...formPlanIds, plan.id]);
                        } else {
                          setFormPlanIds(formPlanIds.filter((id) => id !== plan.id));
                        }
                      }}
                      className="h-3.5 w-3.5 rounded border-zinc-700 bg-zinc-900 text-amber-500 focus:ring-amber-500"
                    />
                    <span className="truncate">{plan.name}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Row 7: Active Toggle */}
          <div className="pt-2">
            <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-zinc-200">
              <input
                type="checkbox"
                checked={formIsActive}
                onChange={(e) => setFormIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500"
              />
              <span className="font-bold">Kích hoạt mã giảm giá ngay sau khi lưu</span>
            </label>
          </div>

          {/* Modal Footer */}
          <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-zinc-800">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-800"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-5 py-2 text-xs font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50"
            >
              {isSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              <span>{editingCoupon ? 'Lưu thay đổi' : 'Tạo mã ngay'}</span>
            </button>
          </div>
        </form>
      </Modal>

      {/* STATS MODAL */}
      <Modal
        isOpen={Boolean(statsModalCoupon)}
        onClose={() => setStatsModalCoupon(null)}
        title={`Thống Kê Mã Giảm Giá: ${statsModalCoupon?.code || ''}`}
        maxWidth="4xl"
      >
        <div className="space-y-6">
          {isLoadingStats ? (
            <div className="py-12 text-center text-zinc-500">
              <Loader2 className="h-6 w-6 animate-spin mx-auto text-amber-500 mb-2" />
              <span>Đang tải số liệu thống kê...</span>
            </div>
          ) : !couponStats ? (
            <div className="py-8 text-center text-zinc-500">
              Không có dữ liệu thống kê cho mã này.
            </div>
          ) : (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
                  <div className="text-[11px] text-zinc-400 font-medium">Đã dùng (Redeemed)</div>
                  <div className="text-xl font-black text-white mt-1">
                    {couponStats.redeemed_count || 0}
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
                  <div className="text-[11px] text-zinc-400 font-medium">Đang giữ chỗ (Reserved)</div>
                  <div className="text-xl font-black text-amber-400 mt-1">
                    {couponStats.reserved_count || 0}
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
                  <div className="text-[11px] text-zinc-400 font-medium">Tổng tiền đã giảm</div>
                  <div className="text-lg font-black text-rose-400 mt-1 font-mono">
                    {formatVND(couponStats.total_discount_vnd || 0)}
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
                  <div className="text-[11px] text-zinc-400 font-medium">Doanh thu thu về</div>
                  <div className="text-lg font-black text-emerald-400 mt-1 font-mono">
                    {formatVND(couponStats.total_revenue_vnd || 0)}
                  </div>
                </div>
              </div>

              {/* Recent Redemptions Table */}
              <div>
                <h4 className="text-xs font-bold text-white mb-2.5">
                  Lịch sử áp dụng gần đây ({couponStats.recent_redemptions?.length || 0})
                </h4>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/40 overflow-hidden">
                  <div className="overflow-x-auto max-h-72">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-zinc-800 bg-zinc-950/80 text-zinc-400">
                          <th className="py-2.5 px-3">Thời Gian</th>
                          <th className="py-2.5 px-3">Khách Hàng</th>
                          <th className="py-2.5 px-3">Giá Gốc</th>
                          <th className="py-2.5 px-3">Đã Giảm</th>
                          <th className="py-2.5 px-3">Thực Trả</th>
                          <th className="py-2.5 px-3 text-center">Trạng Thái</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                        {!couponStats.recent_redemptions || couponStats.recent_redemptions.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-6 text-center text-zinc-500">
                              Chưa có lượt sử dụng nào được ghi nhận.
                            </td>
                          </tr>
                        ) : (
                          couponStats.recent_redemptions.map((item) => (
                            <tr key={item.id} className="hover:bg-zinc-800/20">
                              <td className="py-2.5 px-3 font-mono text-zinc-400 text-[11px]">
                                {formatDate(item.created_at)}
                              </td>
                              <td className="py-2.5 px-3">
                                <span className="font-semibold text-white">
                                  {item.username || item.email || `User #${item.user_id}`}
                                </span>
                              </td>
                              <td className="py-2.5 px-3 font-mono text-zinc-400">
                                {formatVND(item.original_vnd)}
                              </td>
                              <td className="py-2.5 px-3 font-mono text-rose-400 font-bold">
                                -{formatVND(item.discount_vnd)}
                              </td>
                              <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">
                                {formatVND(item.final_price_vnd)}
                              </td>
                              <td className="py-2.5 px-3 text-center">
                                <span
                                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                    item.status === 'redeemed'
                                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                      : item.status === 'reserved'
                                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                      : 'bg-zinc-800 text-zinc-400'
                                  }`}
                                >
                                  {item.status === 'redeemed'
                                    ? 'Đã duyệt'
                                    : item.status === 'reserved'
                                    ? 'Đang chờ'
                                    : 'Đã hủy'}
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </>
          )}

          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={() => setStatsModalCoupon(null)}
              className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-800"
            >
              Đóng
            </button>
          </div>
        </div>
      </Modal>

      {/* CONFIRM DELETE DIALOG */}
      {deleteTarget && (
        <ConfirmDialog
          isOpen={Boolean(deleteTarget)}
          onClose={() => setDeleteTarget(null)}
          onConfirm={handleConfirmDelete}
          title="Xóa Mã Giảm Giá"
          message={`Bạn có chắc chắn muốn xóa mã giảm giá "${deleteTarget.code}" (${deleteTarget.name})? Chỉ mã chưa từng phát sinh lượt giữ chỗ/sử dụng mới có thể xóa; mã đã có lịch sử cần được vô hiệu hóa.`}
          confirmText="Xác nhận xóa"
          isDanger={true}
          isLoading={isDeleting}
        />
      )}
    </div>
  );
};
