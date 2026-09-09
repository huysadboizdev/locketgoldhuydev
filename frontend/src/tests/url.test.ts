import { describe, expect, it } from 'vitest';
import { getPostLoginReturnTo } from '../utils/url';

describe('post-auth role routing', () => {
  it('never sends an admin account into the user dashboard', () => {
    expect(getPostLoginReturnTo('admin', '/dashboard')).toBe('/admin');
    expect(getPostLoginReturnTo('admin', '/admin/coupons')).toBe('/admin/coupons');
  });

  it('keeps normal users inside the user dashboard', () => {
    expect(getPostLoginReturnTo('user', '/admin')).toBe('/dashboard');
    expect(getPostLoginReturnTo('user', '/dashboard/orders')).toBe('/dashboard/orders');
  });
});
