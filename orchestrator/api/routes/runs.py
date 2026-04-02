"""运行管理 API"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session, Database
from models_db import Tenant
from api.auth import get_current_tenant

router = APIRouter()


class RunResponse(BaseModel):
    id: int
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    hotlist_count: int
    rss_count: int
    dedup_count: int
    new_count: int
    matched_count: int
    pushed_count: int
    errors: str


@router.get("")
async def list_runs(
    limit: int = Query(20, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    db = Database(session, tenant.id)
    rows = await db.get_runs(limit=limit)
    return [
        RunResponse(
            id=r.id,
            started_at=r.started_at.isoformat() if r.started_at else None,
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
            hotlist_count=r.hotlist_count or 0,
            rss_count=r.rss_count or 0,
            dedup_count=r.dedup_count or 0,
            new_count=r.new_count or 0,
            matched_count=r.matched_count or 0,
            pushed_count=r.pushed_count or 0,
            errors=r.errors or "",
        )
        for r in rows
    ]


@router.post("")
async def trigger_run(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    """手动触发一次运行"""
    from tasks import run_pipeline
    run_pipeline.delay(str(tenant.id))
    return {"ok": True, "message": "任务已提交"}
