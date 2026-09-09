import { apiClient } from './client';
import type {
  AdminOverviewResponse,
  AdminTimeRange,
  AdminUsersListResponse,
  AdminUserDetailResponse,
  AdminOrdersListResponse,
  AdminActivationOrder,
  AdminPaymentsListResponse,
  AdminPlansResponse,
  AdminPlanItem,
  AdminQueueResponse,
  AdminReviewsResponse,
  AdminAuditLogsResponse,
  AdminSettingsResponse,
  AdminCoupon,
  AdminCouponsResponse,
  AdminCouponDetailResponse,
  AdminCouponStatsResponse,
  AdminCreatorsResponse,
  AdminCreator,
} from '../types/admin';
import type { AnnouncementPopup } from '../types/api';

// Overview
export async function fetchAdminOverview(range: AdminTimeRange = '30d'): Promise<AdminOverviewResponse> {
  return apiClient<AdminOverviewResponse>(`/api/admin/overview?range=${range}`);
}

// Users
export interface FetchUsersParams {
  q?: string;
  role?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export async function fetchAdminUsers(params: FetchUsersParams = {}): Promise<AdminUsersListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.role) sp.set('role', params.role);
  if (params.status) sp.set('status', params.status);
  if (params.page) sp.set('page', String(params.page));
  if (params.limit) sp.set('limit', String(params.limit));
  const query = sp.toString();
  return apiClient<AdminUsersListResponse>(`/api/admin/users${query ? `?${query}` : ''}`);
}

export async function fetchAdminUserDetail(userId: number): Promise<AdminUserDetailResponse> {
  return apiClient<AdminUserDetailResponse>(`/api/admin/users/${userId}`);
}

export async function updateAdminUserStatus(userId: number, isActive: boolean, reason?: string) {
  return apiClient<{ success: boolean; msg?: string }>(`/api/admin/users/${userId}/status`, {
    method: 'POST',
    body: JSON.stringify({ is_active: isActive, reason }),
  });
}

export async function updateAdminUserRole(userId: number, role: 'user' | 'admin', reason?: string) {
  return apiClient<{ success: boolean; msg?: string }>(`/api/admin/users/${userId}/role`, {
    method: 'POST',
    body: JSON.stringify({ role, reason }),
  });
}

export async function adjustAdminUserWallet(userId: number, deltaCoin: number, reason: string, idempotencyKey?: string) {
  return apiClient<{ success: boolean; balance_coin: number; msg?: string }>(`/api/admin/users/${userId}/adjust-wallet`, {
    method: 'POST',
    body: JSON.stringify({
      amount_coin: deltaCoin,
      reason,
      idempotency_key: idempotencyKey,
    }),
  });
}

// Orders
export interface FetchOrdersParams {
  q?: string;
  status?: string;
  platform?: string;
  fulfillment_mode?: string;
  page?: number;
  limit?: number;
}

export async function fetchAdminOrders(params: FetchOrdersParams = {}): Promise<AdminOrdersListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.status) sp.set('status', params.status);
  if (params.platform) sp.set('platform', params.platform);
  if (params.fulfillment_mode) sp.set('fulfillment_mode', params.fulfillment_mode);
  if (params.page) sp.set('page', String(params.page));
  if (params.limit) sp.set('limit', String(params.limit));
  const query = sp.toString();
  return apiClient<AdminOrdersListResponse>(`/api/admin/orders${query ? `?${query}` : ''}`);
}

export async function startManualAdminOrder(orderId: number, note?: string) {
  return apiClient<{ success: boolean; order: AdminActivationOrder; msg?: string }>(`/api/admin/orders/${orderId}/start`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  });
}

