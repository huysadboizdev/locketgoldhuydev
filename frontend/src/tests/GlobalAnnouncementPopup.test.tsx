import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GlobalAnnouncementPopup } from '../components/common/GlobalAnnouncementPopup';
import { ModalPortal } from '../components/common/ModalPortal';
import { OverlayProvider } from '../context/OverlayContext';
import { ToastProvider } from '../context/ToastContext';
import { useToast } from '../hooks/useToast';
import { ToastViewport } from '../components/common/ToastViewport';

vi.mock('../hooks/useSiteSettings', () => ({
  useSiteSettings: () => ({
    settings: {
      popup: {
        enabled: true,
        active: true,
        version: 99,
        title: 'Thông báo toàn trang',
        message: 'Nội dung kiểm thử',
        dismissible: true,
        audience: 'all',
        display_mode: 'every_visit',
        routes: ['*'],
      },
    },
  }),
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: true }),
}));

const AuthToastTrigger = () => {
  const toast = useToast();
  return (
    <button onClick={() => toast.success('Đăng nhập thành công', undefined, { channel: 'auth', duration: 1000 })}>
      Tạo auth toast
    </button>
  );
};

const renderPopup = (extra?: React.ReactNode) =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <OverlayProvider>
          <AuthToastTrigger />
          {extra}
          <GlobalAnnouncementPopup />
          <ToastViewport />
        </OverlayProvider>
      </ToastProvider>
    </MemoryRouter>
  );

describe('GlobalAnnouncementPopup coordination', () => {
  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.useRealTimers();
  });

  it('waits until an auth toast has finished', () => {
    vi.useFakeTimers();
    renderPopup();
    fireEvent.click(screen.getByRole('button', { name: 'Tạo auth toast' }));
    act(() => vi.advanceTimersByTime(999));
    expect(screen.queryByText('Thông báo toàn trang')).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    act(() => vi.advanceTimersByTime(250));
    expect(screen.getByText('Thông báo toàn trang')).toBeInTheDocument();
  });

  it('waits while a transactional dialog is open', () => {
    vi.useFakeTimers();
    const close = vi.fn();
    const { rerender } = renderPopup(
      <ModalPortal isOpen onClose={close} ariaLabel="Modal nghiệp vụ"><button>Đóng nghiệp vụ</button></ModalPortal>
    );
    act(() => vi.advanceTimersByTime(500));
    expect(screen.queryByText('Thông báo toàn trang')).not.toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <ToastProvider>
          <OverlayProvider>
            <AuthToastTrigger />
            <GlobalAnnouncementPopup />
            <ToastViewport />
          </OverlayProvider>
        </ToastProvider>
      </MemoryRouter>
    );
    act(() => vi.advanceTimersByTime(250));
    expect(screen.getByText('Thông báo toàn trang')).toBeInTheDocument();
  });

  it('persists a two-hour snooze across remounts and shows again after expiry', () => {
    vi.useFakeTimers();
    const first = renderPopup();
    act(() => vi.advanceTimersByTime(250));
    fireEvent.click(screen.getByRole('button', { name: /Tắt trong 2 tiếng/ }));
    expect(screen.queryByText('Thông báo toàn trang')).not.toBeInTheDocument();
    expect(Number(localStorage.getItem('locket_popup_snoozed_until_v99'))).toBeGreaterThan(Date.now());

    first.unmount();
    renderPopup();
    act(() => vi.advanceTimersByTime(60 * 60 * 1000));
    expect(screen.queryByText('Thông báo toàn trang')).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(60 * 60 * 1000));
    act(() => vi.advanceTimersByTime(250));
    expect(screen.getByText('Thông báo toàn trang')).toBeInTheDocument();
  });
});
