import React, { useState, useEffect, useCallback } from 'react';
import { AnnouncementDialog } from '../../components/common/AnnouncementDialog';
import {
  Users,
  Globe,
  Key,
  Smartphone,
  Sliders,
  Plus,
  Trash2,
  Upload,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ShieldAlert,
  Bell,
  Sparkles,
  Gift,
  AlertTriangle,
  Shield,
  Info,
  PartyPopper,
  HelpCircle,
  Wrench,
  Eye,
  
  
  
  RotateCcw,
} from 'lucide-react';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { AdminPagination, ADMIN_PAGE_SIZE } from '../../components/admin/AdminPagination';
import {
  fetchAdminAccounts,
  addAdminAccount,
  deleteAdminAccount,
  fetchAdminTokens,
  fetchAdminProxies,
  addAdminProxy,
  deleteAdminProxy,
  uploadAdminMobileconfig,
  deleteAdminMobileconfig,
  fetchAdminSettings,
  updateAdminSettings,
  fetchAdminPopup,
  updateAdminPopup,
} from '../../api/adminEndpoints';
import type { PopupIcon, PopupAudience, PopupDisplayMode } from '../../types/api';

interface AdminPoolAccount {
  id?: string | number;
  slot_id?: string;
  email?: string;
  username?: string;
  status?: string;
}

const AVAILABLE_ICONS: { id: PopupIcon; label: string; icon: React.FC<{ className?: string }> }[] = [
  { id: 'sparkles', label: 'Lấp lánh', icon: Sparkles },
  { id: 'gift', label: 'Quà tặng', icon: Gift },
  { id: 'party', label: 'Sự kiện', icon: PartyPopper },
  { id: 'bell', label: 'Chuông', icon: Bell },
  { id: 'info', label: 'Thông tin', icon: Info },
  { id: 'success', label: 'Thành công', icon: CheckCircle2 },
  { id: 'warning', label: 'Cảnh báo', icon: AlertTriangle },
  { id: 'error', label: 'Báo lỗi', icon: AlertCircle },
  { id: 'help', label: 'Trợ giúp', icon: HelpCircle },
  { id: 'question', label: 'Câu hỏi', icon: HelpCircle },
  { id: 'wrench', label: 'Bảo trì', icon: Wrench },
  { id: 'shield', label: 'Bảo mật', icon: Shield },
];

