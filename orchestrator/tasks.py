"""Celery 任务定义 — 每租户独立 pipeline，按租户 cron 调度"""

import os
import logging
import asyncio
from uuid import UUID
from datetime import datetime

from celery import Celery
from celery.signals import worker_init

log = logging.getLogger("infohub.tasks")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("infohub", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_annotations={
        "tasks.run_pipeline": {"rate_limit": "2/m"},
    },
)


@celery_app.task(name="tasks.run_pipeline", bind=True, max_retries=2)
def run_pipeline(self, tenant_id: str):
    """执行单租户 pipeline"""
    try:
        asyncio.run(_run_pipeline_async(UUID(tenant_id)))
    except Exception as exc:
        log.error(f"Pipeline 失败 tenant={tenant_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


async def _run_pipeline_async(tenant_id: UUID):
    """异步执行 pipeline"""
    from db import SessionLocal
    from main import run

    async with SessionLocal() as session:
        await run(session, tenant_id)
        await session.commit()


def _cron_matches_now(cron_expr: str, now: datetime) -> bool:
    """简易 cron 匹配：只支持 */N 和 * 格式的分钟/小时字段

    格式: minute hour day_of_month month day_of_week
    支持: *, */N, 具体数字
    """
    parts = cron_expr.strip().split()
    if len(parts) < 5:
        return False

    def _match(field: str, value: int) -> bool:
        if field == "*":
            return True
        if field.startswith("*/"):
            try:
                step = int(field[2:])
                return value % step == 0
            except ValueError:
                return False
        try:
            return int(field) == value
        except ValueError:
            return False

    return (
        _match(parts[0], now.minute)
        and _match(parts[1], now.hour)
        and _match(parts[2], now.day)
        and _match(parts[3], now.month)
        and _match(parts[4], now.weekday())  # 0=Monday in Python
    )


@celery_app.task(name="tasks.schedule_all_tenants")
def schedule_all_tenants():
    """遍历所有活跃租户，按各自 cron_schedule 决定是否调度"""
    asyncio.run(_schedule_all())


async def _schedule_all():
    from db import SessionLocal
    from sqlalchemy import select
    from models_db import Tenant, TenantConfig

    now = datetime.now()

    async with SessionLocal() as session:
        result = await session.execute(
            select(Tenant.id, TenantConfig.cron_schedule)
            .join(TenantConfig, Tenant.id == TenantConfig.tenant_id, isouter=True)
            .where(Tenant.is_active == True)
        )
        tenants = list(result)

    dispatched = 0
    for tenant_id, cron_schedule in tenants:
        schedule = cron_schedule or "*/30 * * * *"
        if _cron_matches_now(schedule, now):
            run_pipeline.delay(str(tenant_id))
            dispatched += 1

    log.info(f"调度检查: {len(tenants)} 个租户, {dispatched} 个匹配当前时间")


# Beat 每分钟触发一次调度检查（由 _cron_matches_now 决定哪些租户该跑）
celery_app.conf.beat_schedule = {
    "schedule-all-tenants": {
        "task": "tasks.schedule_all_tenants",
        "schedule": 60.0,  # 每分钟检查一次
    },
}
