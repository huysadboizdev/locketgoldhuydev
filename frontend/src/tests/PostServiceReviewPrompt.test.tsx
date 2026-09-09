import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PostServiceReviewPrompt } from '../components/reviews/PostServiceReviewPrompt';
import { OverlayProvider } from '../context/OverlayContext';
import { ToastProvider } from '../context/ToastContext';
import type { ActivationOrder } from '../types/api';

const completedOrder = {
  id: 42,
  user_id: 7,
  plan_name_snapshot: 'Locket Gold VIP Pro',
  product_id_snapshot: 'vip-pro',
  duration_days_snapshot: 365,
  price_vnd_snapshot: 200_000,
  price_coin_snapshot: 200,
  payment_method: 'qr',
  platform: 'ios',
  locket_username: 'customer',
  fulfillment_mode_snapshot: 'auto_activation',
  status: 'completed',
  created_at: 1,
  updated_at: 2,
} satisfies ActivationOrder;

const renderPrompt = (onClose = vi.fn()) => render(
  <ToastProvider>
    <OverlayProvider>
      <PostServiceReviewPrompt
        isOpen
        order={completedOrder}
        myReview={null}
        onClose={onClose}
        onSubmit={async () => ({ success: true, msg: 'ok' })}
        onUpdate={async () => ({ success: true, msg: 'ok' })}
        onDelete={async () => ({ success: true, msg: 'ok' })}
      />
    </OverlayProvider>
  </ToastProvider>
);

describe('PostServiceReviewPrompt', () => {
  it('thanks the customer and opens the real review form', () => {
    renderPrompt();

    expect(screen.getByRole('heading', { name: 'Cảm ơn bạn đã tin tưởng!' })).toBeInTheDocument();
    expect(screen.getByText('Locket Gold VIP Pro')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Đánh giá trải nghiệm' }));
    expect(screen.getByRole('heading', { name: /Viết đánh giá trải nghiệm/ })).toBeInTheDocument();
  });

  it('can be dismissed without forcing a review', () => {
    const onClose = vi.fn();
    renderPrompt(onClose);
    fireEvent.click(screen.getByRole('button', { name: 'Để sau' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
