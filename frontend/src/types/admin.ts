// TypeScript types for the Unified React Admin SPA

export type AdminTimeRange = '7d' | '30d' | '90d';

export interface AdminPagination {
  total: number;
  limit: number;
  offset: number;
  page: number;
  pages: number;
  has_more: boolean;
}

export interface OverviewCards {
  total_users: number;
  active_users: number;
  new_users?: number;
  pending_payments?: number;
  paid_payments?: number;
  paid_revenue_vnd?: number;
  topup_revenue_vnd?: number;
  plan_purchase_revenue_vnd?: number;
  total_coin_in_wallets?: number;
  total_wallet_balance_coin?: number;
  users_with_coin?: number;
  total_orders?: number;
  completed_orders?: number;
  failed_orders?: number;
  processing_orders?: number;
  queued_orders?: number;
  pending_reviews?: number;
  approved_reviews?: number;
  total_reviews?: number;
  average_rating?: number;
  queue_waiting?: number;
  queue_processing?: number;
  // Nested backward compatibility objects
  activation_orders?: {
    total: number;
    completed: number;
    processing: number;
    failed: number;
    queued: number;
  };
  payments?: {
    total_paid: number;
    pending: number;
    revenue_vnd: number;
    topup_revenue_vnd: number;
    plan_purchase_revenue_vnd: number;
  };
  wallet?: {
    total_balance_coin: number;
    total_users_with_coin: number;
  };
  reviews?: {
    total: number;
    pending: number;
    average_rating: number;
  };
  queue?: {
    total_waiting: number;
    total_processing: number;
  };
}

export interface OverviewSeriesItem {
  date: string;
  revenue_vnd: number;
  paid_payments: number;
  orders: number;
  completed_orders: number;
  new_users: number;
}

export interface RevenueSeriesItem {
  date: string;
  revenue_vnd: number;
  order_count: number;
}

export interface RegistrationSeriesItem {
  date: string;
  count: number;
}

export interface OverviewCharts {
  revenue_series: RevenueSeriesItem[];
  registrations_series: RegistrationSeriesItem[];
  orders_by_status: Record<string, number>;
  orders_by_platform: Record<string, number>;
  payments_by_status: Record<string, number>;
}

export interface AdminOverviewResponse {
  success: boolean;
  range: AdminTimeRange;
  timezone: string;
  cards: OverviewCards;
  series: OverviewSeriesItem[];
  charts?: OverviewCharts;
  recent_orders: any[];
  recent_payments: any[];
  recent?: {
    orders: any[];
    payments: any[];
    audit_logs: AdminAuditLog[];
  };
}

export interface AdminUser {
  id: number;
  email: string;
  username: string;
  display_name: string;
  role: 'user' | 'admin';
  is_active: number | boolean;
  balance_coin: number;
  coin_balance?: number;
  created_at: number;
  order_count?: number;
  payment_count?: number;
}

