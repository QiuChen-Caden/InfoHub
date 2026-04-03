"""配置加载 — 从数据库加载租户配置，兼容旧 YAML 模式"""

import os
import re
import logging
from pathlib import Path
from uuid import UUID
from typing import Optional

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models_db import TenantConfig, TenantSecret
from crypto import decrypt

log = logging.getLogger("infohub.config")

# 默认 AI 配置
DEFAULT_AI = {
    "model": "deepseek/deepseek-chat",
    "timeout": 120,
    "max_tokens": 5000,
    "batch_size": 200,
    "batch_interval": 2,
    "min_score": 0.7,
    "summary_enabled": True,
}

# 默认平台列表
DEFAULT_PLATFORMS = [
    "toutiao", "baidu", "wallstreetcn-hot", "thepaper",
    "bilibili-hot-search", "cls-hot", "ifeng", "tieba",
    "weibo", "douyin", "zhihu",
]


async def load_tenant_config(session: AsyncSession, tenant_id: UUID) -> dict:
    """从数据库加载租户配置，合并默认值"""
    result = await session.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
    )
    tc = result.scalar_one_or_none()

    # 加载租户密钥
    secrets = await _load_secrets(session, tenant_id)

    if not tc:
        log.warning(f"租户 {tenant_id} 无配置，使用默认值")
        return _build_default_config(secrets, tenant_id)

    # 合并 AI 配置
    ai = {**DEFAULT_AI}
    if tc.ai_config:
        ai.update(tc.ai_config)
    # 注入 AI API Key（从 secrets）
    if "ai_api_key" in secrets:
        ai["api_key"] = secrets["ai_api_key"]
    if "ai_api_base" in secrets:
        ai["api_base"] = secrets["ai_api_base"]

    # 合并通知配置 + secrets
    notification = tc.notification or {}
    for key in ("telegram_bot_token", "telegram_chat_id", "feishu_webhook_url",
                "dingtalk_webhook_url", "email_from", "email_password",
                "email_to", "slack_webhook_url"):
        if key in secrets:
            notification[key] = secrets[key]

    config = {
        "timezone": tc.timezone or "Asia/Shanghai",
        "platforms": tc.platforms or DEFAULT_PLATFORMS,
        "interests": tc.interests or [],
        "miniflux_url": os.environ.get("MINIFLUX_URL", "http://miniflux:8080"),
        "miniflux_api_key": secrets.get(
            "miniflux_api_key",
            os.environ.get("MINIFLUX_API_KEY", ""),
        ),
        "rsshub_url": os.environ.get("RSSHUB_URL", "http://rsshub:1200"),
        "sources": {
            "rsshub_feeds": tc.rsshub_feeds or [],
            "external_feeds": tc.external_feeds or [],
        },
        "ai": ai,
        "notification": notification,
        "output_dir": os.environ.get("OUTPUT_DIR", "/app/output"),
        "tenant_id": str(tenant_id),
        "obsidian_vault_path": os.environ.get("OBSIDIAN_VAULT_PATH", "")
                               if tc.obsidian_export else "",
        "cron_schedule": tc.cron_schedule or "*/30 * * * *",
    }

    log.info(f"租户 {tenant_id} 配置加载: "
             f"{len(config['platforms'])} 平台, "
             f"{len(config['interests'])} 兴趣标签")
    return config


async def _load_secrets(session: AsyncSession, tenant_id: UUID) -> dict:
    """加载并解密租户密钥"""
    result = await session.execute(
        select(TenantSecret).where(TenantSecret.tenant_id == tenant_id)
    )
    secrets = {}
    for s in result.scalars().all():
        try:
            secrets[s.key_name] = decrypt(s.encrypted_value)
        except Exception as e:
            log.error(f"解密密钥 {s.key_name} 失败: {e}")
    log.info(f"加载 {len(secrets)} 个租户密钥")
    return secrets


def _build_default_config(secrets: dict, tenant_id: UUID = None) -> dict:
    """构建默认配置"""
    ai = {**DEFAULT_AI}
    if "ai_api_key" in secrets:
        ai["api_key"] = secrets["ai_api_key"]

    return {
        "timezone": "Asia/Shanghai",
        "platforms": DEFAULT_PLATFORMS,
        "interests": [],
        "miniflux_url": os.environ.get("MINIFLUX_URL", "http://miniflux:8080"),
        "miniflux_api_key": secrets.get(
            "miniflux_api_key",
            os.environ.get("MINIFLUX_API_KEY", ""),
        ),
        "rsshub_url": os.environ.get("RSSHUB_URL", "http://rsshub:1200"),
        "sources": {"rsshub_feeds": [], "external_feeds": []},
        "ai": ai,
        "notification": {},
        "output_dir": os.environ.get("OUTPUT_DIR", "/app/output"),
        "tenant_id": str(tenant_id) if tenant_id else "",
        "obsidian_vault_path": "",
        "cron_schedule": "*/30 * * * *",
    }


def _resolve_env_vars(value):
    """递归解析 ${VAR:-default} 格式的环境变量（私有化部署兼容）"""
    if isinstance(value, str):
        pattern = r'\$\{(\w+)(?::-(.*?))?\}'
        def replacer(match):
            var_name = match.group(1)
            default = match.group(2) or ""
            return os.environ.get(var_name, default)
        return re.sub(pattern, replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(v) for v in value]
    return value


def load_config_from_yaml() -> dict:
    """从 YAML 加载配置（私有化部署兼容模式）"""
    config_path = os.environ.get("CONFIG_PATH", "/app/config/config.yaml")
    if not Path(config_path).exists():
        config_path = str(
            Path(__file__).parent.parent / "config" / "config.yaml"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config = _resolve_env_vars(config)

    log.info(f"YAML 配置加载: {config_path}")

    # 加载兴趣标签
    interests_path = os.environ.get(
        "INTERESTS_PATH",
        str(Path(config_path).parent / "interests.txt"),
    )
    if Path(interests_path).exists():
        with open(interests_path, "r", encoding="utf-8") as f:
            config["interests"] = [line.strip() for line in f if line.strip()]

    # 加载 RSS 源
    sources_path = str(Path(config_path).parent / "sources.yaml")
    if Path(sources_path).exists():
        with open(sources_path, "r", encoding="utf-8") as f:
            config["sources"] = yaml.safe_load(f)

    interests_count = len(config.get("interests", []))
    sources = config.get("sources", {})
    feeds_count = len(sources.get("rsshub_feeds", [])) + len(sources.get("external_feeds", []))
    log.info(f"YAML 配置详情: {interests_count} 个兴趣标签, {feeds_count} 个 RSS 源")

    return config
