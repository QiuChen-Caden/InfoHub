// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  plan: string;
  role: 'admin' | 'user' | string;
  created_at: string;
}

export interface AdminOverview {
  total_tenants: number;
  active_tenants: number;
  admin_tenants: number;
  total_news: number;
  hotlist_total: number;
  rss_total: number;
  total_runs: number;
  latest_run: string | null;
}

export interface AdminTenant {
  id: string;
  name: string;
  email: string;
  plan: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
  news_count: number;
  run_count: number;
  latest_run: string | null;
}

export interface AdminRun {
  id: number;
  tenant_id: string;
  tenant_email: string;
  started_at: string | null;
  finished_at: string | null;
  hotlist_count: number;
  rss_count: number;
  dedup_count: number;
  new_count: number;
  matched_count: number;
  pushed_count: number;
  errors: string;
}

export interface AdminTaskStatus {
  running_count: number;
  failed_count: number;
  recent_runs: AdminRun[];
}

export interface AdminTenantDetail {
  tenant: AdminTenant;
  config: Record<string, unknown>;
  stored_secret_keys: string[];
  recent_runs: AdminRun[];
}

export interface UsageData {
  plan: string;
  usage: Record<string, { count: number; limit: number; overage_cost_cents?: number }>;
  limits: Record<string, number>;
}

// News / Runs
export interface NewsItem {
  id: string;
  title: string;
  url: string;
  source: string;
  source_type: string;
  rank: number;
  score: number;
  tags: string;
  summary: string;
  pushed: boolean;
  created_at: string;
}

export interface RunItem {
  id: number;
  started_at: string;
  finished_at: string | null;
  hotlist_count: number;
  rss_count: number;
  dedup_count: number;
  new_count: number;
  matched_count: number;
  pushed_count: number;
  errors: string;
}

export interface Stats {
  total_news: number;
  total_runs: number;
  latest_run: string | null;
  hotlist_total: number;
  rss_total: number;
}

// Config types — matches backend ConfigResponse / ConfigUpdate
export interface ConfigData {
  platforms: string[];
  interests: string[];
  rsshub_feeds: RSSHubFeed[];
  external_feeds: ExternalFeed[];
  notification: Record<string, unknown>;
  ai_config: Record<string, unknown>;
  cron_schedule: string;
  timezone: string;
  obsidian_export: boolean;
}

export interface ConfigUpdateRequest {
  platforms?: string[];
  interests?: string[];
  rsshub_feeds?: RSSHubFeed[];
  external_feeds?: ExternalFeed[];
  notification?: Record<string, unknown>;
  ai_config?: Record<string, unknown>;
  cron_schedule?: string;
  timezone?: string;
  obsidian_export?: boolean;
}

export interface RSSHubFeed {
  route: string;
  name: string;
  category: string;
}

export interface ExternalFeed {
  url: string;
  name: string;
  category: string;
}

export interface ApiKeyItem {
  id: string;
  name: string;
  prefix: string;
  expires_at: string | null;
  created_at: string;
  is_active: boolean;
}

export interface CreateApiKeyResponse {
  key: string;
  id: string;
  name: string;
  prefix: string;
  expires_at: string | null;
}
