import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReviewFormModal } from '../components/reviews/ReviewFormModal';
import { OverlayProvider } from '../context/OverlayContext';
import { ToastProvider } from '../context/ToastContext';

describe('ReviewFormModal image preview lifecycle', () => {
  it('allows submitting a star-only review without written content', async () => {
    const onSubmit = vi.fn(async () => ({ success: true, msg: 'ok' }));
    render(
      <ToastProvider>
        <OverlayProvider>
          <ReviewFormModal
            isOpen
            onClose={() => {}}
            myReview={null}
            onSubmit={onSubmit}
            onUpdate={async () => ({ success: true, msg: 'ok' })}
            onDelete={async () => ({ success: true, msg: 'ok' })}
          />
        </OverlayProvider>
      </ToastProvider>
    );

    fireEvent.click(screen.getByRole('radio', { name: '5 sao' }));
    fireEvent.click(screen.getByRole('button', { name: 'Gửi đánh giá' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(5, '', []));
  });

  it('keeps active previews alive and revokes each object URL exactly when removed or unmounted', () => {
    const createObjectURL = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValueOnce('blob:first')
      .mockReturnValueOnce('blob:second');
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    const { container, unmount } = render(
      <ToastProvider>
        <OverlayProvider>
          <ReviewFormModal
            isOpen
            onClose={() => {}}
            myReview={null}
            onSubmit={async () => ({ success: true, msg: 'ok' })}
            onUpdate={async () => ({ success: true, msg: 'ok' })}
            onDelete={async () => ({ success: true, msg: 'ok' })}
          />
        </OverlayProvider>
      </ToastProvider>
    );

    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [new File(['a'], 'a.png', { type: 'image/png' })] } });
    fireEvent.change(input, { target: { files: [new File(['b'], 'b.png', { type: 'image/png' })] } });

    expect(createObjectURL).toHaveBeenCalledTimes(2);
    expect(revokeObjectURL).not.toHaveBeenCalledWith('blob:first');

    const removeButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('button[title="Xóa ảnh này"]'));
    fireEvent.click(removeButtons[0]);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:first');

    unmount();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:second');
    createObjectURL.mockRestore();
    revokeObjectURL.mockRestore();
  });
});
