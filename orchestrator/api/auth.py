"""JWT + API Key 认证 — 注册、登录、当前用户、API Key 管理"""

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
import jwt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import get_session
from models_db import Tenant, TenantConfig, TenantSecret, ApiKey, QuotaToken
from crypto import encrypt
from miniflux_client import delete_miniflux_user, provision_miniflux_user
from config_loader import DEFAULT_PLATFORMS

log = logging.getLogger("infohub.auth")

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
limiter = Limiter(key_func=get_remote_address)
# 预生成一个有效的 dummy hash，用于时序侧信道防护
_DUMMY_HASH = pwd_context.hash("__dummy_password_for_timing__")

SECRET_KEY = os.environ.get("JWT_SECRET", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

_INSECURE_SECRETS = {"", "change-me-in-production", "infohub-dev-secret-change-me", "change-me"}
if SECRET_KEY in _INSECURE_SECRETS:
    raise RuntimeError(
        "JWT_SECRET 未设置或使用不安全的默认值！"
        "请通过环境变量设置一个安全的随机密钥（至少 32 字符）。"
        "生成方法: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
if len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET 长度必须至少为 32 个字符")


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    role: str
    created_at: datetime


class RedeemQuotaTokenRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=160)


class RedeemQuotaTokenResponse(BaseModel):
    ok: bool = True
    plan: str
    limits: dict[str, int]


def _create_token(tenant_id: UUID, auth_version: int = 1) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(tenant_id), "ver": auth_version, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


API_KEY_PREFIX = "ihk_"
MAX_API_KEYS_PER_TENANT = 5


def _hash_api_key(raw_key: str) -> str:
    """SHA-256 hash for API key storage"""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    """从 JWT 或 API Key 解析当前租户"""
    token = credentials.credentials

    # API Key 认证
    if token.startswith(API_KEY_PREFIX):
        key_hash = _hash_api_key(token)
        result = await session.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=401, detail="无效的 API Key")
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="API Key 已过期")
        tenant = await session.get(Tenant, api_key.tenant_id)
        if not tenant or not tenant.is_active:
            raise HTTPException(status_code=401, detail="账户不存在或已禁用")
        return tenant

    # JWT 认证
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        tenant_id = UUID(payload["sub"])
        token_version = int(payload.get("ver", 1))
    except (jwt.InvalidTokenError, KeyError, ValueError) as e:
        log.warning(f"JWT 验证失败: {type(e).__name__}")
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    tenant = await session.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active or (tenant.auth_version or 1) != token_version:
        raise HTTPException(status_code=401, detail="账户不存在或已禁用")
    return tenant


async def _get_current_tenant_jwt_only(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    """仅 JWT 认证（API Key 管理端点用，防止用 API Key 管理自身）"""
    token = credentials.credentials
    if token.startswith(API_KEY_PREFIX):
        raise HTTPException(status_code=403, detail="API Key 管理需要使用 JWT 登录")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        tenant_id = UUID(payload["sub"])
        token_version = int(payload.get("ver", 1))
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="无效的认证令牌")
    tenant = await session.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active or (tenant.auth_version or 1) != token_version:
        raise HTTPException(status_code=401, detail="账户不存在或已禁用")
    return tenant


async def get_current_admin_tenant(
    tenant: Tenant = Depends(_get_current_tenant_jwt_only),
) -> Tenant:
    """仅允许管理员账号访问。"""
    if (tenant.role or "user") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return tenant


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    email = str(req.email).strip().lower()
    existing = await session.execute(
        select(Tenant).where(func.lower(Tenant.email) == email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="邮箱已注册")

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name=req.name,
        email=email,
        password_hash=pwd_context.hash(req.password),
        role="user",
    )
    session.add(tenant)
    await session.flush()

    session.add(TenantConfig(
        tenant_id=tenant_id,
        platforms=list(DEFAULT_PLATFORMS),
    ))

    # 为租户创建独立 Miniflux 用户（在线程池中执行同步HTTP调用）
    import asyncio
    mx_username = f"tenant_{tenant_id.hex[:12]}"
    mx_password = uuid.uuid4().hex
    try:
        mx_result = await asyncio.to_thread(provision_miniflux_user, mx_username, mx_password)
        if not mx_result or not mx_result.get("user_id"):
            raise RuntimeError("Miniflux 租户用户创建失败")
        if mx_result.get("api_key"):
            session.add(TenantSecret(
                tenant_id=tenant_id,
                key_name="miniflux_api_key",
                encrypted_value=encrypt(mx_result["api_key"]),
            ))
        else:
            session.add(TenantSecret(
                tenant_id=tenant_id,
                key_name="miniflux_username",
                encrypted_value=encrypt(mx_result["username"]),
            ))
            session.add(TenantSecret(
                tenant_id=tenant_id,
                key_name="miniflux_password",
                encrypted_value=encrypt(mx_result["password"]),
            ))
    except Exception as e:
        await session.rollback()
        await asyncio.to_thread(delete_miniflux_user, mx_username)
        log.error(f"Miniflux 用户创建失败，注册回滚: {e}")
        raise HTTPException(status_code=503, detail="RSS 租户资源创建失败，请稍后重试") from e

    await session.commit()

    log.info(f"新用户注册: tenant={tenant_id} email={email}")
    return TokenResponse(access_token=_create_token(tenant_id, tenant.auth_version or 1))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest, session: AsyncSession = Depends(get_session)):
    email = str(req.email).strip().lower()
    result = await session.execute(
        select(Tenant).where(func.lower(Tenant.email) == email)
    )
    tenant = result.scalar_one_or_none()
    # 防止时序侧信道：无论用户是否存在都执行 bcrypt verify
    password_ok = pwd_context.verify(req.password, tenant.password_hash if tenant else _DUMMY_HASH)
    if not tenant or not password_ok:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not tenant.is_active:
        log.warning(f"禁用账户登录尝试: {email}")
        raise HTTPException(status_code=403, detail="账户已禁用")

    log.info(f"用户登录: tenant={tenant.id} email={email}")
    return TokenResponse(access_token=_create_token(tenant.id, tenant.auth_version or 1))


