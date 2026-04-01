"""SQLite 本地存储"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from models import NewsItem

log = logging.getLogger("infohub.db")

SCHEMA = """
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

CREATE INDEX IF NOT EXISTS idx_news_created
    ON news(created_at);
CREATE INDEX IF NOT EXISTS idx_news_source_type
    ON news(source_type);
"""


class Database:
    def __init__(self, output_dir: str):
        db_path = Path(output_dir) / "infohub.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(SCHEMA)

    def filter_new(self, items: List[NewsItem]) -> List[NewsItem]:
        existing = set()
        cursor = self.conn.execute("SELECT id FROM news")
        for row in cursor:
            existing.add(row[0])
        return [it for it in items if it.id not in existing]

    def save_items(self, items: List[NewsItem]):
        for item in items:
            try:
                self.conn.execute(
                    """INSERT OR IGNORE INTO news
                    (id, title, url, source, source_type, rank,
                     published_at, score, tags, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item.id, item.title, item.url, item.source,
                     item.source_type, item.rank, item.published_at,
                     item.score, ",".join(item.tags), item.summary),
                )
            except Exception as e:
                log.error(f"写入失败: {item.title} - {e}")
        self.conn.commit()

    def mark_matched(self, items: List[NewsItem]):
        for item in items:
            self.conn.execute(
                "UPDATE news SET score=?, tags=?, summary=? WHERE id=?",
                (item.score, ",".join(item.tags), item.summary, item.id),
            )
        self.conn.commit()

    def mark_pushed(self, item_ids: List[str]):
        for iid in item_ids:
            self.conn.execute(
                "UPDATE news SET pushed=1 WHERE id=?", (iid,)
            )
        self.conn.commit()

    # ---- 运行历史 ----
    def start_run(self) -> int:
        cursor = self.conn.execute(
            "INSERT INTO run_history (started_at) VALUES (?)",
            (datetime.utcnow().isoformat(),),
        )
        self.conn.commit()
        return cursor.lastrowid

    def finish_run(self, run_id: int, **stats):
        fields = ", ".join(f"{k}=?" for k in stats)
        values = list(stats.values()) + [run_id]
        self.conn.execute(
            f"UPDATE run_history SET finished_at=?, {fields} WHERE id=?",
            [datetime.utcnow().isoformat()] + values,
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
