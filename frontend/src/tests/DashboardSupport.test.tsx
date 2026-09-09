import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { DashboardPage } from '../pages/DashboardPage';

vi.mock('../api/endpoints', () => ({
  fetchPlans: vi.fn(() => new Promise(() => {})),
  fetchWalletBalance: vi.fn(() => new Promise(() => {})),
  fetchUserOrders: vi.fn(() => new Promise(() => {})),
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'huy', display_name: 'Huy', email: 'huy@example.com' },
    logout: vi.fn(),
  }),
}));

vi.mock('../hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn() }),
}));

vi.mock('../context/OverlayContext', () => ({
  useOverlay: () => ({ hasActiveOverlay: false }),
}));

vi.mock('../hooks/useReviews', () => ({
  useReviews: () => ({
    myReview: null,
    myReviewLoading: false,
    hasReview: false,
    isEligible: false,
    refreshMyReview: vi.fn().mockResolvedValue(undefined),
    submitReview: vi.fn(),
    updateReview: vi.fn(),
    deleteReview: vi.fn(),
  }),
}));

vi.mock('../hooks/useLiveRefresh', () => ({ useLiveRefresh: vi.fn() }));
vi.mock('../components/layout/ThemeToggle', () => ({ ThemeToggle: () => null }));
vi.mock('../pages/dashboard/OverviewView', () => ({ OverviewView: () => null }));
vi.mock('../pages/dashboard/ActivationWizard', () => ({ ActivationWizard: () => null }));
vi.mock('../pages/dashboard/WalletView', () => ({ WalletView: () => null }));
vi.mock('../pages/dashboard/OrdersView', () => ({ OrdersView: () => null }));
vi.mock('../pages/dashboard/FeedbackView', () => ({ FeedbackView: () => null }));
vi.mock('../components/reviews/PostServiceReviewPrompt', () => ({ PostServiceReviewPrompt: () => null }));

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <DashboardPage />
    </MemoryRouter>
  );
}

describe('dashboard support launcher', () => {
  it('keeps a clearly labeled support button visible on the dashboard', () => {
    renderDashboard();

    expect(screen.getByRole('button', { name: 'Mở hỗ trợ' })).toBeVisible();
  });

  it('opens the three configured support channels from the dashboard', () => {
    renderDashboard();

    fireEvent.click(screen.getByRole('button', { name: 'Mở hỗ trợ' }));
    const dialog = screen.getByRole('dialog', { name: 'Hỗ trợ trực tiếp' });
    const channels = [
      ['Facebook', 'https://www.facebook.com/huygoodboizdev/'],
      ['Zalo', 'https://zalo.me/0763076124'],
      ['Telegram', 'https://t.me/huydev204'],
    ];

    channels.forEach(([name, href]) => {
      const link = within(dialog).getByRole('link', { name: new RegExp(name) });
      expect(link).toHaveAttribute('href', href);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  it('closes the support panel with Escape', () => {
    renderDashboard();

    fireEvent.click(screen.getByRole('button', { name: 'Mở hỗ trợ' }));
    expect(screen.getByRole('dialog', { name: 'Hỗ trợ trực tiếp' })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Hỗ trợ trực tiếp' })).not.toBeInTheDocument();
  });
});
