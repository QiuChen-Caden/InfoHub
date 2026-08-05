"""Outbound URL validation for tenant-controlled endpoints."""

import ipaddress
import os
import re
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


DEFAULT_RSSHUB_PREFIXES = (
    "/zhihu/", "/hackernews/", "/weibo/", "/bilibili/", "/douyin/",
    "/tieba/", "/baidu/", "/toutiao/", "/thepaper/", "/wallstreetcn/",
)


def validate_http_url_syntax(url: str) -> str:
    """Validate URL syntax and reject obviously unsafe hosts."""
    if not isinstance(url, str) or not url.strip():
        raise UnsafeUrlError("URL 不能为空")

    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("仅允许 http/https URL")
    if not parsed.hostname:
        raise UnsafeUrlError("URL 缺少主机名")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URL 不允许包含用户名或密码")

    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise UnsafeUrlError("URL 不允许访问本地主机")

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise UnsafeUrlError("URL 不允许访问私有或保留地址")

    try:
        parsed.port
    except ValueError as exc:
        raise UnsafeUrlError("URL 端口无效") from exc
    return value


def validate_public_http_url(url: str) -> str:
    """Resolve a URL and require every address to be globally routable."""
    value = validate_http_url_syntax(url)
    parsed = urlparse(value)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise UnsafeUrlError("URL 主机无法解析") from exc

    if not addresses:
        raise UnsafeUrlError("URL 主机无法解析")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeUrlError("URL 解析结果无效") from exc
        if not ip.is_global:
            raise UnsafeUrlError("URL 解析到私有或保留地址")
    return value


def validate_rsshub_route(route: str) -> str:
    if not isinstance(route, str) or not route.startswith("/"):
        raise UnsafeUrlError("RSSHub 路由必须以 / 开头")
    if len(route) > 500 or ".." in route:
        raise UnsafeUrlError("RSSHub 路由无效")
    lowered = route.lower()
    if any(marker in lowered for marker in ("http:", "https:", "%3a", "localhost", "127.0.0.1", "[::1]")):
        raise UnsafeUrlError("RSSHub 路由包含不安全参数")
    if not re.fullmatch(r"/[A-Za-z0-9_./,%?=&+~-]+", route):
        raise UnsafeUrlError("RSSHub 路由包含不允许的字符")

    configured = os.environ.get("RSSHUB_ALLOWED_PREFIXES", "")
    prefixes = tuple(
        item.strip() for item in configured.split(",") if item.strip()
    ) or DEFAULT_RSSHUB_PREFIXES
    if not any(route.startswith(prefix) for prefix in prefixes):
        raise UnsafeUrlError("RSSHub 路由不在允许列表中")
    return route
