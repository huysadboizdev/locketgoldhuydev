import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { Footer } from '../components/layout/Footer';
import { Navbar } from '../components/layout/Navbar';
import { ThemeProvider } from '../context/ThemeContext';

vi.mock('../api/endpoints', () => ({
  fetchGlobalQueueStatus: vi.fn(() => new Promise(() => {})),
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: null,
    isAuthenticated: false,
    logout: vi.fn(),
  }),
}));

describe('support links', () => {
  it.each([
    ['Facebook', 'https://www.facebook.com/huygoodboizdev/'],
    ['Zalo', 'https://zalo.me/0763076124'],
    ['Telegram', 'https://t.me/huydev204'],
  ])('opens %s at the configured profile in a safe new tab', (name, href) => {
    render(<Footer />);

    const link = screen.getByRole('link', { name: new RegExp(name) });
    expect(link).toHaveAttribute('href', href);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('exposes the support section from desktop and mobile navigation', () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <Navbar />
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Mở menu' }));
    const links = screen.getAllByRole('link', { name: 'Hỗ trợ' });
    expect(links).toHaveLength(2);
    links.forEach((link) => expect(link).toHaveAttribute('href', '/#support'));
  });

  it('keeps the desktop header on one row and defers it to wide screens', () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <Navbar />
        </ThemeProvider>
      </MemoryRouter>
    );

    const header = screen.getByRole('banner');
    const desktopNav = screen.getByRole('navigation', { name: 'Menu chính' });
    const supportLink = within(desktopNav).getByRole('link', { name: 'Hỗ trợ' });

    expect(header.firstElementChild).toHaveClass('max-w-[1600px]');
    expect(desktopNav).toHaveClass('2xl:flex', 'shrink-0', 'whitespace-nowrap');
    expect(screen.getByRole('button', { name: 'Mở menu' })).toHaveClass('2xl:hidden');
    expect(supportLink).toHaveClass('bg-amber-500/10', 'focus-visible:outline-none');
  });
});
