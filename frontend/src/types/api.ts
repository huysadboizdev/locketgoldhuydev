export interface UserInfoData {
  uid: string;
  username: string;
  first_name: string;
  last_name: string;
  profile_picture_url: string;
}

export interface UserInfoResponse {
  success: boolean;
  data?: UserInfoData;
  msg?: string;
}

export type DevicePlatform = 'ios' | 'android';

export interface RestoreRequest {
  username: string;
  platform: DevicePlatform;
}

export interface RestoreResponse {
  success: boolean;
  client_id?: string;
  position?: number;
  total_queue?: number;
  estimated_time?: number;
  platform?: DevicePlatform;
  msg?: string;
  error?: string;
}

export type QueueItemStatus = 'waiting' | 'processing' | 'completed' | 'error' | 'not_found';

export interface QueueDnsResult {
  profile_id?: string;
  hostname?: string;
  apple_url?: string;
  android_dns?: string;
}

export interface QueueStatusResponse {
  success: boolean;
  client_id: string;
  username?: string;
  platform?: DevicePlatform | null;
  status: QueueItemStatus;
  position: number;
  total_queue: number;
  estimated_time: number;
  result?: {
    success: boolean;
    msg?: string;
    dns?: QueueDnsResult;
    [key: string]: any;
  } | null;
  error?: string | null;
  msg?: string;
}

export interface GlobalQueueStatusResponse {
  success: boolean;
  status: 'idle' | 'active';
  total_queue: number;
  estimated_time: number;
  avg_processing_time: number;
}

export interface MaintenanceConfig {
  enabled: boolean;
  message?: string;
  allow_admin?: boolean;
  end_at?: string | null;
}

export interface PublicDnsConfig {
  profile_id?: string | null;
  hostname?: string | null;
  doh_url?: string | null;
  apple_url?: string | null;
  configured?: boolean;
  nextdns_profile?: string | null;
  nextdns_hostname?: string | null;
  nextdns_apple_url?: string | null;
  instructions?: {
    android?: {
      private_dns_hostname?: string;
    };
    ios?: {
      mobileconfig_url?: string;
      apple_dns_url?: string;
    };
  };
}

export type PopupIcon =
  | 'info'
  | 'sparkles'
  | 'party'
  | 'warning'
  | 'help'
  | 'gift'
  | 'bell'
  | 'wrench'
  | 'shield'
  | 'success'
  | 'error'
  | 'question';

export type PopupAudience = 'all' | 'guests' | 'logged_in' | 'guest' | 'authenticated';
export type PopupDisplayMode = 'every_visit' | 'once_per_session' | 'once_per_version' | 'always';

export interface AnnouncementPopup {
  enabled: boolean;
  version: number;
  title: string;
  message: string;
  content?: string; // legacy fallback
  icon: PopupIcon;
  button_text: string;
  button_url: string;
  button_link?: string; // legacy fallback
  dismissible: boolean;
  audience: PopupAudience;
  display_mode: PopupDisplayMode;
  routes: string[];
  start_at?: string | null;
  end_at?: string | null;
  active?: boolean;
}

export interface CouponQuote {
  code: string;
  normalized_code: string;
  coupon_name?: string;
  discount_type: 'percent' | 'fixed_vnd' | 'fixed';
  discount_value: number;
  original_vnd: number;
  original_coin: number;
  discount_vnd: number;
  discount_coin: number;
  final_vnd: number;
  final_coin: number;
  message?: string;
}

export interface ValidateCouponResponse {
  success: boolean;
  valid: boolean;
  code?: string;
  normalized_code?: string;
  coupon_name?: string;
  discount_type?: 'percent' | 'fixed_vnd' | 'fixed';
  discount_value?: number;
  original_vnd?: number;
  original_coin?: number;
  discount_vnd?: number;
  discount_coin?: number;
  final_vnd?: number;
  final_coin?: number;
  quote?: CouponQuote;
  error?: string;
  msg?: string;
  message?: string;
}

export interface SiteSettingsResponse {
  success: boolean;
  maintenance: MaintenanceConfig;
  maintenance_active: boolean;
  popup?: AnnouncementPopup;
  theme?: {
    name: string;
  };
  layout?: {
    name: string;
  };
  dns?: PublicDnsConfig;
  nextdns_profile?: string | null;
  nextdns_hostname?: string | null;
  nextdns_apple_url?: string | null;
}

