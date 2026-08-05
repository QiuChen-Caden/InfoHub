"""Transactional notification outbox creation and delivery."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config_loader import load_tenant_config
from metering import check_quota, record_usage
from models import NewsItem
from models_db import News, NotificationOutbox, Tenant
from notifier import Notifier


log = logging.getLogger("infohub.delivery")

CHANNEL_KEYS = {
    "telegram": "telegram_bot_token",
    "feishu": "feishu_webhook_url",
    "dingtalk": "dingtalk_webhook_url",
    "email": "email_from",
    "slack": "slack_webhook_url",
}


def _serialize_item(item: NewsItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "source_type": item.source_type,
        "rank": item.rank,
        "score": item.score,
        "tags": list(item.tags or []),
        "summary": item.summary,
    }


def _deserialize_item(value: dict) -> NewsItem:
    return NewsItem(
        id=str(value["id"]),
        title=str(value.get("title", "")),
        url=str(value.get("url", "")),
        source=str(value.get("source", "")),
        source_type=str(value.get("source_type", "")),
        rank=int(value.get("rank", 0)),
        score=float(value.get("score", 0)),
        tags=list(value.get("tags", [])),
        summary=str(value.get("summary", "")),
    )


async def create_outbox_records(
    session: AsyncSession,
    tenant_id,
    run_id: int,
    channels: list[str],
    items: list[NewsItem],
    now: datetime,
    summary: str,
) -> list[int]:
    payload = {
        "items": [_serialize_item(item) for item in items],
        "now": now.isoformat(),
        "summary": summary,
    }
    ids = []
    for channel in channels:
        stmt = (
            pg_insert(NotificationOutbox)
            .values(
                tenant_id=tenant_id,
                run_id=run_id,
                channel=channel,
                payload=payload,
            )
            .on_conflict_do_nothing(
                constraint="uq_outbox_tenant_run_channel"
            )
            .returning(NotificationOutbox.id)
        )
        outbox_id = (await session.execute(stmt)).scalar_one_or_none()
        if outbox_id is None:
            outbox_id = await session.scalar(
                select(NotificationOutbox.id).where(
                    NotificationOutbox.tenant_id == tenant_id,
                    NotificationOutbox.run_id == run_id,
                    NotificationOutbox.channel == channel,
                )
            )
        if outbox_id is not None:
            ids.append(outbox_id)
    return ids


async def deliver_outbox(
    session: AsyncSession,
    outbox_id: int,
    config: dict | None = None,
) -> tuple[bool, str]:
    result = await session.execute(
        select(NotificationOutbox)
        .where(NotificationOutbox.id == outbox_id)
        .with_for_update()
    )
    outbox = result.scalar_one_or_none()
    if not outbox:
        return False, "outbox 不存在"
    if outbox.status == "sent":
        return True, ""
    if outbox.attempts >= 5:
        return False, "已达到最大重试次数"

    tenant = await session.get(Tenant, outbox.tenant_id)
    if not tenant or not tenant.is_active:
        outbox.status = "cancelled"
        outbox.last_error = "租户不存在或已禁用"
        outbox.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return False, outbox.last_error

    if config is None:
        config = await load_tenant_config(session, outbox.tenant_id)
    timezone_name = config.get("timezone")
    action = f"push_{outbox.channel}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"quota:{outbox.tenant_id}:{action}"},
    )
    if not await check_quota(session, outbox.tenant_id, action, tz_name=timezone_name):
        outbox.status = "failed"
        outbox.last_error = "推送额度已用完"
        outbox.attempts += 1
        outbox.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return False, outbox.last_error

    trigger_key = CHANNEL_KEYS.get(outbox.channel)
    notification = dict(config.get("notification", {}))
    for channel, key in CHANNEL_KEYS.items():
        if channel != outbox.channel:
            notification.pop(key, None)
    if not trigger_key or not notification.get(trigger_key):
        outbox.status = "cancelled"
        outbox.last_error = "通知渠道未配置"
        outbox.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return False, outbox.last_error

    payload = outbox.payload or {}
    items = [_deserialize_item(item) for item in payload.get("items", [])]
    try:
        now = datetime.fromisoformat(payload.get("now", ""))
    except ValueError:
        now = datetime.now(timezone.utc)

    outbox.attempts += 1
    outbox.status = "processing"
    outbox.updated_at = datetime.now(timezone.utc)
    successful, failed = Notifier(notification).send(
        items,
        now,
        summary=str(payload.get("summary", "")),
    )

    if outbox.channel in successful:
        outbox.status = "sent"
        outbox.sent_at = datetime.now(timezone.utc)
        outbox.last_error = ""
        await record_usage(session, outbox.tenant_id, action, tz_name=timezone_name)
        item_ids = [item.id for item in items]
        if item_ids:
            await session.execute(
                update(News)
                .where(News.tenant_id == outbox.tenant_id, News.id.in_(item_ids))
                .values(pushed=True)
            )
        await session.commit()
        return True, ""

    outbox.status = "failed"
    outbox.last_error = f"{outbox.channel} 推送失败"
    outbox.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return False, outbox.last_error
