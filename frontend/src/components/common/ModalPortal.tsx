import React, { useEffect, useId } from 'react';
import { createPortal } from 'react-dom';
import { useScrollLock } from '../../hooks/useScrollLock';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { useOverlay, type OverlayKind } from '../../context/OverlayContext';

interface ModalPortalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  dismissible?: boolean;
  className?: string;
  overlayClassName?: string;
  backdropClassName?: string;
  layerKind?: OverlayKind;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  ariaDescribedBy?: string;
}

export const ModalPortal: React.FC<ModalPortalProps> = ({
  isOpen,
  onClose,
  children,
  dismissible = true,
  className = '',
  overlayClassName = '',
  backdropClassName = 'bg-black/60 backdrop-blur-sm',
  layerKind = 'dialog',
  ariaLabel,
  ariaLabelledBy,
  ariaDescribedBy,
}) => {
  const reactId = useId();
  const layerId = `overlay-${reactId}`;
  const { registerLayer, unregisterLayer, getLayerIndex, isTopLayer } = useOverlay();
  const topmost = isTopLayer(layerId);
  const containerRef = useFocusTrap<HTMLDivElement>(isOpen && topmost);
  useScrollLock(isOpen);

  useEffect(() => {
    if (!isOpen) {
      unregisterLayer(layerId);
      return;
    }
    registerLayer(layerId, layerKind);
    return () => unregisterLayer(layerId);
  }, [isOpen, layerId, layerKind, registerLayer, unregisterLayer]);

  useEffect(() => {
    if (!isOpen || !dismissible || !topmost) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [dismissible, isOpen, onClose, topmost]);

  if (!isOpen || typeof document === 'undefined') return null;

  const layerIndex = Math.max(0, getLayerIndex(layerId));

  return createPortal(
    <div
      className={`fixed inset-0 flex items-center justify-center p-4 sm:p-6 ${overlayClassName}`}
      style={{
        zIndex: 1000 + layerIndex * 10,
        minHeight: '100dvh',
        paddingTop: 'max(1rem, env(safe-area-inset-top))',
        paddingBottom: 'max(1rem, env(safe-area-inset-bottom))',
      }}
      data-overlay-kind={layerKind}
      data-overlay-top={topmost ? 'true' : 'false'}
    >
      {dismissible ? (
        <button
          type="button"
          aria-label="Đóng hộp thoại"
          tabIndex={-1}
          className={`absolute inset-0 cursor-default ${backdropClassName}`}
          onClick={topmost ? onClose : undefined}
        />
      ) : (
        <div aria-hidden="true" className={`absolute inset-0 ${backdropClassName}`} />
      )}
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-label={!ariaLabelledBy ? ariaLabel : undefined}
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
        tabIndex={-1}
        className={`relative z-10 flex w-full max-h-[calc(100dvh-2rem)] flex-col overflow-y-auto rounded-2xl bg-white shadow-2xl outline-none dark:bg-gray-900 ${className}`}
      >
        {children}
      </div>
    </div>,
    document.body
  );
};