export interface HistoryItem {
  username: string;
  status: string;
  duration: number | null;
  completed_at: string | null;
}

export interface RecentHistoryResponse {
  success: boolean;
  items: HistoryItem[];
}

export interface MobileconfigHistoryItem {
  action: string;
  size: number;
  signed: boolean;
  created_at: string;
}

export interface MobileconfigHistoryResponse {
  success: boolean;
  items: MobileconfigHistoryItem[];
}

export interface AuthUser {
  id: number;
  email: string;
  username: string;
  display_name: string;
  avatar_url?: string;
  created_at?: number;
  role?: 'user' | 'admin';
}

export interface AuthMeResponse {
  success: boolean;
  authenticated: boolean;
  user: AuthUser | null;
  csrf_token?: string;
}

export interface AuthResponse {
  success: boolean;
  user?: AuthUser;
  access_token?: string;
  token_type?: string;
  expires_in?: number;
  msg?: string;
  error?: string;
  csrf_token?: string;
}

export interface DownloadTicketResponse {
  success: boolean;
  download_url?: string;
  expires_in?: number;
  msg?: string;
  error?: string;
}

export interface CsrfResponse {
  success: boolean;
  csrf_token: string;
}

export interface ActiveQueueItem {
  client_id: string;
  username: string;
  platform?: DevicePlatform | null;
  status: QueueItemStatus;
  position: number;
  total_queue: number;
  estimated_time: number;
  result?: any;
  error?: string | null;
}

export interface ActiveQueueResponse {
  success: boolean;
  active?: ActiveQueueItem | null;
}

export interface ReviewImage {
  id: number;
  url: string;
  original_filename?: string;
  file_size?: number;
  width?: number;
  height?: number;
}

export interface PublicReview {
  id: number;
  display_name: string;
  masked_username?: string;
  rating: number;
  content: string;
  is_verified: boolean;
  created_at: number;
  images: ReviewImage[];
}

export interface ReviewStats {
  total: number;
  average_rating: number;
  distribution: Record<string, number>;
}

export interface ReviewsResponse {
  success: boolean;
  reviews: PublicReview[];
  stats: ReviewStats;
}

export interface UserReview {
  id: number;
  rating: number;
  content: string;
  status: 'pending' | 'approved' | 'rejected' | 'hidden';
  admin_note?: string | null;
  is_verified: boolean;
  created_at: number;
  updated_at: number;
  images: ReviewImage[];
}

export interface MyReviewResponse {
  success: boolean;
  eligible: boolean;
  has_review: boolean;
  review: UserReview | null;
}

export interface PublicCreatorReview {
  id: number;
  rating: number;
  content: string;
  created_at?: number | null;
  images: ReviewImage[];
}

export interface PublicCreator {
  id: number;
  display_name: string;
  tiktok_handle: string;
  tiktok_url: string;
  screenshot_url: string;
  follower_count?: number | null;
  is_featured: boolean;
  plan_name?: string | null;
  review?: PublicCreatorReview | null;
}

export interface CreatorsResponse {
  success: boolean;
  creators: PublicCreator[];
  total: number;
}

// ---- Plans & Catalog Types ----

export type FulfillmentMode = 'auto_activation' | 'manual_contact' | 'apk_download' | 'disabled';

export interface PlanItem {
  id: number;
  name: string;
  slug: string;
  short_description?: string;
  duration_days: number;
  price_vnd: number;
  price_coin: number;
  product_id?: string;
  features: string[];
  supported_platforms: 'all' | 'ios' | 'android';
  is_active?: boolean | number;
  is_popular?: boolean | number;
  sort_order?: number;
  inventory_status?: 'in_stock' | 'out_of_stock';
  ios_fulfillment_mode: Exclude<FulfillmentMode, 'apk_download'>;
  android_fulfillment_mode: Exclude<FulfillmentMode, 'auto_activation'>;
}

export interface PlansResponse {
  success: boolean;
  plans: PlanItem[];
}

// ---- Wallet & Ledger Types ----

export interface WalletResponse {
  success: boolean;
  balance_coin: number;
}

export interface WalletTransaction {
  id: number;
  user_id: number;
  type: 'topup' | 'purchase' | 'refund' | 'adjustment';
  amount_coin: number;
  balance_before: number;
  balance_after: number;
  reference_type?: string | null;
  reference_id?: string | null;
  description?: string | null;
  idempotency_key?: string | null;
  created_at: number;
}

