import type { NewsItem } from '../types';

interface Props {
  items: NewsItem[];
  compact?: boolean;
}

function scoreBadge(score: number) {
  if (score >= 0.8) return 'bg-green-900/50 text-green-400';
  if (score >= 0.5) return 'bg-yellow-900/50 text-yellow-400';
  return 'bg-gray-800 text-muted';
}

export default function NewsTable({ items, compact }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted text-xs uppercase">
            <th className="pb-2 pr-4">Title</th>
            <th className="pb-2 pr-4">Source</th>
            {!compact && <th className="pb-2 pr-4">Type</th>}
            <th className="pb-2 pr-4">Score</th>
            {!compact && <th className="pb-2 pr-4">Tags</th>}
            <th className="pb-2">Time</th>
          </tr>
        </thead>
        <tbody>
          {items.map((n) => (
            <tr key={n.id} className="border-b border-border/50 hover:bg-white/[0.02]">
              <td className="py-2 pr-4 max-w-xs truncate">
                <a
                  href={n.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent hover:underline"
                >
                  {n.title}
                </a>
              </td>
              <td className="py-2 pr-4 text-muted">{n.source}</td>
              {!compact && (
                <td className="py-2 pr-4">
                  <span className="px-2 py-0.5 rounded text-xs bg-accent/15 text-accent">
                    {n.source_type}
                  </span>
                </td>
              )}
              <td className="py-2 pr-4">
                <span className={`px-2 py-0.5 rounded text-xs ${scoreBadge(n.score)}`}>
                  {n.score.toFixed(2)}
                </span>
              </td>
              {!compact && <td className="py-2 pr-4 text-muted text-xs">{n.tags}</td>}
              <td className="py-2 text-muted text-xs whitespace-nowrap">
                {n.created_at.replace('T', ' ').slice(0, 16)}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={6} className="py-8 text-center text-muted">
                No data
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
