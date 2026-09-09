import React, { useState, useEffect, useRef } from 'react';
import {
  PlanItem,
  DevicePlatform,
  UserInfoData,
  PublicDnsConfig,
  FulfillmentMode,
  CouponQuote,
} from '../../types/api';
import {
  fetchUserInfo,
  purchasePlanWithCoin,
  createPlanPayment,
  validateCoupon,
  renewPayment,
  cancelPayment,
  fetchPlatformConfig,
  createMobileconfigDownloadTicket,
  createApkDownloadTicket,
  fetchQueueStatus,
} from '../../api/endpoints';
import { PlanCatalog } from './PlanCatalog';
import { PaymentQrPanel, PaymentQrData } from '../../components/payment/PaymentQrPanel';
import { usePaymentPolling } from '../../hooks/usePaymentPolling';
import { useToast } from '../../hooks/useToast';
import {
  Apple,
  Smartphone,
  Search,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  ExternalLink,
  Download,
  Loader2,
  ArrowRight,
  ArrowLeft,
  Coins,
  QrCode,
  ShieldAlert,
  Ticket,
  Tag,
} from 'lucide-react';

interface ActivationWizardProps {
  plans: PlanItem[];
  isLoadingPlans: boolean;
  userCoinBalance: number;
  onRefreshWallet: () => void;
  onGoToTopup: (neededCoins?: number) => void;
  onOrderCreated?: (orderId: number) => void;
}

type WizardStep = 'plan' | 'platform' | 'username' | 'contact' | 'payment' | 'completed';

const getFulfillmentMode = (plan: PlanItem, platform: DevicePlatform): Exclude<FulfillmentMode, 'disabled'> => {
  const configured = platform === 'ios'
    ? plan.ios_fulfillment_mode
    : plan.android_fulfillment_mode;
  if (configured && configured !== 'disabled') return configured;
  return platform === 'android' ? 'apk_download' : 'auto_activation';
};

