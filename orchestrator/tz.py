"""时区工具 — 统一时区配置入口"""

from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Shanghai"


def get_tz(name: str = None) -> ZoneInfo:
    """获取 ZoneInfo 对象，默认 Asia/Shanghai"""
    return ZoneInfo(name or DEFAULT_TZ)
