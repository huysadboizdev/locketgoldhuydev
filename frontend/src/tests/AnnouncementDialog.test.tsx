import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AnnouncementDialog } from '../components/common/AnnouncementDialog';
import { OverlayProvider } from '../context/OverlayContext';

const PathProbe = () => <span data-testid="path">{useLocation().pathname}</span>;

const renderDialog = (ui: React.ReactNode) =>
  render(
    <MemoryRouter>
      <OverlayProvider>{ui}</OverlayProvider>
    </MemoryRouter>
  );

describe('AnnouncementDialog', () => {
  it('renders content and closes from the secondary action', () => {
    const handleClose = vi.fn();
    renderDialog(
      <AnnouncementDialog
        isOpen
        onClose={handleClose}
        title="Ưu đãi mới"
        message="Nội dung thông báo"
        buttonText="Xem ngay"
        buttonUrl="https://example.com"
      />
    );

    expect(screen.getByText('Ưu đãi mới')).toBeInTheDocument();
    expect(screen.getByText('Nội dung thông báo')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Để sau' }));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('uses SPA navigation for safe internal links', () => {
    renderDialog(
      <>
        <AnnouncementDialog
          isOpen
          onClose={() => {}}
          title="Thông báo"
          message="Nội dung"
          buttonText="Mở trang"
          buttonUrl="/dashboard"
        />
        <PathProbe />
      </>
    );

    fireEvent.click(screen.getByRole('button', { name: /Mở trang/ }));
    expect(screen.getByTestId('path')).toHaveTextContent('/dashboard');
  });

  it('does not execute links in admin preview mode', () => {
    const handleClose = vi.fn();
    renderDialog(
      <>
        <AnnouncementDialog
          isOpen
          onClose={handleClose}
          title="Xem thử"
          message="Nội dung"
          buttonText="Nút mẫu"
          buttonUrl="/dashboard"
          actionEnabled={false}
          layerKind="dialog"
        />
        <PathProbe />
      </>
    );

    fireEvent.click(screen.getByRole('button', { name: /Nút mẫu/ }));
    expect(screen.getByTestId('path')).toHaveTextContent('/');
    expect(handleClose).not.toHaveBeenCalled();
  });

  it('offers and executes the two-hour snooze action', () => {
    const handleSnooze = vi.fn();
    renderDialog(
      <AnnouncementDialog
        isOpen
        onClose={() => {}}
        onSnooze={handleSnooze}
        title="Thông báo"
        message="Nội dung"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Tắt trong 2 tiếng/ }));
    expect(handleSnooze).toHaveBeenCalledTimes(1);
  });
});