export async function completeManualAdminOrder(orderId: number, note?: string) {
  return apiClient<{ success: boolean; order: AdminActivationOrder; msg?: string }>(`/api/admin/orders/${orderId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  });
}

export async function cancelManualAdminOrder(orderId: number, reason: string) {
  return apiClient<{ success: boolean; order: AdminActivationOrder; msg?: string }>(`/api/admin/orders/${orderId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function refundManualAdminOrder(
  orderId: number,
  reason: string,
  confirmedExternalRefund?: boolean,
  refundReference?: string
) {
  return apiClient<{ success: boolean; order: AdminActivationOrder; msg?: string }>(`/api/admin/orders/${orderId}/refund`, {
    method: 'POST',
    body: JSON.stringify({
      reason,
      confirmed_external_refund: confirmedExternalRefund,
      refund_reference: refundReference,
    }),
  });
}

// Payments
export interface FetchPaymentsParams {
  q?: string;
  status?: string;
  purpose?: string;
  page?: number;
  limit?: number;
}

export async function fetchAdminPayments(params: FetchPaymentsParams = {}): Promise<AdminPaymentsListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.status) sp.set('status', params.status);
  if (params.purpose) sp.set('purpose', params.purpose);
  if (params.page) sp.set('page', String(params.page));
  if (params.limit) sp.set('limit', String(params.limit));
  const query = sp.toString();
  return apiClient<AdminPaymentsListResponse>(`/api/admin/payments${query ? `?${query}` : ''}`);
}

export async function confirmAdminPayment(paymentId: number, bankTxId?: string) {
  return apiClient<{ success: boolean; msg?: string }>(`/api/admin/payments/${paymentId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ bank_transaction_id: bankTxId }),
  });
}

export async function manuallyConfirmAdminPayment(paymentId: number, reason: string, bankTxId?: string) {
  return apiClient<{ success: boolean; manual: boolean; msg?: string }>(
    `/api/admin/payments/${paymentId}/manual-confirm`,
    {
      method: 'POST',
      body: JSON.stringify({
        reason,
        bank_transaction_id: bankTxId,
      }),
    }
  );
}

export async function rejectAdminPayment(paymentId: number, reason?: string) {
  return apiClient<{ success: boolean; msg?: string }>(`/api/admin/payments/${paymentId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

// Plans
export async function fetchAdminPlans(): Promise<AdminPlansResponse> {
  return apiClient<AdminPlansResponse>('/api/admin/plans');
}

export async function createAdminPlan(payload: Partial<AdminPlanItem>) {
  return apiClient<{ success: boolean; plan: AdminPlanItem }>('/api/admin/plans', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateAdminPlan(planId: number, payload: Partial<AdminPlanItem>) {
  return apiClient<{ success: boolean; plan: AdminPlanItem }>(`/api/admin/plans/${planId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function toggleAdminPlan(planId: number, isActive: boolean) {
  return apiClient<{ success: boolean; plan: AdminPlanItem }>(`/api/admin/plans/${planId}/toggle`, {
    method: 'POST',
    body: JSON.stringify({ is_active: isActive }),
  });
}

export async function deleteAdminPlan(planId: number) {
  return apiClient<{ success: boolean; msg?: string }>(`/api/admin/plans/${planId}`, {
    method: 'DELETE',
  });
}

// Queue
export async function fetchAdminQueue(): Promise<AdminQueueResponse> {
  return apiClient<AdminQueueResponse>('/api/admin/queue');
}

// Reviews
export interface FetchReviewsParams {
  status?: string;
  page?: number;
  limit?: number;
}

export async function fetchAdminReviews(params: FetchReviewsParams = {}): Promise<AdminReviewsResponse> {
  const sp = new URLSearchParams();
  if (params.status) sp.set('status', params.status);
  if (params.page) sp.set('page', String(params.page));
  if (params.limit) sp.set('limit', String(params.limit));
  const query = sp.toString();
  return apiClient<AdminReviewsResponse>(`/api/admin/reviews${query ? `?${query}` : ''}`);
}

export async function deleteAdminReview(reviewId: number) {
  return apiClient<{ success: boolean; msg?: string }>(`/api/admin/reviews/${reviewId}`, {
    method: 'DELETE',
  });
}

export async function fetchAdminCreators(params: { q?: string; page?: number; limit?: number } = {}) {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.page) sp.set('page', String(params.page));
  if (params.limit) sp.set('limit', String(params.limit));
  const query = sp.toString();
  return apiClient<AdminCreatorsResponse>(`/api/admin/creators${query ? `?${query}` : ''}`);
}

export async function createAdminCreator(formData: FormData) {
  return apiClient<{ success: boolean; creator: AdminCreator; msg: string }>('/api/admin/creators', {
    method: 'POST',
    body: formData,
  });
}

export async function updateAdminCreator(creatorId: number, formData: FormData) {
  return apiClient<{ success: boolean; creator: AdminCreator; msg: string }>(`/api/admin/creators/${creatorId}`, {
    method: 'PUT',
    body: formData,
  });
}

export async function deleteAdminCreator(creatorId: number) {
  return apiClient<{ success: boolean; msg: string }>(`/api/admin/creators/${creatorId}`, {
    method: 'DELETE',
  });
}

// Accounts Pool
export async function fetchAdminAccounts() {
  return apiClient<{ success: boolean; accounts: any[]; rotator_summary: any }>('/api/admin/accounts');
}

export async function addAdminAccount(payload: { username?: string; email?: string; password?: string }) {
  return apiClient<{ success: boolean; accounts: any[] }>('/api/admin/accounts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteAdminAccount(accountIdentifier: string | number) {
  return apiClient<{ success: boolean; accounts: any[] }>(`/api/admin/accounts/${encodeURIComponent(accountIdentifier)}`, {
    method: 'DELETE',
  });
}

// Tokens
export async function fetchAdminTokens() {
  return apiClient<{ success: boolean; tokens: any[] }>('/api/admin/tokens');
}

// Proxies
export async function fetchAdminProxies() {
  return apiClient<{ success: boolean; proxies: any[] }>('/api/admin/proxies');
}

export async function addAdminProxy(proxyUrl: string) {
  return apiClient<{ success: boolean; proxies: any[] }>('/api/admin/proxies', {
    method: 'POST',
    body: JSON.stringify({ url: proxyUrl }),
  });
}

export async function deleteAdminProxy(proxyIdentifier: string | number) {
  return apiClient<{ success: boolean; proxies: any[] }>(`/api/admin/proxies/${encodeURIComponent(proxyIdentifier)}`, {
    method: 'DELETE',
  });
}

// Mobileconfig
export async function uploadAdminMobileconfig(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient<{ success: boolean; msg?: string }>('/api/admin/mobileconfig', {
    method: 'POST',
    body: formData,
  });
}

export async function deleteAdminMobileconfig() {
  return apiClient<{ success: boolean; msg?: string }>('/api/admin/mobileconfig', {
    method: 'DELETE',
  });
}

// Settings
export async function fetchAdminSettings(): Promise<AdminSettingsResponse> {
  return apiClient<AdminSettingsResponse>('/api/admin/site-settings');
}

export async function updateAdminSettings(settings: any) {
  return apiClient<{ success: boolean; settings: any }>('/api/admin/site-settings', {
    method: 'POST',
    body: JSON.stringify(settings),
  });
}

// Audit Logs
export interface FetchAuditLogsParams {
  action?: string;
  entity_type?: string;
  admin_user_id?: number;
  page?: number;
  limit?: number;
}

export async function fetchAdminAuditLogs(params: FetchAuditLogsParams = {}): Promise<AdminAuditLogsResponse> {
  const sp = new URLSearchParams();
  if (params.action) sp.set('action', params.action);
  if (params.entity_type) sp.set('entity_type', params.entity_type);
  if (params.admin_user_id) sp.set('admin_user_id', String(params.admin_user_id));
  if (params.page) sp.set('page', String(params.page));
  if (params.limit) sp.set('limit', String(params.limit));
  const query = sp.toString();
  return apiClient<AdminAuditLogsResponse>(`/api/admin/audit-logs${query ? `?${query}` : ''}`);
}

// Popup Settings
export async function fetchAdminPopup(): Promise<{ success: boolean; popup: AnnouncementPopup }> {
  return apiClient<{ success: boolean; popup: AnnouncementPopup }>('/api/admin/popup');
}

export async function updateAdminPopup(popup: Partial<AnnouncementPopup>): Promise<{ success: boolean; popup: AnnouncementPopup; msg?: string }> {
  return apiClient<{ success: boolean; popup: AnnouncementPopup; msg?: string }>('/api/admin/popup', {
    method: 'PUT',
    body: JSON.stringify(popup),
  });
}

// Coupons
export interface FetchCouponsParams {
  search?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export async function fetchAdminCoupons(params: FetchCouponsParams = {}): Promise<AdminCouponsResponse> {
  const sp = new URLSearchParams();
  if (params.search) sp.set('search', params.search);
  if (params.status) sp.set('status', params.status);
  if (params.page) sp.set('page', String(params.page));
  if (params.limit) sp.set('limit', String(params.limit));
  const query = sp.toString();
  return apiClient<AdminCouponsResponse>(`/api/admin/coupons${query ? `?${query}` : ''}`);
}

export async function fetchAdminCouponDetail(couponId: number): Promise<AdminCouponDetailResponse> {
  return apiClient<AdminCouponDetailResponse>(`/api/admin/coupons/${couponId}`);
}

export async function createAdminCoupon(data: {
  code: string;
  name: string;
  discount_type: 'percent' | 'fixed_vnd' | 'fixed';
  discount_value: number;
  description?: string;
  max_discount_vnd?: number | null;
  min_order_vnd?: number;
  usage_limit_total?: number | null;
  usage_limit_per_user?: number | null;
  starts_at?: number | string | null;
  ends_at?: number | string | null;
  is_active?: boolean;
  plan_ids?: number[];
}): Promise<{ success: boolean; coupon: AdminCoupon; msg?: string }> {
  return apiClient<{ success: boolean; coupon: AdminCoupon; msg?: string }>('/api/admin/coupons', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateAdminCoupon(
  couponId: number,
  data: Partial<AdminCoupon> & { plan_ids?: number[] }
): Promise<{ success: boolean; coupon: AdminCoupon; msg?: string }> {
  return apiClient<{ success: boolean; coupon: AdminCoupon; msg?: string }>(`/api/admin/coupons/${couponId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function toggleAdminCoupon(
  couponId: number,
  isActive?: boolean
): Promise<{ success: boolean; coupon: AdminCoupon; is_active: boolean; msg?: string }> {
  return apiClient<{ success: boolean; coupon: AdminCoupon; is_active: boolean; msg?: string }>(
    `/api/admin/coupons/${couponId}/toggle`,
    {
      method: 'POST',
      body: JSON.stringify(typeof isActive === 'boolean' ? { is_active: isActive } : {}),
    }
  );
}

export async function deleteAdminCoupon(couponId: number): Promise<{ success: boolean; msg?: string }> {
  return apiClient<{ success: boolean; msg?: string }>(`/api/admin/coupons/${couponId}`, {
    method: 'DELETE',
  });
}

export async function fetchAdminCouponStats(couponId: number): Promise<AdminCouponStatsResponse> {
  return apiClient<AdminCouponStatsResponse>(`/api/admin/coupons/${couponId}/stats`);
}
