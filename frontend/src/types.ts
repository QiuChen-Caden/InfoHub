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
  created_at: string;
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
