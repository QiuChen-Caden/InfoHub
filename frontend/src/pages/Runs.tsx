import { useEffect, useState } from 'react';
import { api } from '../api';
import type { RunItem } from '../types';

export default function Runs() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.runs(100).then(setRuns).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-red-400">Error: {error}</p>;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Run History</h2>
      <div className="bg-card border border-border rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted text-xs uppercase">
              <th className="p-3">ID</th>
              <th className="p-3">Started</th>
              <th className="p-3">Finished</th>
              <th className="p-3">Hotlist</th>
              <th className="p-3">RSS</th>
              <th className="p-3">Dedup</th>
              <th className="p-3">New</th>
              <th className="p-3">Matched</th>
              <th className="p-3">Pushed</th>
              <th className="p-3">Errors</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              const rowColor = r.errors
                ? 'bg-red-900/10'
                : r.finished_at
                  ? ''
                  : 'bg-yellow-900/10';
              return (
                <tr key={r.id} className={`border-b border-border/50 ${rowColor}`}>
                  <td className="p-3">{r.id}</td>
                  <td className="p-3 text-xs text-muted whitespace-nowrap">
                    {r.started_at.replace('T', ' ').slice(0, 19)}
                  </td>
                  <td className="p-3 text-xs text-muted whitespace-nowrap">
                    {r.finished_at?.replace('T', ' ').slice(0, 19) ?? '—'}
                  </td>
                  <td className="p-3">{r.hotlist_count}</td>
                  <td className="p-3">{r.rss_count}</td>
                  <td className="p-3">{r.dedup_count}</td>
                  <td className="p-3">{r.new_count}</td>
                  <td className="p-3">{r.matched_count}</td>
                  <td className="p-3">{r.pushed_count}</td>
                  <td className="p-3 text-xs max-w-xs truncate">
                    {r.errors ? (
                      <span className="text-red-400">{r.errors}</span>
                    ) : (
                      <span className="text-green-400">OK</span>
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
