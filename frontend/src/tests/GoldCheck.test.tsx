// frontend/src/tests/GoldCheck.test.tsx
import { describe, it, expect } from 'vitest';
import { getGoldBlockMessage } from '../pages/dashboard/ActivationWizard';

describe('gold check gate', () => {
  it('blocks live gold account with expires date', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: true,
      expires_date: '2026-12-31T00:00:00Z',
      already_registered: false,
      blocked: true,
    });
    expect(msg).toContain('2026-12-31');
    expect(msg).toContain('đổi gói');
  });

  it('blocks live gold account without expires date', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: true,
      expires_date: null,
      already_registered: false,
      blocked: true,
    });
    expect(msg).toContain('gần đây');
    expect(msg).toContain('đổi gói');
  });

  it('blocks already-registered account with order status', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: false,
      already_registered: true,
      order_status: 'completed',
      blocked: true,
    });
    expect(msg).toContain('(đơn completed)');
    expect(msg).toContain('đổi gói');
  });

  it('blocks already-registered account without order status', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: false,
      already_registered: true,
      order_status: null,
      blocked: true,
    });
    expect(msg).not.toContain('(đơn');
    expect(msg).toContain('đổi gói');
  });

  it('blocks when gold check is unavailable', () => {
    const msg = getGoldBlockMessage({
      success: false,
      is_gold: false,
      already_registered: false,
      blocked: true,
      error: 'gold_check_unavailable',
    });
    expect(msg).toContain('thử lại sau');
    expect(msg).toContain('đổi gói');
  });

  it('passes new user through', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: false,
      already_registered: false,
      blocked: false,
    });
    expect(msg).toBeNull();
  });
});
