"""Data storage layer for both legacy single-instance and new multitenant schemas."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List

from models import NewsItem

log = logging.getLogger("infohub.db")

LEGACY_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT DEFAULT '',
    source TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    rank INTEGER DEFAULT 0,
    published_at TEXT DEFAULT '',
    score REAL DEFAULT 0,
    tags TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    pushed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS run_history (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    hotlist_count INTEGER DEFAULT 0,
    rss_count INTEGER DEFAULT 0,
    dedup_count INTEGER DEFAULT 0,
    new_count INTEGER DEFAULT 0,
    matched_count INTEGER DEFAULT 0,
    pushed_count INTEGER DEFAULT 0,
    errors TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_news_created ON news(created_at);
CREATE INDEX IF NOT EXISTS idx_news_source_type ON news(source_type);
"""

LEGACY_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT DEFAULT '',
    source TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    rank INTEGER DEFAULT 0,
    published_at TEXT DEFAULT '',
    score REAL DEFAULT 0,
    tags TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    pushed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    hotlist_count INTEGER DEFAULT 0,
    rss_count INTEGER DEFAULT 0,
    dedup_count INTEGER DEFAULT 0,
    new_count INTEGER DEFAULT 0,
    matched_count INTEGER DEFAULT 0,
    pushed_count INTEGER DEFAULT 0,
    errors TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_news_created ON news(created_at);
CREATE INDEX IF NOT EXISTS idx_news_source_type ON news(source_type);
"""

MULTITENANT_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    owner_user_id TEXT REFERENCES app_users(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS workspace_settings (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    enabled BOOLEAN DEFAULT TRUE,
    cron_schedule TEXT DEFAULT '*/30 * * * *',
    rsshub_url TEXT DEFAULT '',
    miniflux_url TEXT DEFAULT '',
    obsidian_vault_path TEXT DEFAULT '',
    ai_model TEXT DEFAULT '',
    ai_api_base TEXT DEFAULT '',
    ai_timeout INTEGER DEFAULT 120,
    ai_max_tokens INTEGER DEFAULT 5000,
    ai_batch_size INTEGER DEFAULT 200,
    ai_batch_interval INTEGER DEFAULT 2,
    ai_min_score REAL DEFAULT 0.7,
    ai_summary_enabled BOOLEAN DEFAULT TRUE,
    notification_batch_interval INTEGER DEFAULT 2,
    email_from TEXT DEFAULT '',
    email_to TEXT DEFAULT '',
    platforms_json TEXT DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_secrets (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    ai_api_key TEXT DEFAULT '',
    miniflux_api_key TEXT DEFAULT '',
    telegram_bot_token TEXT DEFAULT '',
    telegram_chat_id TEXT DEFAULT '',
    feishu_webhook_url TEXT DEFAULT '',
    dingtalk_webhook_url TEXT DEFAULT '',
    email_password TEXT DEFAULT '',
    slack_webhook_url TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_interest_tags (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (workspace_id, tag)
);

CREATE TABLE IF NOT EXISTS workspace_feeds (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    feed_type TEXT NOT NULL,
    route TEXT DEFAULT '',
    url TEXT DEFAULT '',
    name TEXT NOT NULL,
    category TEXT DEFAULT '',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    job_type TEXT DEFAULT 'pipeline',
    enabled BOOLEAN DEFAULT TRUE,
    cron_schedule TEXT NOT NULL,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    job_id TEXT REFERENCES ingest_jobs(id) ON DELETE SET NULL,
    trigger_mode TEXT DEFAULT 'system',
    status TEXT DEFAULT 'pending',
    hotlist_count INTEGER DEFAULT 0,
    rss_count INTEGER DEFAULT 0,
    dedup_count INTEGER DEFAULT 0,
    new_count INTEGER DEFAULT 0,
    matched_count INTEGER DEFAULT 0,
    pushed_count INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS content_items (
    id TEXT PRIMARY KEY,
    canonical_url TEXT DEFAULT '',
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    content TEXT DEFAULT '',
    source TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_content_matches (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    content_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    score REAL DEFAULT 0,
    tags TEXT DEFAULT '',
    pushed BOOLEAN DEFAULT FALSE,
    matched_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (workspace_id, content_id)
);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL,
    quantity BIGINT DEFAULT 0,
    unit TEXT DEFAULT 'count',
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    period_key TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    limits_json TEXT DEFAULT '{}',
    price_monthly_cents INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
    plan_id TEXT REFERENCES plans(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'trialing',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    provider TEXT DEFAULT '',
    provider_customer_id TEXT DEFAULT '',
    provider_subscription_id TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_interest_tags_workspace ON workspace_interest_tags(workspace_id, position);
CREATE INDEX IF NOT EXISTS idx_workspace_feeds_workspace ON workspace_feeds(workspace_id, feed_type);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_workspace ON ingest_jobs(workspace_id, enabled);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_workspace ON ingest_runs(workspace_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_content_matches_workspace ON workspace_content_matches(workspace_id, matched_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_workspace ON usage_events(workspace_id, occurred_at DESC);
"""

