"""数据存储 — PostgreSQL (生产) / SQLite (本地开发)"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from models import NewsItem

log = logging.getLogger("infohub.db")

PG_SCHEMA = """
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

SQLITE_SCHEMA = """
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


def _use_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


class Database:
    """统一数据库接口，自动选择 PostgreSQL 或 SQLite"""

    def __init__(self, output_dir: str):
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            import psycopg2
            self.conn = psycopg2.connect(db_url)
            self.conn.autocommit = False
            self._pg = True
            with self.conn.cursor() as cur:
                cur.execute(PG_SCHEMA)
            self.conn.commit()
            log.info("已连接 PostgreSQL")
        else:
            import sqlite3
            db_path = Path(output_dir) / "infohub.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(db_path))
            self.conn.executescript(SQLITE_SCHEMA)
            self._pg = False
            log.info(f"已连接 SQLite: {db_path}")

    def _execute(self, sql: str, params=None):
        """统一执行：PostgreSQL 用 %s 占位符，SQLite 用 ?"""
        if self._pg:
            # 把 ? 转为 %s
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
                cur.execute(sql, (
                    item.id, item.title, item.url, item.source,
                    item.source_type, item.rank, item.published_at,
                    item.score, ",".join(item.tags), item.summary,
                ))
                cur.close()
            except Exception as e:
                log.error(f"写入失败: {item.title} - {e}")
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

    # ---- 运行历史 ----
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
                "INSERT INTO run_history (started_at) VALUES (?)", (now,)
            )
            run_id = cur.lastrowid
        self.conn.commit()
        return run_id

    def finish_run(self, run_id: int, **stats):
        fields = ", ".join(f"{k}=%s" if self._pg else f"{k}=?"
                           for k in stats)
        values = list(stats.values()) + [run_id]
        now = datetime.utcnow().isoformat()
        if self._pg:
            sql = f"UPDATE run_history SET finished_at=%s, {fields} WHERE id=%s"
        else:
            fields_sqlite = ", ".join(f"{k}=?" for k in stats)
            sql = f"UPDATE run_history SET finished_at=?, {fields_sqlite} WHERE id=?"
        cur = self.conn.cursor()
        cur.execute(sql, [now] + values)
        cur.close()
        self.conn.commit()

    def close(self):
        self.conn.close()
