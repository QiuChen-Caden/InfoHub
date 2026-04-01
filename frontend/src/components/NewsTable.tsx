import type { NewsItem } from '../types';

interface Props {
  items: NewsItem[];
  compact?: boolean;
}

function safeHref(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return url;
  } catch {}
  return '#';
}

function scoreColor(score: number) {
  if (score >= 0.8) return 'text-positive';
  if (score >= 0.5) return 'text-accent';
  return 'text-accent/50';
}

export default function NewsTable({ items, compact }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-header-bg text-left text-accent text-xs uppercase">
            <th className="px-2 py-1">Title</th>
            <th className="px-2 py-1">Source</th>
            {!compact && <th className="px-2 py-1">Type</th>}
            <th className="px-2 py-1">Score</th>
            {!compact && <th className="px-2 py-1">Tags</th>}
            <th className="px-2 py-1">Time</th>
          </tr>
        </thead>
        <tbody>
          {items.map((n, i) => (
            <tr key={n.id} className={i % 2 === 0 ? 'bg-card' : 'bg-bg'}>
              <td className="px-2 py-1 max-w-xs truncate">
                <a
                  href={safeHref(n.url)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-link hover:underline"
                >
                  {n.title}
                </a>
              </td>
              <td className="px-2 py-1 text-accent/70">{n.source}</td>
              {!compact && (
                <td className="px-2 py-1 text-accent/70">{n.source_type}</td>
              )}
              <td className={`px-2 py-1 ${scoreColor(n.score)}`}>
                {n.score.toFixed(2)}
              </td>
              {!compact && <td className="px-2 py-1 text-accent/50 truncate max-w-[120px]">{n.tags}</td>}
              <td className="px-2 py-1 text-accent/50 whitespace-nowrap">
                {n.created_at.replace('T', ' ').slice(0, 16)}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={6} className="py-4 text-center text-accent/50">
                NO DATA
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
