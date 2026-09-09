import React from 'react';

interface PhoneMockupProps {
  src: string;
  alt: string;
  priority?: boolean;
  className?: string;
  containerClassName?: string;
  badge?: string;
}

export const PhoneMockup: React.FC<PhoneMockupProps> = ({
  src,
  alt,
  priority = false,
  className = '',
  containerClassName = '',
  badge,
}) => {
  return (
    <div className={`relative ${containerClassName}`}>
      {/* Phone chassis */}
      <div className={`relative mx-auto rounded-[2.5rem] sm:rounded-[2.85rem] border-[5px] sm:border-[6px] border-zinc-800 dark:border-zinc-700/80 bg-zinc-950 p-1.5 sm:p-2 shadow-xl dark:shadow-2xl transition-shadow ${className}`}>
        {/* Screen container: Strictly aspect-[1178/2560] to prevent any layout shift or distortion */}
        <div className="relative aspect-[1178/2560] w-full overflow-hidden rounded-[2rem] sm:rounded-[2.35rem] bg-zinc-950 flex items-center justify-center">
          <img
            src={src}
            alt={alt}
            width={1178}
            height={2560}
            loading={priority ? 'eager' : 'lazy'}
            decoding="async"
            fetchPriority={priority ? 'high' : 'auto'}
            className="h-full w-full object-contain select-none pointer-events-none"
          />

          {badge && (
            <div className="absolute bottom-3 left-3 right-3 rounded-xl bg-zinc-900/85 backdrop-blur-md px-3 py-1.5 text-center text-[10px] sm:text-xs font-medium text-zinc-200 border border-zinc-700/60 shadow-md">
              {badge}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
