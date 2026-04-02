import type { NewsItem, RunItem, Stats, ConfigData, ConfigUpdateRequest } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function put<T>(path: string, body: unknown, headers?: Record<string, string>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  stats: () => get<Stats>('/api/stats'),
  news: (params: {
    limit?: number; offset?: number; source_type?: string;
    source?: string; tag?: string; min_score?: number; max_score?: number;
    start_date?: string; end_date?: string;
  }) => {
    const sp = new URLSearchParams();
    if (params.limit) sp.set('limit', String(params.limit));
    if (params.offset) sp.set('offset', String(params.offset));
    if (params.source_type) sp.set('source_type', params.source_type);
    if (params.source) sp.set('source', params.source);
    if (params.tag) sp.set('tag', params.tag);
    if (params.min_score != null) sp.set('min_score', String(params.min_score));
    if (params.max_score != null) sp.set('max_score', String(params.max_score));
    if (params.start_date) sp.set('start_date', params.start_date);
    if (params.end_date) sp.set('end_date', params.end_date);
    return get<NewsItem[]>(`/api/news?${sp}`);
  },
  newsSources: () => get<string[]>('/api/news/sources'),
  runs: (limit = 20) => get<RunItem[]>(`/api/runs?limit=${limit}`),
  config: () => get<ConfigData>('/api/config'),
  saveConfig: (data: ConfigUpdateRequest, secret: string) =>
    put<{ message: string }>('/api/config', data, { 'X-Config-Secret': secret }),
  triggerRun: () => post<{ message: string; triggered_at: string }>('/api/trigger'),
  triggerStatus: () => get<{ running: boolean; last_error: string; last_triggered: string }>('/api/trigger/status'),
};
