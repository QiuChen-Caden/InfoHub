"""Celery 任务定义 — 每租户独立 pipeline，按租户 cron 调度"""

import os
import sys
import logging
import asyncio
from uuid import UUID
from datetime import datetime, timedelta, timezone

# 确保 /app 在 sys.path 中（prefork 子进程可能丢失 cwd）
_app_dir = os.path.dirname(os.path.abspath(__file__))


def _ensure_path():
    """确保当前目录在 sys.path 中（每次任务执行时调用）"""
    if _app_dir not in sys.path:
        sys.path.insert(0, _app_dir)


_ensure_path()

from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

log = logging.getLogger("infohub.tasks")

REDIS_URL = os.environ.get("REDIS_URL", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL 环境变量未设置")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 环境变量未设置")

celery_app = Celery("infohub", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_annotations={
        "tasks.run_pipeline": {"rate_limit": "2/m"},
    },
)

# 数据库引擎 — 每个事件循环创建一个，避免跨 loop 复用
def _make_session_factory():
    """创建数据库引擎和 session factory（每个 asyncio.run 调用新建）"""
    engine = create_async_engine(
        DATABASE_URL, pool_size=5, max_overflow=5,
        pool_pre_ping=True, pool_recycle=300,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


# 可重试的暂时性异常
_TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OSError)

@celery_app.task(name="tasks.run_pipeline", bind=True, max_retries=2,
                 soft_time_limit=600, time_limit=660)
def run_pipeline(self, tenant_id: str, run_id: int = None):
    """执行单租户 pipeline"""
    _ensure_path()
    log.info(f"任务开始 tenant={tenant_id} run_id={run_id}")
    try:
        asyncio.run(_run_pipeline_async(UUID(tenant_id), run_id))
        log.info(f"任务完成 tenant={tenant_id}")
    except _TRANSIENT_ERRORS as exc:
        log.exception(f"Pipeline 暂时性错误 tenant={tenant_id}")
        raise self.retry(exc=exc, countdown=60)
    except Exception as exc:
        log.exception(f"Pipeline 永久性失败 tenant={tenant_id}")
        raise


async def _run_pipeline_async(tenant_id: UUID, run_id: int = None):
    """异步执行 pipeline"""
    from main import run

    engine, Session = _make_session_factory()
    try:
        async with Session() as session:
            await run(session, tenant_id, run_id=run_id)
            await session.commit()
    finally:
        await engine.dispose()


def _cron_matches_now(cron_expr: str, now: datetime) -> bool:
    """使用 croniter 检查 cron 表达式是否匹配当前分钟"""
    try:
        from croniter import croniter
        if not croniter.is_valid(cron_expr):
            log.warning(f"无效的 cron 表达式: {cron_expr}")
            return False
        # 检查当前分钟是否在上一个匹配点后的 60 秒内
        cron = croniter(cron_expr, now - timedelta(seconds=61))
        next_time = cron.get_next(datetime)
        return (next_time.hour == now.hour and
                next_time.minute == now.minute and
                next_time.day == now.day and
                next_time.month == now.month)
    except Exception as e:
        log.warning(f"cron 匹配失败 {cron_expr}: {e}")
        return False


@celery_app.task(name="tasks.schedule_all_tenants")
def schedule_all_tenants():
    """遍历所有活跃租户，按各自 cron_schedule 决定是否调度"""
    _ensure_path()
    asyncio.run(_schedule_all())


async def _schedule_all():
    from sqlalchemy import select
    from models_db import Tenant, TenantConfig

    # 每次创建轻量引擎（asyncpg 连接不能跨 asyncio.run 复用）
    engine = create_async_engine(
        DATABASE_URL, pool_size=2, max_overflow=0,
        pool_pre_ping=True, pool_recycle=300,
    )
    Session = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone(timedelta(hours=8)))  # Asia/Shanghai

    try:
        async with Session() as session:
            result = await session.execute(
                select(Tenant.id, TenantConfig.cron_schedule)
                .join(TenantConfig, Tenant.id == TenantConfig.tenant_id, isouter=True)
                .where(Tenant.is_active == True)
            )
            tenants = list(result)
    finally:
        await engine.dispose()

    if not tenants:
        log.warning("调度检查: 未找到任何活跃租户")

    dispatched = 0
    for tenant_id, cron_schedule in tenants:
        schedule = cron_schedule or "*/30 * * * *"
        if _cron_matches_now(schedule, now):
            run_pipeline.delay(str(tenant_id))
            dispatched += 1

    log.info(f"调度检查: {len(tenants)} 个租户, {dispatched} 个匹配当前时间")


# Beat 每分钟触发一次调度检查
celery_app.conf.beat_schedule = {
    "schedule-all-tenants": {
        "task": "tasks.schedule_all_tenants",
        "schedule": 60.0,
    },
}
