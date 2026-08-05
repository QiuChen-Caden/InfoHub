"""管理员 API — 跨租户总览、账号操作和全局任务视图。"""

import hashlib
import asyncio
import os
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from api.auth import get_current_admin_tenant
from db import get_session
from models_db import (
    ApiKey, News, NotificationOutbox, QuotaToken, RunHistory, Tenant, TenantConfig,
    TenantSecret, UsageRecord,
)
from metering import FREE_LIMITS
from secret_store import ALLOWED_SECRET_KEYS, extract_config_secrets, upsert_secret
from url_security import UnsafeUrlError, validate_public_http_url

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_ROLES = {"user", "admin"}
VALID_PLANS = {"free", "pro", "enterprise"}
SECRET_FIELDS = {
    "api_key", "api_base", "ai_api_key", "ai_api_base",
    "telegram_bot_token", "telegram_chat_id",
    "feishu_webhook_url", "dingtalk_webhook_url", "email_password",
    "slack_webhook_url", "miniflux_api_key",
}
ADMIN_SECRET_KEYS = ALLOWED_SECRET_KEYS


class AdminOverview(BaseModel):
    total_tenants: int
    active_tenants: int
    admin_tenants: int
    total_news: int
    hotlist_total: int
    rss_total: int
    total_runs: int
    latest_run: Optional[str] = None


class AdminTenantResponse(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    role: str
    is_active: bool
    created_at: Optional[str] = None
    news_count: int
    run_count: int
    latest_run: Optional[str] = None
    quota_limits: dict[str, int]


class AdminRunResponse(BaseModel):
    id: int
    tenant_id: str
    tenant_email: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    hotlist_count: int
    rss_count: int
    dedup_count: int
    new_count: int
    matched_count: int
    pushed_count: int
    errors: str


class AdminTaskStatus(BaseModel):
    running_count: int
    failed_count: int
    recent_runs: list[AdminRunResponse]


class AdminTenantDetail(BaseModel):
    tenant: AdminTenantResponse
    config: dict
    stored_secret_keys: list[str]
    recent_runs: list[AdminRunResponse]


class AdminRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(user|admin)$")


class AdminPlanUpdate(BaseModel):
    plan: str = Field(..., pattern="^(free|pro|enterprise)$")


class AdminPasswordReset(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)


class AdminDeleteConfirm(BaseModel):
    confirm: str


class AdminConfigUpdate(BaseModel):
    platforms: Optional[list] = None
    interests: Optional[list] = None
    rsshub_feeds: Optional[list] = None
    external_feeds: Optional[list] = None
    notification: Optional[dict] = None
    ai_config: Optional[dict] = None
    cron_schedule: Optional[str] = None
    timezone: Optional[str] = None
    obsidian_export: Optional[bool] = None

    @field_validator("cron_schedule")
    @classmethod
    def validate_cron(cls, value):
        if value is not None:
            from croniter import croniter
            if not croniter.is_valid(value):
                raise ValueError(f"无效的 cron 表达式: {value}")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value):
        if value is not None:
            from zoneinfo import ZoneInfo
            try:
                ZoneInfo(value)
            except (KeyError, ValueError):
                raise ValueError(f"无效的时区: {value}")
        return value

    @field_validator("external_feeds")
    @classmethod
    def validate_external_feeds(cls, value):
        if value is None:
            return value
        if len(value) > 100:
            raise ValueError("外部订阅不能超过 100 个")
        from url_security import validate_http_url_syntax
        for feed in value:
            if not isinstance(feed, dict):
                raise ValueError("外部订阅格式无效")
            feed["url"] = validate_http_url_syntax(feed.get("url", ""))
        return value

    @field_validator("rsshub_feeds")
    @classmethod
    def validate_rsshub_feeds(cls, value):
        if value is None:
            return value
        if len(value) > 100:
            raise ValueError("RSSHub 订阅不能超过 100 个")
        from url_security import validate_rsshub_route
        for feed in value:
            if not isinstance(feed, dict):
                raise ValueError("RSSHub 订阅格式无效")
            feed["route"] = validate_rsshub_route(str(feed.get("route", "")))
        return value


