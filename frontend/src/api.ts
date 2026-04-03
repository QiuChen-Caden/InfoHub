import { getToken, clearToken } from './auth';
import type {
  NewsItem, RunItem, Stats, ConfigData, ConfigUpdateRequest,
  LoginRequest, RegisterRequest, TokenResponse, User, UsageData,
  ApiKeyItem, CreateApiKeyResponse,
} from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';
type RequestOptions = {
  redirectOn401?: boolean;
};

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

let _redirecting = false;
function handle401(res: Response, options?: RequestOptions) {
  if (res.status === 401 && options?.redirectOn401 !== false && !_redirecting) {
    _redirecting = true;
    clearToken();
    window.location.href = '/login';
  }
}

async function get<T>(path: string, options?: RequestOptions): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  handle401(res, options);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders() };
  const init: RequestInit = { method: 'POST', headers };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, init);
  handle401(res, options);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function put<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
  handle401(res, options);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function del<T>(path: string, options?: RequestOptions): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  handle401(res, options);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `${res.status} ${res.statusText}`);
  }
  // 处理 204 No Content
  if (res.status === 204) return {} as T;
  return res.json();
}

export const api = {
  // Auth (no JWT needed)
  login: (data: LoginRequest) =>
    post<TokenResponse>('/api/v1/auth/login', data, { redirectOn401: false }),
  register: (data: RegisterRequest) =>
    post<TokenResponse>('/api/v1/auth/register', data, { redirectOn401: false }),
  me: () => get<User>('/api/v1/auth/me'),

  // News
  newsStats: () => get<Stats>('/api/v1/news/stats'),
  newsSources: () => get<string[]>('/api/v1/news/sources'),
  news: (params: {
    limit?: number; offset?: number; source_type?: string; source?: string;
    tag?: string; min_score?: number; max_score?: number;
    start_date?: string; end_date?: string;
  }) => {
    const sp = new URLSearchParams();
    if (params.limit != null) sp.set('limit', String(params.limit));
    if (params.offset != null) sp.set('offset', String(params.offset));
    if (params.source_type) sp.set('source_type', params.source_type);
    if (params.source) sp.set('source', params.source);
    if (params.tag) sp.set('tag', params.tag);
    if (params.min_score != null) sp.set('min_score', String(params.min_score));
    if (params.max_score != null) sp.set('max_score', String(params.max_score));
    if (params.start_date) sp.set('start_date', params.start_date);
    if (params.end_date) sp.set('end_date', params.end_date);
    return get<NewsItem[]>(`/api/v1/news?${sp}`);
  },

  // Runs
  runs: (limit = 20) => get<RunItem[]>(`/api/v1/runs?limit=${limit}`),
  triggerRun: () => post<{ ok: boolean; message: string }>('/api/v1/runs'),

  // Config
  config: () => get<ConfigData>('/api/v1/config'),
  saveConfig: (data: ConfigUpdateRequest) =>
    put<{ ok: boolean }>('/api/v1/config', data),

  // Secrets
  listSecrets: () => get<{ keys: string[] }>('/api/v1/secrets'),
  storeSecret: (key_name: string, value: string) =>
    post<{ ok: boolean }>('/api/v1/secrets', { key_name, value }),
  deleteSecret: (key_name: string) =>
    del<{ ok: boolean }>(`/api/v1/secrets/${encodeURIComponent(key_name)}`),

  // Usage
  usage: () => get<UsageData>('/api/v1/usage'),

  // API Keys
  listApiKeys: () => get<ApiKeyItem[]>('/api/v1/auth/api-keys'),
  createApiKey: (name: string, expires_in_days?: number) =>
    post<CreateApiKeyResponse>('/api/v1/auth/api-keys', { name, expires_in_days }),
  deleteApiKey: (keyId: string) =>
    del<{ ok: boolean }>(`/api/v1/auth/api-keys/${encodeURIComponent(keyId)}`),
};
