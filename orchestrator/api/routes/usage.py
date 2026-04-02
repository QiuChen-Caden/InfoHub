"""用量查询 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models_db import Tenant
from api.auth import get_current_tenant
from metering import get_usage_summary, FREE_LIMITS

router = APIRouter()


@router.get("")
async def usage(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    summary = await get_usage_summary(session, tenant.id)
    return {"plan": tenant.plan, "usage": summary, "limits": FREE_LIMITS}


@router.get("/billing")
async def billing(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    summary = await get_usage_summary(session, tenant.id)
    total_overage = sum(v.get("overage_cost_cents", 0) for v in summary.values())
    return {
        "plan": tenant.plan,
        "total_overage_cost_cents": total_overage,
        "breakdown": summary,
    }
