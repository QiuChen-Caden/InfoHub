"""Redis 日志流 — 将管道日志实时推送到 Redis pub/sub"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

import redis

from tz import get_tz

log = logging.getLogger("infohub.logstream")

REDIS_URL = os.environ.get("REDIS_URL", "")


class RedisLogHandler(logging.Handler):
    """将日志发布到 Redis channel 并存储到 list（供历史查询）"""

    def __init__(self, redis_url: str, tenant_id: UUID, run_id: int, tz_name: str = None):
        super().__init__()
        self.r = redis.Redis.from_url(redis_url)
        self.channel = f"logs:{tenant_id}"
        self.history_key = f"log_history:{tenant_id}"
        self.run_id = run_id
        self.tenant_id = str(tenant_id)
        self.tz = get_tz(tz_name)

    def emit(self, record):
        try:
            entry = json.dumps({
                "ts": datetime.now(self.tz).strftime("%H:%M:%S"),
                "level": record.levelname,
                "msg": record.getMessage(),
                "run_id": self.run_id,
            }, ensure_ascii=False)
            pipe = self.r.pipeline(transaction=False)
            pipe.publish(self.channel, entry)
            pipe.rpush(self.history_key, entry)
            pipe.ltrim(self.history_key, -500, -1)
            pipe.expire(self.history_key, 86400)
            pipe.execute()
        except Exception:
            pass  # 日志处理器不能抛异常

    def close(self):
        try:
            # 发送结束信号
            end = json.dumps({"type": "end", "run_id": self.run_id})
            self.r.publish(self.channel, end)
            self.r.rpush(self.history_key, end)
            self.r.ltrim(self.history_key, -500, -1)
            self.r.close()
        except Exception:
            pass
        super().close()


@contextmanager
def stream_logs_to_redis(tenant_id: UUID, run_id: int, tz_name: str = None):
    """Context manager: 在管道运行期间将日志推送到 Redis"""
    redis_url = REDIS_URL
    if not redis_url:
        log.info("REDIS_URL 未设置，日志流推送已禁用")
        yield
        return

    try:
        handler = RedisLogHandler(redis_url, tenant_id, run_id, tz_name=tz_name)
    except Exception as e:
        log.warning(f"Redis 日志处理器创建失败: {e}，跳过日志流")
        yield
        return

    handler.setLevel(logging.INFO)
    logger = logging.getLogger("infohub")
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()
