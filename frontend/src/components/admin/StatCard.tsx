import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  variant?: 'gold' | 'emerald' | 'blue' | 'purple' | 'rose' | 'zinc';
  trend?: {
    text: string;
    isPositive?: boolean;
  };
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = 'gold',
  trend,
}) => {
  const variantStyles = {
    gold: {
      border: 'border-amber-500/20 hover:border-amber-500/40',
      iconBg: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
      badge: 'bg-amber-500/10 text-amber-400',
    },
    emerald: {
      border: 'border-emerald-500/20 hover:border-emerald-500/40',
      iconBg: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
      badge: 'bg-emerald-500/10 text-emerald-400',
    },
    blue: {
      border: 'border-sky-500/20 hover:border-sky-500/40',
      iconBg: 'bg-sky-500/10 border-sky-500/20 text-sky-400',
      badge: 'bg-sky-500/10 text-sky-400',
    },
    purple: {
      border: 'border-purple-500/20 hover:border-purple-500/40',
      iconBg: 'bg-purple-500/10 border-purple-500/20 text-purple-400',
      badge: 'bg-purple-500/10 text-purple-400',
    },
    rose: {
      border: 'border-rose-500/20 hover:border-rose-500/40',
      iconBg: 'bg-rose-500/10 border-rose-500/20 text-rose-400',
      badge: 'bg-rose-500/10 text-rose-400',
    },
    zinc: {
      border: 'border-zinc-800 hover:border-zinc-700',
      iconBg: 'bg-zinc-800 border-zinc-700 text-zinc-300',
      badge: 'bg-zinc-800 text-zinc-400',
    },
  }[variant];

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border ${variantStyles.border} bg-zinc-900/80 p-5 shadow-lg backdrop-blur-md transition-all`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-zinc-400">{title}</span>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl border ${variantStyles.iconBg}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
          {value}
        </span>
        {trend && (
          <span
            className={`text-[11px] font-semibold ${
              trend.isPositive ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {trend.text}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="mt-1.5 text-xs text-zinc-500">
          {subtitle}
        </p>
      )}
    </div>
  );
};
