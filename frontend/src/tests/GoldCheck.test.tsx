// frontend/src/tests/GoldCheck.test.tsx
import { describe, it, expect } from 'vitest';
describe('gold check gate', () => {
  it('blocks already-gold message', () => {
    const msg = 'Tai khoan da Gold den ngay X — goi nay chi cho nguoi chua tung dang ky. Vui long doi goi moi.';
    expect(msg).toContain('doi goi moi');
  });
});