class AdminSecretUpdate(BaseModel):
    key_name: str
    value: str = Field(..., min_length=1, max_length=2048)


class AdminQuotaTokenCreate(BaseModel):
    plan: str = Field("custom", min_length=1, max_length=20)
    limits: dict[str, int] = Field(default_factory=dict)
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650)
    count: int = Field(1, ge=1, le=100)

    @field_validator("limits")
    @classmethod
    def validate_limits(cls, value):
        unknown = set(value) - set(FREE_LIMITS)
        if unknown:
            raise ValueError(f"不支持的额度项: {', '.join(sorted(unknown))}")
        for key, amount in value.items():
            if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0 or amount > 10_000_000:
                raise ValueError(f"额度 {key} 必须是 0 到 10000000 的整数")
        return value


class AdminQuotaTokenResponse(BaseModel):
    id: str
    prefix: str
    plan: str
    limits: dict[str, int]
    expires_at: Optional[str] = None
    redeemed_by: Optional[str] = None
    redeemed_at: Optional[str] = None
    created_at: Optional[str] = None
    is_active: bool


class AdminQuotaTokenCreateResponse(BaseModel):
    tokens: list[str]
    plan: str
    limits: dict[str, int]
    expires_at: Optional[str] = None


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _mask_value(value):
    if value in (None, ""):
        return value
    text = str(value)
    if len(text) <= 8:
        return "****"
    return f"{text[:3]}****{text[-4:]}"


def _sanitize_dict(data: dict | None) -> dict:
    sanitized = {}
    for key, value in (data or {}).items():
        if key in SECRET_FIELDS:
            sanitized[key] = _mask_value(value)
        else:
            sanitized[key] = value
    return sanitized


def _merge_preserving_masked(new_data: dict | None, existing_data: dict | None) -> dict:
    existing = existing_data or {}
    merged = {}
    for key, value in (new_data or {}).items():
        if key in SECRET_FIELDS and isinstance(value, str) and "****" in value:
            if key in existing:
                merged[key] = existing[key]
            continue
        merged[key] = value
    return merged


def _tenant_response(tenant: Tenant, news_count=0, run_count=0, latest_run=None) -> AdminTenantResponse:
    return AdminTenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        email=tenant.email,
        plan=tenant.plan or "free",
        role=tenant.role or "user",
        is_active=bool(tenant.is_active),
        created_at=_iso(tenant.created_at),
        news_count=int(news_count or 0),
        run_count=int(run_count or 0),
        latest_run=_iso(latest_run),
        quota_limits={str(k): int(v) for k, v in (tenant.quota_limits or {}).items()},
    )


def _run_response(run: RunHistory, tenant_email: str) -> AdminRunResponse:
    return AdminRunResponse(
        id=run.id,
        tenant_id=str(run.tenant_id),
        tenant_email=tenant_email,
        started_at=_iso(run.started_at),
        finished_at=_iso(run.finished_at),
        hotlist_count=run.hotlist_count or 0,
        rss_count=run.rss_count or 0,
        dedup_count=run.dedup_count or 0,
        new_count=run.new_count or 0,
        matched_count=run.matched_count or 0,
        pushed_count=run.pushed_count or 0,
        errors=run.errors or "",
    )


async def _get_target_tenant(session: AsyncSession, tenant_id: UUID) -> Tenant:
    tenant = await session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    return tenant


async def _count_admins(session: AsyncSession) -> int:
    return await session.scalar(
        select(func.count()).select_from(Tenant).where(
            Tenant.role == "admin",
            Tenant.is_active == True,
        )
    ) or 0


async def _tenant_counts(session: AsyncSession, tenant_id: UUID):
    news_count = await session.scalar(
        select(func.count()).select_from(News).where(News.tenant_id == tenant_id)
    ) or 0
    run_count = await session.scalar(
        select(func.count()).select_from(RunHistory).where(RunHistory.tenant_id == tenant_id)
    ) or 0
    latest_run = await session.scalar(
        select(func.max(RunHistory.started_at)).where(RunHistory.tenant_id == tenant_id)
    )
    return news_count, run_count, latest_run


