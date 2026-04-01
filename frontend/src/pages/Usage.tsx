import { useEffect, useState } from 'react';
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { api } from '../api';
import type { RunItem } from '../types';

export default function Usage() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.runs(50).then((r) => setRuns([...r].reverse())).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-red-400">Error: {error}</p>;
  if (!runs.length) return <p className="text-muted">Loading...</p>;

  const data = runs.map((r) => ({
    run: `#${r.id}`,
    hotlist: r.hotlist_count,
    rss: r.rss_count,
    matched: r.matched_count,
    pushed: r.pushed_count,
  }));

  const axisStyle = { fill: '#8b949e', fontSize: 11 };

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Usage Trends</h2>

      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="text-sm text-muted uppercase mb-4">Hotlist / RSS / Matched per Run</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis dataKey="run" tick={axisStyle} />
            <YAxis tick={axisStyle} />
            <Tooltip
              contentStyle={{ backgroundColor: '#161b22', border: '1px solid #21262d', borderRadius: 6 }}
              labelStyle={{ color: '#c9d1d9' }}
            />
            <Legend />
            <Line type="monotone" dataKey="hotlist" stroke="#58a6ff" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="rss" stroke="#3fb950" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="matched" stroke="#d2a8ff" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="text-sm text-muted uppercase mb-4">Pushed Count per Run</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis dataKey="run" tick={axisStyle} />
            <YAxis tick={axisStyle} />
            <Tooltip
              contentStyle={{ backgroundColor: '#161b22', border: '1px solid #21262d', borderRadius: 6 }}
              labelStyle={{ color: '#c9d1d9' }}
            />
            <Bar dataKey="pushed" fill="#f0883e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
