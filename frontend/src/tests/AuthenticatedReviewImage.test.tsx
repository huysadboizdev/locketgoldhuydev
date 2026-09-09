import React from 'react';
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getAccessToken, requestTokenRefresh } from '../api/client';
import { AuthenticatedReviewImage } from '../components/reviews/AuthenticatedReviewImage';

vi.mock('../api/client', () => ({
  getAccessToken: vi.fn(),
  requestTokenRefresh: vi.fn(),
}));

const mockedGetAccessToken = vi.mocked(getAccessToken);
const mockedRequestTokenRefresh = vi.mocked(requestTokenRefresh);

function imageResponse(status = 200): Response {
  return new Response(new Blob(['image-bytes'], { type: 'image/jpeg' }), {
    status,
    headers: { 'Content-Type': 'image/jpeg' },
  });
}

describe('AuthenticatedReviewImage', () => {
  beforeEach(() => {
    mockedGetAccessToken.mockReturnValue('current-token');
    mockedRequestTokenRefresh.mockReset();
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:review-image');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('uses same-origin credentials so a Cloudinary redirect remains CORS-compatible', async () => {
    const fetchMock = vi.fn().mockResolvedValue(imageResponse());
    vi.stubGlobal('fetch', fetchMock);

    render(<AuthenticatedReviewImage src="/api/reviews/images/example.webp" alt="Ảnh đánh giá" />);

    expect(await screen.findByRole('img', { name: 'Ảnh đánh giá' })).toHaveAttribute(
      'src',
      'blob:review-image'
    );
    expect(fetchMock).toHaveBeenCalledWith('/api/reviews/images/example.webp', {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Authorization: 'Bearer current-token' },
    });
  });

  it('keeps the 401 refresh-and-retry flow with same-origin credentials', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(imageResponse(401))
      .mockResolvedValueOnce(imageResponse());
    vi.stubGlobal('fetch', fetchMock);
    mockedRequestTokenRefresh.mockResolvedValue('fresh-token');

    render(<AuthenticatedReviewImage src="/api/reviews/images/private.webp" alt="Ảnh riêng" />);

    expect(await screen.findByRole('img', { name: 'Ảnh riêng' })).toBeInTheDocument();
    expect(mockedRequestTokenRefresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/reviews/images/private.webp', {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Authorization: 'Bearer fresh-token' },
    });
  });
});
