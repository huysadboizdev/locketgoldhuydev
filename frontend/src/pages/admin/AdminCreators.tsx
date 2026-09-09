import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Edit3,
  ExternalLink,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Star,
  Trash2,
  UsersRound,
} from 'lucide-react';
import { Modal } from '../../components/admin/Modal';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { AuthenticatedReviewImage } from '../../components/reviews/AuthenticatedReviewImage';
import {
  createAdminCreator,
  deleteAdminCreator,
  fetchAdminCreators,
  updateAdminCreator,
} from '../../api/adminEndpoints';
import type { AdminCreator } from '../../types/admin';

const formatFollowers = (value?: number | null) => {
  if (value == null) return 'Chưa nhập';
  return new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
};

const fieldClass = 'min-h-11 w-full rounded-xl border border-zinc-300 bg-white px-3.5 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 disabled:bg-zinc-100 disabled:text-zinc-500 disabled:opacity-70 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:disabled:bg-zinc-900';
const labelClass = 'mb-1.5 block text-xs font-semibold text-zinc-700 dark:text-zinc-300';
const MAX_CREATOR_IMAGE_BYTES = 5 * 1024 * 1024;
const CREATOR_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);

export const AdminCreators: React.FC = () => {
  const [items, setItems] = useState<AdminCreator[]>([]);
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<AdminCreator | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AdminCreator | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [handle, setHandle] = useState('');
  const [tiktokUrl, setTiktokUrl] = useState('');
  const [followers, setFollowers] = useState('');
  const [sortOrder, setSortOrder] = useState('0');
  const [cropPercent, setCropPercent] = useState(24);
  const [featured, setFeatured] = useState(false);
  const [active, setActive] = useState(true);
  const [requireReview, setRequireReview] = useState(false);
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchAdminCreators({ q: appliedQuery || undefined, page, limit: 10 });
      setItems(response.items || response.creators || []);
      const nextPages = Math.max(1, response.pagination?.pages || response.pages || 1);
      setPages(nextPages);
      if (page > nextPages) setPage(nextPages);
      setTotal(response.pagination?.total ?? response.total ?? 0);
    } catch (err: any) {
      setError(err.message || 'Không thể tải danh sách TikTok KOL.');
    } finally {
      setLoading(false);
    }
  }, [appliedQuery, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const refresh = () => load();
    window.addEventListener('admin-refresh', refresh);
    return () => window.removeEventListener('admin-refresh', refresh);
  }, [load]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  const resetForm = (creator?: AdminCreator) => {
    setEditing(creator || null);
    setEmail(creator?.email || '');
    setDisplayName(creator?.display_name || '');
    setHandle(creator?.tiktok_handle || '');
    setTiktokUrl(creator?.tiktok_url || '');
    setFollowers(creator?.follower_count == null ? '' : String(creator.follower_count));
    setSortOrder(String(creator?.sort_order || 0));
    setCropPercent(24);
    setFeatured(Boolean(creator?.is_featured));
    setActive(creator ? Boolean(creator.is_active) : true);
    setRequireReview(Boolean(creator?.require_review));
    setScreenshot(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setFormError(null);
    setModalOpen(true);
  };

  const onHandleChange = (value: string) => {
    const clean = value.replace(/^@/, '').toLowerCase();
    setHandle(clean);
    if (!editing || !tiktokUrl || tiktokUrl.includes(editing.tiktok_handle)) {
      setTiktokUrl(clean ? `https://www.tiktok.com/@${clean}` : '');
    }
  };

  const onFileChange = (file: File | null) => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (file) {
      const extensionAllowed = /\.(?:jpe?g|png|webp)$/i.test(file.name);
      if ((!CREATOR_IMAGE_TYPES.has(file.type) && !extensionAllowed) || file.size <= 0) {
        setScreenshot(null);
        setPreviewUrl(null);
        setFormError('Ảnh TikTok phải là tệp JPG, PNG hoặc WebP hợp lệ.');
        return;
      }
      if (file.size > MAX_CREATOR_IMAGE_BYTES) {
        setScreenshot(null);
        setPreviewUrl(null);
        setFormError('Ảnh TikTok không được vượt quá 5 MB.');
        return;
      }
    }
    setScreenshot(file);
    setPreviewUrl(file ? URL.createObjectURL(file) : null);
    setFormError(null);
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (!editing && !email.trim()) return setFormError('Vui lòng nhập email tài khoản đã đăng ký.');
    if (!displayName.trim()) return setFormError('Vui lòng nhập tên hiển thị KOL.');
    if (!handle.trim() || !tiktokUrl.trim()) return setFormError('Vui lòng nhập TikTok handle và URL chính thức.');
    if (!editing && !screenshot) return setFormError('Vui lòng chọn screenshot trang TikTok.');

    const data = new FormData();
    if (!editing) data.append('email', email.trim());
    data.append('tiktok_handle', handle.trim());
    data.append('display_name', displayName.trim());
    data.append('tiktok_url', tiktokUrl.trim());
    data.append('follower_count', followers.trim());
    data.append('sort_order', sortOrder || '0');
    data.append('crop_percent', String(cropPercent));
    data.append('is_featured', String(featured));
    data.append('is_active', String(active));
    data.append('require_review', String(requireReview));
    if (screenshot) data.append('screenshot', screenshot);

    try {
      setSaving(true);
      const response = editing
        ? await updateAdminCreator(editing.id, data)
        : await createAdminCreator(data);
      setNotice(response.msg);
      setModalOpen(false);
      setPage(1);
      await load();
    } catch (err: any) {
      setFormError(err.message || 'Không thể lưu hồ sơ KOL.');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      setDeleting(true);
      const response = await deleteAdminCreator(deleteTarget.id);
      setNotice(response.msg);
      setDeleteTarget(null);
      await load();
    } catch (err: any) {
      setError(err.message || 'Không thể xóa hồ sơ KOL.');
    } finally {
      setDeleting(false);
    }
  };

  const cardGridClass = items.length === 1
    ? 'mx-auto max-w-2xl grid-cols-1'
    : items.length === 2
      ? 'mx-auto max-w-5xl md:grid-cols-2'
      : 'md:grid-cols-2 2xl:grid-cols-3';

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/80">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-base font-bold text-zinc-950 dark:text-white">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400"><UsersRound className="h-4.5 w-4.5" /></span> TikToker / KOL đã xác thực
            </h2>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Nâng tài khoản đã đăng ký thành KOL; không bắt buộc mua gói và chỉ Admin được cấp quyền.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <form className="flex min-w-0" onSubmit={(e) => { e.preventDefault(); setPage(1); setAppliedQuery(query.trim()); }}>
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Email, tên hoặc @TikTok..." className="min-h-11 min-w-0 flex-1 rounded-l-xl border border-zinc-300 bg-zinc-50 px-3 text-xs text-zinc-900 outline-none placeholder:text-zinc-400 focus:border-amber-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white sm:w-64" />
              <button className="min-h-11 rounded-r-xl border border-l-0 border-zinc-300 bg-zinc-100 px-3 text-zinc-600 transition hover:bg-zinc-200 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700" aria-label="Tìm kiếm"><Search className="h-4 w-4" /></button>
            </form>
            <button onClick={load} disabled={loading} className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-zinc-300 bg-white px-4 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300 dark:hover:bg-zinc-900"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Làm mới</button>
            <button onClick={() => resetForm()} className="flex min-h-11 items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 text-xs font-bold text-zinc-950 hover:bg-amber-400"><Plus className="h-4 w-4" /> Nâng KOL</button>
          </div>
        </div>
      </div>

      {(error || notice) && <div className={`flex items-center gap-2 rounded-xl border p-3 text-xs ${error ? 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300' : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300'}`}>{error ? <AlertCircle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />} {error || notice}</div>}

      {loading ? <div className="py-16 text-center text-zinc-400"><Loader2 className="mx-auto mb-2 h-7 w-7 animate-spin text-amber-400" />Đang tải KOL...</div> : items.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-zinc-300 bg-white py-16 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900/40 dark:text-zinc-400">Chưa có TikToker/KOL nào. Hãy nâng tài khoản bằng email.</div>
      ) : (
        <div className={`grid gap-5 ${cardGridClass}`}>
          {items.map((creator) => (
            <article key={creator.id} className="overflow-hidden rounded-3xl border border-zinc-200 bg-white shadow-[0_12px_35px_rgba(24,24,27,0.08)] transition-shadow hover:shadow-[0_18px_45px_rgba(24,24,27,0.12)] dark:border-zinc-800 dark:bg-zinc-900/85 dark:shadow-xl">
              <div className="bg-zinc-950 p-2.5">
                <div className="relative aspect-[1.9/1] overflow-hidden rounded-2xl bg-white">
                <AuthenticatedReviewImage src={creator.screenshot_url} alt={`TikTok @${creator.tiktok_handle}`} className="h-full w-full object-contain object-top" />
                <div className="absolute inset-x-0 top-0 flex justify-between p-3">
                  <span className="rounded-full border border-cyan-400/40 bg-zinc-950/85 px-2.5 py-1 text-[10px] font-bold text-cyan-300 shadow backdrop-blur">TikTok KOL</span>
                  {creator.is_featured && <span className="flex items-center gap-1 rounded-full bg-amber-400 px-2.5 py-1 text-[10px] font-black text-zinc-950"><Sparkles className="h-3 w-3" /> NỔI BẬT</span>}
                </div>
                </div>
              </div>
              <div className="space-y-4 p-5">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0"><h3 className="truncate font-bold text-zinc-950 dark:text-white">{creator.display_name}</h3><p className="mt-0.5 truncate text-xs font-semibold text-cyan-700 dark:text-cyan-300">@{creator.tiktok_handle} · {formatFollowers(creator.follower_count)} follower</p></div>
                  <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${creator.is_active ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300' : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400'}`}>{creator.is_active ? 'Đang hiện' : 'Đang ẩn'}</span>
                </div>
                <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-3.5 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950/60 dark:text-zinc-400">
                  <p className="truncate font-medium text-zinc-700 dark:text-zinc-300">{creator.email}</p><p className="mt-1.5">{creator.plan_name || 'KOL được Admin xác thực'}</p>
                  {creator.review_id ? <p className="mt-2.5 flex items-center gap-1 font-semibold text-amber-700 dark:text-amber-300"><Star className="h-3.5 w-3.5 fill-current" /> {creator.rating}/5 · Đã có feedback</p> : <p className="mt-2.5 text-zinc-500">Chưa gửi feedback</p>}
                </div>
                <div className="flex items-center gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-800">
                  <a href={creator.tiktok_url} target="_blank" rel="noopener noreferrer" className="flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-xl bg-zinc-950 text-xs font-bold text-white transition hover:bg-zinc-800 dark:bg-white dark:text-zinc-950 dark:hover:bg-zinc-200"><ExternalLink className="h-3.5 w-3.5" /> TikTok</a>
                  <button onClick={() => resetForm(creator)} className="flex h-11 w-11 items-center justify-center rounded-xl border border-amber-200 bg-amber-50 text-amber-700 transition hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300" aria-label="Sửa"><Edit3 className="h-4 w-4" /></button>
                  <button onClick={() => setDeleteTarget(creator)} className="flex h-11 w-11 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-rose-600 transition hover:bg-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-500 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-400" aria-label="Xóa"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-4 py-3 text-xs text-zinc-500 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400"><span>{total} KOL · Trang {page}/{pages}</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="min-h-11 rounded-lg border border-zinc-300 bg-white px-3 font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300">Trước</button><button disabled={page >= pages} onClick={() => setPage((p) => p + 1)} className="min-h-11 rounded-lg border border-zinc-300 bg-white px-3 font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300">Sau</button></div></div>

      <Modal isOpen={modalOpen} onClose={() => !saving && setModalOpen(false)} title={editing ? 'Cập nhật TikTok KOL' : 'Nâng tài khoản thành TikTok KOL'} maxWidth="2xl">
        <form onSubmit={save} className="space-y-4">
          {formError && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">{formError}</div>}
          <div><label className={labelClass}>Email tài khoản *</label><input type="email" value={email} disabled={Boolean(editing)} onChange={(e) => setEmail(e.target.value)} className={fieldClass} placeholder="kol@example.com" /><p className="mt-1 text-[11px] text-zinc-500">Email chỉ cần là tài khoản đã đăng ký. Sau khi nâng KOL, tài khoản được mở quyền feedback ngay.</p></div>
          <div className="grid gap-4 sm:grid-cols-2"><div><label className={labelClass}>Tên hiển thị KOL *</label><input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className={fieldClass} placeholder="Bé Dứa" maxLength={50} /></div><div><label className={labelClass}>Follower</label><input type="number" min="0" step="1" value={followers} onChange={(e) => setFollowers(e.target.value)} className={fieldClass} placeholder="65700" /></div></div>
          <div><label className={labelClass}>TikTok handle *</label><input value={handle} onChange={(e) => onHandleChange(e.target.value)} className={fieldClass} placeholder="username" /></div>
          <div><label className={labelClass}>URL TikTok chính thức *</label><input type="url" value={tiktokUrl} onChange={(e) => setTiktokUrl(e.target.value)} className={fieldClass} placeholder="https://www.tiktok.com/@username" /></div>
          <div className="grid gap-4 sm:grid-cols-2"><div><label className={labelClass}>Thứ tự hiển thị</label><input type="number" step="1" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} className={fieldClass} /></div><div><label className={labelClass}>Giữ phần trên ảnh: {cropPercent}%</label><input type="range" min="12" max="45" value={cropPercent} onChange={(e) => setCropPercent(Number(e.target.value))} className="mt-3 w-full accent-amber-500" /><p className="mt-1 text-[11px] leading-4 text-amber-700 dark:text-amber-300/80">Chỉ giữ tên, @TikTok, avatar và follower; loại bỏ bio có số điện thoại/liên hệ.</p></div></div>
          <div><label className={labelClass}>Screenshot trang TikTok {editing ? '(để trống nếu giữ ảnh cũ)' : '*'}</label><input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" onChange={(e) => onFileChange(e.target.files?.[0] || null)} className="block w-full rounded-xl border border-zinc-300 bg-white p-2.5 text-xs text-zinc-600 file:mr-3 file:rounded-lg file:border-0 file:bg-amber-500 file:px-3 file:py-2 file:font-bold file:text-zinc-950 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300" /><p className="mt-1.5 text-[11px] text-zinc-500">Hỗ trợ JPG, PNG, WebP · tối đa 5 MB. Ảnh gốc không được lưu; hệ thống chỉ giữ phần đã cắt an toàn.</p>
            {(previewUrl || editing) && <div className="mt-3 flex justify-center overflow-hidden rounded-2xl border border-zinc-700 bg-black p-2"><div className="relative inline-block overflow-hidden"><AuthenticatedReviewImage src={previewUrl || editing!.screenshot_url} alt="Xem trước screenshot" className="block max-h-80 max-w-full object-contain object-top" />{previewUrl && <><div className="pointer-events-none absolute inset-x-0 top-0 border-b-2 border-emerald-400" style={{ height: `${cropPercent}%` }}><span className="absolute left-2 top-2 rounded-full bg-emerald-500 px-2 py-1 text-[10px] font-bold text-white">Phần công khai</span></div><div className="pointer-events-none absolute left-0 bg-zinc-950/85" style={{ top: `${cropPercent * 0.74}%`, width: '72%', height: `${cropPercent * 0.26}%` }}><span className="absolute bottom-1 left-2 rounded bg-zinc-800 px-1.5 py-0.5 text-[9px] font-bold text-zinc-200">Bio/liên hệ tự che</span></div><div className="pointer-events-none absolute inset-x-0 bottom-0 bg-black/80" style={{ height: `${100 - cropPercent}%` }}><span className="absolute left-1/2 top-2 -translate-x-1/2 whitespace-nowrap rounded-full bg-rose-500 px-2 py-1 text-[10px] font-bold text-white">Phần bị xóa vĩnh viễn</span></div></>}</div></div>}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">{[
            ['Nổi bật trên landing', featured, setFeatured],
            ['Đang hiển thị', active, setActive],
            ['Chỉ hiện khi có feedback', requireReview, setRequireReview],
          ].map(([label, checked, setter]) => <label key={String(label)} className="flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-zinc-300 bg-zinc-50 px-3 text-xs text-zinc-700 transition hover:border-amber-300 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300"><input type="checkbox" checked={Boolean(checked)} onChange={(e) => (setter as React.Dispatch<React.SetStateAction<boolean>>)(e.target.checked)} className="h-4 w-4 accent-amber-500" />{String(label)}</label>)}</div>
          <div className="flex justify-end gap-3 border-t border-zinc-200 pt-4 dark:border-zinc-800"><button type="button" disabled={saving} onClick={() => setModalOpen(false)} className="min-h-11 rounded-xl border border-zinc-300 bg-white px-4 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">Hủy</button><button disabled={saving} className="flex min-h-11 items-center gap-2 rounded-xl bg-amber-500 px-5 text-xs font-bold text-zinc-950 transition hover:bg-amber-400 disabled:opacity-50">{saving && <Loader2 className="h-4 w-4 animate-spin" />}{editing ? 'Lưu thay đổi' : 'Nâng thành KOL'}</button></div>
        </form>
      </Modal>

      {deleteTarget && <ConfirmDialog isOpen={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} onConfirm={confirmDelete} title="Xóa hồ sơ TikTok KOL" message={`Xóa @${deleteTarget.tiktok_handle} khỏi khu vực KOL? Tài khoản và feedback vẫn được giữ nguyên.`} confirmText="Xóa hồ sơ KOL" isLoading={deleting} />}
    </div>
  );
};
