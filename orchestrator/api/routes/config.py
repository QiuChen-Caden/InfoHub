"""配置管理 API"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models_db import Tenant, TenantConfig
from api.auth import get_current_tenant

router = APIRouter()


class ConfigResponse(BaseModel):
    platforms: list
    interests: list
    rsshub_feeds: list
    external_feeds: list
    notification: dict
    ai_config: dict
    cron_schedule: str
    obsidian_export: bool


class ConfigUpdate(BaseModel):
    platforms: Optional[list] = None
    interests: Optional[list] = None
    rsshub_feeds: Optional[list] = None
    external_feeds: Optional[list] = None
    notification: Optional[dict] = None
    ai_config: Optional[dict] = None
    cron_schedule: Optional[str] = None
    obsidian_export: Optional[bool] = None


class InterestsUpdate(BaseModel):
    interests: List[str]


class NotificationUpdate(BaseModel):
    notification: dict


class FeedsUpdate(BaseModel):
    rsshub_feeds: Optional[list] = None
    external_feeds: Optional[list] = None


async def _get_or_create_config(session: AsyncSession, tenant: Tenant) -> TenantConfig:
    result = await session.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant.id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        tc = TenantConfig(tenant_id=tenant.id)
        session.add(tc)
        await session.flush()
    return tc


@router.get("", response_model=ConfigResponse)
async def get_config(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tc = await _get_or_create_config(session, tenant)
    return ConfigResponse(
        platforms=tc.platforms or [],
        interests=tc.interests or [],
        rsshub_feeds=tc.rsshub_feeds or [],
        external_feeds=tc.external_feeds or [],
        notification=tc.notification or {},
        ai_config=tc.ai_config or {},
        cron_schedule=tc.cron_schedule or "*/30 * * * *",
        obsidian_export=tc.obsidian_export or False,
    )


@router.put("")
async def update_config(
    body: ConfigUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tc = await _get_or_create_config(session, tenant)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(tc, field, value)
    await session.commit()
    return {"ok": True}


@router.put("/interests")
async def update_interests(
    body: InterestsUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tc = await _get_or_create_config(session, tenant)
    tc.interests = body.interests
    await session.commit()
    return {"ok": True}


@router.put("/notification")
async def update_notification(
    body: NotificationUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tc = await _get_or_create_config(session, tenant)
    tc.notification = body.notification
    await session.commit()
    return {"ok": True}


@router.put("/feeds")
async def update_feeds(
    body: FeedsUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tc = await _get_or_create_config(session, tenant)
    if body.rsshub_feeds is not None:
        tc.rsshub_feeds = body.rsshub_feeds
    if body.external_feeds is not None:
        tc.external_feeds = body.external_feeds
    await session.commit()
    return {"ok": True}
