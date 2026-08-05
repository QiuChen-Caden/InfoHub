let _cachedTz: string | null = null;

export function setTimezone(tz: string) {
  _cachedTz = tz;
}

export function getTimezone(): string {
  return _cachedTz || 'Asia/Shanghai';
}

export function formatTime(isoStr: string | null | undefined, seconds = false): string {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    const fmt = new Intl.DateTimeFormat('sv-SE', {
      timeZone: getTimezone(),
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      ...(seconds ? { second: '2-digit' } : {}),
      hour12: false,
    });
    return fmt.format(d);
  } catch {
    return isoStr.replace('T', ' ').slice(0, seconds ? 19 : 16);
  }
}
