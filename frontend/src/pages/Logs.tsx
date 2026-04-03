import { useEffect, useState, useRef, useCallback } from 'react';
import { getToken } from '../auth';

interface LogEntry {
  ts: string;
  level: string;
  msg: string;
  run_id?: number;
  type?: string;
}

const LEVEL_COLORS: Record<string, string> = {
  INFO: 'text-positive',
  WARNING: 'text-yellow-400',
  ERROR: 'text-negative',
  DEBUG: 'text-accent/50',
};

const BASE = import.meta.env.VITE_API_BASE ?? '';

export default function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // 加载历史日志
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetch(`${BASE}/api/v1/logs/history`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.logs?.length) {
          setLogs(data.logs.filter((l: LogEntry) => l.type !== 'end'));
        }
      })
      .catch(() => {});
  }, []);

  // 自动滚动
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const startStream = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const token = getToken();
    if (!token) return;

    setConnected(true);

    fetch(`${BASE}/api/v1/logs/stream`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok || !res.body) {
          setConnected(false);
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const entry: LogEntry = JSON.parse(line.slice(6));
              if (entry.type === 'end') {
                setConnected(false);
                return;
              }
              setLogs((prev) => {
                const next = [...prev, entry];
                return next.length > 1000 ? next.slice(-1000) : next;
              });
            } catch {
              // 忽略解析失败
            }
          }
        }
        setConnected(false);
      })
      .catch(() => {
        setConnected(false);
      });
  }, []);

  const stopStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setConnected(false);
  }, []);

  // 自动连接
  useEffect(() => {
    startStream();
    return () => stopStream();
  }, [startStream, stopStream]);

  return (
    <div className="bb-panel flex flex-col h-full">
      <div className="bb-panel-header flex items-center justify-between">
        <span>PIPELINE LOGS</span>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="accent-accent"
            />
            <span className="text-accent/70">AUTO-SCROLL</span>
          </label>
          <button
            onClick={connected ? stopStream : startStream}
            className={`px-2 py-0.5 text-xs font-bold ${
              connected
                ? 'bg-negative/20 text-negative hover:bg-negative/30'
                : 'bg-accent/20 text-accent hover:bg-accent/30'
            }`}
          >
            {connected ? 'DISCONNECT' : 'CONNECT'}
          </button>
          <button
            onClick={() => setLogs([])}
            className="px-2 py-0.5 text-xs font-bold text-accent/50 hover:text-accent"
          >
            CLEAR
          </button>
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? 'bg-positive animate-pulse' : 'bg-accent/30'
            }`}
          />
        </div>
      </div>
      <div className="bb-panel-body flex-1 overflow-y-auto font-mono text-xs leading-5 p-2 bg-[#0a0e14]">
        {logs.length === 0 && (
          <p className="text-accent/30 text-center mt-8">
            {connected ? 'Waiting for logs...' : 'No logs. Trigger a RUN to see output.'}
          </p>
        )}
        {logs.map((entry, i) => (
          <div key={i} className="flex gap-2 hover:bg-white/5">
            <span className="text-accent/40 shrink-0">{entry.ts}</span>
            <span className={`shrink-0 w-12 ${LEVEL_COLORS[entry.level] || 'text-accent'}`}>
              {entry.level?.slice(0, 4).padEnd(4)}
            </span>
            {entry.run_id != null && (
              <span className="text-accent/30 shrink-0">#{entry.run_id}</span>
            )}
            <span className="text-accent/90 break-all">{entry.msg}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