@router.get("/me", response_model=UserResponse)
async def me(tenant: Tenant = Depends(get_current_tenant)):
    return UserResponse(
        id=str(tenant.id),
        name=tenant.name,
        email=tenant.email,
        plan=tenant.plan,
        role=tenant.role or "user",
        created_at=tenant.created_at,
    )


@router.post("/redeem-quota-token", response_model=RedeemQuotaTokenResponse)
async def redeem_quota_token(
    req: RedeemQuotaTokenRequest,
    tenant: Tenant = Depends(_get_current_tenant_jwt_only),
    session: AsyncSession = Depends(get_session),
):
    token_hash = hashlib.sha256(req.token.strip().encode()).hexdigest()
    result = await session.execute(
        select(QuotaToken)
        .where(QuotaToken.token_hash == token_hash)
        .with_for_update()
    )
    quota_token = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (
        not quota_token
        or not quota_token.is_active
        or quota_token.redeemed_by is not None
        or (quota_token.expires_at and quota_token.expires_at <= now)
    ):
        raise HTTPException(status_code=400, detail="额度令牌无效、已使用或已过期")

    limits = {
        str(key): int(value)
        for key, value in (quota_token.quota_limits or {}).items()
    }
    tenant.plan = quota_token.plan
    tenant.quota_limits = limits
    quota_token.redeemed_by = tenant.id
    quota_token.redeemed_at = now
    quota_token.is_active = False
    await session.commit()
    log.info(
        f"额度令牌兑换: tenant={tenant.id} token={quota_token.prefix} plan={quota_token.plan}"
    )
    return RedeemQuotaTokenResponse(plan=quota_token.plan, limits=limits)


# ---- API Key 管理 ----

class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650)


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    expires_at: Optional[datetime]
    created_at: datetime
    is_active: bool


class CreateApiKeyResponse(BaseModel):
    key: str
    id: str
    name: str
    prefix: str
    expires_at: Optional[datetime]


@router.post("/api-keys", response_model=CreateApiKeyResponse)
async def create_api_key(
    req: CreateApiKeyRequest,
    tenant: Tenant = Depends(_get_current_tenant_jwt_only),
    session: AsyncSession = Depends(get_session),
):
    # 检查数量限制
    count_result = await session.execute(
        select(func.count(ApiKey.id)).where(
            ApiKey.tenant_id == tenant.id,
            ApiKey.is_active == True,
        )
    )
    count = count_result.scalar() or 0
    if count >= MAX_API_KEYS_PER_TENANT:
        raise HTTPException(status_code=400, detail=f"最多创建 {MAX_API_KEYS_PER_TENANT} 个 API Key")

    # 生成 key
    raw_key = API_KEY_PREFIX + secrets.token_hex(16)
    key_hash = _hash_api_key(raw_key)
    prefix = raw_key[:8]

    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)

    api_key = ApiKey(
        tenant_id=tenant.id,
        name=req.name,
        key_hash=key_hash,
        prefix=prefix,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()

    log.info(f"API Key 创建: tenant={tenant.id} name={req.name} prefix={prefix}")
    return CreateApiKeyResponse(
        key=raw_key,
        id=str(api_key.id),
        name=api_key.name,
        prefix=prefix,
        expires_at=expires_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    tenant: Tenant = Depends(_get_current_tenant_jwt_only),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.tenant_id == tenant.id)
        .order_by(ApiKey.created_at.desc())
    )
    return [
        ApiKeyResponse(
            id=str(k.id),
            name=k.name,
            prefix=k.prefix,
            expires_at=k.expires_at,
            created_at=k.created_at,
            is_active=k.is_active,
        )
        for k in result.scalars().all()
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    tenant: Tenant = Depends(_get_current_tenant_jwt_only),
    session: AsyncSession = Depends(get_session),
):
    api_key = await session.get(ApiKey, UUID(key_id))
    if not api_key or api_key.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    api_key.is_active = False
    await session.commit()
    log.info(f"API Key 撤销: tenant={tenant.id} key_id={key_id}")
    return {"ok": True}
