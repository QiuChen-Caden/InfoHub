"""Miniflux REST API 封装 — 多租户隔离"""

import hashlib
import logging
import time
import requests
from typing import List, Optional

from models import NewsItem

log = logging.getLogger("infohub.miniflux")

# Miniflux admin 凭据（仅用于创建租户用户）
import os
_ADMIN_URL = os.environ.get("MINIFLUX_URL", "http://miniflux:8080").rstrip("/")
_ADMIN_USER = os.environ.get("MINIFLUX_ADMIN", "admin")
_ADMIN_PASS = os.environ.get("MINIFLUX_PASSWORD", "changeme123")


def provision_miniflux_user(username: str, password: str) -> Optional[dict]:
    """通过 admin API 为租户创建独立 Miniflux 用户，返回 {user_id, api_key}"""
    try:
        # 创建用户
        resp = requests.post(
            f"{_ADMIN_URL}/v1/users",
            auth=(_ADMIN_USER, _ADMIN_PASS),
            json={"username": username, "password": password, "is_admin": False},
            timeout=15,
        )
        if resp.status_code == 409:
            log.info(f"Miniflux 用户 {username} 已存在")
            # 查找已有用户
            users_resp = requests.get(
                f"{_ADMIN_URL}/v1/users",
                auth=(_ADMIN_USER, _ADMIN_PASS),
                timeout=15,
            )
            users_resp.raise_for_status()
            for u in users_resp.json():
                if u["username"] == username:
                    return _ensure_api_key(u["id"])
            return None
        resp.raise_for_status()
        user = resp.json()
        return _ensure_api_key(user["id"])
    except Exception as e:
        log.error(f"创建 Miniflux 用户失败: {e}")
        return None


def _ensure_api_key(user_id: int) -> Optional[dict]:
    """为用户创建 API key"""
    try:
        resp = requests.post(
            f"{_ADMIN_URL}/v1/users/{user_id}/api-keys",
            auth=(_ADMIN_USER, _ADMIN_PASS),
            json={"description": "infohub-auto"},
            timeout=15,
        )
        resp.raise_for_status()
        key_data = resp.json()
        return {"user_id": user_id, "api_key": key_data["api_key"]}
    except Exception as e:
        log.error(f"创建 Miniflux API key 失败: {e}")
        return None


class MinifluxClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        self._auth = None
        if api_key:
            self.headers["X-Auth-Token"] = api_key
            self._available = True
        elif os.environ.get("SINGLE_TENANT") == "true":
            # 仅限私有化单租户部署：回退到 admin basic auth
            admin_user = os.environ.get("MINIFLUX_ADMIN", "")
            admin_pass = os.environ.get("MINIFLUX_PASSWORD", "")
            if admin_user and admin_pass:
                self._auth = (admin_user, admin_pass)
                self._available = True
                log.warning("Miniflux: 单租户模式 admin basic auth 回退")
            else:
                self._available = False
                log.warning("Miniflux API Key 未配置，RSS 功能已禁用")
        else:
            self._available = False
            log.warning("Miniflux API Key 未配置，RSS 功能已禁用")

    def fetch_unread_entries(self, limit: int = 200) -> List[NewsItem]:
        """拉取未读条目，转为统一 NewsItem"""
        if not self._available:
            log.warning("Miniflux API Key 未配置，跳过 RSS 拉取")
            return []
        t0 = time.time()
        try:
            resp = requests.get(
                f"{self.base_url}/v1/entries",
                headers=self.headers,
                auth=self._auth,
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
        elapsed = time.time() - t0
        log.info(f"Miniflux 拉取 {len(items)} 条未读, 耗时 {elapsed:.1f}s")
        return items

    def mark_as_read(self, entry_ids: List[int]):
        """批量标记已读"""
        if not self._available or not entry_ids:
            return
        try:
            resp = requests.put(
                f"{self.base_url}/v1/entries",
                headers=self.headers,
                auth=self._auth,
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
            auth=self._auth,
            json={"feed_url": feed_url, "category_id": category_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["feed_id"]

    def ensure_category(self, name: str) -> int:
        """获取或创建分类（先尝试创建，处理 409 竞态）"""
        try:
            resp = requests.post(
                f"{self.base_url}/v1/categories",
                headers=self.headers,
                auth=self._auth,
                json={"title": name},
                timeout=30,
            )
            if resp.status_code == 409:
                # 已存在，查找 ID
                list_resp = requests.get(
                    f"{self.base_url}/v1/categories",
                    headers=self.headers,
                    auth=self._auth,
                    timeout=30,
                )
                list_resp.raise_for_status()
                for cat in list_resp.json():
                    if cat["title"] == name:
                        return cat["id"]
                raise RuntimeError(f"分类 {name} 创建返回 409 但查找不到")
            resp.raise_for_status()
            return resp.json()["id"]
        except requests.RequestException:
            # 回退：直接查找
            resp = requests.get(
                f"{self.base_url}/v1/categories",
                headers=self.headers,
                auth=self._auth,
                timeout=30,
            )
            resp.raise_for_status()
            for cat in resp.json():
                if cat["title"] == name:
                    return cat["id"]
            raise

    def register_sources(self, sources_config: dict, rsshub_url: str):
        """自动注册 RSSHub 路由和外部 RSS 到 Miniflux"""
        if not self._available:
            return

        # 获取已有 feeds 避免重复
        try:
            resp = requests.get(
                f"{self.base_url}/v1/feeds",
                headers=self.headers,
                auth=self._auth,
                timeout=30,
            )
            existing_urls = {f["feed_url"] for f in resp.json()}
        except Exception as e:
            log.warning(f"获取已有 feeds 失败: {e}, 将尝试注册全部")
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