async def _get_or_create_config(session: AsyncSession, tenant_id: UUID) -> TenantConfig:
    config = await session.get(TenantConfig, tenant_id)
    if not config:
        config = TenantConfig(tenant_id=tenant_id)
        session.add(config)
        await session.flush()
    return config


async def _stored_secret_keys(session: AsyncSession, tenant_id: UUID) -> list[str]:
    result = await session.execute(
        select(TenantSecret.key_name)
        .where(TenantSecret.tenant_id == tenant_id)
        .order_by(TenantSecret.key_name)
    )
    return [row[0] for row in result.all()]


async def _ensure_no_active_run(session: AsyncSession, tenant_id: UUID) -> None:
    stale_before = datetime.now(timezone.utc) - timedelta(minutes=20)
    from sqlalchemy import update
    await session.execute(
        update(RunHistory)
        .where(
            RunHistory.tenant_id == tenant_id,
            RunHistory.finished_at.is_(None),
            RunHistory.started_at < stale_before,
        )
        .values(
            finished_at=datetime.now(timezone.utc),
            errors="任务超时，已自动结束",
        )
    )
    active_run = await session.scalar(
        select(RunHistory.id)
        .where(
            RunHistory.tenant_id == tenant_id,
            RunHistory.finished_at.is_(None),
        )
        .limit(1)
    )
    if active_run:
        raise HTTPException(status_code=409, detail=f"租户任务 #{active_run} 仍在运行")


def _remove_tenant_tree(base_dir: Path, tenant_id: UUID) -> None:
    base = base_dir.resolve(strict=False)
    target = (base / str(tenant_id)).resolve(strict=False)
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise RuntimeError("租户数据目录越界") from exc
    if target.is_dir():
        shutil.rmtree(target)


async def _cleanup_tenant_artifacts(tenant_id: UUID) -> None:
    output_dir = Path(os.environ.get("OUTPUT_DIR", "/app/output")) / "html"
    await asyncio.to_thread(_remove_tenant_tree, output_dir, tenant_id)

    obsidian_dir = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    if obsidian_dir:
        await asyncio.to_thread(_remove_tenant_tree, Path(obsidian_dir), tenant_id)

    redis_url = os.environ.get("REDIS_URL", "")
    if redis_url:
        client = aioredis.from_url(redis_url)
        try:
            await client.delete(f"log_history:{tenant_id}", f"pipeline_lock:{tenant_id}")
        finally:
            await client.aclose()


async def _delete_tenant_external_data(tenant_id: UUID) -> None:
    from miniflux_client import delete_miniflux_user

    username = f"tenant_{tenant_id.hex[:12]}"
    if not await asyncio.to_thread(delete_miniflux_user, username):
        raise HTTPException(status_code=502, detail="Miniflux 租户数据删除失败")
    await _cleanup_tenant_artifacts(tenant_id)


@router.get("/overview", response_model=AdminOverview)
async def overview(
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    total_tenants = await session.scalar(select(func.count()).select_from(Tenant)) or 0
    active_tenants = await session.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.is_active == True)
    ) or 0
    admin_tenants = await session.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.role == "admin")
    ) or 0
    total_news = await session.scalar(select(func.count()).select_from(News)) or 0
    hotlist_total = await session.scalar(
        select(func.count()).select_from(News).where(News.source_type == "hotlist")
    ) or 0
    rss_total = await session.scalar(
        select(func.count()).select_from(News).where(News.source_type == "rss")
    ) or 0
    total_runs = await session.scalar(select(func.count()).select_from(RunHistory)) or 0
    latest_run_dt: Optional[datetime] = await session.scalar(select(func.max(RunHistory.started_at)))

    return AdminOverview(
        total_tenants=total_tenants,
        active_tenants=active_tenants,
        admin_tenants=admin_tenants,
        total_news=total_news,
        hotlist_total=hotlist_total,
        rss_total=rss_total,
        total_runs=total_runs,
        latest_run=latest_run_dt.isoformat() if latest_run_dt else None,
    )


