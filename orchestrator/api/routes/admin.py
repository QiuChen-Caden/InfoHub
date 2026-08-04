"""管理员 API — 跨租户总览、账号操作和全局任务视图。"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_admin_tenant
from db import get_session
from models_db import ApiKey, News, RunHistory, Tenant, TenantConfig, TenantSecret, UsageRecord
from crypto import encrypt

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
ADMIN_SECRET_KEYS = {
    "ai_api_key", "ai_api_base", "miniflux_api_key",
    "telegram_bot_token", "telegram_chat_id", "feishu_webhook_url",
    "dingtalk_webhook_url", "email_from", "email_password",
    "email_to", "slack_webhook_url",
}


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


class AdminSecretUpdate(BaseModel):
    key_name: str
    value: str = Field(..., min_length=1, max_length=2048)


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
    secret = await session.get(TenantSecret, {"tenant_id": tenant.id, "key_name": body.key_name})
    if secret:
        secret.encrypted_value = encrypt(body.value)
    else:
        session.add(TenantSecret(
            tenant_id=tenant.id,
            key_name=body.key_name,
            encrypted_value=encrypt(body.value),
        ))
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
    await session.execute(delete(UsageRecord).where(UsageRecord.tenant_id == tenant.id))
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
    await session.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant.id))
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