MULTITENANT_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    owner_user_id TEXT REFERENCES app_users(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS workspace_settings (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    enabled INTEGER DEFAULT 1,
    cron_schedule TEXT DEFAULT '*/30 * * * *',
    rsshub_url TEXT DEFAULT '',
    miniflux_url TEXT DEFAULT '',
    obsidian_vault_path TEXT DEFAULT '',
    ai_model TEXT DEFAULT '',
    ai_api_base TEXT DEFAULT '',
    ai_timeout INTEGER DEFAULT 120,
    ai_max_tokens INTEGER DEFAULT 5000,
    ai_batch_size INTEGER DEFAULT 200,
    ai_batch_interval INTEGER DEFAULT 2,
    ai_min_score REAL DEFAULT 0.7,
    ai_summary_enabled INTEGER DEFAULT 1,
    notification_batch_interval INTEGER DEFAULT 2,
    email_from TEXT DEFAULT '',
    email_to TEXT DEFAULT '',
    platforms_json TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workspace_secrets (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    ai_api_key TEXT DEFAULT '',
    miniflux_api_key TEXT DEFAULT '',
    telegram_bot_token TEXT DEFAULT '',
    telegram_chat_id TEXT DEFAULT '',
    feishu_webhook_url TEXT DEFAULT '',
    dingtalk_webhook_url TEXT DEFAULT '',
    email_password TEXT DEFAULT '',
    slack_webhook_url TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workspace_interest_tags (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (workspace_id, tag)
);

CREATE TABLE IF NOT EXISTS workspace_feeds (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    feed_type TEXT NOT NULL,
    route TEXT DEFAULT '',
    url TEXT DEFAULT '',
    name TEXT NOT NULL,
    category TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    job_type TEXT DEFAULT 'pipeline',
    enabled INTEGER DEFAULT 1,
    cron_schedule TEXT NOT NULL,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    job_id TEXT REFERENCES ingest_jobs(id) ON DELETE SET NULL,
    trigger_mode TEXT DEFAULT 'system',
    status TEXT DEFAULT 'pending',
    hotlist_count INTEGER DEFAULT 0,
    rss_count INTEGER DEFAULT 0,
    dedup_count INTEGER DEFAULT 0,
    new_count INTEGER DEFAULT 0,
    matched_count INTEGER DEFAULT 0,
    pushed_count INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    started_at TEXT DEFAULT (datetime('now')),
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS content_items (
    id TEXT PRIMARY KEY,
    canonical_url TEXT DEFAULT '',
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    content TEXT DEFAULT '',
    source TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workspace_content_matches (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    content_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    score REAL DEFAULT 0,
    tags TEXT DEFAULT '',
    pushed INTEGER DEFAULT 0,
    matched_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (workspace_id, content_id)
);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL,
    quantity INTEGER DEFAULT 0,
    unit TEXT DEFAULT 'count',
    occurred_at TEXT DEFAULT (datetime('now')),
    period_key TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    limits_json TEXT DEFAULT '{}',
    price_monthly_cents INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
    plan_id TEXT REFERENCES plans(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'trialing',
    current_period_start TEXT,
    current_period_end TEXT,
    cancel_at_period_end INTEGER DEFAULT 0,
    provider TEXT DEFAULT '',
    provider_customer_id TEXT DEFAULT '',
    provider_subscription_id TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_interest_tags_workspace ON workspace_interest_tags(workspace_id, position);
CREATE INDEX IF NOT EXISTS idx_workspace_feeds_workspace ON workspace_feeds(workspace_id, feed_type);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_workspace ON ingest_jobs(workspace_id, enabled);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_workspace ON ingest_runs(workspace_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_content_matches_workspace ON workspace_content_matches(workspace_id, matched_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_workspace ON usage_events(workspace_id, occurred_at DESC);
"""


def _use_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def initialize_database_schema(conn, is_pg: bool):
    """Create the legacy tables and additive multitenant foundation tables."""
    if is_pg:
        cur = conn.cursor()
        try:
            cur.execute(LEGACY_PG_SCHEMA)
            cur.execute(MULTITENANT_PG_SCHEMA)
        finally:
            cur.close()
    else:
        conn.executescript(LEGACY_SQLITE_SCHEMA + "\n" + MULTITENANT_SQLITE_SCHEMA)


class Database:
    """Unified database access for the existing pipeline."""

    def __init__(self, output_dir: str):
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            import psycopg2

            self.conn = psycopg2.connect(db_url)
            self.conn.autocommit = False
            self._pg = True
            initialize_database_schema(self.conn, is_pg=True)
            self.conn.commit()
            log.info("Connected to PostgreSQL")
        else:
            import sqlite3

            db_path = Path(output_dir) / "infohub.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(db_path))
            initialize_database_schema(self.conn, is_pg=False)
            self._pg = False
            log.info(f"Connected to SQLite: {db_path}")

    def _execute(self, sql: str, params=None):
        """Run SQL with placeholder translation for PostgreSQL."""
        if self._pg:
            sql = sql.replace("?", "%s")
        cur = self.conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def filter_new(self, items: List[NewsItem]) -> List[NewsItem]:
        existing = set()
        cur = self._execute("SELECT id FROM news")
        for row in cur:
            existing.add(row[0])
        cur.close()
        return [it for it in items if it.id not in existing]

    def save_items(self, items: List[NewsItem]):
        sql = """INSERT INTO news
            (id, title, url, source, source_type, rank,
             published_at, score, tags, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        if self._pg:
            sql += " ON CONFLICT (id) DO NOTHING"
            sql = sql.replace("?", "%s")
        else:
            sql = "INSERT OR IGNORE INTO news" + sql[len("INSERT INTO news"):]
        for item in items:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    sql,
                    (
                        item.id,
                        item.title,
                        item.url,
                        item.source,
                        item.source_type,
                        item.rank,
                        item.published_at,
                        item.score,
                        ",".join(item.tags),
                        item.summary,
                    ),
                )
                cur.close()
            except Exception as e:
                log.error(f"Failed to save item: {item.title} - {e}")
        self.conn.commit()

    def mark_matched(self, items: List[NewsItem]):
        for item in items:
            self._execute(
                "UPDATE news SET score=?, tags=?, summary=? WHERE id=?",
                (item.score, ",".join(item.tags), item.summary, item.id),
            )
        self.conn.commit()

    def mark_pushed(self, item_ids: List[str]):
        for iid in item_ids:
            self._execute("UPDATE news SET pushed=1 WHERE id=?", (iid,))
        self.conn.commit()

    def start_run(self) -> int:
        now = datetime.utcnow().isoformat()
        if self._pg:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO run_history (started_at) VALUES (%s) RETURNING id",
                (now,),
            )
            run_id = cur.fetchone()[0]
            cur.close()
        else:
            cur = self.conn.execute(
                "INSERT INTO run_history (started_at) VALUES (?)",
                (now,),
            )
            run_id = cur.lastrowid
        self.conn.commit()
        return run_id

    def finish_run(self, run_id: int, **stats):
        values = list(stats.values()) + [run_id]
        now = datetime.utcnow().isoformat()
        if self._pg:
            fields = ", ".join(f"{k}=%s" for k in stats)
            sql = f"UPDATE run_history SET finished_at=%s, {fields} WHERE id=%s"
        else:
            fields = ", ".join(f"{k}=?" for k in stats)
            sql = f"UPDATE run_history SET finished_at=?, {fields} WHERE id=?"
        cur = self.conn.cursor()
        cur.execute(sql, [now] + values)
        cur.close()
        self.conn.commit()

    def close(self):
        self.conn.close()
