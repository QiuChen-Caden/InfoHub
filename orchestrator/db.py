"""PostgreSQL 异步数据层 — 多租户隔离"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models import NewsItem
from models_db import Base, News, RunHistory, UsageRecord

log = logging.getLogger("infohub.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL, pool_size=20, max_overflow=10,
        pool_pre_ping=True, pool_recycle=300,
        connect_args={"command_timeout": 60},
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
else:
    engine = None
    SessionLocal = None
    log.warning("DATABASE_URL 未设置，数据库功能不可用")


async def init_db():
    """创建所有表（开发用，生产用 Alembic）"""
    if not engine:
        raise RuntimeError("DATABASE_URL 未设置，无法初始化数据库")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("数据库表初始化完成")


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


class Database:
    """多租户数据库操作，所有查询绑定 tenant_id"""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def filter_new(self, items: List[NewsItem]) -> List[NewsItem]:
        if not items:
            return []
        ids = [it.id for it in items]
        result = await self.session.execute(
            select(News.id).where(
                News.tenant_id == self.tenant_id,
                News.id.in_(ids),
            )
        )
        existing = {row[0] for row in result}
        return [it for it in items if it.id not in existing]

    async def save_items(self, items: List[NewsItem]):
        """批量 upsert 新闻条目（ON CONFLICT DO NOTHING）"""
        if not items:
            return
        log.info(f"保存 {len(items)} 条新闻到数据库")
        values = [
            dict(
                id=item.id,
                tenant_id=self.tenant_id,
                title=item.title,
                url=item.url,
                source=item.source,
                source_type=item.source_type,
                rank=item.rank,
                published_at=None,
                score=item.score,
                tags=",".join(item.tags) if item.tags else "",
                summary=item.summary,
            )
            for item in items
        ]
        stmt = pg_insert(News).values(values).on_conflict_do_nothing(
            index_elements=["id", "tenant_id"]
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def mark_matched(self, items: List[NewsItem]):
        if not items:
            return
        log.info(f"标记 {len(items)} 条为已匹配")
        for item in items:
            await self.session.execute(
                update(News)
                .where(News.id == item.id, News.tenant_id == self.tenant_id)
                .values(
                    score=item.score,
                    tags=",".join(item.tags) if item.tags else "",
                    summary=item.summary or "",
                )
            )
        await self.session.flush()

    async def mark_pushed(self, item_ids: List[str]):
        if not item_ids:
            return
        await self.session.execute(
            update(News)
            .where(News.tenant_id == self.tenant_id, News.id.in_(item_ids))
            .values(pushed=True)
        )
        await self.session.flush()

    async def start_run(self) -> int:
        run = RunHistory(
            tenant_id=self.tenant_id,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(run)
        await self.session.flush()
        log.info(f"创建运行记录 #{run.id} tenant={self.tenant_id}")
        return run.id

    async def finish_run(self, run_id: int, **stats):
        log.info(f"完成运行记录 #{run_id}")
        await self.session.execute(
            update(RunHistory)
            .where(RunHistory.id == run_id, RunHistory.tenant_id == self.tenant_id)
            .values(finished_at=datetime.now(timezone.utc), **stats)
        )
        await self.session.flush()

    async def get_news(self, limit: int = 50, offset: int = 0,
                       source_type: Optional[str] = None) -> List[News]:
        q = select(News).where(News.tenant_id == self.tenant_id)
        if source_type:
            q = q.where(News.source_type == source_type)
        q = q.order_by(News.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_runs(self, limit: int = 20) -> List[RunHistory]:
        q = (select(RunHistory)
             .where(RunHistory.tenant_id == self.tenant_id)
             .order_by(RunHistory.id.desc())
             .limit(limit))
        result = await self.session.execute(q)
        return list(result.scalars().all())
