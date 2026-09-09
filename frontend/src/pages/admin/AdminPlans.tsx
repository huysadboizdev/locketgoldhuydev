import React, { useState, useEffect, useCallback } from 'react';
import {
  Plus,
  Edit2,
  Trash2,
  Check,
  RefreshCw,
  AlertCircle,
  Loader2,
  Flame,
  Layers,
} from 'lucide-react';
import { Modal } from '../../components/admin/Modal';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { AdminPagination, ADMIN_PAGE_SIZE } from '../../components/admin/AdminPagination';
import {
  fetchAdminPlans,
  createAdminPlan,
  updateAdminPlan,
  toggleAdminPlan,
  deleteAdminPlan,
} from '../../api/adminEndpoints';
import type { AdminPlanItem } from '../../types/admin';

const integerFormatter = new Intl.NumberFormat('vi-VN', {
  maximumFractionDigits: 0,
  useGrouping: true,
});

const formatGroupedInteger = (value: number) =>
  integerFormatter.format(Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0);

const parseGroupedInteger = (value: string) => {
  const digits = value.replace(/\D/g, '');
  if (!digits) return 0;

  const parsed = Number(digits);
  return Number.isSafeInteger(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
};

export const AdminPlans: React.FC = () => {
  const [plans, setPlans] = useState<AdminPlanItem[]>([]);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create / Edit Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<AdminPlanItem | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form Fields
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [shortDescription, setShortDescription] = useState('');
  const [durationDays, setDurationDays] = useState<number>(30);
  const [priceVnd, setPriceVnd] = useState<number>(50000);
  const [priceCoin, setPriceCoin] = useState<number>(50);
  const [productId, setProductId] = useState('');
  const [supportedPlatforms, setSupportedPlatforms] = useState<'all' | 'ios' | 'android'>('all');
  const [iosFulfillmentMode, setIosFulfillmentMode] = useState<'auto_activation' | 'manual_contact' | 'disabled'>('auto_activation');
  const [androidFulfillmentMode, setAndroidFulfillmentMode] = useState<'apk_download' | 'manual_contact' | 'disabled'>('apk_download');
  const [featuresText, setFeaturesText] = useState('');
  const [isPopular, setIsPopular] = useState(false);
  const [isActive, setIsActive] = useState(true);
  const [sortOrder, setSortOrder] = useState<number>(0);

  // Delete modal
  const [deletingPlan, setDeletingPlan] = useState<AdminPlanItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadPlans = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await fetchAdminPlans();
      if (res.success) {
        setPlans(res.plans);
      }
    } catch (err: any) {
      setError(err.message || 'Không thể tải danh sách gói dịch vụ.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  const pages = Math.max(1, Math.ceil(plans.length / ADMIN_PAGE_SIZE));
  const visiblePlans = plans.slice((page - 1) * ADMIN_PAGE_SIZE, page * ADMIN_PAGE_SIZE);

  useEffect(() => {
    setPage((current) => Math.min(current, pages));
  }, [pages]);

  const handleOpenCreate = () => {
    setEditingPlan(null);
    setName('');
    setSlug('');
    setShortDescription('');
    setDurationDays(30);
    setPriceVnd(50000);
    setPriceCoin(50);
    setProductId('');
    setSupportedPlatforms('all');
    setIosFulfillmentMode('auto_activation');
    setAndroidFulfillmentMode('apk_download');
    setFeaturesText('Kích hoạt Locket Gold\nCấp phép tự động\nHỗ trợ 24/7');
    setIsPopular(false);
    setIsActive(true);
    setSortOrder(0);
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (plan: AdminPlanItem) => {
    setEditingPlan(plan);
    setName(plan.name);
    setSlug(plan.slug);
    setShortDescription(plan.short_description || '');
    setDurationDays(plan.duration_days);
    setPriceVnd(plan.price_vnd);
    setPriceCoin(plan.price_coin);
    setProductId(plan.product_id || '');
    setSupportedPlatforms(plan.supported_platforms);
    setIosFulfillmentMode(plan.ios_fulfillment_mode || (plan.supported_platforms === 'android' ? 'disabled' : 'auto_activation'));
    setAndroidFulfillmentMode(plan.android_fulfillment_mode || (plan.supported_platforms === 'ios' ? 'disabled' : 'apk_download'));
    setFeaturesText(Array.isArray(plan.features) ? plan.features.join('\n') : '');
    setIsPopular(Boolean(plan.is_popular));
    setIsActive(Boolean(plan.is_active));
    setSortOrder(plan.sort_order || 0);
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSavePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setFormError('Vui lòng nhập tên gói.');
      return;
    }
    if (!slug.trim()) {
      setFormError('Vui lòng nhập mã định danh (slug).');
      return;
    }
    if (priceVnd % 1000 !== 0) {
      setFormError('Giá tiền VND phải chia hết cho 1.000đ.');
      return;
    }
    if (priceCoin < 0) {
      setFormError('Giá Coin không được âm.');
      return;
    }

    const features = featuresText
      .split('\n')
      .map((f) => f.trim())
      .filter(Boolean);

    const payload = {
      name: name.trim(),
      slug: slug.trim(),
      short_description: shortDescription.trim(),
      duration_days: Number(durationDays),
      price_vnd: Number(priceVnd),
      price_coin: Number(priceCoin),
      product_id: productId.trim() || slug.trim(),
      supported_platforms: supportedPlatforms,
      ios_fulfillment_mode: iosFulfillmentMode,
      android_fulfillment_mode: androidFulfillmentMode,
      features,
      is_popular: isPopular,
      is_active: isActive,
      sort_order: Number(sortOrder),
    };

    try {
      setIsSaving(true);
      setFormError(null);
      if (editingPlan) {
        await updateAdminPlan(editingPlan.id, payload);
      } else {
        await createAdminPlan(payload);
      }
      setIsModalOpen(false);
      loadPlans();
    } catch (err: any) {
      setFormError(err.message || 'Lỗi khi lưu thông tin gói.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleStatus = async (plan: AdminPlanItem) => {
    try {
      await toggleAdminPlan(plan.id, !plan.is_active);
      loadPlans();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi đổi trạng thái gói.');
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingPlan) return;
    try {
      setIsDeleting(true);
      await deleteAdminPlan(deletingPlan.id);
      setDeletingPlan(null);
      loadPlans();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa gói.');
    } finally {
      setIsDeleting(false);
    }
  };

  const formatVnd = (amount: number = 0) => {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
  };

  return (
    <div className="space-y-6">
      {/* Action Header */}
      <div className="flex items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 backdrop-blur-md">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Layers className="h-5 w-5 text-amber-500" />
            <span>Quản Lý Gói Dịch Vụ Locket Gold</span>
          </h2>
          <p className="text-xs text-zinc-400">
            Cấu hình các gói thời hạn, biểu giá VND / Coin và tính năng hiển thị cho khách hàng.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadPlans}
            disabled={isLoading}
            className="rounded-xl border border-zinc-800 bg-zinc-950 p-2.5 text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors"
            title="Tải lại"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
          </button>
          <button
            type="button"
            onClick={handleOpenCreate}
            className="flex items-center gap-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 px-4 py-2.5 text-xs font-bold text-zinc-950 transition-colors shadow-lg shadow-amber-500/10"
          >
            <Plus className="h-4 w-4" />
            <span>Thêm Gói Mới</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {isLoading ? (
          <div className="col-span-full py-12 text-center text-zinc-500">
            <Loader2 className="h-6 w-6 animate-spin text-amber-500 mx-auto mb-2" />
            <span>Đang tải danh mục gói dịch vụ...</span>
          </div>
        ) : plans.length === 0 ? (
          <div className="col-span-full py-12 text-center text-zinc-500">
            Chưa có gói dịch vụ nào được thiết lập.
          </div>
        ) : (
          visiblePlans.map((p) => (
            <div
              key={p.id}
              className={`relative flex flex-col rounded-3xl border p-6 backdrop-blur-md transition-all ${
                p.is_popular
                  ? 'border-amber-500/40 bg-zinc-900/90 shadow-xl shadow-amber-500/5'
                  : 'border-zinc-800 bg-zinc-900/70 hover:border-zinc-700'
              }`}
            >
              {p.is_popular && (
                <div className="absolute -top-3 left-6 flex items-center gap-1 rounded-full bg-amber-500 px-3 py-0.5 text-[10px] font-black uppercase text-zinc-950 shadow-md">
                  <Flame className="h-3 w-3 fill-current" />
                  <span>Phổ Biến Nhất</span>
                </div>
              )}

              <div className="flex items-start justify-between mb-3 pt-1">
                <div>
                  <h3 className="text-lg font-bold text-white">{p.name}</h3>
                  <div className="text-[11px] font-mono text-zinc-400">{p.slug}</div>
                </div>
                <button
                  type="button"
                  onClick={() => handleToggleStatus(p)}
                  className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border transition-colors ${
                    p.is_active
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                  }`}
                  title="Bấm để bật/tắt hiển thị"
                >
                  {p.is_active ? 'Đang bán' : 'Tạm ẩn'}
                </button>
              </div>

              {/* Pricing */}
              <div className="my-3 rounded-2xl bg-zinc-950 border border-zinc-800/80 p-3 space-y-1">
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-zinc-400">Giá VND:</span>
                  <span className="text-base font-extrabold text-white">{formatVnd(p.price_vnd)}</span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-zinc-400">Giá Coin:</span>
                  <span className="text-sm font-bold text-amber-400">{formatGroupedInteger(p.price_coin)} Coin</span>
                </div>
                <div className="flex items-baseline justify-between text-[11px] text-zinc-500 pt-1 border-t border-zinc-800/60">
                  <span>Thời hạn:</span>
                  <span className="font-semibold text-zinc-300">{p.duration_days} ngày</span>
                </div>
                <div className="flex items-baseline justify-between text-[11px] text-zinc-500">
                  <span>Nền tảng:</span>
                  <span className="font-semibold uppercase text-zinc-300">{p.supported_platforms}</span>
                </div>
              </div>

              {/* Features List */}
              <div className="flex-1 space-y-1.5 my-3">
                <span className="text-[11px] font-semibold text-zinc-400 block">Quyền lợi gói:</span>
                {Array.isArray(p.features) && p.features.length > 0 ? (
                  p.features.map((feat, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-xs text-zinc-300">
                      <Check className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                      <span>{feat}</span>
                    </div>
                  ))
                ) : (
                  <span className="text-xs text-zinc-500 italic">Chưa cấu hình tính năng</span>
                )}
              </div>

              {/* Card Actions */}
              <div className="flex items-center justify-end gap-2 pt-4 border-t border-zinc-800/80">
                <button
                  type="button"
                  onClick={() => handleOpenEdit(p)}
                  className="flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-700 hover:text-white transition-colors"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                  <span>Sửa</span>
                </button>
                <button
                  type="button"
                  onClick={() => setDeletingPlan(p)}
                  className="rounded-xl border border-zinc-800 bg-zinc-950 p-2 text-zinc-400 hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
                  title="Xóa gói"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900/60">
        <AdminPagination page={page} pages={pages} total={plans.length} itemLabel="gói" onPageChange={setPage} />
      </div>

      {/* Create / Edit Plan Modal */}
      {isModalOpen && (
        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title={editingPlan ? `Chỉnh Sửa Gói: ${editingPlan.name}` : 'Tạo Gói Dịch Vụ Mới'}
          maxWidth="lg"
        >
          <form onSubmit={handleSavePlan} className="space-y-4 text-xs">
            {formError && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                <span>{formError}</span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Tên gói *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ví dụ: Gói 1 Tháng VIP"
                  required
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Mã Slug *</label>
                <input
                  type="text"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="Ví dụ: monthly_vip"
                  required
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Thời hạn (ngày) *</label>
                <input
                  type="number"
                  min="1"
                  value={durationDays}
                  onChange={(e) => setDurationDays(parseInt(e.target.value, 10) || 1)}
                  required
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Giá VND (chia hết 1000) *</label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9.]*"
                  value={formatGroupedInteger(priceVnd)}
                  onChange={(e) => setPriceVnd(parseGroupedInteger(e.target.value))}
                  required
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Giá Coin *</label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9.]*"
                  value={formatGroupedInteger(priceCoin)}
                  onChange={(e) => setPriceCoin(parseGroupedInteger(e.target.value))}
                  required
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Nền tảng hỗ trợ</label>
                <select
                  value={supportedPlatforms}
                  onChange={(e) => {
                    const next = e.target.value as 'all' | 'ios' | 'android';
                    setSupportedPlatforms(next);
                    if (next === 'ios') {
                      setIosFulfillmentMode(iosFulfillmentMode === 'disabled' ? 'auto_activation' : iosFulfillmentMode);
                      setAndroidFulfillmentMode('disabled');
                    } else if (next === 'android') {
                      setIosFulfillmentMode('disabled');
                      setAndroidFulfillmentMode(androidFulfillmentMode === 'disabled' ? 'apk_download' : androidFulfillmentMode);
                    } else {
                      setIosFulfillmentMode(iosFulfillmentMode === 'disabled' ? 'auto_activation' : iosFulfillmentMode);
                      setAndroidFulfillmentMode(androidFulfillmentMode === 'disabled' ? 'apk_download' : androidFulfillmentMode);
                    }
                  }}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
                >
                  <option value="all">Tất cả (iOS & Android)</option>
                  <option value="ios">Chỉ iOS</option>
                  <option value="android">Chỉ Android</option>
                </select>
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Thứ tự hiển thị (Sort Order)</label>
                <input
                  type="number"
                  value={sortOrder}
                  onChange={(e) => setSortOrder(parseInt(e.target.value, 10) || 0)}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-xl border border-zinc-800 bg-zinc-950/40 p-3">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Luồng xử lý iOS</label>
                <select
                  value={iosFulfillmentMode}
                  disabled={supportedPlatforms === 'android'}
                  onChange={(e) => setIosFulfillmentMode(e.target.value as typeof iosFulfillmentMode)}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 disabled:opacity-50 focus:outline-none focus:border-amber-500"
                >
                  <option value="auto_activation">Kích hoạt tự động</option>
                  <option value="manual_contact">Gửi liên hệ cho Admin</option>
                  <option value="disabled">Không hỗ trợ</option>
                </select>
              </div>
              <div>
                <label className="block text-zinc-300 font-semibold mb-1">Luồng xử lý Android</label>
                <select
                  value={androidFulfillmentMode}
                  disabled={supportedPlatforms === 'ios'}
                  onChange={(e) => setAndroidFulfillmentMode(e.target.value as typeof androidFulfillmentMode)}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 disabled:opacity-50 focus:outline-none focus:border-amber-500"
                >
                  <option value="apk_download">Cấp link tải APK</option>
                  <option value="manual_contact">Gửi liên hệ cho Admin</option>
                  <option value="disabled">Không hỗ trợ</option>
                </select>
              </div>
              <p className="sm:col-span-2 text-[11px] leading-relaxed text-zinc-500">
                VPN/Pro nên chọn “Gửi liên hệ cho Admin”. Gói Android tải file chọn “Cấp link tải APK”. Chỉ luồng tự động mới vào hàng đợi kích hoạt Locket.
              </p>
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1">
                Danh sách tính năng (Mỗi dòng một tính năng)
              </label>
              <textarea
                value={featuresText}
                onChange={(e) => setFeaturesText(e.target.value)}
                placeholder="Tính năng 1&#10;Tính năng 2&#10;Tính năng 3"
                rows={3}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-zinc-100 focus:outline-none focus:border-amber-500"
              />
            </div>

            <div className="flex items-center gap-6 pt-1">
              <label className="flex items-center gap-2 cursor-pointer select-none text-zinc-300">
                <input
                  type="checkbox"
                  checked={isPopular}
                  onChange={(e) => setIsPopular(e.target.checked)}
                  className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500"
                />
                <span>Đánh dấu gói Phổ Biến (Highlight)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none text-zinc-300">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500"
                />
                <span>Kích hoạt bán gói</span>
              </label>
            </div>

            <div className="flex justify-end gap-2.5 pt-3 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="rounded-xl border border-zinc-700 bg-zinc-800 px-4 py-2.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-700"
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-5 py-2.5 text-xs font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50"
              >
                {isSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>{editingPlan ? 'Lưu Thay Đổi' : 'Tạo Gói Mới'}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Delete Confirmation Dialog */}
      {deletingPlan && (
        <ConfirmDialog
          isOpen={Boolean(deletingPlan)}
          onClose={() => setDeletingPlan(null)}
          onConfirm={handleDeleteConfirm}
          title="Xóa Gói Dịch Vụ"
          message={`Bạn có chắc chắn muốn xóa gói "${deletingPlan.name}"? Gói sẽ được ẩn khỏi hệ thống.`}
          confirmText="Xác nhận xóa"
          isDanger={true}
          isLoading={isDeleting}
        />
      )}
    </div>
  );
};
