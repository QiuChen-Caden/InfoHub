import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Stats, RunItem, NewsItem } from '../types';
import StatCard from '../components/StatCard';
import NewsTable from '../components/NewsTable';

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.stats(), api.runs(5), api.news({ limit: 10 })])
      .then(([s, r, n]) => { setStats(s); setRuns(r); setNews(n); })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-red-400">Error: {error}</p>;
  if (!stats) return <p className="text-muted">Loading...</p>;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Dashboard</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard label="Total News" value={stats.total_news} />
        <StatCard label="Total Runs" value={stats.total_runs} />
        <StatCard label="Latest Run" value={stats.latest_run?.replace('T', ' ').slice(0, 16) ?? '—'} />
        <StatCard label="Hotlist" value={stats.hotlist_total} />
        <StatCard label="RSS" value={stats.rss_total} />
      </div>

      {/* Recent runs */}
      <section>
        <h3 className="text-sm font-semibold text-muted uppercase mb-3">Recent Runs</h3>
        <div className="bg-card border border-border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted text-xs uppercase">
                <th className="p-3">ID</th>
                <th className="p-3">Started</th>
                <th className="p-3">Matched</th>
                <th className="p-3">Pushed</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-b border-border/50">
                  <td className="p-3">{r.id}</td>
                  <td className="p-3 text-muted text-xs">{r.started_at.replace('T', ' ').slice(0, 16)}</td>
                  <td className="p-3">{r.matched_count}</td>
                  <td className="p-3">{r.pushed_count}</td>
                  <td className="p-3">
                    {r.errors ? (
                      <span className="text-red-400 text-xs">Error</span>
                    ) : r.finished_at ? (
                      <span className="text-green-400 text-xs">Done</span>
                    ) : (
                      <span className="text-yellow-400 text-xs">Running</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Latest news */}
      <section>
        <h3 className="text-sm font-semibold text-muted uppercase mb-3">Latest News</h3>
        <div className="bg-card border border-border rounded-lg p-4">
          <NewsTable items={news} compact />
        </div>
      </section>
    </div>
  );
}
