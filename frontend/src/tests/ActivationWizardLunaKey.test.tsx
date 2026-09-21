import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ActivationWizard } from '../pages/dashboard/ActivationWizard';
import { OverlayProvider } from '../context/OverlayContext';
import { ToastProvider } from '../context/ToastContext';
import type { PlanItem } from '../types/api';
import {
  fetchGoldCheck,
  fetchOrderDetail,
  fetchQueueStatus,
  fetchUserInfo,
  lunakeyLookup,
  purchasePlanWithCoin,
} from '../api/endpoints';

vi.mock('../api/endpoints', () => ({
  fetchUserInfo: vi.fn(),
  fetchGoldCheck: vi.fn(),
  clearGoldCheckCache: vi.fn(),
  purchasePlanWithCoin: vi.fn(),
  createPlanPayment: vi.fn(),
  validateCoupon: vi.fn(),
  renewPayment: vi.fn(),
  cancelPayment: vi.fn(),
  fetchPlatformConfig: vi.fn().mockResolvedValue({ success: true, dns: { hostname: 'legacy.nextdns.io' } }),
  createMobileconfigDownloadTicket: vi.fn(),
  createApkDownloadTicket: vi.fn(),
  fetchQueueStatus: vi.fn(),
  lunakeyLookup: vi.fn(),
  fetchOrderDetail: vi.fn(),
  fetchPaymentStatus: vi.fn(),
}));

const mockedLookup = vi.mocked(lunakeyLookup);
const mockedPurchaseCoin = vi.mocked(purchasePlanWithCoin);
const mockedOrderDetail = vi.mocked(fetchOrderDetail);
const mockedQueueStatus = vi.mocked(fetchQueueStatus);
const mockedUserInfo = vi.mocked(fetchUserInfo);
const mockedGoldCheck = vi.mocked(fetchGoldCheck);

const lunakeyPlan: PlanItem = {
  id: 42,
  name: 'Locket Gold 1 năm (LunaKey)',
  slug: 'lunakey-1y',
  duration_days: 365,
  price_vnd: 50000,
  price_coin: 50,
  features: ['Gold 1 năm'],
  supported_platforms: 'ios',
  ios_fulfillment_mode: 'auto_activation',
  android_fulfillment_mode: 'disabled',
  activation_provider: 'lunakey',
  provider_category: 'yearly',
  warranty_months: 0,
  existing_gold_supported: false,
};

const legacyPlan: PlanItem = {
  id: 7,
  name: 'Gói cũ 1 tháng',
  slug: 'legacy-1m',
  duration_days: 30,
  price_vnd: 10000,
  price_coin: 10,
  features: [],
  supported_platforms: 'ios',
  ios_fulfillment_mode: 'auto_activation',
  android_fulfillment_mode: 'disabled',
  activation_provider: 'legacy_locket',
};

const renderWizard = (plans: PlanItem[]) => render(
  <ToastProvider>
    <OverlayProvider>
      <ActivationWizard
        plans={plans}
        isLoadingPlans={false}
        userCoinBalance={100}
        onRefreshWallet={vi.fn()}
        onGoToTopup={vi.fn()}
        onOrderCreated={vi.fn()}
      />
    </OverlayProvider>
  </ToastProvider>,
);

const selectPlan = async (needle: string) => {
  fireEvent.click(
    screen.getByRole('button', {
      name: (name) => name.startsWith('Xem chi tiết gói') && name.includes(needle),
    })
  );
  const choose = await screen.findByRole('button', { name: /chọn gói này/i });
  fireEvent.click(choose);
};

const enterUsername = (value: string) => {
  fireEvent.change(screen.getByPlaceholderText(/huydev/), { target: { value } });
};

const clickVerify = () => fireEvent.click(screen.getByRole('button', { name: /Tra cứu/ }));

