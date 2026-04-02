"""私有化部署引导 — 从 YAML 配置自动创建首个租户"""

import os
import uuid
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models_db import Tenant, TenantConfig, TenantSecret
from config_loader import load_config_from_yaml
from crypto import encrypt
from miniflux_client import provision_miniflux_user

log = logging.getLogger("infohub.bootstrap")

BOOTSTRAP_EMAIL = os.environ.get("BOOTSTRAP_EMAIL", "")
BOOTSTRAP_PASSWORD = os.environ.get("BOOTSTRAP_PASSWORD", "")


async def bootstrap_from_yaml(session: AsyncSession):
    """如果数据库中没有任何租户，从 YAML 配置创建第一个租户。

    仅在私有化部署首次启动时生效。设置环境变量：
      BOOTSTRAP_EMAIL=admin@example.com
      BOOTSTRAP_PASSWORD=your-password
    """
    if not BOOTSTRAP_EMAIL or not BOOTSTRAP_PASSWORD:
        return

    # 检查是否已有租户
    result = await session.execute(select(func.count(Tenant.id)))
    count = result.scalar() or 0
    if count > 0:
        return

    log.info("首次启动，从 YAML 配置引导创建租户...")

    try:
        yaml_config = load_config_from_yaml()
    except Exception as e:
        log.warning(f"YAML 配置加载失败，跳过引导: {e}")
        return

    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="Admin",
        email=BOOTSTRAP_EMAIL,
        password_hash=pwd_context.hash(BOOTSTRAP_PASSWORD),
    )
    session.add(tenant)
    await session.flush()

    # 从 YAML 提取配置写入 TenantConfig
    sources = yaml_config.get("sources", {})
    session.add(TenantConfig(
        tenant_id=tenant_id,
        platforms=yaml_config.get("platforms", []),
        interests=yaml_config.get("interests", []),
        rsshub_feeds=sources.get("rsshub_feeds", []),
        external_feeds=sources.get("external_feeds", []),
        notification={},
        ai_config={
            k: v for k, v in yaml_config.get("ai", {}).items()
            if k not in ("api_key", "api_base")
        },
        cron_schedule=yaml_config.get("cron_schedule", "*/30 * * * *"),
    ))

    # 存储 secrets
    ai_config = yaml_config.get("ai", {})
    if ai_config.get("api_key"):
        session.add(TenantSecret(
            tenant_id=tenant_id,
            key_name="ai_api_key",
            encrypted_value=encrypt(ai_config["api_key"]),
        ))
    if ai_config.get("api_base"):
        session.add(TenantSecret(
            tenant_id=tenant_id,
            key_name="ai_api_base",
            encrypted_value=encrypt(ai_config["api_base"]),
        ))

    # 通知渠道 secrets
    notif = yaml_config.get("notification", {})
    for key in ("telegram_bot_token", "telegram_chat_id", "feishu_webhook_url",
                "dingtalk_webhook_url", "email_from", "email_password",
                "email_to", "slack_webhook_url"):
        if notif.get(key):
            session.add(TenantSecret(
                tenant_id=tenant_id,
                key_name=key,
                encrypted_value=encrypt(notif[key]),
            ))

    # 创建 Miniflux 用户
    mx_username = f"tenant_{tenant_id.hex[:12]}"
    mx_password = uuid.uuid4().hex
    mx_result = provision_miniflux_user(mx_username, mx_password)
    if mx_result and mx_result.get("api_key"):
        session.add(TenantSecret(
            tenant_id=tenant_id,
            key_name="miniflux_api_key",
            encrypted_value=encrypt(mx_result["api_key"]),
        ))

    await session.commit()
    log.info(f"引导完成: 租户 {tenant_id} ({BOOTSTRAP_EMAIL})")
