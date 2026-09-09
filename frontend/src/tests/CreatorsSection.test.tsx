import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CreatorsSection } from '../components/creators/CreatorsSection';
import { OverlayProvider } from '../context/OverlayContext';
import { fetchPublicCreators } from '../api/endpoints';

vi.mock('../api/endpoints', () => ({
  fetchPublicCreators: vi.fn(),
}));

const renderSection = () => render(<OverlayProvider><CreatorsSection /></OverlayProvider>);

describe('CreatorsSection', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders an Admin-verified TikTok profile joined with public feedback', async () => {
    vi.mocked(fetchPublicCreators).mockResolvedValue({
      success: true,
      total: 1,
      creators: [{
        id: 1,
        display_name: 'Bé Dứa',
        tiktok_handle: 'vinmeo06',
        tiktok_url: 'https://www.tiktok.com/@vinmeo06',
        screenshot_url: '/api/creators/images/test.webp',
        follower_count: 65700,
        is_featured: true,
        plan_name: 'Locket Gold VIP',
        review: { id: 9, rating: 5, content: 'Dùng rất ổn', images: [] },
      }],
    });

    renderSection();
    expect(await screen.findByText('Bé Dứa')).toBeInTheDocument();
    expect(screen.getByText(/@vinmeo06/)).toBeInTheDocument();
    expect(screen.getByText('Dùng rất ổn')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /TikTok chính chủ/i })).toHaveAttribute(
      'href',
      'https://www.tiktok.com/@vinmeo06',
    );
  });

  it('does not leave an empty marketing section when no KOL is configured', async () => {
    vi.mocked(fetchPublicCreators).mockResolvedValue({ success: true, total: 0, creators: [] });
    const { container } = renderSection();
    await waitFor(() => expect(fetchPublicCreators).toHaveBeenCalledOnce());
    await waitFor(() => expect(container.querySelector('#creators')).not.toBeInTheDocument());
  });
});
