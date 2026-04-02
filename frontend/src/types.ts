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

export interface ConfigData {
  platforms: string[];
  interests: string[];
  ai: {
    model: string;
    api_key: string;
    api_base: string;
    timeout: number;
    max_tokens: number;
    batch_size: number;
    batch_interval: number;
    min_score: number;
    summary_enabled: boolean;
  };
  notification: {
    channels: string[];
    batch_interval: number;
    telegram_bot_token: string;
    telegram_chat_id: string;
    feishu_webhook_url: string;
    dingtalk_webhook_url: string;
    email_from: string;
    email_password: string;
    email_to: string;
    slack_webhook_url: string;
  };
  sources: {
    rsshub_feeds: RSSHubFeed[];
    external_feeds: ExternalFeed[];
  };
  cron_schedule: string;
  rsshub_url: string;
  miniflux_url: string;
  obsidian_vault_path: string;
}

export interface ConfigUpdateRequest {
  platforms: string[];
  interests: string[];
  ai: {
    model: string;
    api_key: string;
    api_base: string;
    timeout: number;
    max_tokens: number;
    batch_size: number;
    batch_interval: number;
    min_score: number;
    summary_enabled: boolean;
  };
  notification: {
    batch_interval: number;
    telegram_bot_token: string;
    telegram_chat_id: string;
    feishu_webhook_url: string;
    dingtalk_webhook_url: string;
    email_from: string;
    email_password: string;
    email_to: string;
    slack_webhook_url: string;
  };
  sources: {
    rsshub_feeds: RSSHubFeed[];
    external_feeds: ExternalFeed[];
  };
  cron_schedule: string;
  rsshub_url: string;
  miniflux_url: string;
  obsidian_vault_path: string;
}
