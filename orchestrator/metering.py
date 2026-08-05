"""用量计量 — 记录 AI/推送调用次数，检查免费额度"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models_db import UsageRecord, Tenant
from tz import get_tz

log = logging.getLogger("infohub.metering")

# 每月免费额度
FREE_LIMITS = {
    "ai_filter": 1000,
    "ai_summary": 100,
    "ai_translate": 200,
    "push_telegram": 500,
    "push_feishu": 500,
    "push_dingtalk": 500,
    "push_email": 500,
    "push_slack": 500,
}

# 超额单价（分，整数避免浮点精度问题）
UNIT_COST = {
    "ai_filter": 1,
    "ai_summary": 5,
    "ai_translate": 2,
    "push_telegram": 1,
    "push_feishu": 1,
    "push_dingtalk": 1,
    "push_email": 1,
    "push_slack": 1,
}


def _limits_for_tenant(tenant: Tenant | None) -> dict[str, int]:
    limits = {**FREE_LIMITS}
    if tenant and tenant.quota_limits:
        for action, amount in tenant.quota_limits.items():
            if action in FREE_LIMITS:
                limits[action] = max(0, int(amount))
    return limits


async def get_tenant_limits(session: AsyncSession, tenant_id: UUID) -> dict[str, int]:
    return _limits_for_tenant(await session.get(Tenant, tenant_id))


def _month_range(now: datetime):
    """返回当月起止时间"""
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        next_month_start = month_start.replace(year=now.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=now.month + 1)
    return month_start, next_month_start


async def record_usage(session: AsyncSession, tenant_id: UUID,
                       action: str, count: int = 1, tokens: int = 0,
                       tz_name: str = None):
    """记录用量（批量 INSERT），只对超出免费额度的部分计费"""
    values = []
    for _ in range(count):
        values.append(dict(
            tenant_id=tenant_id,
            action=action,
            tokens_used=tokens,
            cost_cents=0,
        ))

    if values:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        await session.execute(
            pg_insert(UsageRecord).values(values)
        )
        await session.flush()


async def get_monthly_usage(session: AsyncSession, tenant_id: UUID,
                            action: str, tz_name: str = None) -> int:
    """获取当月某 action 的使用次数（使用范围过滤利用索引）"""
    now = datetime.now(get_tz(tz_name))
    month_start, next_month_start = _month_range(now)
    result = await session.execute(
        select(func.count(UsageRecord.id)).where(
            UsageRecord.tenant_id == tenant_id,
            UsageRecord.action == action,
            UsageRecord.created_at >= month_start,
            UsageRecord.created_at < next_month_start,
        )
    )
    return result.scalar() or 0


async def check_quota(session: AsyncSession, tenant_id: UUID,
                      action: str, requested: int = 1,
                      tz_name: str = None) -> bool:
    """检查是否有足够额度"""
    tenant = await session.get(Tenant, tenant_id)
    limits = _limits_for_tenant(tenant)
    if action not in limits:
        return True
    limit = limits[action]
    if limit <= 0:
        log.warning(f"配额已禁用: tenant={tenant_id} action={action}")
        return False

    used = await get_monthly_usage(session, tenant_id, action, tz_name=tz_name)
    remaining = limit - used
    if remaining >= requested:
        return True
    log.warning(f"配额不足: tenant={tenant_id} action={action} used={used}/{limit}")
    return False


async def get_usage_summary(session: AsyncSession, tenant_id: UUID,
                            tz_name: str = None) -> dict:
    """获取当月用量汇总"""
    now = datetime.now(get_tz(tz_name))
    month_start, next_month_start = _month_range(now)
    limits = await get_tenant_limits(session, tenant_id)
    result = await session.execute(
        select(
            UsageRecord.action,
            func.count(UsageRecord.id).label("count"),
            func.sum(UsageRecord.cost_cents).label("overage_cost"),
        ).where(
            UsageRecord.tenant_id == tenant_id,
            UsageRecord.created_at >= month_start,
            UsageRecord.created_at < next_month_start,
        ).group_by(UsageRecord.action)
    )
    summary = {}
    for row in result:
        limit = limits.get(row.action, 0)
        count = row.count
        summary[row.action] = {
            "count": count,
            "limit": limit,
            "free_used": min(count, limit),
            "overage_count": max(0, count - limit),
            "overage_cost_cents": row.overage_cost or 0,
        }
    return summary
