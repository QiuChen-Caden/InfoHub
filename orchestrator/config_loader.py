"""配置加载 — YAML + 环境变量 + 校验"""

import os
import re
import sys
import logging
from pathlib import Path

import yaml

log = logging.getLogger("infohub.config")


def _resolve_env_vars(value):
    """递归解析 ${VAR:-default} 格式的环境变量"""
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


def _validate_config(config: dict):
    """配置校验，关键项缺失直接 fail-fast"""
    errors = []
    warnings = []

    # 必须有 output_dir
    if not config.get("output_dir"):
        errors.append("output_dir 未配置")

    # AI 配置校验
    ai = config.get("ai", {})
    if not ai.get("api_key"):
        warnings.append("AI API Key 未配置，AI 筛选/摘要/翻译将跳过")

    # 通知渠道成对校验
    notif = config.get("notification", {})
    if notif.get("telegram_bot_token") and not notif.get("telegram_chat_id"):
        errors.append("Telegram: 配置了 bot_token 但缺少 chat_id")
    if notif.get("telegram_chat_id") and not notif.get("telegram_bot_token"):
        errors.append("Telegram: 配置了 chat_id 但缺少 bot_token")
    if notif.get("email_from"):
        if not notif.get("email_password"):
            errors.append("Email: 配置了 email_from 但缺少 email_password")
        if not notif.get("email_to"):
            errors.append("Email: 配置了 email_from 但缺少 email_to")

    # 平台列表
    if not config.get("platforms"):
        warnings.append("未配置监控平台，将使用全部 11 个默认平台")

    # 兴趣标签
    if not config.get("interests"):
        warnings.append("未配置兴趣标签，AI 筛选将无法分类")

    # 输出
    for w in warnings:
        log.warning(f"[配置] {w}")
    if errors:
        for e in errors:
            log.error(f"[配置] {e}")
        log.error("配置校验失败，请修正后重试")
        sys.exit(1)


def load_config() -> dict:
    """加载配置文件并解析环境变量"""
    config_path = os.environ.get("CONFIG_PATH", "/app/config/config.yaml")
    if not Path(config_path).exists():
        config_path = str(
            Path(__file__).parent.parent / "config" / "config.yaml"
        )

    if not Path(config_path).exists():
        log.error(f"配置文件不存在: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config = _resolve_env_vars(config)

    # 本地运行时自动修正 Docker 路径（容器内跳过）
    project_root = Path(__file__).parent.parent
    output_dir = config.get("output_dir", "")
    if output_dir.startswith("/app/") and not Path("/app/config").exists():
        config["output_dir"] = str(project_root / output_dir[5:])

    # 加载兴趣标签
    interests_path = os.environ.get(
        "INTERESTS_PATH",
        str(Path(config_path).parent / "interests.txt"),
    )
    config["interests"] = _load_interests(interests_path)

    # 加载 RSSHub 源配置
    sources_path = str(Path(config_path).parent / "sources.yaml")
    if Path(sources_path).exists():
        with open(sources_path, "r", encoding="utf-8") as f:
            config["sources"] = yaml.safe_load(f)

    # 校验
    _validate_config(config)

    log.info(f"配置加载完成: {len(config.get('platforms', []))} 个平台, "
             f"{len(config.get('interests', []))} 个兴趣标签")

    return config


def _load_interests(path: str) -> list:
    if not Path(path).exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]
