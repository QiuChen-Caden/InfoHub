"""InfoHub REST API — 轻量 FastAPI 层，读取 pipeline 产出的数据"""

import os
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="InfoHub API", version="0.1.0")


# ---- DB 连接 ----

def _get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url), True
    else:
        import sqlite3
        db_path = os.environ.get("SQLITE_PATH", "/app/output/infohub.db")
        return sqlite3.connect(db_path), False


@contextmanager
def get_db():
    conn, is_pg = _get_conn()
    try:
        yield conn, is_pg
    finally:
        conn.close()


# ---- 响应模型 ----

class NewsOut(BaseModel):
    id: str
    title: str
    url: str
    source: str
    source_type: str
    rank: int
    score: float
    tags: str
    summary: str
    pushed: bool
    created_at: str


class RunOut(BaseModel):
    id: int
    started_at: str
    finished_at: Optional[str]
    hotlist_count: int
    rss_count: int
    dedup_count: int
    new_count: int
    matched_count: int
    pushed_count: int
    errors: str


class StatsOut(BaseModel):
    total_news: int
    total_runs: int
    latest_run: Optional[str]
    hotlist_total: int
    rss_total: int


# ---- 路由 ----

@app.get("/api/news", response_model=List[NewsOut])
def list_news(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source_type: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
):
    """查询新闻列表，支持分页和筛选"""
    with get_db() as (conn, is_pg):
        ph = "%s" if is_pg else "?"
        sql = "SELECT id, title, url, source, source_type, rank, score, tags, summary, pushed, created_at FROM news"
        conditions, params = [], []

        if source_type:
            conditions.append(f"source_type = {ph}")
            params.append(source_type)
        if tag:
            conditions.append(f"tags LIKE {ph}")
            params.append(f"%{tag}%")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += f" ORDER BY created_at DESC LIMIT {ph} OFFSET {ph}"
        params.extend([limit, offset])

        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()

    return [
        NewsOut(
            id=r[0], title=r[1], url=r[2], source=r[3],
            source_type=r[4], rank=r[5], score=r[6], tags=r[7],
            summary=r[8], pushed=bool(r[9]),
            created_at=str(r[10]) if r[10] else "",
        )
        for r in rows
    ]


@app.get("/api/runs", response_model=List[RunOut])
def list_runs(limit: int = Query(20, ge=1, le=100)):
    """查询运行历史"""
    with get_db() as (conn, is_pg):
        ph = "%s" if is_pg else "?"
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, started_at, finished_at, hotlist_count, rss_count, "
            f"dedup_count, new_count, matched_count, pushed_count, errors "
            f"FROM run_history ORDER BY id DESC LIMIT {ph}",
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()

    return [
        RunOut(
            id=r[0], started_at=str(r[1]), finished_at=str(r[2]) if r[2] else None,
            hotlist_count=r[3], rss_count=r[4], dedup_count=r[5],
            new_count=r[6], matched_count=r[7], pushed_count=r[8],
            errors=r[9] or "",
        )
        for r in rows
    ]


@app.get("/api/stats", response_model=StatsOut)
def get_stats():
    """获取总体统计"""
    with get_db() as (conn, is_pg):
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM news")
        total_news = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM run_history")
        total_runs = cur.fetchone()[0]
        cur.execute("SELECT MAX(started_at) FROM run_history")
        latest = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM news WHERE source_type='hotlist'")
        hotlist_total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM news WHERE source_type='rss'")
        rss_total = cur.fetchone()[0]
        cur.close()

    return StatsOut(
        total_news=total_news,
        total_runs=total_runs,
        latest_run=str(latest) if latest else None,
        hotlist_total=hotlist_total,
        rss_total=rss_total,
    )


@app.get("/api/health")
def health():
    """健康检查"""
    try:
        with get_db() as (conn, _):
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---- 配置端点 ----

def _mask(val: str) -> str:
    """脱敏：保留前4字符，其余用 * 替代"""
    if not val or len(val) <= 4:
        return "****"
    return val[:4] + "*" * (len(val) - 4)


@app.get("/api/config")
def get_config():
    """返回脱敏后的配置信息"""
    config_dir = Path(os.environ.get("CONFIG_DIR", "/app/config"))
    config_path = config_dir / "config.yaml"
    interests_path = config_dir / "interests.txt"

    if not config_path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")

    raw = config_path.read_text(encoding="utf-8")
    # 解析环境变量占位符
    def _resolve(m: re.Match) -> str:
        var, default = m.group(1), m.group(3) or ""
        return os.environ.get(var, default)
    resolved = re.sub(r"\$\{(\w+)(:-([^}]*))?\}", _resolve, raw)
    cfg = yaml.safe_load(resolved)

    interests: list[str] = []
    if interests_path.exists():
        interests = [l.strip() for l in interests_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 检测已配置的通知渠道
    notif = cfg.get("notification", {})
    channels = []
    channel_keys = {
        "telegram_bot_token": "Telegram",
        "feishu_webhook_url": "Feishu",
        "dingtalk_webhook_url": "DingTalk",
        "email_from": "Email",
        "slack_webhook_url": "Slack",
    }
    for key, name in channel_keys.items():
        if notif.get(key):
            channels.append(name)

    ai = cfg.get("ai", {})
    return {
        "platforms": cfg.get("platforms", []),
        "interests": interests,
        "ai": {
            "model": ai.get("model", ""),
            "timeout": ai.get("timeout", 0),
            "max_tokens": ai.get("max_tokens", 0),
            "batch_size": ai.get("batch_size", 0),
            "min_score": ai.get("min_score", 0),
            "summary_enabled": ai.get("summary_enabled", False),
        },
        "notification": {"channels": channels},
        "cron_schedule": cfg.get("cron_schedule", ""),
    }


# ---- 静态文件（SPA）——放在最后，API 路由优先匹配 ----

_frontend_dir = Path("/app/frontend")
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
