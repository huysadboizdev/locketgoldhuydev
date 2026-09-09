import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminPlans } from '../pages/admin/AdminPlans';
import { OverlayProvider } from '../context/OverlayContext';
import {
  createAdminPlan,
  deleteAdminPlan,
  fetchAdminPlans,
  toggleAdminPlan,
  updateAdminPlan,
} from '../api/adminEndpoints';

vi.mock('../api/adminEndpoints', () => ({
  fetchAdminPlans: vi.fn(),
  createAdminPlan: vi.fn(),
  updateAdminPlan: vi.fn(),
  toggleAdminPlan: vi.fn(),
  deleteAdminPlan: vi.fn(),
}));

const mockedFetchAdminPlans = vi.mocked(fetchAdminPlans);
const mockedCreateAdminPlan = vi.mocked(createAdminPlan);
const mockedUpdateAdminPlan = vi.mocked(updateAdminPlan);
const mockedToggleAdminPlan = vi.mocked(toggleAdminPlan);
const mockedDeleteAdminPlan = vi.mocked(deleteAdminPlan);

const renderPlans = () => render(
  <OverlayProvider>
    <AdminPlans />
  </OverlayProvider>,
);

const openCreatePlan = async () => {
  renderPlans();
  fireEvent.click(await screen.findByRole('button', { name: /Thêm Gói Mới/i }));
  return screen.getByRole('dialog', { name: 'Tạo Gói Dịch Vụ Mới' });
};

describe('AdminPlans create modal', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark', 'light');
    document.documentElement.classList.add('light');
    mockedFetchAdminPlans.mockResolvedValue({ success: true, plans: [] });
    mockedCreateAdminPlan.mockReset();
    mockedUpdateAdminPlan.mockReset();
    mockedToggleAdminPlan.mockReset();
    mockedDeleteAdminPlan.mockReset();
  });

  it('keeps admin styling inside the portal without forcing dark mode', async () => {
    const dialog = await openCreatePlan();

    expect(dialog.closest('.admin-shell')).not.toBeNull();
    expect(dialog.closest('.dark')).toBeNull();
  });

  it('associates every visible field label with its control', async () => {
    await openCreatePlan();

    expect(screen.getByLabelText('Tên gói *')).toBeInTheDocument();
    expect(screen.getByLabelText('Mã Slug *')).toBeInTheDocument();
    expect(screen.getByLabelText('Thời hạn (ngày) *')).toBeInTheDocument();
    expect(screen.getByLabelText(/Giá VND/)).toBeInTheDocument();
    expect(screen.getByLabelText('Giá Coin *')).toBeInTheDocument();
    expect(screen.getByLabelText('Nền tảng hỗ trợ')).toBeInTheDocument();
    expect(screen.getByLabelText(/Danh sách tính năng/)).toBeInTheDocument();
  });

  it('focuses the plan name instead of the close button when opened', async () => {
    await openCreatePlan();

    await waitFor(() => expect(screen.getByLabelText('Tên gói *')).toHaveFocus());
  });

  it('derives the read-only Coin price from the VND price', async () => {
    await openCreatePlan();

    const vndInput = screen.getByLabelText(/Giá VND/);
    const coinInput = screen.getByLabelText('Giá Coin *');
    expect(coinInput).toHaveAttribute('readonly');
    expect(coinInput).toHaveClass('focus-visible:ring-2');
    expect(coinInput).toHaveValue('50');

    fireEvent.change(vndInput, { target: { value: '120.000' } });

    await waitFor(() => expect(coinInput).toHaveValue('120'));
  });

  it('announces validation errors to assistive technology', async () => {
    await openCreatePlan();

    const form = screen.getByRole('button', { name: 'Tạo Gói Mới' }).closest('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    expect(screen.getByRole('alert')).toHaveTextContent('Vui lòng nhập tên gói.');
  });
});
