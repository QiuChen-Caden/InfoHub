"""Miniflux REST API 封装"""

import hashlib
import logging
import requests
from typing import List

from models import NewsItem

log = logging.getLogger("infohub.miniflux")


class MinifluxClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-Auth-Token": api_key,
            "Content-Type": "application/json",
        }
        self._available = bool(api_key)

    def fetch_unread_entries(self, limit: int = 200) -> List[NewsItem]:
        """拉取未读条目，转为统一 NewsItem"""
        if not self._available:
            log.warning("Miniflux API Key 未配置，跳过 RSS 拉取")
            return []
        try:
            resp = requests.get(
                f"{self.base_url}/v1/entries",
                headers=self.headers,
                params={
                    "status": "unread",
                    "limit": limit,
                    "order": "published_at",
                    "direction": "desc",
                },
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            log.error(f"Miniflux 拉取失败: {e}")
            return []

        items = []
        for entry in resp.json().get("entries", []):
            uid = hashlib.md5(
                f"{entry['url']}:rss".encode()
            ).hexdigest()[:16]
            item = NewsItem(
                id=uid,
                title=entry["title"],
                url=entry["url"],
                source=entry.get("feed", {}).get("title", "RSS"),
                source_type="rss",
                published_at=entry.get("published_at", ""),
                content=entry.get("content", ""),
            )
            item._miniflux_id = entry["id"]
            items.append(item)
        return items

    def mark_as_read(self, entry_ids: List[int]):
        """批量标记已读"""
        if not self._available or not entry_ids:
            return
        try:
            resp = requests.put(
                f"{self.base_url}/v1/entries",
                headers=self.headers,
                json={"entry_ids": entry_ids, "status": "read"},
                timeout=30,
            )
            resp.raise_for_status()
            log.info(f"已标记 {len(entry_ids)} 条 Miniflux 条目为已读")
        except Exception as e:
            log.error(f"标记已读失败 ({len(entry_ids)} 条): {e}")

    def create_feed(self, feed_url: str, category_id: int) -> int:
        """创建订阅源，返回 feed_id"""
        resp = requests.post(
            f"{self.base_url}/v1/feeds",
            headers=self.headers,
            json={"feed_url": feed_url, "category_id": category_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["feed_id"]

    def ensure_category(self, name: str) -> int:
        """获取或创建分类"""
        resp = requests.get(
            f"{self.base_url}/v1/categories",
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        for cat in resp.json():
            if cat["title"] == name:
                return cat["id"]
        resp = requests.post(
            f"{self.base_url}/v1/categories",
            headers=self.headers,
            json={"title": name},
            timeout=30,
        )
        return resp.json()["id"]

    def register_sources(self, sources_config: dict, rsshub_url: str):
        """自动注册 RSSHub 路由和外部 RSS 到 Miniflux"""
        if not self._available:
            return

        # 获取已有 feeds 避免重复
        try:
            resp = requests.get(
                f"{self.base_url}/v1/feeds",
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            existing_urls = {f["feed_url"] for f in resp.json()}
        except Exception:
            existing_urls = set()

        # 注册 RSSHub 路由
        for feed in sources_config.get("rsshub_feeds", []):
            url = f"{rsshub_url}{feed['route']}"
            if url in existing_urls:
                continue
            try:
                cat_id = self.ensure_category(feed.get("category", "默认"))
                self.create_feed(url, cat_id)
                log.info(f"注册订阅: {feed['name']} -> {url}")
            except Exception as e:
                log.warning(f"注册失败 {feed['name']}: {e}")

        # 注册外部 RSS
        for feed in sources_config.get("external_feeds", []):
            if feed["url"] in existing_urls:
                continue
            try:
                cat_id = self.ensure_category(feed.get("category", "默认"))
                self.create_feed(feed["url"], cat_id)
                log.info(f"注册订阅: {feed['name']} -> {feed['url']}")
            except Exception as e:
                log.warning(f"注册失败 {feed['name']}: {e}")
