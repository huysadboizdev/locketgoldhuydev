import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  lunakeyLookup,
  createPlanPayment,
  purchasePlanWithCoin,
} from '../api/endpoints';

const jsonResponse = (payload: unknown) =>
  ({
    ok: true,
    status: 200,
    headers: { get: (name: string) => (name.toLowerCase() === 'content-type' ? 'application/json' : null) },
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  }) as unknown as Response;

describe('LunaKey API adapters', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts lookup with plan_id and username (no client UID)', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        lookup_token: 'tok-1',
        profile: { username: 'someone', uid: 'uid-1', has_gold: false },
      })
    );

    const res = await lunakeyLookup(7, 'someone');

    expect(res.lookup_token).toBe('tok-1');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/lunakey/lookup');
    const body = JSON.parse((options as RequestInit).body as string);
    expect(body).toEqual({ plan_id: 7, username: 'someone' });
    expect(body.uid).toBeUndefined();
  });

  it('forwards lookup_token when creating a QR plan payment', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, payment_id: 1 }));

    await createPlanPayment({
      plan_id: 7,
      platform: 'ios',
      username: 'someone',
      lookup_token: 'tok-1',
      idempotency_key: 'idem-1',
    });

    const [, options] = fetchMock.mock.calls[0];
    const body = JSON.parse((options as RequestInit).body as string);
    expect(body.lookup_token).toBe('tok-1');
    expect(body.plan_id).toBe(7);
  });

  it('forwards lookup_token when purchasing with Coin', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, activation_order_id: 9 }));

    await purchasePlanWithCoin({
      plan_id: 7,
      platform: 'ios',
      username: 'someone',
      lookup_token: 'tok-2',
      idempotency_key: 'idem-2',
    });

    const [, options] = fetchMock.mock.calls[0];
    const body = JSON.parse((options as RequestInit).body as string);
    expect(body.lookup_token).toBe('tok-2');
  });
});
