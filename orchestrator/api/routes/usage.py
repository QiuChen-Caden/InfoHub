"""用量查询 API"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models_db import Tenant, TenantConfig
from api.auth import get_current_tenant
from metering import get_usage_summary, get_tenant_limits

log = logging.getLogger("infohub.usage")
router = APIRouter()


async def _get_tenant_tz(session: AsyncSession, tenant_id) -> str:
    result = await session.execute(
        select(TenantConfig.timezone).where(TenantConfig.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none() or "Asia/Shanghai"


@router.get("")
async def usage(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tz_name = await _get_tenant_tz(session, tenant.id)
    summary = await get_usage_summary(session, tenant.id, tz_name=tz_name)
    limits = await get_tenant_limits(session, tenant.id)
    return {"plan": tenant.plan, "usage": summary, "limits": limits}


@router.get("/billing")
async def billing(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    tz_name = await _get_tenant_tz(session, tenant.id)
    summary = await get_usage_summary(session, tenant.id, tz_name=tz_name)
    return {
        "plan": tenant.plan,
        "total_overage_cost_cents": 0,
        "breakdown": summary,
    }
