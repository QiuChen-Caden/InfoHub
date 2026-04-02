import { useEffect, useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ReferenceLine,
} from 'recharts';
import { api } from '../api';
import type { RunItem } from '../types';

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

  // 计算均值用于参考线
  const avgMatched = Math.round(data.reduce((s, d) => s + d.matched, 0) / data.length);
  const avgPushed = Math.round(data.reduce((s, d) => s + d.pushed, 0) / data.length);

  // 最新一条数据用于右侧实时标签
  const latest = data[data.length - 1];

  const axisStyle = { fill: '#666666', fontSize: 9, fontFamily: 'JetBrains Mono, monospace' };
  const legendStyle = { fontSize: 9, fontFamily: 'JetBrains Mono, monospace' };

  return (
    <div className="space-y-2">
      {/* 顶部实时数据条 */}
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

      {/* HOTLIST / RSS / MATCHED — 面积图 */}
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

      {/* PUSHED COUNT — 柱状图 */}
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
    </div>
  );
}
