import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  Eye,
  Coins,
  UserCheck,
  UserX,
  RefreshCw,
  AlertCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  PackageCheck,
} from 'lucide-react';
import { Modal } from '../../components/admin/Modal';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import {
  fetchAdminUsers,
  fetchAdminUserDetail,
  updateAdminUserStatus,
  updateAdminUserRole,
  adjustAdminUserWallet,
} from '../../api/adminEndpoints';
import type { AdminUser, AdminUserDetailResponse } from '../../types/admin';

export const AdminUsers: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [limit] = useState(10);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Detail Modal
  const [selectedUserDetail, setSelectedUserDetail] = useState<AdminUserDetailResponse | null>(null);

  // Status Toggle Modal
  const [statusModalUser, setStatusModalUser] = useState<AdminUser | null>(null);
  const [statusReason, setStatusReason] = useState('');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  // Wallet Adjust Modal
  const [walletModalUser, setWalletModalUser] = useState<AdminUser | null>(null);
  const [walletDelta, setWalletDelta] = useState<number>(0);
  const [walletReason, setWalletReason] = useState('');
  const [isAdjustingWallet, setIsAdjustingWallet] = useState(false);
  const [walletError, setWalletError] = useState<string | null>(null);

  // Role Change Modal
  const [roleModalUser, setRoleModalUser] = useState<AdminUser | null>(null);
  const [targetRole, setTargetRole] = useState<'user' | 'admin'>('user');
  const [isUpdatingRole, setIsUpdatingRole] = useState(false);

  const loadUsers = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await fetchAdminUsers({
        q: searchQuery,
        role: roleFilter,
        status: statusFilter,
        page,
        limit,
      });
      if (res.success) {
        setUsers(res.items);
        setTotal(res.pagination.total);
        const nextPages = Math.max(1, res.pagination.pages);
        setPages(nextPages);
        if (page > nextPages) setPage(nextPages);
      }
    } catch (err: any) {
      setError(err.message || 'Không thể tải danh sách người dùng.');
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, roleFilter, statusFilter, page, limit]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadUsers();
  };

  const handleOpenDetail = async (userId: number) => {
    try {
      const res = await fetchAdminUserDetail(userId);
      if (res.success) {
        setSelectedUserDetail(res);
      }
    } catch (err: any) {
      setError(err.message || 'Lỗi khi tải chi tiết người dùng.');
    }
  };

  const handleConfirmStatusChange = async () => {
    if (!statusModalUser) return;
    try {
      setIsUpdatingStatus(true);
      const newStatus = !statusModalUser.is_active;
      await updateAdminUserStatus(statusModalUser.id, newStatus, statusReason);
      setStatusModalUser(null);
      setStatusReason('');
      loadUsers();
    } catch (err: any) {
      setError(err.message || 'Không thể cập nhật trạng thái người dùng.');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleConfirmWalletAdjust = async () => {
    if (!walletModalUser) return;
    if (walletDelta === 0) {
      setWalletError('Vui lòng nhập số Coin thay đổi khác 0.');
      return;
    }
    if (!walletReason.trim()) {
      setWalletError('Vui lòng nhập lý do điều chỉnh.');
      return;
    }

    try {
      setIsAdjustingWallet(true);
      setWalletError(null);
      const idempotencyKey = `adj_${walletModalUser.id}_${Date.now()}`;
      await adjustAdminUserWallet(walletModalUser.id, walletDelta, walletReason, idempotencyKey);
      setWalletModalUser(null);
      setWalletDelta(0);
      setWalletReason('');
      loadUsers();
    } catch (err: any) {
      setWalletError(err.message || 'Lỗi khi điều chỉnh số dư.');
    } finally {
      setIsAdjustingWallet(false);
    }
  };

  const handleConfirmRoleChange = async () => {
    if (!roleModalUser) return;
    try {
      setIsUpdatingRole(true);
      await updateAdminUserRole(roleModalUser.id, targetRole, 'Admin UI update');
      setRoleModalUser(null);
      loadUsers();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi cập nhật quyền.');
    } finally {
      setIsUpdatingRole(false);
    }
  };

  const formatDate = (timestamp: number) => {
    if (!timestamp) return '---';
    return new Date(timestamp * 1000).toLocaleString('vi-VN');
  };

  return (
    <div className="space-y-6">
      {/* Search & Filter Header */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 backdrop-blur-md">
        <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm theo username, email hoặc tên..."
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 pl-10 pr-4 py-2.5 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
            />
          </div>
          <button
            type="submit"
            className="rounded-xl bg-amber-500 px-4 py-2.5 text-xs font-bold text-zinc-950 hover:bg-amber-400 transition-colors shrink-0"
          >
            Tìm kiếm
          </button>
        </form>

        <div className="flex items-center gap-2.5 shrink-0 overflow-x-auto">
          {/* Role Filter */}
          <select
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-300 focus:outline-none focus:border-amber-500"
          >
            <option value="">Tất cả quyền</option>
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-300 focus:outline-none focus:border-amber-500"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="active">Đang hoạt động</option>
            <option value="inactive">Đã khóa</option>
          </select>

          <button
            type="button"
            onClick={loadUsers}
            disabled={isLoading}
            className="rounded-xl border border-zinc-800 bg-zinc-950 p-2.5 text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors"
            title="Tải lại"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Users Table */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 shadow-xl backdrop-blur-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/60 text-zinc-400">
                <th className="py-3.5 px-4 font-semibold">ID</th>
                <th className="py-3.5 px-4 font-semibold">Người dùng</th>
                <th className="py-3.5 px-4 font-semibold">Vai trò</th>
                <th className="py-3.5 px-4 font-semibold">Trạng thái</th>
                <th className="py-3.5 px-4 font-semibold">Số dư ví</th>
                <th className="py-3.5 px-4 font-semibold">Đơn / GD</th>
                <th className="py-3.5 px-4 font-semibold">Ngày tạo</th>
                <th className="py-3.5 px-4 font-semibold text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-zinc-500">
                    <Loader2 className="h-6 w-6 animate-spin text-amber-500 mx-auto mb-2" />
                    <span>Đang tải danh sách người dùng...</span>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-zinc-500">
                    Không tìm thấy người dùng nào phù hợp.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-zinc-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-mono text-zinc-400">#{u.id}</td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-zinc-800 text-zinc-300 font-bold text-xs uppercase">
                          {u.username.charAt(0)}
                        </div>
                        <div>
                          <div className="font-bold text-white">{u.display_name}</div>
                          <div className="text-[11px] text-zinc-400">@{u.username} • {u.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        type="button"
                        onClick={() => {
                          setRoleModalUser(u);
                          setTargetRole(u.role === 'admin' ? 'user' : 'admin');
                        }}
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border transition-colors ${
                          u.role === 'admin'
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20'
                            : 'bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700'
                        }`}
                        title="Bấm để đổi quyền"
                      >
                        {u.role.toUpperCase()}
                      </button>
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        type="button"
                        onClick={() => {
                          setStatusModalUser(u);
                          setStatusReason('');
                        }}
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold border transition-colors ${
                          u.is_active
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                            : 'bg-rose-500/10 border-rose-500/30 text-rose-400 hover:bg-rose-500/20'
                        }`}
                      >
                        {u.is_active ? (
                          <>
                            <UserCheck className="h-3 w-3" />
                            <span>Hoạt động</span>
                          </>
                        ) : (
                          <>
                            <UserX className="h-3 w-3" />
                            <span>Đã khóa</span>
                          </>
                        )}
                      </button>
                    </td>
                    <td className="py-3.5 px-4 font-bold text-amber-400">
                      <div className="flex items-center gap-1">
                        <span>{new Intl.NumberFormat('vi-VN').format(u.balance_coin ?? u.coin_balance ?? 0)} Coin</span>
                        <button
                          type="button"
                          onClick={() => {
                            setWalletModalUser(u);
                            setWalletDelta(0);
                            setWalletReason('');
                            setWalletError(null);
                          }}
                          className="rounded-md bg-amber-500/10 p-1 text-amber-400 hover:bg-amber-500/20"
                          title="Điều chỉnh số dư ví"
                        >
                          <Coins className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-zinc-400">
                      <span className="font-semibold text-zinc-200">{u.order_count}</span> đơn /{' '}
                      <span className="font-semibold text-zinc-200">{u.payment_count}</span> GD
                    </td>
                    <td className="py-3.5 px-4 text-zinc-400 whitespace-nowrap">
                      {formatDate(u.created_at)}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleOpenDetail(u.id)}
                        className="rounded-xl border border-zinc-700 bg-zinc-800 p-1.5 text-zinc-300 hover:border-amber-500 hover:text-amber-400 transition-colors"
                        title="Xem chi tiết & lịch sử"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex items-center justify-between border-t border-zinc-800 px-4 py-3 bg-zinc-950/40 text-xs text-zinc-400">
          <div>
            Tổng cộng: <span className="font-bold text-zinc-200">{total}</span> người dùng (Trang {page}/{pages || 1})
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-2 font-bold text-zinc-200">{page}</span>
            <button
              type="button"
              disabled={page >= pages || isLoading}
              onClick={() => setPage((p) => Math.min(p + 1, pages))}
              className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* User Detail Modal */}
      {selectedUserDetail && (
        <Modal
          isOpen={Boolean(selectedUserDetail)}
          onClose={() => setSelectedUserDetail(null)}
          title={`Chi Tiết Người Dùng: ${selectedUserDetail.user.display_name} (@${selectedUserDetail.user.username})`}
          maxWidth="2xl"
        >
          <div className="space-y-6 text-xs">
            {/* User Meta Card */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-2xl bg-zinc-950 border border-zinc-800 p-4">
              <div>
                <span className="text-zinc-500 block">Email:</span>
                <span className="font-semibold text-zinc-200">{selectedUserDetail.user.email}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Số dư ví:</span>
                <span className="font-bold text-amber-400">
                  {selectedUserDetail.user.balance_coin ?? selectedUserDetail.user.coin_balance ?? 0} Coin
                </span>
              </div>
              <div>
                <span className="text-zinc-500 block">Vai trò:</span>
                <span className="font-semibold uppercase text-zinc-200">{selectedUserDetail.user.role}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Trạng thái:</span>
                <span className={selectedUserDetail.user.is_active ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                  {selectedUserDetail.user.is_active ? 'Đang hoạt động' : 'Đã khóa'}
                </span>
              </div>
            </div>

            {/* Wallet History */}
            <div>
              <h4 className="font-bold text-sm text-white mb-2 flex items-center gap-1.5">
                <Coins className="h-4 w-4 text-amber-400" />
                <span>Lịch Sử Giao Dịch Ví ({selectedUserDetail.wallet_transactions.length})</span>
              </h4>
              <div className="max-h-40 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950/60 p-2">
                {selectedUserDetail.wallet_transactions.length > 0 ? (
                  <table className="w-full text-left text-[11px]">
                    <thead className="text-zinc-500 border-b border-zinc-800">
                      <tr>
                        <th className="pb-1.5">Loại</th>
                        <th className="pb-1.5">Số lượng</th>
                        <th className="pb-1.5">Số dư sau</th>
                        <th className="pb-1.5">Lý do / Ref</th>
                        <th className="pb-1.5">Thời gian</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-900">
                      {selectedUserDetail.wallet_transactions.map((tx) => (
                        <tr key={tx.id}>
                          <td className="py-1 font-semibold uppercase">{tx.type}</td>
                          <td className={`py-1 font-bold ${tx.amount_coin > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {tx.amount_coin > 0 ? `+${tx.amount_coin}` : tx.amount_coin}
                          </td>
                          <td className="py-1 text-zinc-400">{tx.balance_after} Coin</td>
                          <td className="py-1 text-zinc-400 truncate max-w-[150px]">{tx.description || tx.reference_id || '---'}</td>
                          <td className="py-1 text-zinc-500">{formatDate(tx.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="py-4 text-center text-zinc-500">Chưa có lịch sử ví.</div>
                )}
              </div>
            </div>

            {/* Orders History */}
            <div>
              <h4 className="font-bold text-sm text-white mb-2 flex items-center gap-1.5">
                <PackageCheck className="h-4 w-4 text-emerald-400" />
                <span>Đơn Kích Hoạt ({selectedUserDetail.activation_orders.length})</span>
              </h4>
              <div className="max-h-40 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950/60 p-2">
                {selectedUserDetail.activation_orders.length > 0 ? (
                  <table className="w-full text-left text-[11px]">
                    <thead className="text-zinc-500 border-b border-zinc-800">
                      <tr>
                        <th className="pb-1.5">ID</th>
                        <th className="pb-1.5">Gói</th>
                        <th className="pb-1.5">Locket User</th>
                        <th className="pb-1.5">Platform</th>
                        <th className="pb-1.5">Trạng thái</th>
                        <th className="pb-1.5">Thời gian</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-900">
                      {selectedUserDetail.activation_orders.map((ord) => (
                        <tr key={ord.id}>
                          <td className="py-1 font-mono text-zinc-500">#{ord.id}</td>
                          <td className="py-1 font-semibold text-zinc-200">{ord.plan_name_snapshot}</td>
                          <td className="py-1 font-mono text-amber-300">{ord.locket_username}</td>
                          <td className="py-1 uppercase text-zinc-400">{ord.platform}</td>
                          <td className="py-1 font-bold text-emerald-400">{ord.status}</td>
                          <td className="py-1 text-zinc-500">{formatDate(ord.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="py-4 text-center text-zinc-500">Chưa có đơn hàng nào.</div>
                )}
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Adjust Wallet Modal */}
      {walletModalUser && (
        <Modal
          isOpen={Boolean(walletModalUser)}
          onClose={() => setWalletModalUser(null)}
          title={`Điều Chỉnh Ví: ${walletModalUser.username}`}
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="rounded-xl bg-zinc-950 border border-zinc-800 p-3">
              <span className="text-zinc-400 block">Số dư hiện tại:</span>
              <span className="text-lg font-bold text-amber-400">
                {new Intl.NumberFormat('vi-VN').format(walletModalUser.balance_coin ?? walletModalUser.coin_balance ?? 0)} Coin
              </span>
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1">
                Số lượng Coin thay đổi (+ cộng thêm, - trừ đi):
              </label>
              <input
                type="number"
                value={walletDelta}
                onChange={(e) => setWalletDelta(parseInt(e.target.value, 10) || 0)}
                placeholder="Ví dụ: 50 hoặc -20"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2.5 text-zinc-100 focus:outline-none focus:border-amber-500"
              />
              <span className="text-[11px] text-zinc-500 mt-1 block">
                Số dư sau thay đổi: <strong className="text-zinc-200">{(walletModalUser.balance_coin ?? walletModalUser.coin_balance ?? 0) + walletDelta} Coin</strong>
              </span>
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1">
                Lý do điều chỉnh (bắt buộc):
              </label>
              <textarea
                value={walletReason}
                onChange={(e) => setWalletReason(e.target.value)}
                placeholder="Nhập lý do điều chỉnh để lưu audit log..."
                rows={2}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-zinc-100 focus:outline-none focus:border-amber-500"
              />
            </div>

            {walletError && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300">
                {walletError}
              </div>
            )}

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setWalletModalUser(null)}
                className="rounded-xl border border-zinc-700 bg-zinc-800 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-700"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                onClick={handleConfirmWalletAdjust}
                disabled={isAdjustingWallet}
                className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 hover:bg-amber-400 disabled:opacity-50"
              >
                {isAdjustingWallet && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>Cập nhật số dư</span>
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Toggle Status Dialog */}
      {statusModalUser && (
        <ConfirmDialog
          isOpen={Boolean(statusModalUser)}
          onClose={() => setStatusModalUser(null)}
          onConfirm={handleConfirmStatusChange}
          title={statusModalUser.is_active ? 'Khóa Tài Khoản Người Dùng' : 'Mở Khóa Tài Khoản'}
          message={`Bạn có chắc chắn muốn ${statusModalUser.is_active ? 'khóa' : 'mở khóa'} tài khoản @${statusModalUser.username} (${statusModalUser.email})?`}
          confirmText={statusModalUser.is_active ? 'Khóa tài khoản' : 'Mở khóa'}
          isDanger={Boolean(statusModalUser.is_active)}
          isLoading={isUpdatingStatus}
        />
      )}

      {/* Role Change Dialog */}
      {roleModalUser && (
        <ConfirmDialog
          isOpen={Boolean(roleModalUser)}
          onClose={() => setRoleModalUser(null)}
          onConfirm={handleConfirmRoleChange}
          title="Thay Đổi Quyền Quản Trị"
          message={`Chuyển quyền của @${roleModalUser.username} thành "${targetRole.toUpperCase()}"?`}
          confirmText="Xác nhận đổi quyền"
          isDanger={targetRole === 'admin'}
          isLoading={isUpdatingRole}
        />
      )}
    </div>
  );
};
