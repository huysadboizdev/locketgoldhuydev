import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ToastViewport } from '../components/common/ToastViewport';
import { ToastProvider } from '../context/ToastContext';
import { useToast } from '../hooks/useToast';

const Trigger = () => {
  const toast = useToast();
  return (
    <>
      <span data-testid="auth-state">{toast.hasAuthToast ? 'busy' : 'idle'}</span>
      <button onClick={() => toast.success('Thành công')}>success</button>
      <button onClick={() => toast.error('Thất bại')}>error</button>
      <button onClick={() => toast.warning('Cảnh báo')}>warning</button>
      <button onClick={() => toast.info('Thông tin')}>info</button>
      <button onClick={() => toast.success('Đăng nhập', undefined, { channel: 'auth', duration: 1000 })}>auth</button>
    </>
  );
};

const setup = () => render(<ToastProvider><Trigger /><ToastViewport /></ToastProvider>);

describe('global toast system', () => {
  afterEach(() => vi.useRealTimers());

  it('renders distinct success, error, warning and info variants with a three-item viewport', () => {
    setup();
    for (const name of ['success', 'error', 'warning', 'info']) fireEvent.click(screen.getByRole('button', { name }));
    expect(document.querySelectorAll('[data-toast-type]')).toHaveLength(3);
    expect(screen.getByText('Thành công')).toBeInTheDocument();
    expect(screen.getByText('Thất bại')).toBeInTheDocument();
    expect(screen.getByText('Cảnh báo')).toBeInTheDocument();
    expect(screen.queryByText('Thông tin')).not.toBeInTheDocument();
  });

  it('tracks auth toasts and auto-dismisses them', () => {
    vi.useFakeTimers();
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'auth' }));
    expect(screen.getByTestId('auth-state')).toHaveTextContent('busy');
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByTestId('auth-state')).toHaveTextContent('idle');
  });

  it('pauses auto-dismiss while the toast is hovered', () => {
    vi.useFakeTimers();
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'auth' }));
    const item = screen.getByText('Đăng nhập').closest('[data-toast-type]')!;
    fireEvent.mouseEnter(item);
    act(() => vi.advanceTimersByTime(1500));
    expect(screen.getByText('Đăng nhập')).toBeInTheDocument();
    fireEvent.mouseLeave(item);
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.queryByText('Đăng nhập')).not.toBeInTheDocument();
  });
});