export interface AdminUsersListResponse {
  success: boolean;
  items: AdminUser[];
  pagination: AdminPagination;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AdminUserDetailResponse {
  success: boolean;
  user: AdminUser;
  wallet_transactions: any[];
  activation_orders: any[];
  payments: any[];
  reviews: any[];
}

export interface AdminActivationOrder {
  id: number;
  user_id: number;
  username?: string;
  user_username?: string;
  user_email?: string;
  plan_id: number;
  plan_name_snapshot: string;
  product_id_snapshot?: string;
  duration_days_snapshot: number;
  price_vnd_snapshot: number;
  price_coin_snapshot: number;
  payment_method: 'coin' | 'qr';
  payment_order_id?: number;
  payment_status?: string;
  payment_code?: string;
  transfer_code?: string;
  platform: 'ios' | 'android';
  locket_username?: string;
  fulfillment_mode_snapshot: 'auto_activation' | 'manual_contact' | 'apk_download';
  contact_zalo?: string;
  contact_facebook?: string;
  status: 'awaiting_payment' | 'paid' | 'awaiting_queue' | 'queued' | 'processing' | 'completed' | 'failed' | 'refunded' | 'cancelled';
  queue_client_id?: string;
  admin_note?: string;
  handled_by_admin_id?: number;
  handled_at?: number;
  download_accessed_at?: number;
  created_at: number;
  updated_at: number;
}

export interface AdminOrdersListResponse {
  success: boolean;
  items: AdminActivationOrder[];
  pagination: AdminPagination;
  total: number;
  page: number;
  limit: number;
  pages: number;
  manual_pending_count?: number;
}

export interface AdminPaymentsListResponse {
  success: boolean;
  items: any[];
  pagination: AdminPagination;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AdminPlanItem {
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
  is_active: boolean | number;
  is_popular: boolean | number;
  sort_order: number;
  inventory_status: 'in_stock' | 'out_of_stock';
  ios_fulfillment_mode: 'auto_activation' | 'manual_contact' | 'disabled';
  android_fulfillment_mode: 'apk_download' | 'manual_contact' | 'disabled';
  created_at?: number;
  updated_at?: number;
}

export interface AdminPlansResponse {
  success: boolean;
  plans: AdminPlanItem[];
}

export interface AdminQueueItem {
  client_id: string;
  username: string;
  platform?: string;
  status: string;
  position: number;
  total_queue: number;
  estimated_time: number;
  created_at: number;
  started_at?: number | null;
  completed_at?: number | null;
  order_id?: number | null;
  plan_id?: number | null;
  plan_name?: string | null;
  error?: string | null;
  attempts?: number;
}

export interface AdminQueueResponse {
  success: boolean;
  active_workers?: number;
  total_in_queue?: number;
  items?: AdminQueueItem[];
  snapshot?: {
    active_workers: number;
    total_in_queue: number;
    items: AdminQueueItem[];
  };
}

export interface AdminReviewItem {
  id: number;
  user_id: number;
  email: string;
  username: string;
  display_name: string;
  rating: number;
  content: string;
  status: 'pending' | 'approved' | 'rejected' | 'hidden';
  staff_note?: string | null;
  is_pinned: number | boolean;
  sort_priority: number;
  is_verified: number | boolean;
  created_at: number;
  updated_at: number;
  images: { id: number; url: string; original_filename?: string }[];
}

export interface AdminReviewsResponse {
  success: boolean;
  items: AdminReviewItem[];
  pagination: AdminPagination;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AdminCreator {
  id: number;
  user_id: number;
  email: string;
  username: string;
  display_name: string;
  account_display_name?: string;
  user_is_active: boolean;
  tiktok_handle: string;
  tiktok_url: string;
  screenshot_name: string;
  screenshot_url: string;
  follower_count?: number | null;
  is_featured: boolean;
  is_active: boolean;
  require_review: boolean;
  sort_order: number;
  review_id?: number | null;
  rating?: number | null;
  review_content?: string | null;
  plan_name?: string | null;
  created_at: number;
  updated_at: number;
}

export interface AdminCreatorsResponse {
  success: boolean;
  creators: AdminCreator[];
  items: AdminCreator[];
  pagination: AdminPagination;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AdminAuditLog {
  id: number;
  admin_user_id: number;
  admin_username?: string;
  admin_email?: string;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  details?: any;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: number;
}

export interface AdminAuditLogsResponse {
  success: boolean;
  items: AdminAuditLog[];
  pagination: AdminPagination;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AdminSettingsResponse {
  success: boolean;
  settings: {
    maintenance?: {
      enabled: boolean;
      message?: string;
      allow_admin?: boolean;
      end_at?: string | null;
    };
    theme?: {
      name: string;
      primary_color?: string;
    };
    layout?: {
      name: string;
      show_announcement?: boolean;
      announcement_text?: string;
    };
    popup?: {
      enabled: boolean;
      version?: number;
      title?: string;
      message?: string;
      content?: string;
      icon?: string;
      button_text?: string;
      button_url?: string;
      button_link?: string;
      dismissible?: boolean;
      audience?: string;
      display_mode?: string;
      routes?: string[];
      start_at?: string | null;
      end_at?: string | null;
    };
    [key: string]: any;
  };
}

export interface AdminCoupon {
  id: number;
  code: string;
  normalized_code: string;
  name: string;
  description?: string | null;
  discount_type: 'percent' | 'fixed_vnd' | 'fixed';
  discount_value: number;
  max_discount_vnd?: number | null;
  min_order_vnd: number;
  usage_limit_total?: number | null;
  usage_limit_per_user?: number | null;
  starts_at?: number | null;
  ends_at?: number | null;
  is_active: number | boolean;
  created_by_admin_id?: number | null;
  created_at: number;
  updated_at: number;
  applicable_plan_ids?: number[];
  reserved_count?: number;
  redeemed_count?: number;
  released_count?: number;
  total_used?: number;
  is_exhausted?: boolean;
}

export interface AdminCouponRedemptionItem {
  id: number;
  coupon_id: number;
  user_id: number;
  username?: string;
  email?: string;
  payment_order_id?: number | null;
  activation_order_id?: number | null;
  original_vnd: number;
  discount_vnd: number;
  final_price_vnd: number;
  status: 'reserved' | 'redeemed' | 'released';
  created_at: number;
  redeemed_at?: number | null;
}

export interface AdminCouponStats {
  coupon: AdminCoupon;
  reserved_count: number;
  redeemed_count: number;
  released_count: number;
  total_discount_vnd: number;
  total_revenue_vnd: number;
  recent_redemptions: AdminCouponRedemptionItem[];
}

export interface AdminCouponsResponse {
  success: boolean;
  items: AdminCoupon[];
  coupons?: AdminCoupon[];
  pagination: AdminPagination;
  total: number;
  page: number;
  limit: number;
  pages: number;
  has_more: boolean;
}

export interface AdminCouponDetailResponse {
  success: boolean;
  coupon: AdminCoupon;
}

export interface AdminCouponStatsResponse {
  success: boolean;
  stats: AdminCouponStats;
  coupon?: AdminCoupon;
  reserved_count?: number;
  redeemed_count?: number;
  released_count?: number;
  total_discount_vnd?: number;
  total_revenue_vnd?: number;
  recent_redemptions?: AdminCouponRedemptionItem[];
}
