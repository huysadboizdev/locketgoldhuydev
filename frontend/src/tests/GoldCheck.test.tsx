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
      block_reason: 'already_gold_live',
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
      block_reason: 'already_gold_live',
    });
    expect(msg).toContain('gần đây');
    expect(msg).toContain('đổi gói');
  });

  it('blocks in-flight order (duplicate_in_progress)', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: false,
      already_registered: true,
      order_status: 'paid',
      blocked: true,
      block_reason: 'duplicate_in_progress',
    });
    expect(msg).toContain('đang được xử lý');
    expect(msg).toContain('liên hệ admin');
  });

  it('allows renewal for completed order history (is_renewal=true)', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: false,
      already_registered: true,
      order_status: 'completed',
      blocked: false,
      is_renewal: true,
      block_reason: null,
    });
    expect(msg).toBeNull();
  });

  it('allows new user through', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: false,
      already_registered: false,
      blocked: false,
    });
    expect(msg).toBeNull();
  });

  it('allows timeout/fail-open (fail-open policy)', () => {
    const msg = getGoldBlockMessage({
      success: true,
      is_gold: false,
      already_registered: false,
      blocked: false,
      check: 'timeout',
    });
    expect(msg).toBeNull();
  });
});
