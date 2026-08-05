"""Encrypted tenant-secret helpers and legacy config migration."""

from sqlalchemy.ext.asyncio import AsyncSession

from crypto import encrypt
from models_db import TenantConfig, TenantSecret
from url_security import validate_public_http_url


SECRET_MASK = "********"

AI_SECRET_ALIASES = {
    "api_key": "ai_api_key",
    "api_base": "ai_api_base",
    "ai_api_key": "ai_api_key",
    "ai_api_base": "ai_api_base",
}

NOTIFICATION_SECRET_KEYS = {
    "telegram_bot_token",
    "telegram_chat_id",
    "feishu_webhook_url",
    "dingtalk_webhook_url",
    "email_from",
    "email_password",
    "email_to",
    "slack_webhook_url",
}

ALLOWED_SECRET_KEYS = {
    "ai_api_key",
    "ai_api_base",
    "miniflux_api_key",
    *NOTIFICATION_SECRET_KEYS,
}

URL_SECRET_KEYS = {
    "ai_api_base",
    "feishu_webhook_url",
    "dingtalk_webhook_url",
    "slack_webhook_url",
}


def is_secret_mask(value) -> bool:
    return isinstance(value, str) and value and set(value) == {"*"}


async def upsert_secret(
    session: AsyncSession,
    tenant_id,
    key_name: str,
    value: str,
) -> None:
    secret = await session.get(
        TenantSecret,
        {"tenant_id": tenant_id, "key_name": key_name},
    )
    encrypted_value = encrypt(value)
    if secret:
        secret.encrypted_value = encrypted_value
    else:
        session.add(TenantSecret(
            tenant_id=tenant_id,
            key_name=key_name,
            encrypted_value=encrypted_value,
        ))


async def extract_config_secrets(
    session: AsyncSession,
    tenant_id,
    notification: dict | None,
    ai_config: dict | None,
) -> tuple[dict, dict]:
    """Move secret-bearing config values into tenant_secrets."""
    clean_notification = dict(notification or {})
    clean_ai = dict(ai_config or {})

    for config_key, stored_key in AI_SECRET_ALIASES.items():
        if config_key not in clean_ai:
            continue
        value = clean_ai.pop(config_key)
        if value not in (None, "") and not is_secret_mask(value):
            if stored_key in URL_SECRET_KEYS:
                validate_public_http_url(str(value))
            await upsert_secret(session, tenant_id, stored_key, str(value))

    for key in NOTIFICATION_SECRET_KEYS:
        if key not in clean_notification:
            continue
        value = clean_notification.pop(key)
        if value not in (None, "") and not is_secret_mask(value):
            if key in URL_SECRET_KEYS:
                validate_public_http_url(str(value))
            await upsert_secret(session, tenant_id, key, str(value))

    return clean_notification, clean_ai


async def migrate_plaintext_config_secrets(
    session: AsyncSession,
    config: TenantConfig,
) -> None:
    clean_notification, clean_ai = await extract_config_secrets(
        session,
        config.tenant_id,
        config.notification,
        config.ai_config,
    )
    if clean_notification != (config.notification or {}):
        config.notification = clean_notification
    if clean_ai != (config.ai_config or {}):
        config.ai_config = clean_ai


def masked_config(
    notification: dict | None,
    ai_config: dict | None,
    stored_keys: set[str],
) -> tuple[dict, dict]:
    safe_notification = {
        key: (SECRET_MASK if key in NOTIFICATION_SECRET_KEYS else value)
        for key, value in (notification or {}).items()
    }
    safe_ai = {
        key: (SECRET_MASK if key in AI_SECRET_ALIASES else value)
        for key, value in (ai_config or {}).items()
    }

    for key in stored_keys & NOTIFICATION_SECRET_KEYS:
        safe_notification[key] = SECRET_MASK
    if "ai_api_key" in stored_keys:
        safe_ai["api_key"] = SECRET_MASK
    if "ai_api_base" in stored_keys:
        safe_ai["api_base"] = SECRET_MASK
    return safe_notification, safe_ai
