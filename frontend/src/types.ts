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

export interface ConfigData {
  platforms: string[];
  interests: string[];
  ai: {
    model: string;
    timeout: number;
    max_tokens: number;
    batch_size: number;
    min_score: number;
    summary_enabled: boolean;
  };
  notification: {
    channels: string[];
  };
  cron_schedule: string;
}