describe('ActivationWizard LunaKey behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('resolves the profile through the provider lookup (no legacy user/gold check)', async () => {
    mockedLookup.mockResolvedValue({
      success: true,
      lookup_token: 'tok-1',
      profile: { username: 'someone', uid: 'uid-1', name: 'Some One', has_gold: false },
    });
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');

    enterUsername('someone');
    clickVerify();

    expect(await screen.findByText(/@someone/)).toBeInTheDocument();
    expect(mockedLookup).toHaveBeenCalledWith(42, 'someone');
    expect(mockedUserInfo).not.toHaveBeenCalled();
    expect(mockedGoldCheck).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Tiếp tục thanh toán/ })).toBeEnabled();
  });

  it('clears the confirmation when the username changes', async () => {
    mockedLookup.mockResolvedValue({
      success: true,
      lookup_token: 'tok-1',
      profile: { username: 'someone', uid: 'uid-1', name: 'Some One', has_gold: false },
    });
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('someone');
    clickVerify();
    await screen.findByText(/@someone/);

    enterUsername('other');

    expect(screen.queryByText(/@someone/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Tiếp tục thanh toán/ })).toBeDisabled();
  });

  it('ignores a slow lookup response after the plan is re-selected', async () => {
    let resolveStale: (value: unknown) => void = () => {};
    mockedLookup.mockImplementationOnce(
      () => new Promise((resolve) => { resolveStale = resolve; }) as ReturnType<typeof lunakeyLookup>
    );
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('userA');
    clickVerify();

    // Navigate back and re-select the plan while the first lookup is in flight.
    fireEvent.click(screen.getByRole('button', { name: /Quay lại/ }));
    await selectPlan('LunaKey');

    await act(async () => {
      resolveStale({
        success: true,
        lookup_token: 'stale-token',
        profile: { username: 'userA', uid: 'uid-A', name: 'User A', has_gold: false },
      });
      await Promise.resolve();
    });

    expect(screen.queryByText(/@userA/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Tiếp tục thanh toán/ })).toBeDisabled();
  });

  it('blocks an existing-Gold account when the plan does not support renewal', async () => {
    mockedLookup.mockResolvedValue({
      success: true,
      lookup_token: 'tok-gold',
      profile: { username: 'golduser', uid: 'uid-g', name: 'Gold User', has_gold: true },
    });
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('golduser');
    clickVerify();

    expect((await screen.findAllByText(/đang có Gold/)).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Tiếp tục thanh toán/ })).toBeDisabled();
  });

  it('tracks a LunaKey Coin purchase through the provider, with no DNS/mobileconfig UI', async () => {
    mockedLookup.mockResolvedValue({
      success: true,
      lookup_token: 'tok-1',
      profile: { username: 'buyer', uid: 'uid-b', name: 'Buyer', has_gold: false },
    });
    mockedPurchaseCoin.mockResolvedValue({ success: true, activation_order_id: 77, status: 'paid' });
    mockedOrderDetail.mockResolvedValue({
      success: true,
      order: {
        id: 77,
        user_id: 1,
        plan_name_snapshot: lunakeyPlan.name,
        product_id_snapshot: '',
        duration_days_snapshot: 365,
        price_vnd_snapshot: 50000,
        price_coin_snapshot: 50,
        payment_method: 'coin',
        platform: 'ios',
        locket_username: 'buyer',
        fulfillment_mode_snapshot: 'auto_activation',
        status: 'paid',
        created_at: 0,
        updated_at: 0,
        provider: 'lunakey',
        provider_status: 'processing',
        provider_status_label: 'Đang xử lý',
      },
    });

    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('buyer');
    clickVerify();
    await screen.findByText(/@buyer/);
    fireEvent.click(screen.getByRole('button', { name: /Tiếp tục thanh toán/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Xác nhận thanh toán ngay/ }));

    expect(await screen.findByText(/Đang xử lý kích hoạt qua LunaKey/)).toBeInTheDocument();
    // Provider order tracking, not the legacy account queue.
    await waitFor(() => expect(mockedOrderDetail).toHaveBeenCalledWith(77), { timeout: 4000 });
    expect(mockedQueueStatus).not.toHaveBeenCalled();
    // No DNS/mobileconfig installation UI for a provider order.
    expect(screen.queryByText(/Hostname DNS riêng tư/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Cài đặt Profile DNS/)).not.toBeInTheDocument();
  }, 15000);

  it('stops polling and drops the spinner for a refunded provider order', async () => {
    mockedLookup.mockResolvedValue({
      success: true,
      lookup_token: 'tok-1',
      profile: { username: 'buyer', uid: 'uid-b', name: 'Buyer', has_gold: false },
    });
    mockedPurchaseCoin.mockResolvedValue({ success: true, activation_order_id: 78, status: 'paid' });
    mockedOrderDetail.mockResolvedValue({
      success: true,
      order: {
        id: 78,
        user_id: 1,
        plan_name_snapshot: lunakeyPlan.name,
        product_id_snapshot: '',
        duration_days_snapshot: 365,
        price_vnd_snapshot: 50000,
        price_coin_snapshot: 50,
        payment_method: 'coin',
        platform: 'ios',
        locket_username: 'buyer',
        fulfillment_mode_snapshot: 'auto_activation',
        status: 'refunded',
        created_at: 0,
        updated_at: 0,
        provider: 'lunakey',
        provider_status: 'refunded',
        provider_status_label: 'Đã hoàn tiền',
      },
    });

    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('buyer');
    clickVerify();
    await screen.findByText(/@buyer/);
    fireEvent.click(screen.getByRole('button', { name: /Tiếp tục thanh toán/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Xác nhận thanh toán ngay/ }));

    expect((await screen.findAllByText(/Đơn đã được hoàn Coin/, undefined, { timeout: 4000 })).length).toBeGreaterThan(0);
    await waitFor(() => expect(mockedOrderDetail).toHaveBeenCalled(), { timeout: 4000 });
    const callsAfterTerminal = mockedOrderDetail.mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 3300));
    expect(mockedOrderDetail.mock.calls.length).toBe(callsAfterTerminal);
  }, 15000);

  it('keeps the legacy username/gold flow for non-provider plans', async () => {
    mockedUserInfo.mockResolvedValue({
      success: true,
      data: { uid: 'legacy-uid', username: 'legacyuser', first_name: 'Legacy', last_name: '', profile_picture_url: '' },
    });
    mockedGoldCheck.mockResolvedValue({
      success: true, is_gold: false, already_registered: false, blocked: false, error: null, is_renewal: false,
    });
    renderWizard([legacyPlan]);
    await selectPlan('Gói cũ');
    enterUsername('legacyuser');
    clickVerify();

    expect(await screen.findByText(/@legacyuser/)).toBeInTheDocument();
    expect(mockedUserInfo).toHaveBeenCalledWith('legacyuser');
    expect(mockedGoldCheck).toHaveBeenCalledWith('legacyuser');
    expect(mockedLookup).not.toHaveBeenCalled();
  });

  it('CASE 1: renders avatar, name, full UID and remaining Gold days', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: {
        username: 'huydev204', name: 'Huy Dev', uid: 'fvyvh5FQccP4djpWMQS09Lm3otu2',
        has_gold: true, avatar: 'https://cdn/a.jpg',
        gold_expiry: '2027-04-02T23:37:50Z', gold_days_left: 15,
      },
    });
    renderWizard([{ ...lunakeyPlan, existing_gold_supported: true }]);
    await selectPlan('LunaKey');
    enterUsername('huydev204');
    clickVerify();

    expect(await screen.findByText('Huy Dev')).toBeInTheDocument();
    expect(screen.getByText('@huydev204')).toBeInTheDocument();
    expect(screen.getByText(/fvyvh5FQccP4djpWMQS09Lm3otu2/)).toBeInTheDocument();
    expect(screen.getByText(/Đang có Locket Gold \(15 ngày còn lại\)/)).toBeInTheDocument();
    expect(screen.getByText(/Hết hạn:/)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'huydev204' })).toHaveAttribute('src', 'https://cdn/a.jpg');
    expect(screen.getByRole('button', { name: /Gia hạn thêm/ })).toBeEnabled();
  });

  it('CASE 2: shows "Chưa có Locket Gold" when the account has no Gold', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: 'newbie', name: 'Newbie', uid: 'uid-new', has_gold: false, avatar: null,
                 gold_expiry: null, gold_days_left: null },
    });
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('newbie');
    clickVerify();

    expect(await screen.findByText('Chưa có Locket Gold')).toBeInTheDocument();
    expect(screen.queryByText(/ngày còn lại/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Gia hạn thêm/ })).not.toBeInTheDocument();
  });

  it('CASE 3: renders a single @ even when the provider username already has one', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: '@Someone', uid: 'uid', has_gold: false },
    });
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('@Someone');
    clickVerify();

    expect(await screen.findByText('@Someone')).toBeInTheDocument();
    expect(screen.queryByText('@@Someone')).not.toBeInTheDocument();
  });

  it('CASE 4: accepts a Locket link and renders the provider profile', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: 'Someone', uid: 'uid-link', has_gold: false },
    });
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('https://locket.camera/links/Someone');
    clickVerify();

    await waitFor(() => expect(mockedLookup).toHaveBeenCalledWith(42, 'https://locket.camera/links/Someone'));
    expect(await screen.findByText('@Someone')).toBeInTheDocument();
  });

  it('CASE 6: falls back to an initial when the avatar is null', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: 'avatarless', uid: 'uid', has_gold: false, avatar: null },
    });
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('avatarless');
    clickVerify();

    expect(await screen.findByText('@avatarless')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('CASE 7: shows 0 remaining days without inventing a number', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: 'u', uid: 'uid', has_gold: true, gold_expiry: null, gold_days_left: 0 },
    });
    renderWizard([{ ...lunakeyPlan, existing_gold_supported: true }]);
    await selectPlan('LunaKey');
    enterUsername('u');
    clickVerify();

    expect(await screen.findByText(/Đang có Locket Gold \(0 ngày còn lại\)/)).toBeInTheDocument();
  });

  it('CASE 8: shows an expired state when gold_expiry is in the past', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: 'u', uid: 'uid', has_gold: true, avatar: null,
                 gold_expiry: '2020-01-01T00:00:00Z', gold_days_left: 0 },
    });
    renderWizard([{ ...lunakeyPlan, existing_gold_supported: true }]);
    await selectPlan('LunaKey');
    enterUsername('u');
    clickVerify();

    expect(await screen.findByText(/Locket Gold đã hết hạn/)).toBeInTheDocument();
    expect(screen.queryByText(/Đang có Locket Gold/)).not.toBeInTheDocument();
  });

  it('CASE 9: shows a friendly error and does not crash when the provider fails', async () => {
    mockedLookup.mockRejectedValue(new Error('Không thể tra cứu lúc này. Vui lòng thử lại sau.'));
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('boom');
    clickVerify();

    expect(await screen.findByRole('alert')).toHaveTextContent(/Không thể tra cứu/);
  });

  it('CASE 10: submits the lookup when Enter is pressed', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: 'enter', uid: 'uid', has_gold: false },
    });
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    const input = screen.getByPlaceholderText(/huydev204/);
    fireEvent.change(input, { target: { value: 'enter' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => expect(mockedLookup).toHaveBeenCalledWith(42, 'enter'));
  });

  it('CASE 11: does not fire duplicate lookups when the button is spammed', async () => {
    let resolveLookup: (value: unknown) => void = () => {};
    mockedLookup.mockImplementationOnce(
      () => new Promise((resolve) => { resolveLookup = resolve; }) as ReturnType<typeof lunakeyLookup>
    );
    renderWizard([lunakeyPlan]);
    await selectPlan('LunaKey');
    enterUsername('spam');
    const button = screen.getByRole('button', { name: /Tra cứu/ });
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);

    await act(async () => {
      resolveLookup({ success: true, lookup_token: 't', profile: { username: 'spam', uid: 'u', has_gold: false } });
      await Promise.resolve();
    });

    expect(mockedLookup).toHaveBeenCalledTimes(1);
  });

  it('computes remaining days from gold_expiry when gold_days_left is missing', async () => {
    const future = new Date(Date.now() + 10 * 86_400_000).toISOString();
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: 'u', uid: 'uid', has_gold: true, avatar: null,
                 gold_expiry: future, gold_days_left: null },
    });
    renderWizard([{ ...lunakeyPlan, existing_gold_supported: true }]);
    await selectPlan('LunaKey');
    enterUsername('u');
    clickVerify();

    expect(await screen.findByText(/Đang có Locket Gold \(10 ngày còn lại\)/)).toBeInTheDocument();
  });

  it('never renders NaN/undefined when Gold fields are missing', async () => {
    mockedLookup.mockResolvedValue({
      success: true, lookup_token: 'tok',
      profile: { username: 'u', uid: 'uid', has_gold: true, gold_expiry: null, gold_days_left: null },
    });
    renderWizard([{ ...lunakeyPlan, existing_gold_supported: true }]);
    await selectPlan('LunaKey');
    enterUsername('u');
    clickVerify();

    expect(await screen.findByText('Đang có Locket Gold')).toBeInTheDocument();
    expect(screen.queryByText(/NaN|undefined/)).not.toBeInTheDocument();
  });
});
