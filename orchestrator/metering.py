"""用量计量 — 记录 AI/推送调用次数，检查免费额度"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models_db import UsageRecord, Tenant

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


def _month_range(now: datetime):
    """返回当月起止时间"""
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        next_month_start = month_start.replace(year=now.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=now.month + 1)
    return month_start, next_month_start


async def record_usage(session: AsyncSession, tenant_id: UUID,
                       action: str, count: int = 1, tokens: int = 0):
    """记录用量（批量 INSERT），只对超出免费额度的部分计费"""
    tenant = await session.get(Tenant, tenant_id)
    is_paid = tenant and tenant.plan in ("pro", "enterprise")

    used = await get_monthly_usage(session, tenant_id, action)
    limit = FREE_LIMITS.get(action, 0)
    unit_cost = UNIT_COST.get(action, 0)

    values = []
    for i in range(count):
        current_total = used + i
        cost = 0 if (is_paid or current_total < limit) else unit_cost
        values.append(dict(
            tenant_id=tenant_id,
            action=action,
            tokens_used=tokens,
            cost_cents=cost,
        ))

    overage_count = sum(1 for v in values if v["cost_cents"] > 0)
    if overage_count > 0:
        log.info(f"超额计费: tenant={tenant_id} action={action} count={overage_count}")

    if values:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        await session.execute(
            pg_insert(UsageRecord).values(values)
        )
        await session.flush()


async def get_monthly_usage(session: AsyncSession, tenant_id: UUID,
                            action: str) -> int:
    """获取当月某 action 的使用次数（使用范围过滤利用索引）"""
    now = datetime.now(timezone.utc)
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
                      action: str, requested: int = 1) -> bool:
    """检查是否有足够额度"""
    tenant = await session.get(Tenant, tenant_id)
    if tenant and tenant.plan in ("pro", "enterprise"):
        return True

    limit = FREE_LIMITS.get(action, 0)
    if limit == 0:
        return True

    used = await get_monthly_usage(session, tenant_id, action)
    remaining = limit - used
    if remaining >= requested:
        return True
    log.warning(f"配额不足: tenant={tenant_id} action={action} used={used}/{limit}")
    return False


async def get_usage_summary(session: AsyncSession, tenant_id: UUID) -> dict:
    """获取当月用量汇总"""
    now = datetime.now(timezone.utc)
    month_start, next_month_start = _month_range(now)
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
        limit = FREE_LIMITS.get(row.action, 0)
        count = row.count
        summary[row.action] = {
            "count": count,
            "limit": limit,
            "free_used": min(count, limit),
            "overage_count": max(0, count - limit),
            "overage_cost_cents": row.overage_cost or 0,
        }
    return summary
