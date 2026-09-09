import { apiClient } from './client';
import type {
  DevicePlatform,
  UserInfoResponse,
  RestoreResponse,
  QueueStatusResponse,
  GlobalQueueStatusResponse,
  SiteSettingsResponse,
  RecentHistoryResponse,
  MobileconfigHistoryResponse,
  CsrfResponse,
  AuthMeResponse,
  AuthResponse,
  ActiveQueueResponse,
  DownloadTicketResponse,
  ReviewsResponse,
  MyReviewResponse,
  CreatorsResponse,
  PlansResponse,
  WalletResponse,
  WalletTransactionsResponse,
  TopupPaymentResponse,
  PlanPaymentResponse,
  PaymentStatusResponse,
  OrdersListResponse,
  OrderDetailResponse,
  CoinPurchaseResponse,
  PlatformConfigResponse,
  ValidateCouponResponse,
} from '../types/api';


/**
 * Tra cứu thông tin người dùng qua Username
 */
export async function fetchUserInfo(username: string): Promise<UserInfoResponse> {
  return apiClient<UserInfoResponse>('/api/get-user-info', {
    method: 'POST',
    body: JSON.stringify({ username }),
  });
}

/**
 * Gửi yêu cầu vào hàng đợi kích hoạt kèm lựa chọn nền tảng iOS/Android
 */
export async function requestRestore(username: string, platform: DevicePlatform): Promise<RestoreResponse> {
  return apiClient<RestoreResponse>('/api/restore', {
    method: 'POST',
    body: JSON.stringify({ username, platform }),
  });
}

/**
 * Polling kiểm tra trạng thái hàng đợi theo client_id
 */
export async function fetchQueueStatus(clientId: string): Promise<QueueStatusResponse> {
  return apiClient<QueueStatusResponse>('/api/queue/status', {
    method: 'POST',
    body: JSON.stringify({ client_id: clientId }),
  });
}

/**
 * Lấy trạng thái tổng quan của hàng đợi
 */
export async function fetchGlobalQueueStatus(): Promise<GlobalQueueStatusResponse> {
  return apiClient<GlobalQueueStatusResponse>('/api/queue/global-status', {
    method: 'GET',
  });
}

/**
 * Đọc cấu hình trang và trạng thái bảo trì
 */
export async function fetchSiteSettings(): Promise<SiteSettingsResponse> {
  return apiClient<SiteSettingsResponse>('/api/site-settings', {
    method: 'GET',
  });
}

/**
 * Lịch sử kích hoạt gần nhất đã ẩn danh
 */
export async function fetchRecentHistory(): Promise<RecentHistoryResponse> {
  return apiClient<RecentHistoryResponse>('/api/recent-history', {
    method: 'GET',
    cache: 'no-store',
  });
}

/**
 * Lịch sử cập nhật file mobileconfig
 */
export async function fetchMobileconfigHistory(): Promise<MobileconfigHistoryResponse> {
  return apiClient<MobileconfigHistoryResponse>('/api/mobileconfig/history', {
    method: 'GET',
  });
}

/**
 * Đường dẫn trực tiếp tải file profile iOS
 */
export const MOBILECONFIG_DOWNLOAD_URL = '/api/mobileconfig';

/* =========================================================================
 * AUTHENTICATION & CUSTOMER ACCOUNT APIS
 * ========================================================================= */

/**
 * Lấy CSRF token cho phiên hiện tại
 */
export async function fetchCsrfToken(): Promise<CsrfResponse> {
  return apiClient<CsrfResponse>('/api/auth/csrf', {
    method: 'GET',
  });
}

/**
 * Lấy trạng thái đăng nhập và thông tin tài khoản hiện tại
 */
export async function fetchAuthMe(): Promise<AuthMeResponse> {
  return apiClient<AuthMeResponse>('/api/auth/me', {
    method: 'GET',
  });
}

/**
 * Đăng ký tài khoản người dùng mới
 */
