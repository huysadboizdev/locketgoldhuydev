import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OrdersView } from '../pages/dashboard/OrdersView';
import { OverlayProvider } from '../context/OverlayContext';
import type { ActivationOrder } from '../types/api';
import { fetchUserOrders, fetchPlatformConfig } from '../api/endpoints';

vi.mock('../api/endpoints', () => ({
  fetchUserOrders: vi.fn(),
  fetchPlatformConfig: vi.fn(),
  createMobileconfigDownloadTicket: vi.fn(),
  createApkDownloadTicket: vi.fn(),
}));

const mockedFetchOrders = vi.mocked(fetchUserOrders);
const mockedPlatformConfig = vi.mocked(fetchPlatformConfig);

const makeOrder = (overrides: Partial<ActivationOrder>): ActivationOrder => ({
  id: 1,
  user_id: 1,
  plan_name_snapshot: 'Locket Gold',
  product_id_snapshot: '',
  duration_days_snapshot: 365,
  price_vnd_snapshot: 50000,
  price_coin_snapshot: 50,
  payment_method: 'coin',
  platform: 'ios',
  locket_username: 'buyer',
  fulfillment_mode_snapshot: 'auto_activation',
  status: 'paid',
  created_at: 1700000000,
  updated_at: 1700000000,
  ...overrides,
});

const renderOrders = () => render(
  <OverlayProvider>
    <OrdersView />
  </OverlayProvider>,
);

const mockOrders = (items: ActivationOrder[]) => {
  mockedFetchOrders.mockResolvedValue({
    success: true,
    items,
    pagination: { total: items.length, limit: 10, offset: 0, has_more: false },
  });
};

const openFirstDetail = async () => {
  const buttons = await screen.findAllByRole('button', { name: /Xem/ });
  fireEvent.click(buttons[0]);
  return screen.getByRole('dialog');
};

describe('OrdersView LunaKey tracking', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedPlatformConfig.mockResolvedValue({
      success: true,
      dns: { hostname: 'legacy.nextdns.io', apple_url: 'https://apple.nextdns.io' },
      supported_platforms: ['ios', 'android'],
      apk_available: false,
      apk_delivery: 'unavailable',
      mobileconfig_available: true,
      bank_configured: true,
    } as any);
  });

  it('shows the provider status label and no DNS install UI for a LunaKey order', async () => {
    mockOrders([
      makeOrder({
        id: 11,
        provider: 'lunakey',
        provider_status: 'awaiting_reconciliation',
        provider_status_label: 'Đang kiểm tra kết quả',
      }),
    ]);
    renderOrders();

    expect(await screen.findAllByText('Đang kiểm tra kết quả')).not.toHaveLength(0);

    const dialog = await openFirstDetail();
    expect(dialog).toHaveTextContent('Kích hoạt qua LunaKey');
    expect(dialog).toHaveTextContent('Không cần DNS');
    expect(dialog).not.toHaveTextContent('Hostname DNS riêng tư');
    // awaiting_reconciliation is still in progress, so a spinner is expected.
    expect(dialog.querySelector('.animate-spin')).not.toBeNull();
  });

  it('renders refunded and cancelled LunaKey orders as terminal (no spinner)', async () => {
    mockOrders([
      makeOrder({ id: 21, provider: 'lunakey', provider_status: 'refunded', provider_status_label: 'Đã hoàn tiền', status: 'refunded' }),
      makeOrder({ id: 22, provider: 'lunakey', provider_status: 'cancelled', provider_status_label: 'Đã hủy', status: 'cancelled' }),
    ]);
    renderOrders();

    expect(await screen.findAllByText('Đã hoàn tiền')).not.toHaveLength(0);
    expect(screen.getAllByText('Đã hủy').length).toBeGreaterThan(0);

    const dialog = await openFirstDetail();
    expect(dialog).toHaveTextContent('Đơn đã được hoàn Coin');
    expect(dialog.querySelector('.animate-spin')).toBeNull();
  });

  it('keeps the DNS guide for a legacy iOS order', async () => {
    mockOrders([
      makeOrder({ id: 31, provider: 'legacy_locket', status: 'completed', fulfillment_mode_snapshot: 'auto_activation' }),
    ]);
    renderOrders();

    const dialog = await openFirstDetail();
    expect(dialog).toHaveTextContent('legacy.nextdns.io');
    expect(dialog).not.toHaveTextContent('Kích hoạt qua LunaKey');
  });

  it('refetches orders from the backend on remount (not RAM state)', async () => {
    mockOrders([makeOrder({ id: 41, provider: 'lunakey', provider_status: 'processing', provider_status_label: 'Đang xử lý' })]);

    const first = renderOrders();
    await waitFor(() => expect(mockedFetchOrders).toHaveBeenCalledTimes(1));
    first.unmount();

    renderOrders();
    await waitFor(() => expect(mockedFetchOrders).toHaveBeenCalledTimes(2));
  });
});
