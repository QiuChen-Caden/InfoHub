"""密钥管理 API"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models_db import Tenant, TenantSecret
from api.auth import get_current_tenant
from crypto import encrypt

log = logging.getLogger("infohub.secrets")
router = APIRouter()

ALLOWED_KEYS = {
    "ai_api_key", "ai_api_base",
    "miniflux_api_key",
}


class SecretCreate(BaseModel):
    key_name: str
    value: str = Field(..., min_length=1, max_length=2048)


@router.post("")
async def store_secret(
    body: SecretCreate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    if body.key_name not in ALLOWED_KEYS:
        raise HTTPException(400, f"不支持的密钥名: {body.key_name}")

    existing = await session.execute(
        select(TenantSecret).where(
            TenantSecret.tenant_id == tenant.id,
            TenantSecret.key_name == body.key_name,
        )
    )
    secret = existing.scalar_one_or_none()
    if secret:
        secret.encrypted_value = encrypt(body.value)
    else:
        session.add(TenantSecret(
            tenant_id=tenant.id,
            key_name=body.key_name,
            encrypted_value=encrypt(body.value),
        ))
    await session.commit()
    log.info(f"密钥存储: tenant={tenant.id} key={body.key_name}")
    return {"ok": True}


@router.delete("/{key_name}")
async def delete_secret(
    key_name: str,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    if key_name not in ALLOWED_KEYS:
        raise HTTPException(400, f"不支持的密钥名: {key_name}")
    result = await session.execute(
        delete(TenantSecret).where(
            TenantSecret.tenant_id == tenant.id,
            TenantSecret.key_name == key_name,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(404, "密钥不存在")
    await session.commit()
    log.info(f"密钥删除: tenant={tenant.id} key={key_name}")
    return {"ok": True}


@router.get("")
async def list_secrets(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    """列出已存储的密钥名（不返回值）"""
    result = await session.execute(
        select(TenantSecret.key_name).where(
            TenantSecret.tenant_id == tenant.id,
        )
    )
    return {"keys": [row[0] for row in result]}
