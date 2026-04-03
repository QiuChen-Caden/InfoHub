import { useEffect, useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ReferenceLine,
} from 'recharts';
import { api } from '../api';
import type { RunItem, UsageData } from '../types';

const COLORS = {
  hotlist: '#FF8C00',
  rss: '#00FF00',
  matched: '#00FFFF',
  pushed: '#FF8C00',
  grid: '#1a1a1a',
  axis: '#555555',
  crosshair: '#FF8C00',
};

function BloombergTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-black border border-accent/60 px-2 py-1 text-xs font-mono">
      <div className="text-accent/70 border-b border-border pb-0.5 mb-0.5">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex justify-between gap-4">
          <span style={{ color: p.color }}>{p.dataKey.toUpperCase()}</span>
          <span style={{ color: p.color }} className="font-bold">{p.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

export default function Usage() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.allSettled([
      api.runs(50),
      api.usage(),
    ]).then(([rRes, uRes]) => {
      if (rRes.status === 'fulfilled') setRuns([...rRes.value].reverse());
      if (uRes.status === 'fulfilled') setUsage(uRes.value);
      if (rRes.status === 'rejected' && uRes.status === 'rejected') {
        setError((rRes as PromiseRejectedResult).reason?.message || 'Load failed');
      }
    });
  }, []);

  if (error) return <p className="text-negative">ERR: {error}</p>;
  if (!runs.length && !usage) return <p className="text-accent/50">LOADING...</p>;

  const data = runs.map((r) => ({
    run: `#${r.id}`,
    hotlist: r.hotlist_count,
    rss: r.rss_count,
    matched: r.matched_count,
    pushed: r.pushed_count,
  }));

  const avgMatched = data.length ? Math.round(data.reduce((s, d) => s + d.matched, 0) / data.length) : 0;
  const avgPushed = data.length ? Math.round(data.reduce((s, d) => s + d.pushed, 0) / data.length) : 0;
  const latest = data.length ? data[data.length - 1] : null;

  const axisStyle = { fill: '#666666', fontSize: 9, fontFamily: 'JetBrains Mono, monospace' };
  const legendStyle = { fontSize: 9, fontFamily: 'JetBrains Mono, monospace' };

  return (
    <div className="space-y-2">
      {/* Usage metering panel */}
      {usage && (
        <div className="bb-panel">
          <div className="bb-panel-header">PLAN &amp; USAGE</div>
          <div className="bb-panel-body text-xs space-y-2">
            <div className="flex items-center gap-4">
              <span className="text-accent/70">PLAN:</span>
              <span className="text-accent font-bold">{usage.plan.toUpperCase()}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries(usage.usage).map(([action, info]) => {
                const pct = info.limit > 0 ? Math.min(100, Math.round((info.count / info.limit) * 100)) : 0;
                return (
                  <div key={action} className="border border-border p-2">
                    <div className="text-accent/70 mb-1">{action.toUpperCase()}</div>
                    <div className="text-accent font-bold">{info.count} / {info.limit}</div>
                    <div className="w-full bg-border h-1 mt-1">
                      <div className={`h-1 ${pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-yellow-500' : 'bg-green-500'}`} style={{ width: `${pct}%` }} />
                    </div>
                    {(info.overage_cost_cents ?? 0) > 0 && (
                      <div className="text-negative mt-0.5">OVERAGE: ${((info.overage_cost_cents ?? 0) / 100).toFixed(2)}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Latest run data bar */}
      {latest && (
        <div className="bb-panel">
          <div className="bb-panel-body flex items-center gap-4 text-xs py-1">
            <span className="text-accent/50">LATEST RUN {latest.run}</span>
            <span className="text-accent/30">|</span>
            <span style={{ color: COLORS.hotlist }}>HOTLIST <span className="font-bold">{latest.hotlist}</span></span>
            <span style={{ color: COLORS.rss }}>RSS <span className="font-bold">{latest.rss}</span></span>
            <span style={{ color: COLORS.matched }}>MATCHED <span className="font-bold">{latest.matched}</span></span>
            <span style={{ color: COLORS.pushed }}>PUSHED <span className="font-bold">{latest.pushed}</span></span>
            <span className="text-accent/30">|</span>
            <span className="text-accent/50">AVG MATCHED <span className="text-link">{avgMatched}</span></span>
            <span className="text-accent/50">AVG PUSHED <span className="text-accent">{avgPushed}</span></span>
          </div>
        </div>
      )}

      {/* HOTLIST / RSS / MATCHED area chart */}
      {data.length > 0 && (
        <div className="bb-panel">
          <div className="bb-panel-header flex items-center justify-between">
            <span>HOTLIST / RSS / MATCHED PER RUN</span>
            <span className="text-accent/40 text-[9px] font-normal tracking-normal">AREA CHART &middot; {data.length} RUNS</span>
          </div>
          <div className="bb-panel-body" style={{ background: 'linear-gradient(180deg, #0a0a0a 0%, #000000 100%)' }}>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradHotlist" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COLORS.hotlist} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={COLORS.hotlist} stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="gradRss" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COLORS.rss} stopOpacity={0.2} />
                    <stop offset="100%" stopColor={COLORS.rss} stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="gradMatched" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COLORS.matched} stopOpacity={0.2} />
                    <stop offset="100%" stopColor={COLORS.matched} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={COLORS.grid} strokeDasharray="none" vertical={false} />
                <XAxis dataKey="run" tick={axisStyle} axisLine={{ stroke: '#333' }} tickLine={false} />
                <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
                <Tooltip content={<BloombergTooltip />} cursor={{ stroke: COLORS.crosshair, strokeWidth: 1, strokeDasharray: '3 3' }} />
                <Legend wrapperStyle={legendStyle} formatter={(v: string) => <span style={{ color: '#888', fontSize: 9 }}>{v.toUpperCase()}</span>} />
                <ReferenceLine y={avgMatched} stroke={COLORS.matched} strokeDasharray="6 3" strokeOpacity={0.4} label={{ value: `AVG ${avgMatched}`, fill: COLORS.matched, fontSize: 9, position: 'right' }} />
                <Area type="monotone" dataKey="hotlist" stroke={COLORS.hotlist} strokeWidth={1.5} fill="url(#gradHotlist)" dot={false} activeDot={{ r: 3, stroke: COLORS.hotlist, fill: '#000' }} />
                <Area type="monotone" dataKey="rss" stroke={COLORS.rss} strokeWidth={1.5} fill="url(#gradRss)" dot={false} activeDot={{ r: 3, stroke: COLORS.rss, fill: '#000' }} />
                <Area type="monotone" dataKey="matched" stroke={COLORS.matched} strokeWidth={1.5} fill="url(#gradMatched)" dot={false} activeDot={{ r: 3, stroke: COLORS.matched, fill: '#000' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* PUSHED COUNT bar chart */}
      {data.length > 0 && (
        <div className="bb-panel">
          <div className="bb-panel-header flex items-center justify-between">
            <span>PUSHED COUNT PER RUN</span>
            <span className="text-accent/40 text-[9px] font-normal tracking-normal">BAR CHART &middot; {data.length} RUNS</span>
          </div>
          <div className="bb-panel-body" style={{ background: 'linear-gradient(180deg, #0a0a0a 0%, #000000 100%)' }}>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradPushed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COLORS.pushed} stopOpacity={0.9} />
                    <stop offset="100%" stopColor={COLORS.pushed} stopOpacity={0.4} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={COLORS.grid} strokeDasharray="none" vertical={false} />
                <XAxis dataKey="run" tick={axisStyle} axisLine={{ stroke: '#333' }} tickLine={false} />
                <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
                <Tooltip content={<BloombergTooltip />} cursor={{ fill: 'rgba(255,140,0,0.06)' }} />
                <ReferenceLine y={avgPushed} stroke={COLORS.pushed} strokeDasharray="6 3" strokeOpacity={0.4} label={{ value: `AVG ${avgPushed}`, fill: COLORS.pushed, fontSize: 9, position: 'right' }} />
                <Bar dataKey="pushed" fill="url(#gradPushed)" maxBarSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}