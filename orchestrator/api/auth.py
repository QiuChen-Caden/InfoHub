"""JWT 认证 — 注册、登录、当前用户"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import get_session
from models_db import Tenant, TenantConfig, TenantSecret
from crypto import encrypt
from miniflux_client import provision_miniflux_user

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
    created_at: datetime


def _create_token(tenant_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(tenant_id), "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    """从 JWT 解析当前租户，注入到路由"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        tenant_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as e:
        log.warning(f"JWT 验证失败: {type(e).__name__}")
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    tenant = await session.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=401, detail="账户不存在或已禁用")
    return tenant


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(
        select(Tenant).where(Tenant.email == req.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="邮箱已注册")

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name=req.name,
        email=req.email,
        password_hash=pwd_context.hash(req.password),
    )
    session.add(tenant)
    await session.flush()

    session.add(TenantConfig(tenant_id=tenant_id))

    # 为租户创建独立 Miniflux 用户（在线程池中执行同步HTTP调用）
    import asyncio
    mx_username = f"tenant_{tenant_id.hex[:12]}"
    mx_password = uuid.uuid4().hex
    try:
        mx_result = await asyncio.to_thread(provision_miniflux_user, mx_username, mx_password)
        if mx_result and mx_result.get("api_key"):
            session.add(TenantSecret(
                tenant_id=tenant_id,
                key_name="miniflux_api_key",
                encrypted_value=encrypt(mx_result["api_key"]),
            ))
    except Exception as e:
        log.warning(f"Miniflux 用户创建失败，跳过: {e}")

    await session.commit()

    log.info(f"新用户注册: tenant={tenant_id} email={req.email}")
    return TokenResponse(access_token=_create_token(tenant_id))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Tenant).where(Tenant.email == req.email)
    )
    tenant = result.scalar_one_or_none()
    # 防止时序侧信道：无论用户是否存在都执行 bcrypt verify
    password_ok = pwd_context.verify(req.password, tenant.password_hash if tenant else _DUMMY_HASH)
    if not tenant or not password_ok:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not tenant.is_active:
        log.warning(f"禁用账户登录尝试: {req.email}")
        raise HTTPException(status_code=403, detail="账户已禁用")

    log.info(f"用户登录: tenant={tenant.id} email={req.email}")
    return TokenResponse(access_token=_create_token(tenant.id))


@router.get("/me", response_model=UserResponse)
async def me(tenant: Tenant = Depends(get_current_tenant)):
    return UserResponse(
        id=str(tenant.id),
        name=tenant.name,
        email=tenant.email,
        plan=tenant.plan,
        created_at=tenant.created_at,
    )
