import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import { formatTime } from '../tz';
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

  if (error) return <p className="text-negative">错误: {error}</p>;

  return (
    <div className="bb-panel flex-1">
      <div className="bb-panel-header">运行历史</div>
      <div className="bb-panel-body overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0">
            <tr className="bg-header-bg text-left text-accent text-xs uppercase">
              <th className="px-2 py-1">ID</th>
              <th className="px-2 py-1">开始时间</th>
              <th className="px-2 py-1">结束时间</th>
              <th className="px-2 py-1">热榜</th>
              <th className="px-2 py-1">RSS</th>
              <th className="px-2 py-1">去重</th>
              <th className="px-2 py-1">新增</th>
              <th className="px-2 py-1">匹配</th>
              <th className="px-2 py-1">推送</th>
              <th className="px-2 py-1">状态</th>
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
                    {formatTime(r.started_at, true)}
                  </td>
                  <td className="px-2 py-1 text-accent/70 whitespace-nowrap">
                    {formatTime(r.finished_at, true)}
                  </td>
                  <td className="px-2 py-1">{r.hotlist_count}</td>
                  <td className="px-2 py-1">{r.rss_count}</td>
                  <td className="px-2 py-1">{r.dedup_count}</td>
                  <td className="px-2 py-1">{r.new_count}</td>
                  <td className="px-2 py-1">{r.matched_count}</td>
                  <td className="px-2 py-1">{r.pushed_count}</td>
                  <td className="px-2 py-1">
                    {r.errors ? (
                      <span className="text-negative">错误</span>
                    ) : !r.finished_at ? (
                      <span className="text-accent">运行中</span>
                    ) : (
                      <span className="text-positive">成功</span>
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
