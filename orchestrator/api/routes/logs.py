"""实时日志流 API — SSE + 历史查询"""

import logging
import os
import json
import asyncio
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from models_db import Tenant
from api.auth import get_current_tenant

log = logging.getLogger("infohub.logs")
router = APIRouter()

REDIS_URL = os.environ.get("REDIS_URL", "")


@router.get("/stream")
async def stream_logs(tenant: Tenant = Depends(get_current_tenant)):
    """SSE 实时日志流 — 订阅 Redis pub/sub channel"""
    log.info(f"SSE 日志流连接: tenant={tenant.id}")

    async def event_generator() -> AsyncGenerator[str, None]:
        r = aioredis.from_url(REDIS_URL)
        ps = r.pubsub()
        await ps.subscribe(f"logs:{tenant.id}")
        try:
            while True:
                msg = await asyncio.wait_for(
                    ps.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=30.0,
                )
                if msg and msg["type"] == "message":
                    data = msg["data"].decode("utf-8")
                    yield f"data: {data}\n\n"
                    # 检查是否是结束信号
                    try:
                        parsed = json.loads(data)
                        if parsed.get("type") == "end":
                            break
                    except (json.JSONDecodeError, KeyError):
                        pass
                elif msg is None:
                    # 超时，发送心跳保持连接
                    yield ": keepalive\n\n"
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            log.info(f"SSE 日志流断开: tenant={tenant.id}")
            try:
                await ps.unsubscribe(f"logs:{tenant.id}")
                await ps.close()
                await r.close()
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history")
async def log_history(tenant: Tenant = Depends(get_current_tenant)):
    """返回最近的日志历史"""
    if not REDIS_URL:
        return {"logs": []}

    r = aioredis.from_url(REDIS_URL)
    try:
        key = f"log_history:{tenant.id}"
        raw_entries = await r.lrange(key, -200, -1)
        logs = []
        for entry in raw_entries:
            try:
                logs.append(json.loads(entry.decode("utf-8")))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        return {"logs": logs}
    finally:
        await r.close()