@router.get("/tasks", response_model=AdminTaskStatus)
async def task_status(
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    running_count = await session.scalar(
        select(func.count()).select_from(RunHistory).where(RunHistory.finished_at.is_(None))
    ) or 0
    failed_count = await session.scalar(
        select(func.count()).select_from(RunHistory).where(
            RunHistory.finished_at.is_not(None),
            RunHistory.errors != "",
        )
    ) or 0
    result = await session.execute(
        select(RunHistory, Tenant.email)
        .join(Tenant, Tenant.id == RunHistory.tenant_id)
        .order_by(RunHistory.id.desc())
        .limit(20)
    )
    return AdminTaskStatus(
        running_count=running_count,
        failed_count=failed_count,
        recent_runs=[_run_response(run, email) for run, email in result.all()],
    )


@router.get("/tenants", response_model=list[AdminTenantResponse])
async def tenants(
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    news_counts = (
        select(News.tenant_id, func.count().label("news_count"))
        .group_by(News.tenant_id)
        .subquery()
    )
    run_counts = (
        select(
            RunHistory.tenant_id,
            func.count().label("run_count"),
            func.max(RunHistory.started_at).label("latest_run"),
        )
        .group_by(RunHistory.tenant_id)
        .subquery()
    )
    result = await session.execute(
        select(
            Tenant,
            func.coalesce(news_counts.c.news_count, 0),
            func.coalesce(run_counts.c.run_count, 0),
            run_counts.c.latest_run,
        )
        .outerjoin(news_counts, news_counts.c.tenant_id == Tenant.id)
        .outerjoin(run_counts, run_counts.c.tenant_id == Tenant.id)
        .order_by(Tenant.created_at.desc())
    )

    rows = []
    for tenant, news_count, run_count, latest_run in result.all():
        rows.append(_tenant_response(tenant, news_count, run_count, latest_run))
    return rows


@router.get("/tenants/{tenant_id}", response_model=AdminTenantDetail)
async def tenant_detail(
    tenant_id: UUID,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    news_count, run_count, latest_run = await _tenant_counts(session, tenant.id)
    config = await session.get(TenantConfig, tenant.id)
    run_result = await session.execute(
        select(RunHistory)
        .where(RunHistory.tenant_id == tenant.id)
        .order_by(RunHistory.id.desc())
        .limit(20)
    )
    safe_config = {
        "platforms": [],
        "interests": [],
        "rsshub_feeds": [],
        "external_feeds": [],
        "notification": {},
        "ai_config": {},
        "cron_schedule": "*/30 * * * *",
        "timezone": "Asia/Shanghai",
        "obsidian_export": False,
    }
    if config:
        safe_config = {
            "platforms": config.platforms or [],
            "interests": config.interests or [],
            "rsshub_feeds": config.rsshub_feeds or [],
            "external_feeds": config.external_feeds or [],
            "notification": _sanitize_dict(config.notification),
            "ai_config": _sanitize_dict(config.ai_config),
            "cron_schedule": config.cron_schedule or "*/30 * * * *",
            "timezone": config.timezone or "Asia/Shanghai",
            "obsidian_export": bool(config.obsidian_export),
        }
    return AdminTenantDetail(
        tenant=_tenant_response(tenant, news_count, run_count, latest_run),
        config=safe_config,
        stored_secret_keys=await _stored_secret_keys(session, tenant.id),
        recent_runs=[_run_response(run, tenant.email) for run in run_result.scalars().all()],
    )


@router.put("/tenants/{tenant_id}/config", response_model=AdminTenantDetail)
async def update_tenant_config(
    tenant_id: UUID,
    body: AdminConfigUpdate,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    config = await _get_or_create_config(session, tenant.id)
    updates = body.model_dump(exclude_none=True)
    if "notification" in updates:
        updates["notification"] = _merge_preserving_masked(updates["notification"], config.notification)
    if "ai_config" in updates:
        updates["ai_config"] = _merge_preserving_masked(updates["ai_config"], config.ai_config)
    if "notification" in updates or "ai_config" in updates:
        try:
            notification, ai_config = await extract_config_secrets(
                session,
                tenant.id,
                updates.pop("notification", config.notification),
                updates.pop("ai_config", config.ai_config),
            )
        except UnsafeUrlError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        config.notification = notification
        config.ai_config = ai_config
    for field, value in updates.items():
        setattr(config, field, value)
    await session.commit()
    return await tenant_detail(tenant.id, _admin, session)


@router.post("/tenants/{tenant_id}/secrets")
async def set_tenant_secret(
    tenant_id: UUID,
    body: AdminSecretUpdate,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    if body.key_name not in ADMIN_SECRET_KEYS:
        raise HTTPException(status_code=400, detail=f"不支持的密钥名: {body.key_name}")
    if body.key_name in {"ai_api_base", "feishu_webhook_url", "dingtalk_webhook_url", "slack_webhook_url"}:
        try:
            validate_public_http_url(body.value)
        except UnsafeUrlError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    await upsert_secret(session, tenant.id, body.key_name, body.value)
    await session.commit()
    return {"ok": True}


@router.post("/quota-tokens", response_model=AdminQuotaTokenCreateResponse)
async def create_quota_tokens(
    body: AdminQuotaTokenCreate,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    limits = {**FREE_LIMITS, **body.limits}
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
        if body.expires_in_days else None
    )
    raw_tokens = []
    for _ in range(body.count):
        raw_token = "ihq_" + secrets.token_urlsafe(32)
        raw_tokens.append(raw_token)
        session.add(QuotaToken(
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            prefix=raw_token[:12],
            plan=body.plan,
            quota_limits=limits,
            expires_at=expires_at,
        ))
    await session.commit()
    return AdminQuotaTokenCreateResponse(
        tokens=raw_tokens,
        plan=body.plan,
        limits=limits,
        expires_at=_iso(expires_at),
    )


@router.get("/quota-tokens", response_model=list[AdminQuotaTokenResponse])
async def list_quota_tokens(
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(QuotaToken).order_by(QuotaToken.created_at.desc()).limit(200)
    )
    return [
        AdminQuotaTokenResponse(
            id=str(token.id),
            prefix=token.prefix,
            plan=token.plan,
            limits={str(k): int(v) for k, v in (token.quota_limits or {}).items()},
            expires_at=_iso(token.expires_at),
            redeemed_by=str(token.redeemed_by) if token.redeemed_by else None,
            redeemed_at=_iso(token.redeemed_at),
            created_at=_iso(token.created_at),
            is_active=bool(token.is_active),
        )
        for token in result.scalars().all()
    ]


@router.delete("/quota-tokens/{token_id}")
async def revoke_quota_token(
    token_id: UUID,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    token = await session.get(QuotaToken, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="额度令牌不存在")
    if token.redeemed_by:
        raise HTTPException(status_code=409, detail="已兑换的额度令牌不能撤销")
    token.is_active = False
    await session.commit()
    return {"ok": True}


@router.delete("/tenants/{tenant_id}/secrets/{key_name}")
async def delete_tenant_secret(
    tenant_id: UUID,
    key_name: str,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    if key_name not in ADMIN_SECRET_KEYS:
        raise HTTPException(status_code=400, detail=f"不支持的密钥名: {key_name}")
    result = await session.execute(
        delete(TenantSecret).where(
            TenantSecret.tenant_id == tenant.id,
            TenantSecret.key_name == key_name,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="密钥不存在")
    await session.commit()
    return {"ok": True}


@router.put("/tenants/{tenant_id}/status", response_model=AdminTenantResponse)
async def update_tenant_status(
    tenant_id: UUID,
    body: dict,
    admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    is_active = body.get("is_active")
    if not isinstance(is_active, bool):
        raise HTTPException(status_code=422, detail="is_active 必须是布尔值")
    if tenant.id == admin.id and not is_active:
        raise HTTPException(status_code=400, detail="不能禁用当前管理员账号")
    if (tenant.role or "user") == "admin" and not is_active and await _count_admins(session) <= 1:
        raise HTTPException(status_code=400, detail="不能禁用最后一个管理员")
    tenant.is_active = is_active
    await session.commit()
    news_count, run_count, latest_run = await _tenant_counts(session, tenant.id)
    return _tenant_response(tenant, news_count, run_count, latest_run)


@router.put("/tenants/{tenant_id}/role", response_model=AdminTenantResponse)
async def update_tenant_role(
    tenant_id: UUID,
    body: AdminRoleUpdate,
    admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail="无效角色")
    if tenant.id == admin.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="不能降级当前管理员账号")
    if (tenant.role or "user") == "admin" and body.role != "admin" and await _count_admins(session) <= 1:
        raise HTTPException(status_code=400, detail="不能降级最后一个管理员")
    tenant.role = body.role
    await session.commit()
    news_count, run_count, latest_run = await _tenant_counts(session, tenant.id)
    return _tenant_response(tenant, news_count, run_count, latest_run)


@router.put("/tenants/{tenant_id}/plan", response_model=AdminTenantResponse)
async def update_tenant_plan(
    tenant_id: UUID,
    body: AdminPlanUpdate,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    if body.plan not in VALID_PLANS:
        raise HTTPException(status_code=422, detail="无效套餐")
    tenant.plan = body.plan
    await session.commit()
    news_count, run_count, latest_run = await _tenant_counts(session, tenant.id)
    return _tenant_response(tenant, news_count, run_count, latest_run)


@router.post("/tenants/{tenant_id}/reset-password")
async def reset_tenant_password(
    tenant_id: UUID,
    body: AdminPasswordReset,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    tenant.password_hash = pwd_context.hash(body.password)
    tenant.auth_version = (tenant.auth_version or 1) + 1
    await session.commit()
    return {"ok": True}


@router.delete("/tenants/{tenant_id}/data")
async def clear_tenant_data(
    tenant_id: UUID,
    body: AdminDeleteConfirm,
    _admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    if body.confirm != tenant.email:
        raise HTTPException(status_code=400, detail="确认文本必须等于租户邮箱")
    await _ensure_no_active_run(session, tenant.id)
    await _cleanup_tenant_artifacts(tenant.id)
    await session.execute(delete(UsageRecord).where(UsageRecord.tenant_id == tenant.id))
    await session.execute(delete(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id))
    await session.execute(delete(News).where(News.tenant_id == tenant.id))
    await session.execute(delete(RunHistory).where(RunHistory.tenant_id == tenant.id))
    await session.commit()
    return {"ok": True}


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: UUID,
    body: AdminDeleteConfirm,
    admin: Tenant = Depends(get_current_admin_tenant),
    session: AsyncSession = Depends(get_session),
):
    tenant = await _get_target_tenant(session, tenant_id)
    if tenant.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前管理员账号")
    if body.confirm != tenant.email:
        raise HTTPException(status_code=400, detail="确认文本必须等于租户邮箱")
    if (tenant.role or "user") == "admin" and await _count_admins(session) <= 1:
        raise HTTPException(status_code=400, detail="不能删除最后一个管理员")
    await _ensure_no_active_run(session, tenant.id)
    await _delete_tenant_external_data(tenant.id)
    await session.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant.id))
    await session.execute(delete(QuotaToken).where(QuotaToken.redeemed_by == tenant.id))
    await session.execute(delete(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id))
    await session.execute(delete(TenantSecret).where(TenantSecret.tenant_id == tenant.id))
    await session.execute(delete(TenantConfig).where(TenantConfig.tenant_id == tenant.id))
    await session.execute(delete(UsageRecord).where(UsageRecord.tenant_id == tenant.id))
    await session.execute(delete(News).where(News.tenant_id == tenant.id))
    await session.execute(delete(RunHistory).where(RunHistory.tenant_id == tenant.id))
    await session.execute(
        delete(Tenant)
        .where(Tenant.id == tenant.id)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    return {"ok": True}
