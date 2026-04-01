import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import type { Stats, RunItem, NewsItem } from '../types';
import StatCard from '../components/StatCard';
import NewsTable from '../components/NewsTable';

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [error, setError] = useState('');
  const [running, setRunning] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState('');

  const loadData = useCallback(() => {
    Promise.all([api.stats(), api.runs(5), api.news({ limit: 10 })])
      .then(([s, r, n]) => { setStats(s); setRuns(r); setNews(n); })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    loadData();
    api.triggerStatus().then((s) => setRunning(s.running)).catch(() => {});
  }, [loadData]);

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      api.triggerStatus().then((s) => {
        if (!s.running) {
          setRunning(false);
          setTriggerMsg(s.last_error ? `ERR: ${s.last_error}` : 'RUN COMPLETE');
          loadData();
        }
      });
    }, 3000);
    return () => clearInterval(id);
  }, [running, loadData]);

  const handleTrigger = () => {
    setTriggerMsg('');
    api.triggerRun()
      .then(() => { setRunning(true); setTriggerMsg('RUN STARTED...'); })
      .catch((e) => setTriggerMsg(e.message));
  };

  if (error) return <p className="text-negative">ERR: {error}</p>;
  if (!stats) return <p className="text-accent/50">LOADING...</p>;

  return (
    <div className="flex flex-col gap-2 h-full">
      {/* Row 1: Stats + Trigger */}
      <div className="grid grid-cols-6 gap-2 shrink-0">
        <StatCard label="TOTAL NEWS" value={stats.total_news} />
        <StatCard label="TOTAL RUNS" value={stats.total_runs} />
        <StatCard label="LATEST RUN" value={stats.latest_run?.replace('T', ' ').slice(0, 16) ?? '—'} />
        <StatCard label="HOTLIST" value={stats.hotlist_total} />
        <StatCard label="RSS" value={stats.rss_total} />
        <div className="bb-panel flex flex-col">
          <div className="bb-panel-header">CONTROL</div>
          <div className="bb-panel-body flex-1 flex flex-col items-center justify-center gap-1">
            <button
              onClick={handleTrigger}
              disabled={running}
              className="px-3 py-1 text-xs font-bold bg-accent text-black hover:bg-accent/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? '[ RUNNING... ]' : '[ TRIGGER RUN ]'}
            </button>
            {triggerMsg && (
              <span className={`text-xs ${triggerMsg.startsWith('ERR') ? 'text-negative' : 'text-positive'}`}>
                {triggerMsg}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Row 2: Runs + News side by side */}
      <div className="grid grid-cols-2 gap-2 flex-1 min-h-0">
        {/* Recent Runs */}
        <div className="bb-panel flex flex-col min-h-0">
          <div className="bb-panel-header">RECENT RUNS</div>
          <div className="bb-panel-body flex-1 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0">
                <tr className="bg-header-bg text-left text-accent text-xs uppercase">
                  <th className="px-2 py-1">ID</th>
                  <th className="px-2 py-1">STARTED</th>
                  <th className="px-2 py-1">MTCH</th>
                  <th className="px-2 py-1">PUSH</th>
                  <th className="px-2 py-1">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r, i) => (
                  <tr key={r.id} className={i % 2 === 0 ? 'bg-card' : 'bg-bg'}>
                    <td className="px-2 py-1">{r.id}</td>
                    <td className="px-2 py-1 text-accent/70">{r.started_at.replace('T', ' ').slice(0, 16)}</td>
                    <td className="px-2 py-1">{r.matched_count}</td>
                    <td className="px-2 py-1">{r.pushed_count}</td>
                    <td className="px-2 py-1">
                      {r.errors ? (
                        <span className="text-negative">ERR</span>
                      ) : r.finished_at ? (
                        <span className="text-positive">OK</span>
                      ) : (
                        <span className="text-accent">RUN</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Latest News */}
        <div className="bb-panel flex flex-col min-h-0">
          <div className="bb-panel-header">LATEST NEWS</div>
          <div className="bb-panel-body flex-1 overflow-y-auto">
            <NewsTable items={news} compact />
          </div>
        </div>
      </div>
    </div>
  );
}
