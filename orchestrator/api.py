"""InfoHub REST API — 轻量 FastAPI 层，读取 pipeline 产出的数据"""

import os
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
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
        from pathlib import Path
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
