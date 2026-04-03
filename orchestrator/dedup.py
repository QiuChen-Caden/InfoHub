"""跨源去重 — URL 归一化 + 标题相似度 + 来源优先级"""

import re
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import List

from models import NewsItem

log = logging.getLogger("infohub.dedup")

SOURCE_PRIORITY = {"hotlist": 1, "rss": 0}

# URL 追踪参数黑名单
_TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
    'utm_term', 'from', 'source', 'spm', 'share_source',
    'share_medium', 'timestamp', 'tt_from', 'unique_k',
}


def deduplicate(items: List[NewsItem]) -> List[NewsItem]:
    seen_urls: dict = {}
    seen_titles: dict = {}
    result_list: list = []
    result_set: set = set()  # 用于 O(1) 删除检查
    url_dups = 0
    title_dups = 0

    for item in items:
        norm_url = _normalize_url(item.url) if item.url else ""
        norm_title = _normalize_title(item.title)

        # 1. URL 归一化去重
        if norm_url and norm_url in seen_urls:
            existing = seen_urls[norm_url]
            if _priority(item) > _priority(existing):
                if id(existing) in result_set:
                    result_list = [r for r in result_list if r is not existing]
                    result_set.discard(id(existing))
                result_list.append(item)
                result_set.add(id(item))
                seen_urls[norm_url] = item
                _replace_title(seen_titles, existing, item)
            url_dups += 1
            continue

        # 2. 标题相似度去重
        matched_key = _find_similar(norm_title, seen_titles)
        if matched_key:
            existing = seen_titles[matched_key]
            if _priority(item) > _priority(existing):
                if id(existing) in result_set:
                    result_list = [r for r in result_list if r is not existing]
                    result_set.discard(id(existing))
                result_list.append(item)
                result_set.add(id(item))
                del seen_titles[matched_key]
                seen_titles[norm_title] = item
                if existing.url:
                    old_url = _normalize_url(existing.url)
                    seen_urls.pop(old_url, None)
                if norm_url:
                    seen_urls[norm_url] = item
            title_dups += 1
            continue

        # 新条目
        if norm_url:
            seen_urls[norm_url] = item
        seen_titles[norm_title] = item
        result_list.append(item)
        result_set.add(id(item))

    removed = len(items) - len(result_list)
    if removed > 0:
        log.info(f"去重: {len(items)} → {len(result_list)} (URL重复 {url_dups}, 标题重复 {title_dups})")
    return result_list


def _priority(item: NewsItem) -> int:
    base = SOURCE_PRIORITY.get(item.source_type, 0) * 1000
    return base + max(0, 100 - item.rank)


def _replace_title(seen_titles: dict, old: NewsItem, new: NewsItem):
    old_key = _normalize_title(old.title)
    seen_titles.pop(old_key, None)
    seen_titles[_normalize_title(new.title)] = new


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        qs = parse_qs(p.query, keep_blank_values=False)
        clean = {k: v for k, v in qs.items()
                 if k.lower() not in _TRACKING_PARAMS}
        return urlunparse((
            'https',
            p.netloc.lower().lstrip('www.'),
            p.path.rstrip('/'),
            p.params,
            urlencode(clean, doseq=True),
            '',
        ))
    except Exception:
        return url


def _normalize_title(title: str) -> str:
    return re.sub(r'[^\w\u4e00-\u9fff]', '', title).lower()


def _find_similar(norm: str, seen: dict) -> str:
    if not norm:
        return ""
    for key in seen:
        if _similarity(norm, key) > 0.65:
            return key
    return ""


def _similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    bg_a = {a[i:i+2] for i in range(len(a)-1)}
    bg_b = {b[i:i+2] for i in range(len(b)-1)}
    if not bg_a or not bg_b:
        sa, sb = set(a), set(b)
        return len(sa & sb) / max(len(sa | sb), 1)
    jaccard = len(bg_a & bg_b) / len(bg_a | bg_b)
    len_ratio = min(len(a), len(b)) / max(len(a), len(b))
    return jaccard * 0.7 + len_ratio * 0.3
