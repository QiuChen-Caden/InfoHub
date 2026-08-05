"""移植自 TrendRadar 的热榜抓取逻辑"""

import time
import random
import hashlib
import logging
import requests
from typing import List

from models import NewsItem

log = logging.getLogger("infohub.hotlist")

API_BASE = "https://newsnow.busiyi.world/api/s"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

PLATFORMS = {
    "toutiao":              "今日头条",
    "baidu":                "百度热搜",
    "wallstreetcn-hot":     "华尔街见闻",
    "thepaper":             "澎湃新闻",
    "bilibili-hot-search":  "B站热搜",
    "cls-hot":              "财联社",
    "ifeng":                "凤凰网",
    "tieba":                "贴吧",
    "weibo":                "微博",
    "douyin":               "抖音",
    "zhihu":                "知乎",
}


def fetch_platform(platform_id: str, timeout: int = 10,
                   max_retries: int = 2) -> List[dict]:
    """抓取单个平台，带重试和退避"""
    t0 = time.time()
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(
                API_BASE,
                params={"id": platform_id, "latest": ""},
                headers=HEADERS,
                timeout=timeout,
            )
            if not resp.ok:
                log.warning(f"{platform_id} HTTP {resp.status_code}")
                if attempt < max_retries:
                    wait = random.uniform(3, 5) + attempt * random.uniform(1, 2)
                    time.sleep(wait)
                    continue
                return []
            data = resp.json()
            if data.get("items"):
                items = data["items"]
                elapsed = time.time() - t0
                log.info(f"{platform_id} 抓取 {len(items)} 条, 耗时 {elapsed:.1f}s")
                return items
        except Exception as e:
            if attempt < max_retries:
                wait = random.uniform(3, 5) + attempt * random.uniform(1, 2)
                log.info(f"{platform_id} 重试 {attempt+1}, 等待 {wait:.1f}s")
                time.sleep(wait)
            else:
                log.warning(f"{platform_id} 抓取失败: {e}")
    return []


def fetch_all_hotlists(enabled_platforms: List[str] = None) -> List[NewsItem]:
    """批量抓取所有平台"""
    platforms = enabled_platforms or list(PLATFORMS.keys())
    items = []
    success, failed = [], []

    log.info(f"热榜抓取开始: {len(platforms)} 个平台")

    for pid in platforms:
        raw = fetch_platform(pid)
        if raw:
            success.append(pid)
            for entry in raw:
                uid = hashlib.md5(
                    f"{entry.get('url', '')}:{pid}".encode()
                ).hexdigest()[:16]
                items.append(NewsItem(
                    id=uid,
                    title=entry["title"],
                    url=entry.get("url", ""),
                    source=PLATFORMS.get(pid, pid),
                    source_type="hotlist",
                    rank=entry.get("rank", 0),
                ))
        else:
            failed.append(pid)
        # 请求间隔 100ms + 抖动
        time.sleep(0.1 + random.uniform(0.01, 0.02))

    log.info(f"热榜抓取完成: 成功 {len(success)}/{len(platforms)} 个平台, 共 {len(items)} 条, 成功: {success}, 失败: {failed}")
    return items