export const AdminSystem: React.FC = () => {
  const [activeSubtab, setActiveSubtab] = useState<'accounts' | 'popup' | 'proxies' | 'tokens' | 'mobileconfig' | 'settings'>('accounts');

  // Accounts state (Account Pool & Rotator)
  const [accounts, setAccounts] = useState<AdminPoolAccount[]>([]);
  const [accountsPage, setAccountsPage] = useState(1);
  const [newAccUsername, setNewAccUsername] = useState('');
  const [newAccPassword, setNewAccPassword] = useState('');
  const [isAddingAcc, setIsAddingAcc] = useState(false);
  const [deleteAccountTarget, setDeleteAccountTarget] = useState<AdminPoolAccount | null>(null);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);

  // Popup Management state (12-field contract)
  const [popupForm, setPopupForm] = useState({
    enabled: false,
    version: 1,
    title: '',
    message: '',
    icon: 'sparkles' as PopupIcon,
    button_text: '',
    button_url: '',
    dismissible: true,
    audience: 'all' as PopupAudience,
    display_mode: 'once_per_session' as PopupDisplayMode,
    routes: '*',
    start_at: '',
    end_at: '',
  });
  const [isSavingPopup, setIsSavingPopup] = useState(false);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  // Proxies state
  const [proxies, setProxies] = useState<any[]>([]);
  const [proxiesPage, setProxiesPage] = useState(1);
  const [newProxyUrl, setNewProxyUrl] = useState('');
  const [isAddingProxy, setIsAddingProxy] = useState(false);
  const [deleteProxyTarget, setDeleteProxyTarget] = useState<any | null>(null);
  const [isDeletingProxy, setIsDeletingProxy] = useState(false);

  // Tokens state
  const [tokens, setTokens] = useState<any[]>([]);
  const [tokensPage, setTokensPage] = useState(1);

  // Mobileconfig state
  const [mcFile, setMcFile] = useState<File | null>(null);
  const [isUploadingMc, setIsUploadingMc] = useState(false);
  const [isConfirmingDeleteMc, setIsConfirmingDeleteMc] = useState(false);
  const [isDeletingMc, setIsDeletingMc] = useState(false);

  // Site Settings state (Maintenance Mode & General)
  const [settings, setSettings] = useState<any>(null);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  // Load subtab data
  const loadData = useCallback(async () => {
    setError(null);
    try {
      if (activeSubtab === 'accounts') {
        const res = await fetchAdminAccounts();
        if (res.success) {
          setAccounts(res.accounts || []);
        }
      } else if (activeSubtab === 'popup') {
        const res = await fetchAdminPopup();
        if (res.success && res.popup) {
          const p = res.popup;
          setPopupForm({
            enabled: Boolean(p.enabled),
            version: Number(p.version) || 1,
            title: p.title || '',
            message: p.message || (p as any).content || '',
            icon: (p.icon as PopupIcon) || 'sparkles',
            button_text: p.button_text || '',
            button_url: p.button_url || (p as any).button_link || '',
            dismissible: p.dismissible !== false,
            audience: p.audience || 'all',
            display_mode: p.display_mode || 'once_per_session',
            routes: Array.isArray(p.routes) ? p.routes.join(', ') : (p.routes || '*'),
            start_at: p.start_at ? p.start_at.slice(0, 16) : '',
            end_at: p.end_at ? p.end_at.slice(0, 16) : '',
          });
        }
      } else if (activeSubtab === 'proxies') {
        const res = await fetchAdminProxies();
        if (res.success) {
          setProxies(res.proxies || []);
        }
      } else if (activeSubtab === 'tokens') {
        const res = await fetchAdminTokens();
        if (res.success) {
          setTokens(res.tokens || []);
        }
      } else if (activeSubtab === 'settings') {
        const res = await fetchAdminSettings();
        if (res.success) {
          setSettings(res.settings || {});
        }
      }
    } catch (err: any) {
      setError(err.message || 'Lỗi khi tải dữ liệu cấu hình hệ thống.');
    }
  }, [activeSubtab]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const accountPages = Math.max(1, Math.ceil(accounts.length / ADMIN_PAGE_SIZE));
  const proxyPages = Math.max(1, Math.ceil(proxies.length / ADMIN_PAGE_SIZE));
  const tokenPages = Math.max(1, Math.ceil(tokens.length / ADMIN_PAGE_SIZE));
  const visibleAccounts = accounts.slice((accountsPage - 1) * ADMIN_PAGE_SIZE, accountsPage * ADMIN_PAGE_SIZE);
  const visibleProxies = proxies.slice((proxiesPage - 1) * ADMIN_PAGE_SIZE, proxiesPage * ADMIN_PAGE_SIZE);
  const visibleTokens = tokens.slice((tokensPage - 1) * ADMIN_PAGE_SIZE, tokensPage * ADMIN_PAGE_SIZE);

  useEffect(() => setAccountsPage((current) => Math.min(current, accountPages)), [accountPages]);
  useEffect(() => setProxiesPage((current) => Math.min(current, proxyPages)), [proxyPages]);
  useEffect(() => setTokensPage((current) => Math.min(current, tokenPages)), [tokenPages]);

  // Account operations (Account Pool)
  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAccUsername.trim() || !newAccPassword) return;
    try {
      setIsAddingAcc(true);
      setError(null);
      await addAdminAccount({ email: newAccUsername.trim(), password: newAccPassword });
      setNewAccUsername('');
      setNewAccPassword('');
      setNotice('Đã thêm tài khoản vào pool thành công!');
      setTimeout(() => setNotice(null), 3000);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi thêm tài khoản.');
    } finally {
      setIsAddingAcc(false);
    }
  };

  const handleConfirmDeleteAccount = async () => {
    if (!deleteAccountTarget) return;
    const identifier = deleteAccountTarget.slot_id ?? deleteAccountTarget.id ?? deleteAccountTarget.username ?? deleteAccountTarget.email;
    if (identifier === undefined || identifier === null || String(identifier).trim() === '') {
      setError('Không xác định được tài khoản cần xóa. Vui lòng tải lại danh sách.');
      setDeleteAccountTarget(null);
      return;
    }
    try {
      setIsDeletingAccount(true);
      await deleteAdminAccount(identifier);
      setDeleteAccountTarget(null);
      setNotice('Đã xóa tài khoản khỏi pool thành công!');
      setTimeout(() => setNotice(null), 3000);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa tài khoản.');
    } finally {
      setIsDeletingAccount(false);
    }
  };

  // Popup operations
  const handleSavePopup = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSavingPopup(true);
      setError(null);

      // Validate button_url if provided
      const trimmedUrl = popupForm.button_url.trim();
      if (
        trimmedUrl &&
        ((!trimmedUrl.startsWith('/') && !trimmedUrl.startsWith('https://')) ||
          trimmedUrl.startsWith('//') ||
          trimmedUrl.includes('\\'))
      ) {
        setError('Link nút hành động phải bắt đầu bằng "/" (đường dẫn nội bộ) hoặc "https://" (liên kết ngoài).');
        setIsSavingPopup(false);
        return;
      }
      if (Boolean(popupForm.button_text.trim()) !== Boolean(trimmedUrl)) {
        setError('Chữ trên nút và đường dẫn nút bấm phải được nhập cùng nhau.');
        setIsSavingPopup(false);
        return;
      }

      const routesArray = popupForm.routes
        .split(',')
        .map((r) => r.trim())
        .filter(Boolean);

      const payload = {
        enabled: Boolean(popupForm.enabled),
        version: Math.max(1, Number(popupForm.version) || 1),
        title: popupForm.title.trim(),
        message: popupForm.message.trim(),
        icon: popupForm.icon,
        button_text: popupForm.button_text.trim(),
        button_url: trimmedUrl,
        dismissible: Boolean(popupForm.dismissible),
        audience: popupForm.audience,
        display_mode: popupForm.display_mode,
        routes: routesArray.length > 0 ? routesArray : ['*'],
        start_at: popupForm.start_at ? new Date(popupForm.start_at).toISOString() : null,
        end_at: popupForm.end_at ? new Date(popupForm.end_at).toISOString() : null,
      };

      const res = await updateAdminPopup(payload);
      if (res.success) {
        setNotice('Đã lưu và cập nhật cấu hình Popup thành công!');
        setTimeout(() => setNotice(null), 3500);
      }
    } catch (err: any) {
      setError(err.message || 'Lỗi khi cập nhật cấu hình Popup.');
    } finally {
      setIsSavingPopup(false);
    }
  };

  // Proxy operations
  const handleAddProxy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProxyUrl.trim()) return;
    try {
      setIsAddingProxy(true);
      setError(null);
      await addAdminProxy(newProxyUrl.trim());
      setNewProxyUrl('');
      setNotice('Đã thêm proxy thành công!');
      setTimeout(() => setNotice(null), 3000);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi thêm proxy.');
    } finally {
      setIsAddingProxy(false);
    }
  };

  const handleConfirmDeleteProxy = async () => {
    if (!deleteProxyTarget) return;
    const identifier = deleteProxyTarget.id ?? deleteProxyTarget.url ?? deleteProxyTarget;
    try {
      setIsDeletingProxy(true);
      await deleteAdminProxy(identifier);
      setDeleteProxyTarget(null);
      setNotice('Đã xóa proxy thành công!');
      setTimeout(() => setNotice(null), 3000);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa proxy.');
    } finally {
      setIsDeletingProxy(false);
    }
  };

  // Mobileconfig operations
  const handleUploadMobileconfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mcFile) return;
    try {
      setIsUploadingMc(true);
      setError(null);
      await uploadAdminMobileconfig(mcFile);
      setMcFile(null);
      setNotice('Tải lên tệp cấu hình Mobileconfig thành công!');
      setTimeout(() => setNotice(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Lỗi khi tải lên mobileconfig.');
    } finally {
      setIsUploadingMc(false);
    }
  };

  const handleConfirmDeleteMobileconfig = async () => {
    try {
      setIsDeletingMc(true);
      await deleteAdminMobileconfig();
      setIsConfirmingDeleteMc(false);
      setNotice('Đã xóa mobileconfig thành công.');
      setTimeout(() => setNotice(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa mobileconfig.');
    } finally {
      setIsDeletingMc(false);
    }
  };

  // Settings operations
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSavingSettings(true);
      setError(null);
      await updateAdminSettings(settings);
      setNotice('Đã lưu cấu hình hệ thống thành công!');
      setTimeout(() => setNotice(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Lỗi khi lưu cấu hình.');
    } finally {
      setIsSavingSettings(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Subtab Segmented Control */}
      <div className="flex items-center gap-2 overflow-x-auto rounded-2xl border border-zinc-800 bg-zinc-900/80 p-2 backdrop-blur-md">
        {[
          { id: 'accounts', label: 'Account Pool & Rotator', icon: Users },
          { id: 'popup', label: 'Popup Thông Báo', icon: Bell },
          { id: 'proxies', label: 'Máy Chủ Proxy', icon: Globe },
          { id: 'tokens', label: 'Token Cache', icon: Key },
          { id: 'mobileconfig', label: 'Cấu Hình Mobileconfig', icon: Smartphone },
          { id: 'settings', label: 'Bảo Trì & Hệ Thống', icon: Sliders },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubtab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveSubtab(tab.id as any)}
              className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition-all whitespace-nowrap ${
                isActive
                  ? 'bg-amber-500 text-zinc-950 shadow-md shadow-amber-500/10'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

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

      {/* SUBTAB 1: ACCOUNTS POOL (PROTECTED - FEEDING WORKER QUEUE) */}
      {activeSubtab === 'accounts' && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Plus className="h-4 w-4 text-amber-500" />
              <span>Thêm Tài Khoản Vào Pool Xoay Vòng</span>
            </h3>
            <form onSubmit={handleAddAccount} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <input
                type="email"
                value={newAccUsername}
                onChange={(e) => setNewAccUsername(e.target.value)}
                placeholder="Email tài khoản Locket"
                required
                className="rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-amber-500"
              />
              <input
                type="password"
                value={newAccPassword}
                onChange={(e) => setNewAccPassword(e.target.value)}
                placeholder="Mật khẩu"
                required
                className="rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-amber-500"
              />
              <button
                type="submit"
                disabled={isAddingAcc}
                className="flex items-center justify-center gap-1.5 rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50"
              >
                {isAddingAcc && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>Thêm tài khoản</span>
              </button>
            </form>
          </div>

          {/* Accounts List */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 shadow-xl overflow-hidden">
            <div className="border-b border-zinc-800 px-5 py-3.5 bg-zinc-950/40 flex items-center justify-between">
              <h3 className="text-xs font-bold text-zinc-300">
                Danh sách tài khoản ({accounts.length})
              </h3>
            </div>
            <div className="divide-y divide-zinc-800/60 text-xs">
              {accounts.length === 0 ? (
                <div className="py-8 text-center text-zinc-500">Chưa có tài khoản nào trong pool.</div>
              ) : (
                visibleAccounts.map((acc, idx) => {
                  const slotId = String(acc.slot_id ?? acc.id ?? idx + 1);
                  const shortSlot = slotId.length > 16
                    ? `${slotId.slice(0, 8)}…${slotId.slice(-4)}`
                    : slotId;
                  const email = acc.email || acc.username || 'Tài khoản không xác định';

                  return (
                    <div
                      key={slotId}
                      className="flex min-w-0 items-center justify-between gap-3 px-4 py-3 sm:px-5 hover:bg-zinc-800/30"
                    >
                      <div className="flex min-w-0 flex-1 items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 font-bold text-amber-500 ring-1 ring-amber-500/20">
                          {(accountsPage - 1) * ADMIN_PAGE_SIZE + idx + 1}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-bold text-white" title={email}>{email}</div>
                          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-zinc-400">
                            <span
                              className="max-w-full truncate rounded-md bg-zinc-950/70 px-2 py-0.5 font-mono"
                              title={`Slot: ${slotId}`}
                            >
                              Slot: {shortSlot}
                            </span>
                            <span className="inline-flex items-center gap-1 whitespace-nowrap text-emerald-500">
                              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                              Hoạt động
                            </span>
                          </div>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setDeleteAccountTarget(acc)}
                        className="rounded-lg p-2 text-zinc-400 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
                        title="Xóa tài khoản khỏi pool"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  );
                })
              )}
            </div>
            <AdminPagination
              page={accountsPage}
              pages={accountPages}
              total={accounts.length}
              itemLabel="tài khoản"
              onPageChange={setAccountsPage}
            />
          </div>
        </div>
      )}

      {/* SUBTAB 2: POPUP ANNOUNCEMENT NOTICE (FULL 12 FIELDS & LIVE PREVIEW) */}
      {activeSubtab === 'popup' && (
        <form onSubmit={handleSavePopup} className="space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 sm:p-6 shadow-lg backdrop-blur-md space-y-6">
            {/* Header with Title & Live Preview Button */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-800/80 pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Bell className="h-5 w-5 text-amber-500" />
                  <span>Quản Lý Popup Thông Báo Toàn Trang</span>
                </h3>
                <p className="text-xs text-zinc-400 mt-1">
                  Cấu hình đầy đủ 12 trường dữ liệu, lịch trình tự động và kiểm thử trực tiếp trên giao diện người dùng.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsPreviewOpen(true)}
                  className="flex items-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-xs font-bold text-amber-400 hover:bg-amber-500/20 transition-all shadow-sm"
                >
                  <Eye className="h-4 w-4" />
                  <span>Xem thử Popup</span>
                </button>
              </div>
            </div>

            {/* Field 1 & Field 2: Enabled & Version */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-xs font-bold text-white flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={popupForm.enabled}
                      onChange={(e) => setPopupForm({ ...popupForm, enabled: e.target.checked })}
                      className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-amber-500 focus:ring-amber-500"
                    />
                    <span>Kích hoạt hiển thị Popup</span>
                  </label>
                  <p className="text-[11px] text-zinc-400 mt-1">
                    Bật hoặc tắt hiển thị thông báo popup trên toàn hệ thống
                  </p>
                </div>
                <span
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                    popupForm.enabled ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-zinc-800 text-zinc-400'
                  }`}
                >
                  {popupForm.enabled ? 'Đang Bật' : 'Đang Tắt'}
                </span>
              </div>

              <div className="flex items-center justify-between gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-bold text-white mb-1">
                    Phiên bản (Version): {popupForm.version}
                  </label>
                  <p className="text-[11px] text-zinc-400">
                    Tăng version để hiển thị lại với khách đã từng bấm đóng ở bản cũ.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setPopupForm({ ...popupForm, version: popupForm.version + 1 })}
                  className="flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-700 transition"
                  title="Tăng version lên 1"
                >
                  <RotateCcw className="h-3 w-3 text-amber-400" />
                  <span>+1 Version</span>
                </button>
              </div>
            </div>

            {/* Field 3: Title */}
            <div>
              <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                Tiêu đề Popup <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={popupForm.title}
                onChange={(e) => setPopupForm({ ...popupForm, title: e.target.value })}
                placeholder="VD: Ưu Đãi Nâng Cấp Locket Gold Tháng Này!"
                required
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
              />
            </div>

            {/* Field 4: Message Content */}
            <div>
              <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                Nội dung thông báo (Hỗ trợ xuống dòng) <span className="text-rose-400">*</span>
              </label>
              <textarea
                value={popupForm.message}
                onChange={(e) => setPopupForm({ ...popupForm, message: e.target.value })}
                rows={4}
                placeholder="Nhập nội dung chi tiết thông báo cho người dùng..."
                required
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
              />
            </div>

            {/* Field 5: Icon Picker (12 options) */}
            <div>
              <label className="block text-xs font-bold text-zinc-300 mb-2">
                Biểu tượng Popup (Chọn 1 trong 12 biểu tượng)
              </label>
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                {AVAILABLE_ICONS.map((item) => {
                  const Icon = item.icon;
                  const isSelected = popupForm.icon === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setPopupForm({ ...popupForm, icon: item.id })}
                      className={`flex flex-col items-center gap-1.5 rounded-xl p-2.5 text-xs transition border ${
                        isSelected
                          ? 'border-amber-500 bg-amber-500/15 text-amber-300 ring-1 ring-amber-500'
                          : 'border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:bg-zinc-800/80 hover:text-white'
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                      <span className="text-[11px] font-medium">{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Field 6 & Field 7: Button Text & Button URL */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  Chữ trên nút hành động (Call To Action)
                </label>
                <input
                  type="text"
                  value={popupForm.button_text}
                  onChange={(e) => setPopupForm({ ...popupForm, button_text: e.target.value })}
                  placeholder="VD: Nâng Cấp Ngay (Để trống nếu không dùng nút)"
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  Đường dẫn nút bấm (Chỉ chấp nhận "/" hoặc "https://")
                </label>
                <input
                  type="text"
                  value={popupForm.button_url}
                  onChange={(e) => setPopupForm({ ...popupForm, button_url: e.target.value })}
                  placeholder="VD: /dashboard hoặc https://zalo.me/..."
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            {/* Field 8, 9, 10: Dismissible, Audience & Display Mode */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  Đối tượng xem (Audience)
                </label>
                <select
                  value={popupForm.audience}
                  onChange={(e) => setPopupForm({ ...popupForm, audience: e.target.value as PopupAudience })}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-100 focus:outline-none focus:border-amber-500"
                >
                  <option value="all">Tất cả mọi người (All)</option>
                  <option value="guests">Chỉ khách chưa đăng nhập (Guests)</option>
                  <option value="logged_in">Chỉ thành viên đã đăng nhập (Logged-in)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  Tần suất xuất hiện (Display Mode)
                </label>
                <select
                  value={popupForm.display_mode}
                  onChange={(e) => setPopupForm({ ...popupForm, display_mode: e.target.value as PopupDisplayMode })}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-100 focus:outline-none focus:border-amber-500"
                >
                  <option value="once_per_session">1 lần mỗi phiên duyệt (Khuyên dùng)</option>
                  <option value="once_per_version">1 lần duy nhất cho mỗi phiên bản</option>
                  <option value="every_visit">Xuất hiện mỗi khi vào trang</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  Cho phép đóng (Dismissible)
                </label>
                <div className="flex items-center h-[38px]">
                  <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-zinc-200">
                    <input
                      type="checkbox"
                      checked={popupForm.dismissible}
                      onChange={(e) => setPopupForm({ ...popupForm, dismissible: e.target.checked })}
                      className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500"
                    />
                    <span>Hiện nút đóng & phím ESC</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Field 11: Target Routes */}
            <div>
              <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                Các đường dẫn áp dụng (Phân cách bằng dấu phẩy)
              </label>
              <input
                type="text"
                value={popupForm.routes}
                onChange={(e) => setPopupForm({ ...popupForm, routes: e.target.value })}
                placeholder="* (Tất cả trang) hoặc: /, /dashboard, /track"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
              />
              <p className="text-[11px] text-zinc-400 mt-1">
                Điền <code className="text-amber-400">*</code> để áp dụng toàn website, hoặc chỉ định đường dẫn: <code className="text-amber-400">/, /dashboard, /track</code>
              </p>
            </div>

            {/* Field 12: Schedule Window (Start at / End at) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  Thời gian bắt đầu hiển thị (Tùy chọn)
                </label>
                <input
                  type="datetime-local"
                  value={popupForm.start_at}
                  onChange={(e) => setPopupForm({ ...popupForm, start_at: e.target.value })}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  Thời gian kết thúc hiển thị (Tùy chọn)
                </label>
                <input
                  type="datetime-local"
                  value={popupForm.end_at}
                  onChange={(e) => setPopupForm({ ...popupForm, end_at: e.target.value })}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            {/* Submit Bar */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setIsPreviewOpen(true)}
                className="flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-800 px-5 py-2.5 text-xs font-bold text-zinc-200 hover:bg-zinc-700 transition"
              >
                <Eye className="h-4 w-4" />
                <span>Xem Thử</span>
              </button>

              <button
                type="submit"
                disabled={isSavingPopup}
                className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-6 py-2.5 text-xs font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50 shadow-lg shadow-amber-500/15"
              >
                {isSavingPopup && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>Lưu Cấu Hình Popup</span>
              </button>
            </div>
          </div>
        </form>
      )}

      {/* SUBTAB 3: PROXIES */}
      {activeSubtab === 'proxies' && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Plus className="h-4 w-4 text-amber-500" />
              <span>Thêm Máy Chủ Proxy Mới</span>
            </h3>
            <form onSubmit={handleAddProxy} className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                value={newProxyUrl}
                onChange={(e) => setNewProxyUrl(e.target.value)}
                placeholder="http://username:password@ip:port hoặc socks5://..."
                required
                className="flex-1 rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-amber-500"
              />
              <button
                type="submit"
                disabled={isAddingProxy}
                className="flex items-center justify-center gap-1.5 rounded-xl bg-amber-500 px-5 py-2 text-xs font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50"
              >
                {isAddingProxy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>Thêm proxy</span>
              </button>
            </form>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 shadow-xl overflow-hidden">
            <div className="border-b border-zinc-800 px-5 py-3.5 bg-zinc-950/40">
              <h3 className="text-xs font-bold text-zinc-300">
                Danh sách proxy ({proxies.length})
              </h3>
            </div>
            <div className="divide-y divide-zinc-800/60 text-xs">
              {proxies.length === 0 ? (
                <div className="py-8 text-center text-zinc-500">Chưa có proxy nào được định cấu hình.</div>
              ) : (
                visibleProxies.map((p, idx) => (
                  <div key={(proxiesPage - 1) * ADMIN_PAGE_SIZE + idx} className="flex items-center justify-between px-5 py-3 hover:bg-zinc-800/30">
                    <span className="font-mono text-zinc-300">{p.url || p}</span>
                    <button
                      type="button"
                      onClick={() => setDeleteProxyTarget(p)}
                      className="rounded-lg p-2 text-zinc-400 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
                      title="Xóa proxy"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
            <AdminPagination page={proxiesPage} pages={proxyPages} total={proxies.length} itemLabel="proxy" onPageChange={setProxiesPage} />
          </div>
        </div>
      )}

      {/* SUBTAB 4: TOKENS */}
      {activeSubtab === 'tokens' && (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 shadow-xl overflow-hidden">
          <div className="border-b border-zinc-800 px-5 py-3.5 bg-zinc-950/40">
            <h3 className="text-xs font-bold text-zinc-300">
              Token Cache Hệ Thống ({tokens.length})
            </h3>
          </div>
          <div className="divide-y divide-zinc-800/60 text-xs">
            {tokens.length === 0 ? (
              <div className="py-8 text-center text-zinc-500">Không có token khả dụng trong bộ nhớ cache.</div>
            ) : (
              visibleTokens.map((t, idx) => (
                <div key={(tokensPage - 1) * ADMIN_PAGE_SIZE + idx} className="flex items-center justify-between px-5 py-3">
                  <span className="font-mono text-zinc-300">{t.key || t.token || `Token #${(tokensPage - 1) * ADMIN_PAGE_SIZE + idx + 1}`}</span>
                  <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-[10px] font-bold text-emerald-400 border border-emerald-500/20">
                    Hoạt động
                  </span>
                </div>
              ))
            )}
          </div>
          <AdminPagination page={tokensPage} pages={tokenPages} total={tokens.length} itemLabel="token" onPageChange={setTokensPage} />
        </div>
      )}

      {/* SUBTAB 5: MOBILECONFIG */}
      {activeSubtab === 'mobileconfig' && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md">
            <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
              <Upload className="h-4 w-4 text-amber-500" />
              <span>Tải Lên Tệp Cấu Hình Mobileconfig (.mobileconfig)</span>
            </h3>
            <p className="text-xs text-zinc-400 mb-4">
              Tệp cấu hình DNS này sẽ được người dùng iOS tải về khi thực hiện cài đặt theo hướng dẫn.
            </p>

            <form onSubmit={handleUploadMobileconfig} className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <input
                type="file"
                accept=".mobileconfig"
                onChange={(e) => setMcFile(e.target.files?.[0] || null)}
                className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 file:mr-3 file:rounded-lg file:border-0 file:bg-zinc-800 file:px-3 file:py-1 file:text-xs file:font-semibold file:text-zinc-200 hover:file:bg-zinc-700"
              />
              <button
                type="submit"
                disabled={!mcFile || isUploadingMc}
                className="flex items-center justify-center gap-1.5 rounded-xl bg-amber-500 px-5 py-2.5 text-xs font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50"
              >
                {isUploadingMc && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>Tải lên và kích hoạt</span>
              </button>
            </form>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 flex items-center justify-between">
            <div>
              <h4 className="text-xs font-bold text-white">Xóa tệp Mobileconfig hiện tại</h4>
              <p className="text-[11px] text-zinc-400">Khôi phục về trạng thái cấu hình DNS tự động.</p>
            </div>
            <button
              type="button"
              onClick={() => setIsConfirmingDeleteMc(true)}
              className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-xs font-bold text-rose-400 hover:bg-rose-500/20"
            >
              Xóa tệp
            </button>
          </div>
        </div>
      )}

      {/* SUBTAB 6: MAINTENANCE & SYSTEM SETTINGS */}
      {activeSubtab === 'settings' && (
        <form onSubmit={handleSaveSettings} className="space-y-6">
          {/* Maintenance Card */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-amber-500" />
              <span>Chế Độ Bảo Trì (Maintenance Mode)</span>
            </h3>

            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-zinc-200">
                <input
                  type="checkbox"
                  checked={Boolean(settings?.maintenance?.enabled)}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      maintenance: { ...settings?.maintenance, enabled: e.target.checked },
                    })
                  }
                  className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500"
                />
                <span className="font-bold">Bật chế độ bảo trì hệ thống</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-zinc-200">
                <input
                  type="checkbox"
                  checked={settings?.maintenance?.allow_admin !== false}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      maintenance: { ...settings?.maintenance, allow_admin: e.target.checked },
                    })
                  }
                  className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500"
                />
                <span>Cho phép Admin truy cập khi bảo trì</span>
              </label>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-400 mb-1">
                Thông báo bảo trì hiển thị cho người dùng:
              </label>
              <textarea
                value={settings?.maintenance?.message || ''}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    maintenance: { ...settings?.maintenance, message: e.target.value },
                  })
                }
                rows={3}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>
          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={isSavingSettings}
              className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-6 py-2.5 text-xs font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50 shadow-lg shadow-amber-500/10"
            >
              {isSavingSettings && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              <span>Lưu Cấu Hình Bảo Trì</span>
            </button>
          </div>
        </form>
      )}

      {/* Confirm Delete Mobileconfig Dialog */}
      {isConfirmingDeleteMc && (
        <ConfirmDialog
          isOpen={isConfirmingDeleteMc}
          onClose={() => setIsConfirmingDeleteMc(false)}
          onConfirm={handleConfirmDeleteMobileconfig}
          title="Xóa Cấu Hình Mobileconfig"
          message="Bạn có chắc chắn muốn xóa tệp mobileconfig hiện tại? Hệ thống sẽ khôi phục cấu hình DNS mặc định."
          confirmText="Xác nhận xóa"
          isDanger={true}
          isLoading={isDeletingMc}
        />
      )}

      {/* Confirm Delete Account Dialog */}
      {deleteAccountTarget && (
        <ConfirmDialog
          isOpen={Boolean(deleteAccountTarget)}
          onClose={() => setDeleteAccountTarget(null)}
          onConfirm={handleConfirmDeleteAccount}
          title="Xóa Tài Khoản Khỏi Pool"
          message={`Bạn có chắc chắn muốn xóa tài khoản "${deleteAccountTarget.email || deleteAccountTarget.username}" khỏi pool xoay vòng?`}
          confirmText="Xóa tài khoản"
          isDanger={true}
          isLoading={isDeletingAccount}
        />
      )}

      {/* Confirm Delete Proxy Dialog */}
      {deleteProxyTarget && (
        <ConfirmDialog
          isOpen={Boolean(deleteProxyTarget)}
          onClose={() => setDeleteProxyTarget(null)}
          onConfirm={handleConfirmDeleteProxy}
          title="Xóa Máy Chủ Proxy"
          message={`Bạn có chắc chắn muốn xóa proxy "${deleteProxyTarget.url || deleteProxyTarget}"?`}
          confirmText="Xóa proxy"
          isDanger={true}
          isLoading={isDeletingProxy}
        />
      )}
      
      {/* LIVE PREVIEW MODAL */}
      <AnnouncementDialog
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        title={popupForm.title || 'Tiêu đề Popup'}
        message={popupForm.message || 'Nội dung thông báo chi tiết của popup sẽ xuất hiện tại đây...'}
        icon={popupForm.icon}
        buttonText={popupForm.button_text}
        buttonUrl={popupForm.button_url}
        dismissible={popupForm.dismissible}
        layerKind="dialog"
        actionEnabled={false}
        onSnooze={() => setIsPreviewOpen(false)}
      />
    </div>
  );
};
