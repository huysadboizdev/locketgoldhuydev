import React, { useId } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Info, Bell, Sparkles, Gift, Tag, AlertTriangle, AlertCircle,
  CheckCircle2, Zap, Star, Crown, Shield, PartyPopper, HelpCircle,
  Wrench, X, ExternalLink, ChevronRight, Clock3,
} from 'lucide-react';
import { ModalPortal } from './ModalPortal';
import type { OverlayKind } from '../../context/OverlayContext';

export function renderPopupIcon(iconName?: string) {
  const iconProps = { className: 'h-7 w-7 text-zinc-950 stroke-[2.2]' };
  switch (iconName?.toLowerCase().replace(/_/g, '-')) {
    case 'bell': return <Bell {...iconProps} />;
    case 'sparkles': return <Sparkles {...iconProps} />;
    case 'gift': return <Gift {...iconProps} />;
    case 'party': return <PartyPopper {...iconProps} />;
    case 'tag': return <Tag {...iconProps} />;
    case 'warning': case 'alert-triangle': return <AlertTriangle {...iconProps} />;
    case 'error': case 'alert-circle': return <AlertCircle {...iconProps} />;
    case 'success': case 'check-circle': case 'check': return <CheckCircle2 {...iconProps} />;
    case 'help': case 'question': return <HelpCircle {...iconProps} />;
    case 'wrench': return <Wrench {...iconProps} />;
    case 'zap': return <Zap {...iconProps} />;
    case 'star': return <Star {...iconProps} />;
    case 'crown': return <Crown {...iconProps} />;
    case 'shield': return <Shield {...iconProps} />;
    case 'info': default: return <Info {...iconProps} />;
  }
}

interface AnnouncementDialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  message: string;
  icon?: string | null;
  buttonText?: string | null;
  buttonUrl?: string | null;
  dismissible?: boolean;
  layerKind?: OverlayKind;
  actionEnabled?: boolean;
  onSnooze?: () => void;
}

export const AnnouncementDialog: React.FC<AnnouncementDialogProps> = ({
  isOpen,
  onClose,
  title,
  message,
  icon,
  buttonText,
  buttonUrl,
  dismissible = true,
  layerKind = 'announcement',
  actionEnabled = true,
  onSnooze,
}) => {
  const navigate = useNavigate();
  const uniqueId = useId().replace(/:/g, '');
  const titleId = `announcement-title-${uniqueId}`;
  const messageId = `announcement-message-${uniqueId}`;

  const rawButtonUrl = (buttonUrl || '').trim();
  const containsUnsafeUrlChars = /[\u0000-\u0020\u007f]/.test(rawButtonUrl) || rawButtonUrl.includes('\\');
  const isSafeInternalUrl = rawButtonUrl.startsWith('/') && !rawButtonUrl.startsWith('//') && !containsUnsafeUrlChars;
  const isExternalUrl = rawButtonUrl.startsWith('https://') && !containsUnsafeUrlChars;
  const safeButtonUrl = isSafeInternalUrl || isExternalUrl ? rawButtonUrl : '';
  const hasButton = Boolean(buttonText && safeButtonUrl);

  const handleActionClick = () => {
    if (!actionEnabled || !safeButtonUrl) return;
    if (dismissible) onClose();
    if (isExternalUrl) window.open(safeButtonUrl, '_blank', 'noopener,noreferrer');
    else navigate(safeButtonUrl);
  };

  return (
    <ModalPortal
      isOpen={isOpen}
      onClose={onClose}
      dismissible={dismissible}
      layerKind={layerKind}
      ariaLabelledBy={titleId}
      ariaDescribedBy={messageId}
      backdropClassName="bg-black/50"
      className="max-w-lg overflow-hidden !rounded-3xl !border !border-amber-500/30 !bg-zinc-950 !text-white shadow-2xl shadow-amber-500/10"
    >
      <div className="relative flex max-h-[calc(100dvh-2rem)] flex-col overflow-hidden p-5 sm:p-8">
        <div className="pointer-events-none absolute -left-24 -top-24 h-48 w-48 rounded-full bg-amber-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -right-24 h-48 w-48 rounded-full bg-yellow-500/15 blur-3xl" />

        {dismissible && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng thông báo"
            className="absolute right-3 top-3 z-20 flex h-11 w-11 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900/80 text-zinc-400 transition hover:bg-zinc-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50 sm:right-4 sm:top-4"
          >
            <X className="h-4 w-4" />
          </button>
        )}

        <div className="relative z-10 flex min-h-0 flex-col items-center text-center">
          <div className="mb-4 flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-amber-500 via-amber-400 to-yellow-300 shadow-xl shadow-amber-500/25 ring-4 ring-amber-500/20">
            {renderPopupIcon(icon || undefined)}
          </div>
          <h2 id={titleId} className="px-8 text-xl font-black tracking-tight text-white sm:text-2xl">
            {title}
          </h2>
          <div
            id={messageId}
            className="custom-scrollbar mt-3 min-h-0 overflow-y-auto whitespace-pre-line px-1 text-sm leading-relaxed text-zinc-300 sm:text-base"
          >
            {message}
          </div>

          <div className="mt-6 flex w-full shrink-0 flex-col gap-2.5">
            {hasButton && (
              <button
                type="button"
                onClick={handleActionClick}
                aria-disabled={!actionEnabled}
                className={`group relative flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-amber-400 via-amber-500 to-yellow-500 px-5 py-3.5 font-bold text-zinc-950 shadow-lg shadow-amber-500/20 transition focus:outline-none focus:ring-2 focus:ring-amber-400 ${actionEnabled ? 'hover:brightness-105 active:scale-[0.99]' : 'cursor-default'}`}
              >
                <span>{buttonText}</span>
                {isExternalUrl ? <ExternalLink className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
            )}
            {dismissible && (
              <div className={`grid gap-2.5 ${onSnooze ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1'}`}>
                <button
                  type="button"
                  onClick={onClose}
                  className="min-h-11 w-full rounded-2xl border border-zinc-800 bg-zinc-900/60 px-4 py-2.5 text-xs font-medium text-zinc-400 transition hover:bg-zinc-800/80 hover:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-amber-400"
                >
                  {hasButton ? 'Để sau' : 'Đã hiểu'}
                </button>
                {onSnooze && (
                  <button
                    type="button"
                    onClick={onSnooze}
                    className="flex min-h-11 w-full items-center justify-center gap-1.5 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs font-semibold text-amber-300 transition hover:bg-amber-500/20 hover:text-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-400"
                  >
                    <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
                    Tắt trong 2 tiếng
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </ModalPortal>
  );
};
