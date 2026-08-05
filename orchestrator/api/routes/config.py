"""配置管理 API"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models_db import Tenant, TenantConfig
from api.auth import get_current_tenant
from models_db import TenantSecret
from secret_store import extract_config_secrets, masked_config
from url_security import UnsafeUrlError, validate_http_url_syntax, validate_rsshub_route

log = logging.getLogger("infohub.config.api")
router = APIRouter()


class ConfigResponse(BaseModel):
    platforms: list
    interests: list
    rsshub_feeds: list
    external_feeds: list
    notification: dict
    ai_config: dict
    cron_schedule: str
    timezone: str
    obsidian_export: bool


class ConfigUpdate(BaseModel):
    platforms: Optional[list] = None
    interests: Optional[list] = None
    rsshub_feeds: Optional[list] = None
    external_feeds: Optional[list] = None
    notification: Optional[dict] = None
    ai_config: Optional[dict] = None
    cron_schedule: Optional[str] = None
    timezone: Optional[str] = None
    obsidian_export: Optional[bool] = None

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, value):
        if value is not None and len(value) > 50:
            raise ValueError("平台数量不能超过 50")
        return value

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, value):
        if value is not None:
            if len(value) > 100:
                raise ValueError("兴趣标签不能超过 100 个")
            if any(not isinstance(item, str) or not item.strip() or len(item) > 100 for item in value):
                raise ValueError("兴趣标签必须是 1 到 100 字符的字符串")
        return value

    @field_validator("external_feeds")
    @classmethod
    def validate_external_feeds(cls, value):
        return _validate_external_feeds(value)

    @field_validator("rsshub_feeds")
    @classmethod
    def validate_rsshub_feeds(cls, value):
        return _validate_rsshub_feeds(value)

    @field_validator("ai_config")
    @classmethod
    def validate_ai_config(cls, value):
        if value is None:
            return value
        bounds = {
            "timeout": (1, 300),
            "max_tokens": (1, 20_000),
            "batch_size": (1, 500),
            "batch_interval": (0, 60),
            "min_score": (0, 1),
        }
        for key, (minimum, maximum) in bounds.items():
            if key in value:
                number = value[key]
                if not isinstance(number, (int, float)) or isinstance(number, bool) or not minimum <= number <= maximum:
                    raise ValueError(f"AI 配置 {key} 超出允许范围")
        return value

    @field_validator("cron_schedule")
    @classmethod
    def validate_cron(cls, v):
        if v is not None:
            from croniter import croniter
            if not croniter.is_valid(v):
                raise ValueError(f"无效的 cron 表达式: {v}")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v):
        if v is not None:
            from zoneinfo import ZoneInfo
            try:
                ZoneInfo(v)
            except (KeyError, ValueError):
                raise ValueError(f"无效的时区: {v}")
        return v


class InterestsUpdate(BaseModel):
    interests: List[str]


class NotificationUpdate(BaseModel):
    notification: dict


class FeedsUpdate(BaseModel):
    rsshub_feeds: Optional[list] = None
    external_feeds: Optional[list] = None

    @field_validator("external_feeds")
    @classmethod
    def validate_external_feeds(cls, value):
        return _validate_external_feeds(value)

    @field_validator("rsshub_feeds")
    @classmethod
    def validate_rsshub_feeds(cls, value):
        return _validate_rsshub_feeds(value)


def _validate_external_feeds(value):
    if value is None:
        return value
    if len(value) > 100:
        raise ValueError("外部订阅不能超过 100 个")
    for feed in value:
        if not isinstance(feed, dict):
            raise ValueError("外部订阅格式无效")
        try:
            feed["url"] = validate_http_url_syntax(feed.get("url", ""))
        except UnsafeUrlError as exc:
            raise ValueError(str(exc)) from exc
        if len(str(feed.get("name", ""))) > 200 or len(str(feed.get("category", ""))) > 100:
            raise ValueError("订阅名称或分类过长")
    return value


def _validate_rsshub_feeds(value):
    if value is None:
        return value
    if len(value) > 100:
        raise ValueError("RSSHub 订阅不能超过 100 个")
    for feed in value:
        if not isinstance(feed, dict):
            raise ValueError("RSSHub 订阅格式无效")
        try:
            feed["route"] = validate_rsshub_route(str(feed.get("route", "")))
        except UnsafeUrlError as exc:
            raise ValueError(str(exc)) from exc
        if len(str(feed.get("name", ""))) > 200 or len(str(feed.get("category", ""))) > 100:
            raise ValueError("订阅名称或分类过长")
    return value


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
    secret_result = await session.execute(
        select(TenantSecret.key_name).where(TenantSecret.tenant_id == tenant.id)
    )
    stored_keys = {row[0] for row in secret_result}
    notification, ai_config = masked_config(
        tc.notification,
        tc.ai_config,
        stored_keys,
    )
    return ConfigResponse(
        platforms=tc.platforms or [],
        interests=tc.interests or [],
        rsshub_feeds=tc.rsshub_feeds or [],
        external_feeds=tc.external_feeds or [],
        notification=notification,
        ai_config=ai_config,
        cron_schedule=tc.cron_schedule or "*/30 * * * *",
        timezone=tc.timezone or "Asia/Shanghai",
        obsidian_export=tc.obsidian_export or False,
    )


@router.put("")
async def update_config(
    body: ConfigUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tc = await _get_or_create_config(session, tenant)
    updates = body.model_dump(exclude_none=True)
    if "notification" in updates or "ai_config" in updates:
        try:
            notification, ai_config = await extract_config_secrets(
                session,
                tenant.id,
                updates.pop("notification", tc.notification),
                updates.pop("ai_config", tc.ai_config),
            )
        except UnsafeUrlError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        tc.notification = notification
        tc.ai_config = ai_config
    for field, value in updates.items():
        setattr(tc, field, value)
    await session.commit()
    log.info(f"配置更新: tenant={tenant.id} fields={list(body.model_dump(exclude_none=True).keys())}")
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
    log.info(f"兴趣标签更新: tenant={tenant.id} count={len(body.interests)}")
    return {"ok": True}


@router.put("/notification")
async def update_notification(
    body: NotificationUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tc = await _get_or_create_config(session, tenant)
    try:
        notification, ai_config = await extract_config_secrets(
            session, tenant.id, body.notification, tc.ai_config
        )
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    tc.notification = notification
    tc.ai_config = ai_config
    await session.commit()
    log.info(f"通知配置更新: tenant={tenant.id}")
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
    log.info(f"订阅源更新: tenant={tenant.id}")
    return {"ok": True}
