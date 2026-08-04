import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import { formatTime } from '../tz';
import type { Stats, RunItem, NewsItem } from '../types';
import StatCard from '../components/StatCard';
import NewsTable from '../components/NewsTable';

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [error, setError] = useState('');
  const [triggerMsg, setTriggerMsg] = useState('');
  const [triggering, setTriggering] = useState(false);
  const [polling, setPolling] = useState(false);

  const loadData = useCallback(() => {
    Promise.allSettled([api.newsStats(), api.runs(5), api.news({ limit: 10 })])
      .then(([sRes, rRes, nRes]) => {
        if (sRes.status === 'fulfilled') setStats(sRes.value);
        if (rRes.status === 'fulfilled') setRuns(rRes.value);
        if (nRes.status === 'fulfilled') setNews(nRes.value);
        const failures = [sRes, rRes, nRes].filter(r => r.status === 'rejected');
        if (failures.length === 3) {
          setError((failures[0] as PromiseRejectedResult).reason?.message || '加载失败');
        }
      });
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // 触发后轮询，直到最新 run 完成
  useEffect(() => {
    if (!polling) return;
    const id = setInterval(() => {
      api.runs(5).then(latestRuns => {
        setRuns(latestRuns);
        const newest = latestRuns[0];
        if (newest?.finished_at) {
          setPolling(false);
          setTriggerMsg(newest.errors ? '运行失败' : '运行完成');
          // 刷新全部数据
          loadData();
        }
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, [polling, loadData]);

  const handleTrigger = () => {
    setTriggerMsg('');
    setTriggering(true);
    api.triggerRun()
      .then(() => {
        setTriggerMsg('运行中...');
        setPolling(true);
        // 1 秒后刷新，此时 DB 已有 RunHistory 行
        setTimeout(loadData, 1000);
      })
      .catch((e) => setTriggerMsg('错误: ' + e.message))
      .finally(() => setTriggering(false));
  };

  if (error) return <p className="text-negative">错误: {error}</p>;
  if (!stats) return <p className="text-accent/50">加载中...</p>;

  return (
    <div className="flex flex-col gap-2 h-full">
      {/* Row 1: Stats + Trigger */}
      <div className="grid grid-cols-6 gap-2 shrink-0">
        <StatCard label="新闻总数" value={stats.total_news} />
        <StatCard label="运行总数" value={stats.total_runs} />
        <StatCard label="最近运行" value={formatTime(stats.latest_run)} />
        <StatCard label="热榜" value={stats.hotlist_total} />
        <StatCard label="RSS" value={stats.rss_total} />
        <div className="bb-panel flex flex-col">
          <div className="bb-panel-header">控制</div>
          <div className="bb-panel-body flex-1 flex flex-col items-center justify-center gap-1">
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="px-3 py-1 text-xs font-bold bg-accent text-black hover:bg-accent/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {triggering ? '[ 提交中... ]' : '[ 触发运行 ]'}
            </button>
            {triggerMsg && (
              <span className={`text-xs ${triggerMsg.startsWith('错误') ? 'text-negative' : 'text-positive'}`}>
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
          <div className="bb-panel-header">最近运行</div>
          <div className="bb-panel-body flex-1 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0">
                <tr className="bg-header-bg text-left text-accent text-xs uppercase">
                  <th className="px-2 py-1">ID</th>
                  <th className="px-2 py-1">开始时间</th>
                  <th className="px-2 py-1">匹配</th>
                  <th className="px-2 py-1">推送</th>
                  <th className="px-2 py-1">状态</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r, i) => (
                  <tr key={r.id} className={i % 2 === 0 ? 'bg-card' : 'bg-bg'}>
                    <td className="px-2 py-1">{r.id}</td>
                    <td className="px-2 py-1 text-accent/70">{formatTime(r.started_at)}</td>
                    <td className="px-2 py-1">{r.matched_count}</td>
                    <td className="px-2 py-1">{r.pushed_count}</td>
                    <td className="px-2 py-1">
                      {r.errors ? (
                        <span className="text-negative">错误</span>
                      ) : r.finished_at ? (
                        <span className="text-positive">成功</span>
                      ) : (
                        <span className="text-accent">运行中</span>
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
          <div className="bb-panel-header">最新新闻</div>
          <div className="bb-panel-body flex-1 overflow-y-auto">
            <NewsTable items={news} compact />
          </div>
        </div>
      </div>
    </div>
  );
}