export interface WalletTransactionsResponse {
  success: boolean;
  items: WalletTransaction[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

// ---- Payments & VietQR Types ----

export interface BankConfig {
  bank_id: string;
  account_no: string;
  account_name: string;
  template: string;
  is_configured: boolean;
}

export interface TopupPaymentResponse {
  success: boolean;
  payment_id: number;
  payment_code: string;
  payment_ref: string;
  transfer_code: string;
  amount_vnd: number;
  coin_amount: number;
  qr_url: string;
  expires_at: number;
  expires_in?: number;
  server_time?: number;
  bank_config: BankConfig;
  status?: PaymentStatus;
  msg?: string;
  error?: string;
}

export interface PlanPaymentResponse {
  success: boolean;
  payment_id: number;
  payment_code: string;
  payment_ref: string;
  transfer_code: string;
  activation_order_id: number;
  amount_vnd: number;
  coin_amount: number;
  qr_url: string;
  expires_at: number;
  expires_in?: number;
  server_time?: number;
  bank_config: BankConfig;
  status?: PaymentStatus;
  msg?: string;
  error?: string;
  fulfillment_mode?: FulfillmentMode;
}

export type PaymentStatus = 'pending' | 'paid' | 'expired' | 'cancelled' | 'underpaid' | 'review_needed';

export interface PaymentOrder {
  id: number;
  payment_code: string;
  payment_ref?: string;
  transfer_code: string;
  user_id: number;
  purpose: 'wallet_topup' | 'plan_purchase';
  plan_id?: number | null;
  amount_vnd: number;
  coin_amount: number;
  provider: string;
  status: PaymentStatus;
  qr_payload?: string | null;
  qr_url?: string;
  bank_transaction_id?: string | null;
  expires_at: number;
  expires_in?: number;
  server_time?: number;
  bank_config?: BankConfig;
  paid_at?: number | null;
  created_at: number;
  updated_at: number;
}

export interface PaymentStatusResponse {
  success: boolean;
  payment: PaymentOrder;
  activation_order?: ActivationOrder | null;
  server_time?: number;
  error?: string;
  msg?: string;
}

// ---- Activation Orders Types ----

export type ActivationOrderStatus =
  | 'awaiting_payment'
  | 'paid'
  | 'awaiting_queue'
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'refunded'
  | 'cancelled';

export interface ActivationOrder {
  id: number;
  user_id: number;
  plan_id?: number | null;
  plan_name_snapshot: string;
  product_id_snapshot: string;
  duration_days_snapshot: number;
  price_vnd_snapshot: number;
  price_coin_snapshot: number;
  payment_method: 'coin' | 'qr';
  payment_order_id?: number | null;
  platform: DevicePlatform;
  locket_username: string;
  fulfillment_mode_snapshot: Exclude<FulfillmentMode, 'disabled'>;
  contact_zalo?: string | null;
  contact_facebook?: string | null;
  admin_note?: string | null;
  handled_by_admin_id?: number | null;
  handled_at?: number | null;
  download_accessed_at?: number | null;
  status: ActivationOrderStatus;
  queue_client_id?: string | null;
  created_at: number;
  updated_at: number;
}

export interface OrdersListResponse {
  success: boolean;
  items: ActivationOrder[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

export interface OrderDetailResponse {
  success: boolean;
  order: ActivationOrder;
  queue?: QueueStatusResponse | null;
  error?: string;
  msg?: string;
}

export interface CoinPurchaseResponse {
  success: boolean;
  activation_order_id: number;
  client_id?: string | null;
  status: ActivationOrderStatus;
  msg?: string;
  remaining_balance?: number;
  shortage_coin?: number;
  current_balance?: number;
  required_coin?: number;
  error?: string;
  fulfillment_mode?: FulfillmentMode;
  idempotent?: boolean;
}

// ---- Safe Platform Config ----

export interface PlatformConfigResponse {
  success: boolean;
  dns: PublicDnsConfig;
  supported_platforms: ('ios' | 'android')[];
  apk_available: boolean;
  mobileconfig_available: boolean;
  bank_configured: boolean;
}

export interface GoldCheckResponse {
  success: boolean;
  uid?: string | null;
  is_gold: boolean;
  expires_date?: string | null;
  product_id?: string | null;
  already_registered: boolean;
  order_status?: string | null;
  blocked: boolean;
  check?: string;
  msg?: string;
  error?: string;
}