export const ActivationWizard: React.FC<ActivationWizardProps> = ({
  plans,
  isLoadingPlans,
  userCoinBalance,
  onRefreshWallet,
  onGoToTopup,
  onOrderCreated,
}) => {
  const toast = useToast();
  const [currentStep, setCurrentStep] = useState<WizardStep>('plan');

  // Selected data
  const [selectedPlan, setSelectedPlan] = useState<PlanItem | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<DevicePlatform | null>(null);
  const [usernameInput, setUsernameInput] = useState('');
  const [userInfo, setUserInfo] = useState<UserInfoData | null>(null);
  const [isVerifyingUser, setIsVerifyingUser] = useState(false);
  const [userVerifyError, setUserVerifyError] = useState<string | null>(null);
  const [contactZalo, setContactZalo] = useState('');
  const [contactFacebook, setContactFacebook] = useState('');
  const [contactError, setContactError] = useState<string | null>(null);

  // Coupon state
  const [couponInput, setCouponInput] = useState('');
  const [appliedCoupon, setAppliedCoupon] = useState<CouponQuote | null>(null);
  const [isValidatingCoupon, setIsValidatingCoupon] = useState(false);
  const [couponError, setCouponError] = useState<string | null>(null);

  // Payment state
  const [paymentMethod, setPaymentMethod] = useState<'coin' | 'qr'>('coin');
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  // QR payment active order state
  const [qrOrder, setQrOrder] = useState<PaymentQrData | null>(null);
  const [isRenewingQr, setIsRenewingQr] = useState(false);
  const [renewQrError, setRenewQrError] = useState<string | null>(null);
  const qrAttemptRef = useRef<{ key: string; signature: string } | null>(null);
  const lastAutoQrSignatureRef = useRef<string | null>(null);
  const coinAttemptRef = useRef<{ key: string; signature: string } | null>(null);
  const notifiedPurchasesRef = useRef<Set<string>>(new Set());

  // Completed activation state
  const [activationOrderId, setActivationOrderId] = useState<number | null>(null);
  const [queueClientId, setQueueClientId] = useState<string | null>(null);
  const [queueStatus, setQueueStatus] = useState<string>('waiting');
  const [queuePosition, setQueuePosition] = useState<number>(0);
  const [queueError, setQueueError] = useState<string | null>(null);

  // Platform DNS config & download tickets
  const [platformConfig, setPlatformConfig] = useState<PublicDnsConfig | null>(null);
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [isCreatingTicket, setIsCreatingTicket] = useState(false);
  const [ticketError, setTicketError] = useState<string | null>(null);
  const fulfillmentMode = selectedPlan && selectedPlatform
    ? getFulfillmentMode(selectedPlan, selectedPlatform)
    : null;

  const stepAfterPlatform = (plan: PlanItem, platform: DevicePlatform): WizardStep => {
    const mode = getFulfillmentMode(plan, platform);
    if (mode === 'auto_activation') return 'username';
    if (mode === 'manual_contact') return 'contact';
    return 'payment';
  };

  // Load platform config once
  useEffect(() => {
    fetchPlatformConfig()
      .then((res) => {
        if (res && res.success) {
          setPlatformConfig(res.dns);
        }
      })
      .catch(() => {});
  }, []);

  // Copy helper with clean state feedback
  const handleCopy = (text: string, label: string) => {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(
      () => {
        setCopiedText(label);
        setTimeout(() => setCopiedText(null), 2500);
      },
      () => {}
    );
  };

  const maskZalo = (phone: string): string => {
    const digits = phone.replace(/\D/g, '');
    if (digits.length <= 6) return phone;
    return `${digits.slice(0, 3)}***${digits.slice(-4)}`;
  };

  interface StepDef {
    id: WizardStep;
    label: string;
  }

  const getActiveSteps = (): StepDef[] => {
    const list: StepDef[] = [{ id: 'plan', label: 'Gói dịch vụ' }];
    if (!selectedPlan || selectedPlan.supported_platforms === 'all') {
      list.push({ id: 'platform', label: 'Thiết bị' });
    }
    if (fulfillmentMode === 'auto_activation' || (!selectedPlan && !selectedPlatform)) {
      list.push({ id: 'username', label: 'Tài khoản' });
    } else if (fulfillmentMode === 'manual_contact') {
      list.push({ id: 'contact', label: 'Liên hệ' });
    }
    list.push({ id: 'payment', label: 'Thanh toán' });
    list.push({
      id: 'completed',
      label: fulfillmentMode === 'manual_contact' ? 'Gửi đơn' : fulfillmentMode === 'apk_download' ? 'Tải APK' : 'Kích hoạt',
    });
    return list;
  };

  const getPreviousStep = (): WizardStep => {
    const steps = getActiveSteps();
    const idx = steps.findIndex((s) => s.id === currentStep);
    if (idx > 0) return steps[idx - 1].id;
    return 'plan';
  };

  const currentStepNumber = getActiveSteps().findIndex((s) => s.id === currentStep) + 1;

  // Step 1: Select plan
  const handleSelectPlan = (plan: PlanItem) => {
    setSelectedPlan(plan);
    setCouponInput('');
    setAppliedCoupon(null);
    setCouponError(null);
    setUsernameInput('');
    setUserInfo(null);
    setUserVerifyError(null);
    setContactZalo('');
    setContactFacebook('');
    setContactError(null);
    setQrOrder(null);
    qrAttemptRef.current = null;
    lastAutoQrSignatureRef.current = null;
    coinAttemptRef.current = null;
    setPaymentError(null);

    // If plan only supports a specific platform, auto-select or validate
    if (plan.supported_platforms === 'ios') {
      setSelectedPlatform('ios');
      setCurrentStep(stepAfterPlatform(plan, 'ios'));
    } else if (plan.supported_platforms === 'android') {
      setSelectedPlatform('android');
      setCurrentStep(stepAfterPlatform(plan, 'android'));
    } else {
      setSelectedPlatform(null);
      setCurrentStep('platform');
    }
  };

  // Step 2: Select platform
  const handleSelectPlatform = (platform: DevicePlatform) => {
    if (selectedPlan) {
      if (selectedPlan.supported_platforms !== 'all' && selectedPlan.supported_platforms !== platform) {
        return;
      }
    }
    setSelectedPlatform(platform);
    setUsernameInput('');
    setUserInfo(null);
    setUserVerifyError(null);
    setContactZalo('');
    setContactFacebook('');
    setContactError(null);
    setQrOrder(null);
    qrAttemptRef.current = null;
    coinAttemptRef.current = null;
    setPaymentError(null);
    if (selectedPlan) setCurrentStep(stepAfterPlatform(selectedPlan, platform));
  };

  // Step 3: Verify username
  const handleVerifyUsername = async () => {
    const raw = usernameInput.trim();
    if (!raw) {
      setUserVerifyError('Vui lòng nhập Username hoặc link lời mời Locket.');
      return;
    }
    setIsVerifyingUser(true);
    setUserVerifyError(null);

    try {
      const res = await fetchUserInfo(raw);
      if (res && res.success && res.data) {
        setUserInfo(res.data);
      } else {
        setUserVerifyError(res.msg || 'Không tìm thấy tài khoản Locket. Vui lòng kiểm tra lại.');
        setUserInfo(null);
      }
    } catch (err: any) {
      setUserVerifyError(err.message || 'Lỗi kết nối khi xác thực tài khoản.');
      setUserInfo(null);
    } finally {
      setIsVerifyingUser(false);
    }
  };

  const handleContinueContact = () => {
    const zaloDigits = contactZalo.replace(/[\s.()\-]/g, '');
    let facebookValid = false;
    try {
      const parsed = new URL(contactFacebook.trim());
      facebookValid = parsed.protocol === 'https:' && ['facebook.com', 'www.facebook.com', 'm.facebook.com'].includes(parsed.hostname.toLowerCase()) && parsed.pathname !== '/';
    } catch {}
    if (!/^\+?\d{9,15}$/.test(zaloDigits)) {
      setContactError('Số điện thoại Zalo phải có từ 9 đến 15 chữ số.');
      return;
    }
    if (!facebookValid) {
      setContactError('Vui lòng nhập link Facebook đầy đủ, bắt đầu bằng https://facebook.com/...');
      return;
    }
    setContactError(null);
    setCurrentStep('payment');
  };

  // Coupon handlers
  const closeActiveQrOrder = async (): Promise<boolean> => {
    if (!qrOrder) return true;
    try {
      await cancelPayment(qrOrder.payment_ref || qrOrder.payment_code);
      setQrOrder(null);
      qrAttemptRef.current = null;
      lastAutoQrSignatureRef.current = null;
      return true;
    } catch (err: any) {
      setPaymentError(err.message || 'Không thể đóng mã QR hiện tại. Vui lòng kiểm tra trạng thái thanh toán.');
      return false;
    }
  };

  const handleApplyCoupon = async () => {
    if (!selectedPlan) return;
    const cleanCode = couponInput.trim().toUpperCase();
    if (!cleanCode) {
      setCouponError('Vui lòng nhập mã giảm giá.');
      return;
    }

    try {
      setIsValidatingCoupon(true);
      setCouponError(null);
      const res = await validateCoupon(cleanCode, selectedPlan.id);
      if (res.success && res.valid) {
        if (!(await closeActiveQrOrder())) {
          setCouponError('Không thể đổi giá khi mã QR hiện tại chưa được đóng.');
          return;
        }
        setAppliedCoupon({
          code: res.code || cleanCode,
          normalized_code: res.normalized_code || cleanCode,
          coupon_name: res.coupon_name,
          discount_type: res.discount_type || 'percent',
          discount_value: res.discount_value || 0,
          original_vnd: res.original_vnd ?? selectedPlan.price_vnd,
          original_coin: res.original_coin ?? selectedPlan.price_coin,
          discount_vnd: res.discount_vnd ?? 0,
          discount_coin: res.discount_coin ?? 0,
          final_vnd: res.final_vnd ?? selectedPlan.price_vnd,
          final_coin: res.final_coin ?? selectedPlan.price_coin,
          message: res.message,
        });
        // Clear existing QR order so a new one is created with discounted price
        if (qrOrder) {
          setQrOrder(null);
          qrAttemptRef.current = null;
        }
      } else {
        setAppliedCoupon(null);
        setCouponError(res.message || 'Mã giảm giá không hợp lệ hoặc không đủ điều kiện.');
      }
    } catch (err: any) {
      setAppliedCoupon(null);
      setCouponError(err.message || 'Không thể xác thực mã giảm giá lúc này.');
    } finally {
      setIsValidatingCoupon(false);
    }
  };

  const handleRemoveCoupon = async () => {
    if (!(await closeActiveQrOrder())) {
      setCouponError('Không thể bỏ mã khi QR hiện tại chưa được đóng.');
      return;
    }
    setAppliedCoupon(null);
    setCouponInput('');
    setCouponError(null);
    if (qrOrder) {
      setQrOrder(null);
      qrAttemptRef.current = null;
    }
  };

  // Step 4: Pay with Coin
  const handlePayWithCoin = async () => {
    if (!selectedPlan || !selectedPlatform || !fulfillmentMode) return;
    setIsProcessingPayment(true);
    setPaymentError(null);

    try {
      const couponCode = appliedCoupon?.code;
      const signature = `${selectedPlan.id}:${selectedPlatform}:${fulfillmentMode}:${usernameInput.trim()}:${contactZalo.trim()}:${contactFacebook.trim()}:${couponCode || ''}`;
      const previousAttempt = coinAttemptRef.current;
      const idempotencyKey =
        previousAttempt?.signature === signature
          ? previousAttempt.key
          : crypto.randomUUID();
      coinAttemptRef.current = { key: idempotencyKey, signature };
      const res = await purchasePlanWithCoin({
        plan_id: selectedPlan.id,
        platform: selectedPlatform,
        username: usernameInput.trim(),
        contact_zalo: contactZalo.trim(),
        contact_facebook: contactFacebook.trim(),
        idempotency_key: idempotencyKey,
        coupon_code: couponCode,
      });

      if (res && res.success) {
        const toastKey = `coin-order-${res.activation_order_id}`;
        if (!notifiedPurchasesRef.current.has(toastKey)) {
          notifiedPurchasesRef.current.add(toastKey);
          toast.success(
            'Mua gói thành công',
            `Cảm ơn bạn đã chọn ${selectedPlan.name}. Đơn hàng đã được tiếp nhận và đang chuyển sang bước xử lý.`,
            { duration: 6_000, dedupeKey: toastKey }
          );
        }
        setActivationOrderId(res.activation_order_id);
        setQueueClientId(res.client_id || null);
        setQueueStatus(res.status === 'queued' ? 'waiting' : res.status);
        setCurrentStep('completed');
        onRefreshWallet();
        if (onOrderCreated) onOrderCreated(res.activation_order_id);
      } else {
        setPaymentError(res.msg || 'Thanh toán bằng Coin thất bại.');
      }
    } catch (err: any) {
      setPaymentError(err.message || 'Lỗi hệ thống khi thanh toán bằng Coin.');
    } finally {
      setIsProcessingPayment(false);
    }
  };

  // Step 4: Pay with VietQR
  const handleCreateQrPayment = async () => {
    if (!selectedPlan || !selectedPlatform || !fulfillmentMode) return;
    setIsProcessingPayment(true);
    setPaymentError(null);

    try {
      const couponCode = appliedCoupon?.code;
      const signature = `${selectedPlan.id}:${selectedPlatform}:${fulfillmentMode}:${usernameInput.trim()}:${contactZalo.trim()}:${contactFacebook.trim()}:${couponCode || ''}`;
      const previousAttempt = qrAttemptRef.current;
      const idempotencyKey =
        previousAttempt?.signature === signature
          ? previousAttempt.key
          : crypto.randomUUID();
      qrAttemptRef.current = { key: idempotencyKey, signature };
      const res = await createPlanPayment({
        plan_id: selectedPlan.id,
        platform: selectedPlatform,
        username: usernameInput.trim(),
        contact_zalo: contactZalo.trim(),
        contact_facebook: contactFacebook.trim(),
        idempotency_key: idempotencyKey,
        coupon_code: couponCode,
      });

      if (res && res.success) {
        setActivationOrderId(res.activation_order_id);
        setQrOrder({
          payment_id: res.payment_id,
          payment_code: res.payment_code,
          payment_ref: res.payment_ref,
          transfer_code: res.transfer_code,
          amount_vnd: res.amount_vnd,
          coin_amount: res.coin_amount,
          qr_url: res.qr_url,
          expires_at: res.expires_at,
          server_time: res.server_time,
          status: res.status || 'pending',
          bank_config: res.bank_config,
          purpose: 'plan_purchase',
          plan_name: selectedPlan.name,
          locket_username: usernameInput.trim(),
          platform: selectedPlatform,
        });
      } else {
        setPaymentError(res.msg || 'Không thể tạo mã thanh toán VietQR.');
      }
    } catch (err: any) {
      setPaymentError(err.message || 'Lỗi khi khởi tạo đơn thanh toán VietQR.');
    } finally {
      setIsProcessingPayment(false);
    }
  };

  // Auto create QR order when entering payment step if user chooses QR
  useEffect(() => {
    if (currentStep === 'payment' && paymentMethod === 'qr' && !qrOrder && !isProcessingPayment) {
      const signature = `${selectedPlan?.id || ''}:${selectedPlatform || ''}:${fulfillmentMode || ''}:${usernameInput.trim()}:${contactZalo.trim()}:${contactFacebook.trim()}:${appliedCoupon?.code || ''}`;
      if (lastAutoQrSignatureRef.current !== signature) {
        lastAutoQrSignatureRef.current = signature;
        void handleCreateQrPayment();
      }
    }
  }, [currentStep, paymentMethod, appliedCoupon, qrOrder, isProcessingPayment]);

  const handleRenewQrOrder = async () => {
    if (!qrOrder) return;
    setIsRenewingQr(true);
    setRenewQrError(null);
    try {
      const res = await renewPayment(qrOrder.payment_ref || qrOrder.payment_code);
      if (res && res.success && res.payment) {
        setQrOrder({
          payment_id: res.payment.id,
          payment_code: res.payment.payment_code,
          payment_ref: res.payment.payment_ref,
          transfer_code: res.payment.transfer_code,
          amount_vnd: res.payment.amount_vnd,
          coin_amount: res.payment.coin_amount,
          qr_url: res.payment.qr_url || '',
          expires_at: res.payment.expires_at,
          server_time: res.payment.server_time,
          status: res.payment.status,
          bank_config: res.payment.bank_config,
          purpose: 'plan_purchase',
          plan_name: selectedPlan?.name,
          locket_username: usernameInput.trim(),
          platform: selectedPlatform || undefined,
        });
      } else {
        setRenewQrError(res.msg || 'Không thể gia hạn mã thanh toán.');
      }
    } catch (err: any) {
      setRenewQrError(err.message || 'Lỗi khi gia hạn mã thanh toán.');
    } finally {
      setIsRenewingQr(false);
    }
  };

  // Poll QR payment status
  usePaymentPolling({
    paymentCode: qrOrder?.payment_code || null,
    enabled: currentStep === 'payment' && !!qrOrder,
    onStatusChange: (newStatus, _payment, activationOrder) => {
      setQrOrder((prev) =>
        prev
          ? {
              ...prev,
              status: newStatus,
            }
          : null
      );
      if (newStatus === 'paid') {
        const paidOrderId = activationOrder?.id || activationOrderId;
        const toastKey = `qr-payment-${_payment.id}`;
        if (!notifiedPurchasesRef.current.has(toastKey)) {
          notifiedPurchasesRef.current.add(toastKey);
          toast.success(
            'Thanh toán thành công',
            `Cảm ơn bạn đã mua ${selectedPlan?.name || 'gói Locket Gold'}. Hệ thống đã nhận tiền và đang xử lý đơn hàng.`,
            { duration: 6_000, dedupeKey: toastKey }
          );
        }
        if (activationOrder) {
          setActivationOrderId(activationOrder.id);
          setQueueClientId(activationOrder.queue_client_id || null);
          setQueueStatus(activationOrder.status);
        }
        setCurrentStep('completed');
        onRefreshWallet();
        if (paidOrderId && onOrderCreated) onOrderCreated(paidOrderId);
      } else if (newStatus === 'expired' || newStatus === 'cancelled') {
        setPaymentError('Mã thanh toán đã hết hạn hoặc bị hủy. Vui lòng tạo mã mới để tiếp tục.');
      }
    },
  });

  // Polling Queue status when completed/processing for auto_activation
  useEffect(() => {
    if (currentStep !== 'completed' || fulfillmentMode !== 'auto_activation' || !queueClientId || queueStatus === 'completed') return;

    let timerId: any = null;
    const pollQueue = async () => {
      try {
        const res = await fetchQueueStatus(queueClientId);
        if (res && res.success) {
          setQueueStatus(res.status);
          setQueuePosition(res.position);
          if (res.error) setQueueError(res.error);
        }
      } catch {}

      if (queueStatus !== 'completed' && queueStatus !== 'error') {
        timerId = setTimeout(pollQueue, 3000);
      }
    };

    timerId = setTimeout(pollQueue, 2500);
    return () => clearTimeout(timerId);
  }, [currentStep, fulfillmentMode, queueClientId, queueStatus]);

  // Request download ticket on completion
  const handleRequestDownloadTicket = async () => {
    if (!activationOrderId && !queueClientId) return;
    setIsCreatingTicket(true);
    setTicketError(null);

    try {
      const param = { activationOrderId: activationOrderId || undefined, clientId: queueClientId || undefined };
      let res;
      if (selectedPlatform === 'ios') {
        res = await createMobileconfigDownloadTicket(param);
      } else {
        res = await createApkDownloadTicket(param);
      }

      if (res && res.success && res.download_url) {
        window.location.href = res.download_url;
      } else {
        setTicketError(res.msg || 'Không thể tạo vé tải xuống.');
      }
    } catch (err: any) {
      setTicketError(err.message || 'Lỗi khi yêu cầu vé tải.');
    } finally {
      setIsCreatingTicket(false);
    }
  };

  const handleReset = () => {
    setCurrentStep('plan');
    setSelectedPlan(null);
    setSelectedPlatform(null);
    setUsernameInput('');
    setUserInfo(null);
    setUserVerifyError(null);
    setContactZalo('');
    setContactFacebook('');
    setContactError(null);
    setQrOrder(null);
    qrAttemptRef.current = null;
    coinAttemptRef.current = null;
    setPaymentError(null);
    setActivationOrderId(null);
    setQueueClientId(null);
    setQueueStatus('waiting');
  };

  return (
    <div className="space-y-5">
      {/* Stepper Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-4 overflow-x-auto">
        <div className="flex items-center gap-2 sm:gap-4 min-w-max text-xs sm:text-sm font-semibold">
          {getActiveSteps().map((stepItem, index, arr) => {
            const isCurrent = currentStep === stepItem.id;
            const currentIdx = arr.findIndex((s) => s.id === currentStep);
            const isPassed = currentIdx > index;

            return (
              <React.Fragment key={stepItem.id}>
                <div
                  className={`flex items-center gap-1.5 ${
                    isCurrent
                      ? 'text-amber-600 dark:text-amber-400 font-bold'
                      : isPassed
                      ? 'text-zinc-800 dark:text-zinc-200'
                      : 'text-zinc-400'
                  }`}
                >
                  <span
                    className={`flex h-5 w-5 items-center justify-center rounded-full border text-[10px] ${
                      isCurrent
                        ? 'border-amber-500 bg-amber-500 text-zinc-950 font-bold'
                        : isPassed
                        ? 'border-zinc-700 bg-zinc-800 text-zinc-200'
                        : 'border-current'
                    }`}
                  >
                    {isPassed ? <Check className="h-3 w-3" /> : index + 1}
                  </span>
                  <span>{stepItem.label}</span>
                </div>
                {index < arr.length - 1 && (
                  <span className="text-zinc-300 dark:text-zinc-700">/</span>
                )}
              </React.Fragment>
            );
          })}
        </div>

        {currentStep !== 'plan' && currentStep !== 'completed' && (
          <button
            type="button"
            onClick={handleReset}
            className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition-colors shrink-0 ml-4"
          >
            Làm lại từ đầu
          </button>
        )}
      </div>

      {/* Step 1: Chọn gói */}
      {currentStep === 'plan' && (
        <div className="space-y-4">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-white">
              Bước {currentStepNumber}: Lựa chọn gói Locket Gold
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Chọn thời hạn và quyền lợi phù hợp với nhu cầu của bạn.
            </p>
          </div>
          <PlanCatalog
            plans={plans}
            isLoading={isLoadingPlans}
            selectedPlanId={selectedPlan?.id}
            onSelectPlan={handleSelectPlan}
          />
        </div>
      )}

      {/* Step 2: Chọn thiết bị */}
      {currentStep === 'platform' && selectedPlan && (
        <div className="space-y-5 max-w-3xl">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-white">
              Bước {currentStepNumber}: Chọn thiết bị kích hoạt
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Gói đã chọn: <span className="font-semibold text-zinc-800 dark:text-zinc-200">{selectedPlan.name}</span>. Vui lòng chọn hệ điều hành bạn đang sử dụng.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* iOS Option */}
            <button
              type="button"
              disabled={selectedPlan.supported_platforms === 'android'}
              onClick={() => handleSelectPlatform('ios')}
              className={`flex min-h-40 flex-col items-center justify-center rounded-3xl border p-5 text-center transition-all ${
                selectedPlatform === 'ios'
                  ? 'border-amber-500 bg-amber-500/10 shadow-md ring-2 ring-amber-500/20'
                  : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 hover:border-amber-500/40'
              } ${
                selectedPlan.supported_platforms === 'android'
                  ? 'opacity-40 cursor-not-allowed'
                  : ''
              }`}
            >
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-500/10 text-sky-600 dark:text-sky-400 mb-3">
                <Apple className="h-7 w-7" />
              </div>
              <span className="text-sm font-bold text-zinc-900 dark:text-white">iPhone / iPad</span>
              <span className="mt-1 text-[11px] text-zinc-500">Hệ điều hành iOS</span>
              {selectedPlan.supported_platforms === 'android' && (
                <span className="mt-2 text-[10px] text-rose-500">Gói này không hỗ trợ iOS</span>
              )}
            </button>

            {/* Android Option */}
            <button
              type="button"
              disabled={selectedPlan.supported_platforms === 'ios'}
              onClick={() => handleSelectPlatform('android')}
              className={`flex min-h-40 flex-col items-center justify-center rounded-3xl border p-5 text-center transition-all ${
                selectedPlatform === 'android'
                  ? 'border-amber-500 bg-amber-500/10 shadow-md ring-2 ring-amber-500/20'
                  : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 hover:border-amber-500/40'
              } ${
                selectedPlan.supported_platforms === 'ios'
                  ? 'opacity-40 cursor-not-allowed'
                  : ''
              }`}
            >
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 mb-3">
                <Smartphone className="h-7 w-7" />
              </div>
              <span className="text-sm font-bold text-zinc-900 dark:text-white">Điện thoại Android</span>
              <span className="mt-1 text-[11px] text-zinc-500">Samsung, Xiaomi, Oppo...</span>
              {selectedPlan.supported_platforms === 'ios' && (
                <span className="mt-2 text-[10px] text-rose-500">Gói này không hỗ trợ Android</span>
              )}
            </button>
          </div>

          <div className="flex items-center justify-between pt-4">
            <button
              type="button"
              onClick={() => setCurrentStep(getPreviousStep())}
              className="flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Quay lại</span>
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Nhập Username (cho auto_activation) */}
      {currentStep === 'username' && selectedPlan && selectedPlatform && (
        <div className="space-y-5 max-w-3xl">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-white">
              Bước {currentStepNumber}: Nhập tài khoản Locket
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Nhập username Locket chính xác hoặc liên kết lời mời bạn bè để hệ thống kiểm tra và kích hoạt.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={usernameInput}
                onChange={(e) => {
                  setUsernameInput(e.target.value);
                  setUserVerifyError(null);
                }}
                placeholder="VD: huydev hoặc locket.cam/huydev"
                disabled={isVerifyingUser}
                className="flex-1 rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-3 text-xs sm:text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              />
              <button
                type="button"
                disabled={isVerifyingUser || !usernameInput.trim()}
                onClick={handleVerifyUsername}
                className="gold-secondary rounded-2xl border px-4 py-3 text-xs font-bold flex items-center gap-1.5 transition-all disabled:opacity-50"
              >
                {isVerifyingUser ? (
                  <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
                <span>Kiểm tra</span>
              </button>
            </div>

            {userVerifyError && (
              <p className="flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{userVerifyError}</span>
              </p>
            )}

            {/* Verified User Preview Card */}
            {userInfo && (
              <div className="flex items-center gap-3.5 rounded-2xl border border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-950/20 p-4">
                {userInfo.profile_picture_url ? (
                  <img
                    src={userInfo.profile_picture_url}
                    alt={userInfo.username}
                    className="h-11 w-11 rounded-full object-cover border border-emerald-500/40"
                  />
                ) : (
                  <div className="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 font-bold text-sm">
                    {userInfo.username.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs sm:text-sm font-bold text-zinc-900 dark:text-white truncate">
                      {userInfo.first_name} {userInfo.last_name}
                    </span>
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                  </div>
                  <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                    @{userInfo.username} · UID: {userInfo.uid ? `${userInfo.uid.slice(0, 10)}...` : 'Hợp lệ'}
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-zinc-100 dark:border-zinc-800">
            <button
              type="button"
              onClick={() => setCurrentStep(getPreviousStep())}
              className="flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Quay lại</span>
            </button>

            <button
              type="button"
              disabled={!usernameInput.trim() || isVerifyingUser}
              onClick={() => setCurrentStep('payment')}
              className="gold-primary rounded-2xl px-6 py-3 text-xs sm:text-sm font-bold flex items-center gap-2 transition-all disabled:opacity-50"
            >
              <span>Tiếp tục thanh toán</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Thông tin liên hệ cho gói Admin xử lý (manual_contact) */}
      {currentStep === 'contact' && selectedPlan && selectedPlatform && (
        <div className="space-y-5 max-w-3xl">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-white">
              Bước {currentStepNumber}: Thông tin để Admin liên hệ
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Gói dịch vụ này được Admin xử lý và bàn giao trực tiếp. Vui lòng cung cấp số điện thoại Zalo và liên kết Facebook của bạn.
            </p>
          </div>

          <div className="space-y-4 rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-5">
            <div>
              <label className="mb-1.5 block text-xs font-bold text-zinc-700 dark:text-zinc-300">Số điện thoại Zalo *</label>
              <input
                type="tel"
                value={contactZalo}
                onChange={(e) => { setContactZalo(e.target.value); setContactError(null); }}
                placeholder="VD: 0912345678"
                autoComplete="tel"
                className="w-full rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-4 py-3 text-sm text-zinc-900 dark:text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold text-zinc-700 dark:text-zinc-300">Link Facebook liên hệ *</label>
              <input
                type="url"
                value={contactFacebook}
                onChange={(e) => { setContactFacebook(e.target.value); setContactError(null); }}
                placeholder="https://facebook.com/ten.tai.khoan"
                autoComplete="url"
                className="w-full rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-4 py-3 text-sm text-zinc-900 dark:text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            {contactError && (
              <p className="flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {contactError}
              </p>
            )}
            <p className="text-[11px] leading-relaxed text-zinc-500">
              Chúng tôi cam kết bảo mật thông tin liên hệ và chỉ sử dụng cho mục đích kích hoạt đơn hàng này.
            </p>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-zinc-100 dark:border-zinc-800">
            <button type="button" onClick={() => setCurrentStep(getPreviousStep())} className="flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200">
              <ArrowLeft className="h-4 w-4" /> Quay lại
            </button>
            <button type="button" onClick={handleContinueContact} disabled={!contactZalo.trim() || !contactFacebook.trim()} className="gold-primary rounded-2xl px-6 py-3 text-xs sm:text-sm font-bold flex items-center gap-2 disabled:opacity-50">
              Tiếp tục thanh toán <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Thanh toán */}
      {currentStep === 'payment' && selectedPlan && selectedPlatform && (() => {
        const effectivePriceVnd = appliedCoupon ? appliedCoupon.final_vnd : selectedPlan.price_vnd;
        const effectivePriceCoin = appliedCoupon ? appliedCoupon.final_coin : selectedPlan.price_coin;
        const discountAmountVnd = appliedCoupon ? appliedCoupon.discount_vnd : 0;
        const discountAmountCoin = appliedCoupon ? appliedCoupon.discount_coin : 0;

        return (
        <div className="space-y-5 max-w-3xl">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-white">
              Bước {currentStepNumber}: Chọn phương thức thanh toán
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Đơn hàng: <span className="font-semibold text-zinc-800 dark:text-zinc-200">{selectedPlan.name}</span>
            </p>
          </div>

          {/* Coupon Code Section */}
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-zinc-800 dark:text-zinc-200 flex items-center gap-1.5">
                <Ticket className="h-4 w-4 text-amber-500" />
                <span>Mã giảm giá (Coupon)</span>
              </label>
              {appliedCoupon && (
                <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                  <Check className="h-3 w-3" />
                  Đã áp dụng mã
                </span>
              )}
            </div>

            {!appliedCoupon ? (
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-400" />
                  <input
                    type="text"
                    value={couponInput}
                    onChange={(e) => {
                      setCouponInput(e.target.value.toUpperCase());
                      setCouponError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleApplyCoupon();
                      }
                    }}
                    placeholder="Nhập mã ưu đãi (VD: GOLDVIP)"
                    disabled={isValidatingCoupon}
                    className="w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 pl-9 pr-3 py-2 text-xs font-mono font-bold uppercase text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-amber-500"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleApplyCoupon}
                  disabled={isValidatingCoupon || !couponInput.trim()}
                  className="gold-secondary rounded-xl px-4 py-2 text-xs font-bold flex items-center gap-1.5 transition-all disabled:opacity-50"
                >
                  {isValidatingCoupon ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500" />
                  ) : (
                    <span>Áp dụng</span>
                  )}
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/10 p-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-500 text-zinc-950 font-bold">
                    <Ticket className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-amber-500 text-xs">
                        {appliedCoupon.code}
                      </span>
                      {appliedCoupon.coupon_name && (
                        <span className="text-[11px] text-zinc-400 truncate">
                          ({appliedCoupon.coupon_name})
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold mt-0.5">
                      Giảm {new Intl.NumberFormat('vi-VN').format(appliedCoupon.discount_vnd)} đ (-{new Intl.NumberFormat('vi-VN').format(appliedCoupon.discount_coin)} Coin)
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleRemoveCoupon}
                  className="rounded-lg px-2.5 py-1 text-xs font-medium text-zinc-500 hover:text-rose-500 hover:bg-rose-500/10 transition"
                >
                  Hủy áp dụng
                </button>
              </div>
            )}

            {couponError && (
              <p className="flex items-center gap-1 text-[11px] text-rose-500">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{couponError}</span>
              </p>
            )}

            {appliedCoupon?.message && (
              <p className="text-[11px] text-zinc-400 italic">
                {appliedCoupon.message}
              </p>
            )}
          </div>

          {/* Payment Method Selector */}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={async () => {
                if (paymentMethod === 'qr' && !(await closeActiveQrOrder())) return;
                setPaymentMethod('coin');
                setPaymentError(null);
              }}
              className={`flex items-center gap-3 rounded-2xl border p-4 transition-all ${
                paymentMethod === 'coin'
                  ? 'border-amber-500 bg-amber-500/10 shadow-sm ring-1 ring-amber-500/30'
                  : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 hover:border-zinc-300'
              }`}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/20 text-amber-600 dark:text-amber-400">
                <Coins className="h-5 w-5" />
              </div>
              <div className="text-left">
                <div className="text-xs sm:text-sm font-bold text-zinc-900 dark:text-white">Ví xu Locket</div>
                <div className="text-[11px] text-zinc-500">
                  Số dư: <span className="font-semibold text-amber-600 dark:text-amber-400">{new Intl.NumberFormat('vi-VN').format(userCoinBalance)} Coin</span>
                </div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => {
                setPaymentMethod('qr');
                setPaymentError(null);
              }}
              className={`flex items-center gap-3 rounded-2xl border p-4 transition-all ${
                paymentMethod === 'qr'
                  ? 'border-amber-500 bg-amber-500/10 shadow-sm ring-1 ring-amber-500/30'
                  : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 hover:border-zinc-300'
              }`}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400">
                <QrCode className="h-5 w-5" />
              </div>
              <div className="text-left">
                <div className="text-xs sm:text-sm font-bold text-zinc-900 dark:text-white">VietQR Tự động</div>
                <div className="text-[11px] text-zinc-500">Ngân hàng, MoMo</div>
              </div>
            </button>
          </div>

          {/* Error Notice */}
          {paymentError && (
            <div className="flex items-center gap-2 rounded-2xl border border-rose-500/30 bg-rose-50 dark:bg-rose-950/30 p-3.5 text-xs text-rose-600 dark:text-rose-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{paymentError}</span>
            </div>
          )}

          {/* Coin Payment View */}
          {paymentMethod === 'coin' && (
            <div className="rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <span className="text-xs text-zinc-500">Giá gốc:</span>
                <span className={`text-sm font-semibold text-zinc-900 dark:text-white ${appliedCoupon ? 'line-through text-zinc-400' : ''}`}>
                  {new Intl.NumberFormat('vi-VN').format(selectedPlan.price_coin)} Coin
                </span>
              </div>
              {appliedCoupon && (
                <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                  <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Giảm giá ({appliedCoupon.code}):</span>
                  <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                    -{new Intl.NumberFormat('vi-VN').format(discountAmountCoin)} Coin
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <span className="text-xs font-bold text-zinc-700 dark:text-zinc-300">Cần thanh toán:</span>
                <span className="text-base font-black text-amber-500">
                  {new Intl.NumberFormat('vi-VN').format(effectivePriceCoin)} Coin
                </span>
              </div>
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <span className="text-xs text-zinc-500">Số dư hiện tại:</span>
                <span className="text-sm font-bold text-amber-600 dark:text-amber-400">
                  {new Intl.NumberFormat('vi-VN').format(userCoinBalance)} Coin
                </span>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-zinc-500">Số dư sau thanh toán:</span>
                <span
                  className={`text-sm font-bold ${
                    userCoinBalance >= effectivePriceCoin
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-rose-500'
                  }`}
                >
                  {userCoinBalance >= effectivePriceCoin
                    ? `${new Intl.NumberFormat('vi-VN').format(userCoinBalance - effectivePriceCoin)} Coin`
                    : `Thiếu ${new Intl.NumberFormat('vi-VN').format(effectivePriceCoin - userCoinBalance)} Coin`}
                </span>
              </div>

              {userCoinBalance < effectivePriceCoin ? (
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => onGoToTopup(effectivePriceCoin - userCoinBalance)}
                    className="gold-primary w-full rounded-2xl py-3 text-xs sm:text-sm font-bold flex items-center justify-center gap-2"
                  >
                    <span>Nạp thêm {new Intl.NumberFormat('vi-VN').format(effectivePriceCoin - userCoinBalance)} Coin</span>
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="pt-2">
                  <button
                    type="button"
                    disabled={isProcessingPayment}
                    onClick={handlePayWithCoin}
                    className="gold-primary w-full rounded-2xl py-3 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all active:scale-[0.99] disabled:opacity-50"
                  >
                    {isProcessingPayment ? (
                      <Loader2 className="h-4 w-4 animate-spin text-zinc-950" />
                    ) : (
                      <Coins className="h-4 w-4" />
                    )}
                    <span>Xác nhận thanh toán ngay ({new Intl.NumberFormat('vi-VN').format(effectivePriceCoin)} Coin)</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* QR Payment View */}
          {paymentMethod === 'qr' && (
            <div className="rounded-3xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <span className="text-xs text-zinc-500">Giá gói:</span>
                <span className={`text-sm font-semibold text-zinc-900 dark:text-white ${appliedCoupon ? 'line-through text-zinc-400' : ''}`}>
                  {new Intl.NumberFormat('vi-VN').format(selectedPlan.price_vnd)} đ
                </span>
              </div>
              {appliedCoupon && (
                <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                  <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Giảm giá ({appliedCoupon.code}):</span>
                  <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                    -{new Intl.NumberFormat('vi-VN').format(discountAmountVnd)} đ
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <span className="text-xs font-bold text-zinc-700 dark:text-zinc-300">Cần thanh toán:</span>
                <span className="text-base font-black text-amber-500">
                  {new Intl.NumberFormat('vi-VN').format(effectivePriceVnd)} đ
                </span>
              </div>

              {isProcessingPayment && !qrOrder ? (
                <div className="flex flex-col items-center justify-center py-10 space-y-2">
                  <Loader2 className="h-7 w-7 animate-spin text-amber-500" />
                  <span className="text-xs text-zinc-500">Đang tạo mã thanh toán VietQR...</span>
                </div>
              ) : qrOrder ? (
                <PaymentQrPanel
                  payment={qrOrder}
                  isRenewing={isRenewingQr}
                  renewError={renewQrError}
                  onRenew={handleRenewQrOrder}
                />
              ) : (
                <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                  <p className="text-xs text-zinc-500">Chưa tạo được mã thanh toán.</p>
                  <button
                    type="button"
                    onClick={() => void handleCreateQrPayment()}
                    className="gold-secondary rounded-xl px-4 py-2 text-xs font-bold"
                  >
                    Thử tạo lại QR
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between pt-4">
            <button
              type="button"
              onClick={async () => {
                if (!(await closeActiveQrOrder())) return;
                setCurrentStep(getPreviousStep());
              }}
              className="flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Quay lại</span>
            </button>
          </div>
        </div>
        );
      })()}

      {/* Step 5: Xác nhận & Hướng dẫn sau kích hoạt */}
      {currentStep === 'completed' && (
        <div className="space-y-5 max-w-3xl">
          {/* Status Header */}
          <div className="rounded-3xl border border-amber-500/30 bg-amber-500/[0.04] p-6 text-center space-y-3">
            {fulfillmentMode === 'manual_contact' || fulfillmentMode === 'apk_download' || queueStatus === 'completed' ? (
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500 text-white shadow-lg">
                <CheckCircle2 className="h-8 w-8" />
              </div>
            ) : queueStatus === 'error' ? (
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-500 text-white shadow-lg">
                <AlertCircle className="h-8 w-8" />
              </div>
            ) : (
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/20 text-amber-600 dark:text-amber-400 shadow-md">
                <Loader2 className="h-8 w-8 animate-spin" />
              </div>
            )}

            <div>
              <h3 className="text-lg sm:text-xl font-extrabold text-zinc-900 dark:text-white">
                {fulfillmentMode === 'manual_contact'
                  ? queueStatus === 'completed'
                    ? 'Admin đã hoàn thành đơn!'
                    : queueStatus === 'processing'
                    ? 'Admin đang xử lý đơn của bạn'
                    : 'Đã gửi đơn tới Admin!'
                  : fulfillmentMode === 'apk_download'
                  ? 'Thanh toán thành công — APK đã sẵn sàng!'
                  : queueStatus === 'completed'
                  ? 'Kích hoạt Locket Gold thành công!'
                  : queueStatus === 'error'
                  ? 'Kích hoạt không thành công'
                  : 'Đang xếp hàng kích hoạt tự động'}
              </h3>
              <p className="mt-1 text-xs sm:text-sm text-zinc-500 dark:text-zinc-400">
                {fulfillmentMode === 'auto_activation' && usernameInput.trim() && (
                  <>Tài khoản: <span className="font-bold text-zinc-800 dark:text-zinc-200">@{usernameInput.trim()}</span> · </>
                )}
                {fulfillmentMode === 'manual_contact' && contactZalo.trim() && (
                  <>Zalo: <span className="font-bold text-zinc-800 dark:text-zinc-200">{maskZalo(contactZalo)}</span> · </>
                )}
                Gói: <span className="font-semibold text-zinc-800 dark:text-zinc-200">{selectedPlan?.name}</span>
              </p>
            </div>

            {/* Queue position badge (auto_activation only) */}
            {fulfillmentMode === 'auto_activation' && queueStatus !== 'completed' && queueStatus !== 'error' && (
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-50 dark:bg-amber-950/40 px-4 py-1.5 text-xs text-amber-800 dark:text-amber-300">
                <span>Vị trí trong hàng đợi: <strong>#{queuePosition || 1}</strong></span>
              </div>
            )}

            {fulfillmentMode === 'auto_activation' && queueStatus === 'error' && (
              <div className="text-xs text-rose-600 dark:text-rose-400 p-2">
                {queueError || 'Lỗi trong quá trình kích hoạt. Vui lòng liên hệ Admin để được hỗ trợ.'}
              </div>
            )}
          </div>

          {/* Fulfillment-specific Guide */}
          {fulfillmentMode === 'manual_contact' ? (
            /* MANUAL CONTACT VIEW */
            <div className="rounded-3xl border border-amber-200 dark:border-amber-900/60 bg-white dark:bg-zinc-900/60 p-6 space-y-4">
              <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300">
                <CheckCircle2 className="h-5 w-5 shrink-0" />
                <h4 className="text-sm sm:text-base font-bold">Thông tin liên hệ đã được ghi nhận</h4>
              </div>
              <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">
                Đơn hàng của bạn đã được chuyển vào hàng đợi xử lý của Quản trị viên. Admin sẽ chủ động liên hệ qua số Zalo <strong>{maskZalo(contactZalo)}</strong> hoặc liên kết Facebook bạn đã đăng ký để hướng dẫn và kích hoạt tài khoản.
              </p>
              {contactFacebook && (
                <div>
                  <a
                    href={contactFacebook}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-sky-600 dark:text-sky-400 hover:underline"
                  >
                    <span>Kiểm tra liên kết Facebook đã gửi</span>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
              )}
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/50 p-3.5 text-[11px] text-zinc-500 dark:text-zinc-400">
                Bạn có thể đóng trang này bất cứ lúc nào. Tiến độ xử lý và trạng thái mới nhất luôn được cập nhật theo thời gian thực trong mục <strong>Đơn kích hoạt</strong>.
              </div>
            </div>
          ) : fulfillmentMode === 'apk_download' ? (
            /* APK DOWNLOAD VIEW - Strictly NO DNS Instructions */
            <div className="rounded-3xl border border-emerald-200 dark:border-emerald-900/60 bg-white dark:bg-zinc-900/60 p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                  <Smartphone className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  <h4 className="text-sm sm:text-base font-bold text-zinc-900 dark:text-white">
                    Tải ứng dụng Locket Gold APK
                  </h4>
                </div>
                <span className="rounded-full bg-emerald-100 dark:bg-emerald-950 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                  Android APK
                </span>
              </div>

              <div className="space-y-2 text-xs text-zinc-600 dark:text-zinc-300">
                <p className="font-semibold text-zinc-800 dark:text-zinc-200">
                  Hướng dẫn cài đặt ứng dụng Android:
                </p>
                <ol className="list-decimal pl-4 space-y-1.5 leading-relaxed">
                  <li>Nhấn nút <strong>"Tải ứng dụng Locket Gold APK"</strong> bên dưới để tải gói cài đặt an toàn.</li>
                  <li>Nếu thiết bị hiển thị cảnh báo tải file, chọn <strong>"Vẫn tải xuống"</strong>.</li>
                  <li>Mở tệp APK đã tải về và bật quyền <strong>"Cho phép cài đặt từ nguồn này" (Unknown Sources)</strong> nếu được yêu cầu.</li>
                  <li>Hoàn tất cài đặt, mở ứng dụng và đăng nhập tài khoản Locket của bạn để trải nghiệm ngay.</li>
                </ol>
              </div>

              {/* APK Download Button */}
              <div className="pt-2">
                <button
                  type="button"
                  disabled={isCreatingTicket}
                  onClick={handleRequestDownloadTicket}
                  className="gold-primary w-full rounded-2xl py-3.5 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50"
                >
                  {isCreatingTicket ? (
                    <Loader2 className="h-4 w-4 animate-spin text-zinc-950" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  <span>Tải ứng dụng Locket Gold APK</span>
                </button>
              </div>

              {ticketError && (
                <p className="text-xs text-rose-500">{ticketError}</p>
              )}

              {/* Android Security Notice */}
              <div className="rounded-2xl border border-amber-300/40 bg-amber-50/80 dark:bg-amber-950/30 p-3.5 space-y-1">
                <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800 dark:text-amber-300">
                  <ShieldAlert className="h-4 w-4 shrink-0" />
                  <span>Lưu ý quan trọng khi cài đặt APK</span>
                </div>
                <p className="text-[11px] leading-relaxed text-amber-700 dark:text-amber-400">
                  Gói APK hoạt động độc lập và <strong>không yêu cầu cấu hình DNS</strong>. Nếu thiết bị đã có phiên bản Locket từ Google Play Store, vui lòng gỡ cài đặt trước để tránh xung đột chữ ký ứng dụng.
                </p>
              </div>
            </div>
          ) : selectedPlatform === 'ios' ? (
            /* iOS ONLY GUIDE (auto_activation) */
            <div className="rounded-3xl border border-sky-200 dark:border-sky-900/60 bg-white dark:bg-zinc-900/60 p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                  <Apple className="h-5 w-5 text-sky-600 dark:text-sky-400" />
                  <h4 className="text-sm sm:text-base font-bold text-zinc-900 dark:text-white">
                    Cài đặt DNS NextDNS cho iPhone/iPad
                  </h4>
                </div>
                <span className="rounded-full bg-sky-100 dark:bg-sky-950 px-2.5 py-0.5 text-[10px] font-bold text-sky-700 dark:text-sky-300">
                  Thiết bị: iOS
                </span>
              </div>

              {/* Hostname Copy */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                  Hostname DNS riêng tư:
                </label>
                <div className="flex items-center gap-2 rounded-2xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-950 px-3.5 py-2.5">
                  <code className="text-xs font-mono font-bold text-sky-700 dark:text-sky-300 flex-1">
                    {platformConfig?.hostname || 'Chưa cấu hình DNS'}
                  </code>
                  {platformConfig?.hostname && (
                    <button
                      type="button"
                      onClick={() => handleCopy(platformConfig.hostname!, 'ios_dns')}
                      className="flex items-center gap-1 rounded-xl px-2.5 py-1 text-xs font-semibold bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300 hover:opacity-80 transition-opacity"
                    >
                      {copiedText === 'ios_dns' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                      <span>{copiedText === 'ios_dns' ? 'Đã sao chép' : 'Sao chép'}</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Steps Guide */}
              <div className="space-y-2 text-xs text-zinc-600 dark:text-zinc-300 pt-2">
                <p className="font-semibold text-zinc-800 dark:text-zinc-200">
                  Hướng dẫn cài đặt qua Safari:
                </p>
                <ol className="list-decimal pl-4 space-y-1.5 leading-relaxed">
                  <li>Nhấn nút <strong>"Cài đặt Profile DNS"</strong> bên dưới bằng trình duyệt <strong>Safari</strong> và chọn Cho phép.</li>
                  <li>Mở <strong>Cài đặt</strong> trên iPhone → Chọn mục <strong>"Đã tải về hồ sơ"</strong>.</li>
                  <li>Nhấn <strong>Cài đặt</strong> ở góc trên bên phải và xác nhận mã khóa máy.</li>
                  <li>Tắt hoàn toàn ứng dụng Locket (vuốt tắt từ đa nhiệm) rồi mở lại để trải nghiệm.</li>
                </ol>
              </div>

              {/* Download Ticket Button */}
              <div className="pt-3 flex flex-col sm:flex-row gap-3">
                <button
                  type="button"
                  disabled={isCreatingTicket || queueStatus !== 'completed'}
                  onClick={handleRequestDownloadTicket}
                  className="gold-primary flex-1 rounded-2xl py-3 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50"
                >
                  {isCreatingTicket ? (
                    <Loader2 className="h-4 w-4 animate-spin text-zinc-950" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  <span>{queueStatus === 'completed' ? 'Cài đặt Profile DNS NextDNS' : 'Chờ kích hoạt hoàn tất'}</span>
                </button>

                {platformConfig?.apple_url && (
                  <a
                    href={platformConfig.apple_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="gold-secondary rounded-2xl border px-4 py-3 text-xs font-semibold flex items-center justify-center gap-1.5 text-zinc-700 dark:text-zinc-300"
                  >
                    <span>Mở trang NextDNS Apple</span>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>

              {ticketError && (
                <p className="text-xs text-rose-500">{ticketError}</p>
              )}

              <p className="text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-3 rounded-xl border border-amber-300/40">
                ⚠️ Lưu ý: Giữ nguyên Profile DNS này trên thiết bị để duy trì tính năng chống thu hồi và trải nghiệm đầy đủ.
              </p>
            </div>
          ) : (
            /* ANDROID ONLY GUIDE (auto_activation) */
            <div className="rounded-3xl border border-emerald-200 dark:border-emerald-900/60 bg-white dark:bg-zinc-900/60 p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                  <Smartphone className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  <h4 className="text-sm sm:text-base font-bold text-zinc-900 dark:text-white">
                    Thiết lập DNS riêng tư cho Android
                  </h4>
                </div>
                <span className="rounded-full bg-emerald-100 dark:bg-emerald-950 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                  Thiết bị: Android
                </span>
              </div>

              {/* Hostname Copy */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                  Tên máy chủ Private DNS:
                </label>
                <div className="flex items-center gap-2 rounded-2xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-950 px-3.5 py-2.5">
                  <code className="text-xs font-mono font-bold text-emerald-700 dark:text-emerald-300 flex-1">
                    {platformConfig?.hostname || 'Chưa cấu hình DNS'}
                  </code>
                  {platformConfig?.hostname && (
                    <button
                      type="button"
                      onClick={() => handleCopy(platformConfig.hostname!, 'android_dns')}
                      className="flex items-center gap-1 rounded-xl px-2.5 py-1 text-xs font-semibold bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 hover:opacity-80 transition-opacity"
                    >
                      {copiedText === 'android_dns' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                      <span>{copiedText === 'android_dns' ? 'Đã sao chép' : 'Sao chép'}</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Steps Guide */}
              <div className="space-y-2 text-xs text-zinc-600 dark:text-zinc-300 pt-2">
                <p className="font-semibold text-zinc-800 dark:text-zinc-200">
                  Hướng dẫn cấu hình DNS riêng tư trên Android:
                </p>
                <ol className="list-decimal pl-4 space-y-1.5 leading-relaxed">
                  <li>Mở <strong>Cài đặt</strong> trên máy Android → Chọn <strong>Kết nối / Mạng & Internet</strong>.</li>
                  <li>Chọn mục <strong>DNS riêng tư (Private DNS)</strong>.</li>
                  <li>Chọn <strong>"Tên máy chủ nhà cung cấp DNS riêng tư"</strong> và dán Hostname phía trên vào.</li>
                  <li>Nhấn <strong>Lưu</strong>, sau đó khởi động lại ứng dụng Locket để hoàn tất.</li>
                </ol>
              </div>

              <p className="text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-3 rounded-xl border border-amber-300/40">
                ⚠️ Lưu ý: Luôn duy trì cài đặt Private DNS này để đảm bảo trạng thái Gold của tài khoản không bị gián đoạn.
              </p>
            </div>
          )}

          {/* Bottom actions */}
          <div className="pt-2 text-center">
            <button
              type="button"
              onClick={handleReset}
              className="gold-secondary rounded-2xl border px-6 py-3 text-xs font-bold transition-all"
            >
              Kích hoạt gói mới
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
