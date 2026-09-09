import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ModalPortal } from '../components/common/ModalPortal';
import { OverlayProvider } from '../context/OverlayContext';

const renderWithOverlay = (ui: React.ReactNode) => render(<OverlayProvider>{ui}</OverlayProvider>);

describe('ModalPortal and overlay stack', () => {
  beforeEach(() => {
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
  });

  it('renders in document.body, focuses the dialog and restores body scroll', async () => {
    const { unmount } = renderWithOverlay(
      <ModalPortal isOpen onClose={() => {}} ariaLabel="Kiểm thử modal">
        <button>Thao tác đầu tiên</button>
      </ModalPortal>
    );

    const dialog = screen.getByRole('dialog', { name: 'Kiểm thử modal' });
    expect(document.body).toContainElement(dialog);
    expect(document.body.style.overflow).toBe('hidden');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Thao tác đầu tiên' })).toHaveFocus());

    unmount();
    expect(document.body.style.overflow).toBe('');
  });

  it('keeps scroll locked until every nested dialog has closed', () => {
    const Harness = () => {
      const [childOpen, setChildOpen] = useState(true);
      return (
        <>
          <ModalPortal isOpen onClose={() => {}} ariaLabel="Modal cha">
            <button>Cha</button>
          </ModalPortal>
          <ModalPortal isOpen={childOpen} onClose={() => setChildOpen(false)} ariaLabel="Modal con">
            <button onClick={() => setChildOpen(false)}>Đóng con</button>
          </ModalPortal>
        </>
      );
    };

    const { unmount } = renderWithOverlay(<Harness />);
    expect(document.body.style.overflow).toBe('hidden');
    fireEvent.click(screen.getByRole('button', { name: 'Đóng con' }));
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('');
  });

  it('Escape closes only the top-most dialog', async () => {
    const closeParent = vi.fn();
    const closeChild = vi.fn();
    renderWithOverlay(
      <>
        <ModalPortal isOpen onClose={closeParent} ariaLabel="Modal cha"><button>Cha</button></ModalPortal>
        <ModalPortal isOpen onClose={closeChild} ariaLabel="Modal con"><button>Con</button></ModalPortal>
      </>
    );

    await waitFor(() => expect(screen.getByRole('dialog', { name: 'Modal con' })).toHaveAttribute('tabindex', '-1'));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(closeChild).toHaveBeenCalledTimes(1);
    expect(closeParent).not.toHaveBeenCalled();
  });
});
