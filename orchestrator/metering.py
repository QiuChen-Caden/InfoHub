"""用量计量 — 记录 AI/推送调用次数，检查免费额度"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, extract
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

# 超额单价（分）
UNIT_COST = {
    "ai_filter": 1,
    "ai_summary": 5,
    "ai_translate": 2,
    "push_telegram": 0.5,
    "push_feishu": 0.5,
    "push_dingtalk": 0.5,
    "push_email": 0.5,
    "push_slack": 0.5,
}


async def record_usage(session: AsyncSession, tenant_id: UUID,
                       action: str, count: int = 1, tokens: int = 0):
    """记录用量，只对超出免费额度的部分计费"""
    tenant = await session.get(Tenant, tenant_id)
    is_paid = tenant and tenant.plan in ("pro", "enterprise")

    used = await get_monthly_usage(session, tenant_id, action)
    limit = FREE_LIMITS.get(action, 0)
    unit_cost = UNIT_COST.get(action, 0)

    for i in range(count):
        current_total = used + i
        # 只有超出免费额度的调用才计费（付费用户不计费）
        if is_paid or current_total < limit:
            cost = 0
        else:
            cost = int(unit_cost)
        session.add(UsageRecord(
            tenant_id=tenant_id,
            action=action,
            tokens_used=tokens,
            cost_cents=cost,
        ))
    await session.flush()


async def get_monthly_usage(session: AsyncSession, tenant_id: UUID,
                            action: str) -> int:
    """获取当月某 action 的使用次数"""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(func.count(UsageRecord.id)).where(
            UsageRecord.tenant_id == tenant_id,
            UsageRecord.action == action,
            extract("year", UsageRecord.created_at) == now.year,
            extract("month", UsageRecord.created_at) == now.month,
        )
    )
    return result.scalar() or 0


async def check_quota(session: AsyncSession, tenant_id: UUID,
                      action: str, requested: int = 1) -> bool:
    """检查是否有足够额度执行 requested 次操作

    pro/enterprise 不限。free 用户：如果剩余额度 >= requested 则通过，
    否则拒绝（不允许部分执行后超额）。
    """
    tenant = await session.get(Tenant, tenant_id)
    if tenant and tenant.plan in ("pro", "enterprise"):
        return True

    limit = FREE_LIMITS.get(action, 0)
    if limit == 0:
        return True

    used = await get_monthly_usage(session, tenant_id, action)
    remaining = limit - used
    return remaining >= requested


async def get_usage_summary(session: AsyncSession, tenant_id: UUID) -> dict:
    """获取当月用量汇总，区分免费用量和超额用量"""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(
            UsageRecord.action,
            func.count(UsageRecord.id).label("count"),
            func.sum(UsageRecord.cost_cents).label("overage_cost"),
        ).where(
            UsageRecord.tenant_id == tenant_id,
            extract("year", UsageRecord.created_at) == now.year,
            extract("month", UsageRecord.created_at) == now.month,
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
