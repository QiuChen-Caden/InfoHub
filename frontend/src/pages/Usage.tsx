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

  if (error) return <p className="text-negative">ERR: {error}</p>;
  if (!runs.length) return <p className="text-accent/50">LOADING...</p>;

  const data = runs.map((r) => ({
    run: `#${r.id}`,
    hotlist: r.hotlist_count,
    rss: r.rss_count,
    matched: r.matched_count,
    pushed: r.pushed_count,
  }));

  const axisStyle = { fill: '#FF8C00', fontSize: 10 };

  return (
    <div className="space-y-2">
      <div className="bb-panel">
        <div className="bb-panel-header">HOTLIST / RSS / MATCHED PER RUN</div>
        <div className="bb-panel-body">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333333" />
              <XAxis dataKey="run" tick={axisStyle} />
              <YAxis tick={axisStyle} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0a0a0a', border: '1px solid #333333' }}
                labelStyle={{ color: '#FF8C00' }}
              />
              <Legend />
              <Line type="monotone" dataKey="hotlist" stroke="#FF8C00" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="rss" stroke="#00FF00" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="matched" stroke="#00FFFF" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bb-panel">
        <div className="bb-panel-header">PUSHED COUNT PER RUN</div>
        <div className="bb-panel-body">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333333" />
              <XAxis dataKey="run" tick={axisStyle} />
              <YAxis tick={axisStyle} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0a0a0a', border: '1px solid #333333' }}
                labelStyle={{ color: '#FF8C00' }}
              />
              <Bar dataKey="pushed" fill="#FF8C00" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
