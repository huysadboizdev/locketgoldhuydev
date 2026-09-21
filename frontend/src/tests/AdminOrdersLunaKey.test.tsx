import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminOrders } from '../pages/admin/AdminOrders';
import { OverlayProvider } from '../context/OverlayContext';
import type { AdminActivationOrder } from '../types/admin';
import {
  fetchAdminOrders,
  reconcileAdminProviderJob,
  retryAdminProviderJob,
} from '../api/adminEndpoints';

vi.mock('../api/adminEndpoints', () => ({
  fetchAdminOrders: vi.fn(),
  startManualAdminOrder: vi.fn(),
  completeManualAdminOrder: vi.fn(),
  cancelManualAdminOrder: vi.fn(),
  refundManualAdminOrder: vi.fn(),
  retryAdminProviderJob: vi.fn(),
  reconcileAdminProviderJob: vi.fn(),
  fetchAdminProviderStatus: vi.fn().mockResolvedValue({ success: true, provider: { paused: false } }),
  resumeAdminProvider: vi.fn().mockResolvedValue({ success: true, provider: { paused: false } }),
}));

const mockedFetchOrders = vi.mocked(fetchAdminOrders);
const mockedRetry = vi.mocked(retryAdminProviderJob);
const mockedReconcile = vi.mocked(reconcileAdminProviderJob);

const lunakeyOrder: AdminActivationOrder = {
  id: 55,
  user_id: 1,
  plan_id: 10,
  plan_name_snapshot: 'Locket Gold 1 năm (LunaKey)',
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
  activation_provider_snapshot: 'lunakey',
  provider_category_snapshot: 'yearly',
  provider_uid: 'uid-1',
  provider_request_id: 'req-1',
  provider_job_status: 'awaiting_reconciliation',
  provider_job_attempts: 2,
};

const renderAdmin = () => render(
  <OverlayProvider>
    <AdminOrders />
  </OverlayProvider>,
);

const openDetail = async () => {
  const buttons = await screen.findAllByTitle('Xem chi tiết');
  fireEvent.click(buttons[0]);
  return screen.getByRole('dialog');
};

describe('AdminOrders LunaKey provider actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedFetchOrders.mockResolvedValue({
      success: true,
      items: [lunakeyOrder],
      pagination: { total: 1, page: 1, limit: 10, pages: 1 },
      total: 1,
      page: 1,
      limit: 10,
      pages: 1,
    });
  });

  it('shows the provider job panel for a LunaKey order', async () => {
    renderAdmin();
    const dialog = await openDetail();
    expect(dialog).toHaveTextContent('Nguồn LunaKey');
    expect(dialog).toHaveTextContent('awaiting_reconciliation');
    expect(dialog).toHaveTextContent('req-1');
  });

  it('surfaces a failed retry as an error instead of a fake success', async () => {
    mockedRetry.mockRejectedValue(new Error('job_in_flight'));
    renderAdmin();
    const dialog = await openDetail();

    fireEvent.click(screen.getByRole('button', { name: /Thử lại/ }));

    await waitFor(() => expect(mockedRetry).toHaveBeenCalledWith(55));
    expect(await screen.findByText('job_in_flight')).toBeInTheDocument();
    expect(dialog).toHaveTextContent('Nguồn LunaKey');
  });

  it('blocks a reconcile with a short note before calling the API', async () => {
    renderAdmin();
    await openDetail();

    fireEvent.change(screen.getByPlaceholderText(/Ghi chú đối soát/), { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận' }));

    expect(await screen.findByText(/tối thiểu 5 ký tự/)).toBeInTheDocument();
    expect(mockedReconcile).not.toHaveBeenCalled();
  });
});
