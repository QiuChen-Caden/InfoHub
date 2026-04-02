"""JWT 认证 — 注册、登录、当前用户"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models_db import Tenant, TenantConfig, TenantSecret
from crypto import encrypt
from miniflux_client import provision_miniflux_user

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.environ.get("JWT_SECRET", "infohub-dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 72


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    tenant = await session.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=401, detail="账户不存在或已禁用")
    return tenant


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(
        select(Tenant).where(Tenant.email == req.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="邮箱已注册")

    # 在 Python 侧生成 UUID，确保 flush 前就有值
    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name=req.name,
        email=req.email,
        password_hash=pwd_context.hash(req.password),
    )
    session.add(tenant)
    await session.flush()  # 确保 tenant 行写入后再创建关联记录

    # 创建默认配置
    session.add(TenantConfig(tenant_id=tenant_id))

    # 为租户创建独立 Miniflux 用户
    mx_username = f"tenant_{tenant_id.hex[:12]}"
    mx_password = uuid.uuid4().hex
    mx_result = provision_miniflux_user(mx_username, mx_password)
    if mx_result and mx_result.get("api_key"):
        session.add(TenantSecret(
            tenant_id=tenant_id,
            key_name="miniflux_api_key",
            encrypted_value=encrypt(mx_result["api_key"]),
        ))

    await session.commit()

    return TokenResponse(access_token=_create_token(tenant_id))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Tenant).where(Tenant.email == req.email)
    )
    tenant = result.scalar_one_or_none()
    if not tenant or not pwd_context.verify(req.password, tenant.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not tenant.is_active:
        raise HTTPException(status_code=403, detail="账户已禁用")

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
