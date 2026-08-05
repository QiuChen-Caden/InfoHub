export type Theme = 'night' | 'day';

const STORAGE_KEY = 'infohub-theme';

export function getStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'night';
  return window.localStorage.getItem(STORAGE_KEY) === 'day' ? 'day' : 'night';
}

export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return;
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme === 'day' ? 'light' : 'dark';
  window.localStorage.setItem(STORAGE_KEY, theme);
  window.dispatchEvent(new CustomEvent('infohub-theme-change', { detail: theme }));
}

export function toggleTheme(current: Theme): Theme {
  const next = current === 'day' ? 'night' : 'day';
  applyTheme(next);
  return next;
}
