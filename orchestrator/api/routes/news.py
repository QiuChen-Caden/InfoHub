"""新闻查询 API"""

import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session, Database
from models_db import Tenant
from api.auth import get_current_tenant

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
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    source_type: Optional[str] = None,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    db = Database(session, tenant.id)
    rows = await db.get_news(limit=limit, offset=offset, source_type=source_type)
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


@router.get("/report", response_class=HTMLResponse)
async def latest_report(tenant: Tenant = Depends(get_current_tenant)):
    """返回该租户最新的 HTML 报告"""
    output_dir = os.environ.get("OUTPUT_DIR", "/app/output")
    report_path = Path(output_dir) / "html" / str(tenant.id) / "latest" / "current.html"
    if not report_path.exists():
        return HTMLResponse("<h1>暂无报告</h1>", status_code=404)
    return HTMLResponse(report_path.read_text(encoding="utf-8"))
