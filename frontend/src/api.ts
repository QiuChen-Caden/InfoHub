import type { NewsItem, RunItem, Stats, ConfigData } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  stats: () => get<Stats>('/api/stats'),
  news: (params: { limit?: number; offset?: number; source_type?: string; tag?: string }) => {
    const sp = new URLSearchParams();
    if (params.limit) sp.set('limit', String(params.limit));
    if (params.offset) sp.set('offset', String(params.offset));
    if (params.source_type) sp.set('source_type', params.source_type);
    if (params.tag) sp.set('tag', params.tag);
    return get<NewsItem[]>(`/api/news?${sp}`);
  },
  runs: (limit = 20) => get<RunItem[]>(`/api/runs?limit=${limit}`),
  config: () => get<ConfigData>('/api/config'),
};
