import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import type { RunItem } from '../types';

export default function Runs() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [error, setError] = useState('');

  const loadRuns = useCallback(() => {
    api.runs(100).then(setRuns).catch((e) => setError(e.message));
  }, []);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  // 如果有正在运行的任务（无 finished_at），每 5 秒轮询
  const hasRunning = runs.some(r => !r.finished_at);
  useEffect(() => {
    if (!hasRunning) return;
    const id = setInterval(loadRuns, 5000);
    return () => clearInterval(id);
  }, [hasRunning, loadRuns]);

  if (error) return <p className="text-negative">ERR: {error}</p>;

  return (
    <div className="bb-panel flex-1">
      <div className="bb-panel-header">RUN HISTORY</div>
      <div className="bb-panel-body overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0">
            <tr className="bg-header-bg text-left text-accent text-xs uppercase">
              <th className="px-2 py-1">ID</th>
              <th className="px-2 py-1">STARTED</th>
              <th className="px-2 py-1">FINISHED</th>
              <th className="px-2 py-1">HOT</th>
              <th className="px-2 py-1">RSS</th>
              <th className="px-2 py-1">DDP</th>
              <th className="px-2 py-1">NEW</th>
              <th className="px-2 py-1">MTCH</th>
              <th className="px-2 py-1">PUSH</th>
              <th className="px-2 py-1">STATUS</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r, i) => {
              const rowBg = r.errors
                ? 'bg-negative/10'
                : !r.finished_at
                  ? 'bg-accent/10'
                  : i % 2 === 0 ? 'bg-card' : 'bg-bg';
              return (
                <tr key={r.id} className={rowBg}>
                  <td className="px-2 py-1">{r.id}</td>
                  <td className="px-2 py-1 text-accent/70 whitespace-nowrap">
                    {r.started_at.replace('T', ' ').slice(0, 19)}
                  </td>
                  <td className="px-2 py-1 text-accent/70 whitespace-nowrap">
                    {r.finished_at?.replace('T', ' ').slice(0, 19) ?? '—'}
                  </td>
                  <td className="px-2 py-1">{r.hotlist_count}</td>
                  <td className="px-2 py-1">{r.rss_count}</td>
                  <td className="px-2 py-1">{r.dedup_count}</td>
                  <td className="px-2 py-1">{r.new_count}</td>
                  <td className="px-2 py-1">{r.matched_count}</td>
                  <td className="px-2 py-1">{r.pushed_count}</td>
                  <td className="px-2 py-1">
                    {r.errors ? (
                      <span className="text-negative">ERR</span>
                    ) : !r.finished_at ? (
                      <span className="text-accent">RUN</span>
                    ) : (
                      <span className="text-positive">OK</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
