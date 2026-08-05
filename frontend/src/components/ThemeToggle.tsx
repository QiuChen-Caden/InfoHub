import { useState } from 'react';
import { getStoredTheme, toggleTheme, type Theme } from '../theme';

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getStoredTheme);
  const isDay = theme === 'day';

  return (
    <button
      type="button"
      onClick={() => setTheme(current => toggleTheme(current))}
      className="border border-border px-2 py-0.5 text-xs text-accent hover:bg-accent/10 cursor-pointer"
      aria-label={isDay ? '切换到夜间版' : '切换到白天版'}
      title={isDay ? '切换到夜间版' : '切换到白天版'}
    >
      {isDay ? '夜间版' : '白天版'}
    </button>
  );
}
