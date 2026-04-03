"""运行管理 API"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session, Database
from models_db import Tenant
from api.auth import get_current_tenant

log = logging.getLogger("infohub.runs")
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
    limit: int = Query(20, ge=1, le=100),
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
    """手动触发一次运行 — 先在 DB 创建 RunHistory 行，再提交 Celery 任务"""
    db = Database(session, tenant.id)
    run_id = await db.start_run()
    await session.commit()

    log.info(f"手动触发运行: tenant={tenant.id} run_id={run_id}")
    try:
        from tasks import run_pipeline
        run_pipeline.delay(str(tenant.id), run_id)
    except Exception as e:
        log.error(f"任务提交失败: tenant={tenant.id} run_id={run_id}: {e}")
        # 标记该运行为失败，避免永久 "运行中" 状态
        await db.finish_run(run_id, errors=f"任务提交失败: {e}")
        await session.commit()
        raise HTTPException(status_code=503, detail="任务队列不可用，请稍后重试")
    return {"ok": True, "message": "任务已提交", "run_id": run_id}
