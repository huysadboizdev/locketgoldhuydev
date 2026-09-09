import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

interface ThemeToggleProps {
  className?: string;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className = '' }) => {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
      onClick={toggleTheme}
      className={`relative inline-flex h-11 w-11 items-center justify-center rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/80 text-zinc-700 dark:text-zinc-200 shadow-sm transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/50 ${className}`}
    >
      {isDark ? (
        <Sun className="h-5 w-5 text-amber-400 transition-transform duration-200" />
      ) : (
        <Moon className="h-5 w-5 text-zinc-700 transition-transform duration-200" />
      )}
      <span className="sr-only">
        {isDark ? 'Giao diện tối đang bật. Bấm để đổi sang sáng.' : 'Giao diện sáng đang bật. Bấm để đổi sang tối.'}
      </span>
    </button>
  );
};