export async function registerApi(data: {
  email: string;
  username: string;
  display_name?: string;
  password: string;
}): Promise<AuthResponse> {
  return apiClient<AuthResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Đăng nhập người dùng bằng email hoặc username
 */
export async function loginApi(data: {
  identifier: string;
  password: string;
  remember_me?: boolean;
}): Promise<AuthResponse> {
  return apiClient<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Đăng nhập hoặc đăng ký bằng Google ID token
 */
export async function loginWithGoogleApi(credential: string): Promise<AuthResponse> {
  return apiClient<AuthResponse>('/api/auth/google', {
    method: 'POST',
    body: JSON.stringify({ credential }),
  });
}

/**
 * Đăng xuất tài khoản
 */
export async function logoutApi(): Promise<{ success: boolean; msg?: string }> {
  return apiClient<{ success: boolean; msg?: string }>('/api/auth/logout', {
    method: 'POST',
  });
}

/**
 * Làm mới access token bằng HttpOnly refresh token cookie
 */
export async function refreshAuthApi(): Promise<AuthResponse> {
  return apiClient<AuthResponse>('/api/auth/refresh', {
    method: 'POST',
  });
}

/**
 * Tạo vé tải xuống (single-use ticket) để tải profile mobileconfig cho iOS
 */
export async function createMobileconfigDownloadTicket(param: string | { clientId?: string; activationOrderId?: number }): Promise<DownloadTicketResponse> {
  const payload = typeof param === 'string'
    ? { client_id: param }
    : { client_id: param.clientId, activation_order_id: param.activationOrderId };
  return apiClient<DownloadTicketResponse>('/api/mobileconfig/download-ticket', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Tạo vé tải xuống (single-use ticket) để tải ứng dụng APK cho Android
 */
export async function createApkDownloadTicket(param: string | { clientId?: string; activationOrderId?: number }): Promise<DownloadTicketResponse> {
  const payload = typeof param === 'string'
    ? { client_id: param }
    : { client_id: param.clientId, activation_order_id: param.activationOrderId };
  return apiClient<DownloadTicketResponse>('/api/apk/download-ticket', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Lấy yêu cầu hàng đợi đang hoạt động của người dùng (nếu có)
 */
export async function fetchMyActiveQueue(): Promise<ActiveQueueResponse> {
  return apiClient<ActiveQueueResponse>('/api/queue/my-active', {
    method: 'GET',
  });
}

/* =========================================================================
 * REVIEWS & RATINGS APIS
 * ========================================================================= */

/**
 * Lấy danh sách đánh giá công khai đã duyệt cùng thống kê xếp hạng
 */
export async function fetchPublicReviews(): Promise<ReviewsResponse> {
  return apiClient<ReviewsResponse>('/api/reviews', {
    method: 'GET',
    cache: 'no-store',
  });
}

/**
 * Lấy đánh giá của chính người dùng hiện tại và trạng thái hợp lệ
 */
export async function fetchMyReview(): Promise<MyReviewResponse> {
  return apiClient<MyReviewResponse>('/api/reviews/me', {
    method: 'GET',
  });
}

/**
 * Gửi đánh giá mới (Multipart FormData chứa rating, content, images)
 */
export async function submitReviewApi(formData: FormData): Promise<{ success: boolean; msg: string; review_id?: number }> {
  return apiClient<{ success: boolean; msg: string; review_id?: number }>('/api/reviews', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Cập nhật đánh giá hiện tại (Multipart FormData chứa rating, content, images)
 */
export async function updateMyReviewApi(formData: FormData): Promise<{ success: boolean; msg: string }> {
  return apiClient<{ success: boolean; msg: string }>('/api/reviews/me', {
    method: 'PUT',
    body: formData,
  });
}

/**
 * Xóa vĩnh viễn đánh giá của chính mình
 */
export async function deleteMyReviewApi(): Promise<{ success: boolean; msg: string }> {
  return apiClient<{ success: boolean; msg: string }>('/api/reviews/me', {
    method: 'DELETE',
  });
}

export async function fetchPublicCreators(): Promise<CreatorsResponse> {
  return apiClient<CreatorsResponse>('/api/creators', { method: 'GET', cache: 'no-store' });
}

/* =========================================================================
 * PLANS, WALLET, PAYMENTS & ORDERS APIS
 * ========================================================================= */

/**
 * Lấy danh sách các gói dịch vụ Locket Gold đang hoạt động
 */
export async function fetchPlans(): Promise<PlansResponse> {
  return apiClient<PlansResponse>('/api/plans', {
    method: 'GET',
  });
}

/**
 * Lấy số dư Coin trong ví người dùng
 */
export async function fetchWalletBalance(): Promise<WalletResponse> {
  return apiClient<WalletResponse>('/api/wallet', {
    method: 'GET',
    cache: 'no-store',
  });
}

/**
 * Lấy danh sách biến động số dư / sổ cái giao dịch
 */
export async function fetchWalletTransactions(limit = 20, offset = 0): Promise<WalletTransactionsResponse> {
  return apiClient<WalletTransactionsResponse>(`/api/wallet/transactions?limit=${limit}&offset=${offset}`, {
    method: 'GET',
    cache: 'no-store',
  });
}

/**
 * Tạo yêu cầu nạp Coin qua chuyển khoản VietQR
 */
export async function createTopupPayment(amountVnd: number, idempotencyKey?: string): Promise<TopupPaymentResponse> {
  return apiClient<TopupPaymentResponse>('/api/payments/topup', {
    method: 'POST',
    body: JSON.stringify({ amount_vnd: amountVnd, idempotency_key: idempotencyKey }),
  });
}

/**
/**
 * Xác thực và lấy báo giá chiết khấu cho mã giảm giá
 */
export async function validateCoupon(code: string, planId: number): Promise<ValidateCouponResponse> {
  return apiClient<ValidateCouponResponse>('/api/coupons/validate', {
    method: 'POST',
    body: JSON.stringify({
      code: code.trim(),
      plan_id: planId,
    }),
  });
}

/**
 * Tạo yêu cầu thanh toán trực tiếp qua mã VietQR cho một gói cụ thể
 */
export async function createPlanPayment(data: {
  plan_id: number;
  platform: DevicePlatform;
  username?: string;
  contact_zalo?: string;
  contact_facebook?: string;
  idempotency_key?: string;
  coupon_code?: string;
}): Promise<PlanPaymentResponse> {
  return apiClient<PlanPaymentResponse>('/api/payments/plan', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Polling kiểm tra trạng thái thanh toán theo payment_code hoặc payment_ref
 */
export async function fetchPaymentStatus(paymentCode: string): Promise<PaymentStatusResponse> {
  return apiClient<PaymentStatusResponse>(`/api/payments/${encodeURIComponent(paymentCode)}`, {
    method: 'GET',
    cache: 'no-store',
  });
}

/**
 * Tạo lại mã VietQR mới (renew) khi mã cũ đã hết hạn hoặc bị hủy
 */
export async function renewPayment(paymentRef: string): Promise<PaymentStatusResponse> {
  return apiClient<PaymentStatusResponse>(`/api/payments/${encodeURIComponent(paymentRef)}/renew`, {
    method: 'POST',
  });
}

/** Hủy QR chưa thanh toán và giải phóng lượt giữ chỗ của mã giảm giá. */
export async function cancelPayment(paymentRef: string): Promise<PaymentStatusResponse> {
  return apiClient<PaymentStatusResponse>(`/api/payments/${encodeURIComponent(paymentRef)}/cancel`, {
    method: 'POST',
  });
}

/**
 * Mua và kích hoạt gói Locket Gold trực tiếp bằng số dư Coin
 */
export async function purchasePlanWithCoin(data: {
  plan_id: number;
  platform: DevicePlatform;
  username?: string;
  contact_zalo?: string;
  contact_facebook?: string;
  idempotency_key?: string;
  coupon_code?: string;
}): Promise<CoinPurchaseResponse> {
  return apiClient<CoinPurchaseResponse>('/api/orders/coin', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Lấy danh sách các đơn kích hoạt của người dùng hiện tại
 */
export async function fetchUserOrders(limit = 20, offset = 0): Promise<OrdersListResponse> {
  return apiClient<OrdersListResponse>(`/api/orders?limit=${limit}&offset=${offset}`, {
    method: 'GET',
    cache: 'no-store',
  });
}

/**
 * Lấy chi tiết một đơn kích hoạt kèm trạng thái hàng đợi nếu có
 */
export async function fetchOrderDetail(orderId: number): Promise<OrderDetailResponse> {
  return apiClient<OrderDetailResponse>(`/api/orders/${orderId}`, {
    method: 'GET',
  });
}

/**
 * Lấy cấu hình public an toàn cho nền tảng (DNS, file download)
 */
export async function fetchPlatformConfig(): Promise<PlatformConfigResponse> {
  return apiClient<PlatformConfigResponse>('/api/platform-config', {
    method: 'GET',
  });
}
