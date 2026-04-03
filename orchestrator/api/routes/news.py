"""新闻查询 API"""

import logging
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models_db import Tenant, News, RunHistory
from api.auth import get_current_tenant

log = logging.getLogger("infohub.news")
router = APIRouter()


class NewsResponse(BaseModel):
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
    created_at: Optional[str] = None


@router.get("")
async def list_news(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source_type: Optional[str] = None,
    source: Optional[str] = None,
    tag: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tid = tenant.id
    q = select(News).where(News.tenant_id == tid)
    if source_type:
        q = q.where(News.source_type == source_type)
    if source:
        q = q.where(News.source == source)
    if tag:
        # 转义 LIKE 元字符防止用户注入 % 和 _
        safe_tag = tag.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        q = q.where(News.tags.ilike(f"%{safe_tag}%"))
    if min_score is not None:
        q = q.where(News.score >= min_score)
    if max_score is not None:
        q = q.where(News.score <= max_score)
    if start_date:
        q = q.where(
            News.created_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )
    if end_date:
        q = q.where(
            News.created_at <= datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        )
    q = q.order_by(News.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    rows = list(result.scalars().all())
    return [
        NewsResponse(
            id=r.id, title=r.title, url=r.url or "",
            source=r.source or "", source_type=r.source_type or "",
            rank=r.rank or 0, score=r.score or 0,
            tags=r.tags or "", summary=r.summary or "",
            pushed=r.pushed or False,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]


@router.get("/sources")
async def list_sources(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    """返回该租户所有不重复的 source 值"""
    result = await session.execute(
        select(News.source)
        .where(News.tenant_id == tenant.id)
        .distinct()
        .order_by(News.source)
    )
    return [row[0] for row in result if row[0]]


@router.get("/stats")
async def news_stats(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tid = tenant.id

    total_news_q = await session.execute(
        select(func.count()).select_from(News).where(News.tenant_id == tid)
    )
    total_news = total_news_q.scalar() or 0

    total_runs_q = await session.execute(
        select(func.count()).select_from(RunHistory).where(RunHistory.tenant_id == tid)
    )
    total_runs = total_runs_q.scalar() or 0

    latest_run_q = await session.execute(
        select(RunHistory.started_at)
        .where(RunHistory.tenant_id == tid)
        .order_by(RunHistory.id.desc())
        .limit(1)
    )
    latest_row = latest_run_q.scalar_one_or_none()
    latest_run = latest_row.isoformat() if latest_row else None

    hotlist_q = await session.execute(
        select(func.count()).select_from(News).where(
            News.tenant_id == tid, News.source_type == "hotlist"
        )
    )
    hotlist_total = hotlist_q.scalar() or 0

    rss_q = await session.execute(
        select(func.count()).select_from(News).where(
            News.tenant_id == tid, News.source_type == "rss"
        )
    )
    rss_total = rss_q.scalar() or 0

    return {
        "total_news": total_news,
        "total_runs": total_runs,
        "latest_run": latest_run,
        "hotlist_total": hotlist_total,
        "rss_total": rss_total,
    }


@router.get("/report", response_class=HTMLResponse)
async def latest_report(tenant: Tenant = Depends(get_current_tenant)):
    """返回该租户最新的 HTML 报告"""
    output_dir = os.environ.get("OUTPUT_DIR", "/app/output")
    report_path = Path(output_dir) / "html" / str(tenant.id) / "latest" / "current.html"
    if not report_path.exists():
        return HTMLResponse("<h1>暂无报告</h1>", status_code=404)
    return HTMLResponse(report_path.read_text(encoding="utf-8"))
