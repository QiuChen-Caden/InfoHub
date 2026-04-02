"""Workspace repository for the upcoming multitenant SaaS migration."""

from __future__ import annotations

import copy
import os
import re
import uuid
from pathlib import Path
from typing import Any

from db import initialize_database_schema

DEFAULT_WORKSPACE_CONFIG = {
    "platforms": [],
    "interests": [],
    "ai": {
        "model": "",
        "api_key": "",
        "api_base": "",
        "timeout": 120,
        "max_tokens": 5000,
        "batch_size": 200,
        "batch_interval": 2,
        "min_score": 0.7,
        "summary_enabled": True,
    },
    "notification": {
        "channels": [],
        "batch_interval": 2,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "feishu_webhook_url": "",
        "dingtalk_webhook_url": "",
        "email_from": "",
        "email_password": "",
        "email_to": "",
        "slack_webhook_url": "",
    },
    "sources": {
        "rsshub_feeds": [],
        "external_feeds": [],
    },
    "cron_schedule": "*/30 * * * *",
    "rsshub_url": "",
    "miniflux_url": "",
    "obsidian_vault_path": "",
}

SECRET_FIELDS = {
    "ai.api_key",
    "notification.telegram_bot_token",
    "notification.telegram_chat_id",
    "notification.feishu_webhook_url",
    "notification.dingtalk_webhook_url",
    "notification.email_password",
    "notification.slack_webhook_url",
    "miniflux_api_key",
}


def _workspace_defaults() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_WORKSPACE_CONFIG)


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 4)


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return base or "workspace"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class WorkspaceRepository:
    """Read and write workspace-scoped configuration from the database."""

    def __init__(self, output_dir: str = "/app/output"):
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            import psycopg2

            self.conn = psycopg2.connect(db_url)
            self.conn.autocommit = False
            self._pg = True
        else:
            import sqlite3

            sqlite_path = os.environ.get("SQLITE_PATH")
            if sqlite_path:
                db_path = Path(sqlite_path)
            else:
                db_path = Path(output_dir) / "infohub.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(db_path))
            self._pg = False

        initialize_database_schema(self.conn, self._pg)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()):
        if self._pg:
            sql = sql.replace("?", "%s")
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
        cur = self._execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        cur = self._execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def _row_exists(self, table: str, key_column: str, key_value: str) -> bool:
        row = self._fetchone(
            f"SELECT 1 FROM {table} WHERE {key_column}=?",
            (key_value,),
        )
        return row is not None

    def _insert_dict(self, table: str, values: dict[str, Any]):
        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        self._execute(sql, tuple(values[col] for col in columns)).close()

    def _update_dict(self, table: str, key_column: str, key_value: str, values: dict[str, Any]):
        assignments = ", ".join(f"{col}=?" for col in values)
        sql = f"UPDATE {table} SET {assignments}, updated_at={self._current_timestamp_sql()} WHERE {key_column}=?"
        params = tuple(values[col] for col in values) + (key_value,)
        self._execute(sql, params).close()

    def _upsert_dict(self, table: str, key_column: str, key_value: str, values: dict[str, Any]):
        if self._row_exists(table, key_column, key_value):
            self._update_dict(table, key_column, key_value, values)
            return
        payload = {key_column: key_value, **values}
        self._insert_dict(table, payload)

    def _current_timestamp_sql(self) -> str:
        return "CURRENT_TIMESTAMP"

    def _load_secret_row(self, workspace_id: str) -> dict[str, str]:
        row = self._fetchone(
            """
            SELECT ai_api_key, miniflux_api_key, telegram_bot_token, telegram_chat_id,
                   feishu_webhook_url, dingtalk_webhook_url, email_password, slack_webhook_url
            FROM workspace_secrets
            WHERE workspace_id=?
            """,
            (workspace_id,),
        )
        if not row:
            return {
                "ai_api_key": "",
                "miniflux_api_key": "",
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "feishu_webhook_url": "",
                "dingtalk_webhook_url": "",
                "email_password": "",
                "slack_webhook_url": "",
            }
        return {
            "ai_api_key": row[0] or "",
            "miniflux_api_key": row[1] or "",
            "telegram_bot_token": row[2] or "",
            "telegram_chat_id": row[3] or "",
            "feishu_webhook_url": row[4] or "",
            "dingtalk_webhook_url": row[5] or "",
            "email_password": row[6] or "",
            "slack_webhook_url": row[7] or "",
        }

    def create_workspace(
        self,
        name: str,
        owner_email: str,
        slug: str | None = None,
        owner_name: str = "",
    ) -> dict[str, Any]:
        workspace_slug = _slugify(slug or name)
        existing = self.get_workspace_by_slug(workspace_slug)
        if existing:
            return existing

        owner = self._get_or_create_user(owner_email=owner_email, display_name=owner_name)
        workspace_id = _new_id("ws")
        try:
            self._insert_dict(
                "workspaces",
                {
                    "id": workspace_id,
                    "slug": workspace_slug,
                    "name": name,
                    "owner_user_id": owner["id"],
                    "status": "active",
                },
            )
            self._insert_dict(
                "workspace_members",
                {
                    "workspace_id": workspace_id,
                    "user_id": owner["id"],
                    "role": "owner",
                },
            )
            self._ensure_workspace_defaults(workspace_id)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_workspace(workspace_id)

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT id, slug, name, owner_user_id, status, created_at, updated_at
            FROM workspaces
            WHERE id=?
            """,
            (workspace_id,),
        )
        if not row:
            return None
        return {
            "id": row[0],
            "slug": row[1],
            "name": row[2],
            "owner_user_id": row[3],
            "status": row[4],
            "created_at": str(row[5]),
            "updated_at": str(row[6]),
        }

    def get_workspace_by_slug(self, slug: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT id FROM workspaces WHERE slug=?", (slug,))
        if not row:
            return None
        return self.get_workspace(row[0])

    def list_workspaces(self) -> list[dict[str, Any]]:
        rows = self._fetchall(
            """
            SELECT id, slug, name, owner_user_id, status, created_at, updated_at
            FROM workspaces
            ORDER BY created_at ASC
            """
        )
        return [
            {
                "id": row[0],
                "slug": row[1],
                "name": row[2],
                "owner_user_id": row[3],
                "status": row[4],
                "created_at": str(row[5]),
                "updated_at": str(row[6]),
            }
            for row in rows
        ]

    def get_workspace_config(self, workspace_id: str, include_secrets: bool = False) -> dict[str, Any] | None:
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return None

        config = _workspace_defaults()
        config["workspace"] = workspace

        settings_row = self._fetchone(
            """
            SELECT cron_schedule, rsshub_url, miniflux_url, obsidian_vault_path,
                   ai_model, ai_api_base, ai_timeout, ai_max_tokens, ai_batch_size,
                   ai_batch_interval, ai_min_score, ai_summary_enabled,
                   notification_batch_interval, email_from, email_to, platforms_json
            FROM workspace_settings
            WHERE workspace_id=?
            """,
            (workspace_id,),
        )
        if settings_row:
            config["cron_schedule"] = settings_row[0] or config["cron_schedule"]
            config["rsshub_url"] = settings_row[1] or ""
            config["miniflux_url"] = settings_row[2] or ""
            config["obsidian_vault_path"] = settings_row[3] or ""
            config["ai"]["model"] = settings_row[4] or ""
            config["ai"]["api_base"] = settings_row[5] or ""
            config["ai"]["timeout"] = settings_row[6]
            config["ai"]["max_tokens"] = settings_row[7]
            config["ai"]["batch_size"] = settings_row[8]
            config["ai"]["batch_interval"] = settings_row[9]
            config["ai"]["min_score"] = settings_row[10]
            config["ai"]["summary_enabled"] = bool(settings_row[11])
            config["notification"]["batch_interval"] = settings_row[12]
            config["notification"]["email_from"] = settings_row[13] or ""
            config["notification"]["email_to"] = settings_row[14] or ""
            config["platforms"] = self._decode_json_list(settings_row[15])

        secrets = self._load_secret_row(workspace_id)
        config["ai"]["api_key"] = secrets["ai_api_key"] if include_secrets else _mask_secret(secrets["ai_api_key"])
        config["notification"]["telegram_bot_token"] = secrets["telegram_bot_token"] if include_secrets else _mask_secret(secrets["telegram_bot_token"])
        config["notification"]["telegram_chat_id"] = secrets["telegram_chat_id"] if include_secrets else _mask_secret(secrets["telegram_chat_id"])
        config["notification"]["feishu_webhook_url"] = secrets["feishu_webhook_url"] if include_secrets else _mask_secret(secrets["feishu_webhook_url"])
        config["notification"]["dingtalk_webhook_url"] = secrets["dingtalk_webhook_url"] if include_secrets else _mask_secret(secrets["dingtalk_webhook_url"])
        config["notification"]["email_password"] = secrets["email_password"] if include_secrets else _mask_secret(secrets["email_password"])
        config["notification"]["slack_webhook_url"] = secrets["slack_webhook_url"] if include_secrets else _mask_secret(secrets["slack_webhook_url"])
        config["miniflux_api_key"] = secrets["miniflux_api_key"] if include_secrets else _mask_secret(secrets["miniflux_api_key"])

        tag_rows = self._fetchall(
            """
            SELECT tag
            FROM workspace_interest_tags
            WHERE workspace_id=?
            ORDER BY position ASC, created_at ASC, id ASC
            """,
            (workspace_id,),
        )
        config["interests"] = [row[0] for row in tag_rows]

        feed_rows = self._fetchall(
            """
            SELECT feed_type, route, url, name, category, enabled
            FROM workspace_feeds
            WHERE workspace_id=?
            ORDER BY created_at ASC, id ASC
            """,
            (workspace_id,),
        )
        rsshub_feeds = []
        external_feeds = []
        for row in feed_rows:
            payload = {
                "name": row[3] or "",
                "category": row[4] or "",
                "enabled": bool(row[5]),
            }
            if row[0] == "rsshub":
                rsshub_feeds.append({"route": row[1] or "", **payload})
            else:
                external_feeds.append({"url": row[2] or "", **payload})
        config["sources"] = {
            "rsshub_feeds": rsshub_feeds,
            "external_feeds": external_feeds,
        }

        channels = []
        if secrets["telegram_bot_token"]:
            channels.append("Telegram")
        if secrets["feishu_webhook_url"]:
            channels.append("Feishu")
        if secrets["dingtalk_webhook_url"]:
            channels.append("DingTalk")
        if config["notification"]["email_from"]:
            channels.append("Email")
        if secrets["slack_webhook_url"]:
            channels.append("Slack")
        config["notification"]["channels"] = channels

        return config

    def save_workspace_config(
        self,
        workspace_id: str,
        config: dict[str, Any],
        preserve_existing_secrets: bool = True,
    ):
        if not self.get_workspace(workspace_id):
            raise ValueError(f"Workspace not found: {workspace_id}")

        merged = _workspace_defaults()
        merged["platforms"] = list(config.get("platforms", merged["platforms"]))
        merged["interests"] = list(config.get("interests", merged["interests"]))
        merged["cron_schedule"] = config.get("cron_schedule", merged["cron_schedule"]) or merged["cron_schedule"]
        merged["rsshub_url"] = config.get("rsshub_url", "")
        merged["miniflux_url"] = config.get("miniflux_url", "")
        merged["obsidian_vault_path"] = config.get("obsidian_vault_path", "")

        ai = config.get("ai", {})
        notif = config.get("notification", {})
        sources = config.get("sources", {})
        merged["ai"].update({k: ai.get(k, merged["ai"][k]) for k in merged["ai"]})
        merged["notification"].update({k: notif.get(k, merged["notification"][k]) for k in merged["notification"] if k != "channels"})
        merged["sources"]["rsshub_feeds"] = list(sources.get("rsshub_feeds", []))
        merged["sources"]["external_feeds"] = list(sources.get("external_feeds", []))

        existing_secrets = self._load_secret_row(workspace_id)
        secrets = {
            "ai_api_key": self._coalesce_secret(ai.get("api_key", ""), existing_secrets["ai_api_key"], preserve_existing_secrets),
            "miniflux_api_key": self._coalesce_secret(config.get("miniflux_api_key", ""), existing_secrets["miniflux_api_key"], preserve_existing_secrets),
            "telegram_bot_token": self._coalesce_secret(notif.get("telegram_bot_token", ""), existing_secrets["telegram_bot_token"], preserve_existing_secrets),
            "telegram_chat_id": self._coalesce_secret(notif.get("telegram_chat_id", ""), existing_secrets["telegram_chat_id"], preserve_existing_secrets),
            "feishu_webhook_url": self._coalesce_secret(notif.get("feishu_webhook_url", ""), existing_secrets["feishu_webhook_url"], preserve_existing_secrets),
            "dingtalk_webhook_url": self._coalesce_secret(notif.get("dingtalk_webhook_url", ""), existing_secrets["dingtalk_webhook_url"], preserve_existing_secrets),
            "email_password": self._coalesce_secret(notif.get("email_password", ""), existing_secrets["email_password"], preserve_existing_secrets),
            "slack_webhook_url": self._coalesce_secret(notif.get("slack_webhook_url", ""), existing_secrets["slack_webhook_url"], preserve_existing_secrets),
        }

        try:
            self._upsert_dict(
                "workspace_settings",
                "workspace_id",
                workspace_id,
                {
                    "enabled": 1,
                    "cron_schedule": merged["cron_schedule"],
                    "rsshub_url": merged["rsshub_url"],
                    "miniflux_url": merged["miniflux_url"],
                    "obsidian_vault_path": merged["obsidian_vault_path"],
                    "ai_model": merged["ai"]["model"],
                    "ai_api_base": merged["ai"]["api_base"],
                    "ai_timeout": merged["ai"]["timeout"],
                    "ai_max_tokens": merged["ai"]["max_tokens"],
                    "ai_batch_size": merged["ai"]["batch_size"],
                    "ai_batch_interval": merged["ai"]["batch_interval"],
                    "ai_min_score": merged["ai"]["min_score"],
                    "ai_summary_enabled": 1 if merged["ai"]["summary_enabled"] else 0,
                    "notification_batch_interval": merged["notification"]["batch_interval"],
                    "email_from": merged["notification"]["email_from"],
                    "email_to": merged["notification"]["email_to"],
                    "platforms_json": self._encode_json_list(merged["platforms"]),
                },
            )
            self._upsert_dict("workspace_secrets", "workspace_id", workspace_id, secrets)
            self._replace_interest_tags(workspace_id, merged["interests"])
            self._replace_feeds(workspace_id, merged["sources"])
            self._sync_pipeline_job(workspace_id, merged["cron_schedule"])
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _replace_interest_tags(self, workspace_id: str, tags: list[str]):
        self._execute("DELETE FROM workspace_interest_tags WHERE workspace_id=?", (workspace_id,)).close()
        deduped = []
        seen = set()
        for tag in tags:
            clean = str(tag).strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            deduped.append(clean)
        for idx, tag in enumerate(deduped):
            self._insert_dict(
                "workspace_interest_tags",
                {
                    "id": _new_id("tag"),
                    "workspace_id": workspace_id,
                    "tag": tag,
                    "position": idx,
                },
            )

    def _replace_feeds(self, workspace_id: str, sources: dict[str, Any]):
        self._execute("DELETE FROM workspace_feeds WHERE workspace_id=?", (workspace_id,)).close()
        for feed in sources.get("rsshub_feeds", []):
            route = str(feed.get("route", "")).strip()
            name = str(feed.get("name", "")).strip()
            if not route or not name:
                continue
            self._insert_dict(
                "workspace_feeds",
                {
                    "id": _new_id("feed"),
                    "workspace_id": workspace_id,
                    "feed_type": "rsshub",
                    "route": route,
                    "url": "",
                    "name": name,
                    "category": str(feed.get("category", "")).strip(),
                    "enabled": 1 if feed.get("enabled", True) else 0,
                },
            )
        for feed in sources.get("external_feeds", []):
            url = str(feed.get("url", "")).strip()
            name = str(feed.get("name", "")).strip()
            if not url or not name:
                continue
            self._insert_dict(
                "workspace_feeds",
                {
                    "id": _new_id("feed"),
                    "workspace_id": workspace_id,
                    "feed_type": "external",
                    "route": "",
                    "url": url,
                    "name": name,
                    "category": str(feed.get("category", "")).strip(),
                    "enabled": 1 if feed.get("enabled", True) else 0,
                },
            )

    def _sync_pipeline_job(self, workspace_id: str, cron_schedule: str):
        job_row = self._fetchone(
            """
            SELECT id
            FROM ingest_jobs
            WHERE workspace_id=? AND job_type='pipeline'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (workspace_id,),
        )
        if job_row:
            self._update_dict(
                "ingest_jobs",
                "id",
                job_row[0],
                {
                    "enabled": 1,
                    "cron_schedule": cron_schedule,
                    "job_type": "pipeline",
                    "workspace_id": workspace_id,
                },
            )
            return
        self._insert_dict(
            "ingest_jobs",
            {
                "id": _new_id("job"),
                "workspace_id": workspace_id,
                "job_type": "pipeline",
                "enabled": 1,
                "cron_schedule": cron_schedule,
            },
        )

    def _ensure_workspace_defaults(self, workspace_id: str):
        defaults = _workspace_defaults()
        self._upsert_dict(
            "workspace_settings",
            "workspace_id",
            workspace_id,
            {
                "enabled": 1,
                "cron_schedule": defaults["cron_schedule"],
                "rsshub_url": defaults["rsshub_url"],
                "miniflux_url": defaults["miniflux_url"],
                "obsidian_vault_path": defaults["obsidian_vault_path"],
                "ai_model": defaults["ai"]["model"],
                "ai_api_base": defaults["ai"]["api_base"],
                "ai_timeout": defaults["ai"]["timeout"],
                "ai_max_tokens": defaults["ai"]["max_tokens"],
                "ai_batch_size": defaults["ai"]["batch_size"],
                "ai_batch_interval": defaults["ai"]["batch_interval"],
                "ai_min_score": defaults["ai"]["min_score"],
                "ai_summary_enabled": 1 if defaults["ai"]["summary_enabled"] else 0,
                "notification_batch_interval": defaults["notification"]["batch_interval"],
                "email_from": defaults["notification"]["email_from"],
                "email_to": defaults["notification"]["email_to"],
                "platforms_json": self._encode_json_list(defaults["platforms"]),
            },
        )
        self._upsert_dict(
            "workspace_secrets",
            "workspace_id",
            workspace_id,
            {
                "ai_api_key": "",
                "miniflux_api_key": "",
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "feishu_webhook_url": "",
                "dingtalk_webhook_url": "",
                "email_password": "",
                "slack_webhook_url": "",
            },
        )
        self._sync_pipeline_job(workspace_id, defaults["cron_schedule"])

    def _get_or_create_user(self, owner_email: str, display_name: str = "") -> dict[str, Any]:
        row = self._fetchone(
            "SELECT id, email, display_name, status FROM app_users WHERE email=?",
            (owner_email,),
        )
        if row:
            return {
                "id": row[0],
                "email": row[1],
                "display_name": row[2],
                "status": row[3],
            }
        user_id = _new_id("usr")
        self._insert_dict(
            "app_users",
            {
                "id": user_id,
                "email": owner_email,
                "display_name": display_name,
                "password_hash": "",
                "status": "active",
            },
        )
        return {
            "id": user_id,
            "email": owner_email,
            "display_name": display_name,
            "status": "active",
        }

    def _coalesce_secret(self, new_value: str, old_value: str, preserve_existing: bool) -> str:
        clean = str(new_value or "").strip()
        if not preserve_existing:
            return clean
        if not clean:
            return old_value
        return clean

    def _decode_json_list(self, raw: str | None) -> list[str]:
        if not raw:
            return []
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                return []
            parts = [item.strip().strip('"').strip("'") for item in inner.split(",")]
            return [item for item in parts if item]
        return [item for item in raw.split(",") if item]

    def _encode_json_list(self, items: list[str]) -> str:
        clean = [str(item).strip() for item in items if str(item).strip()]
        escaped = [item.replace("\\", "\\\\").replace('"', '\\"') for item in clean]
        return "[" + ",".join(f'"{item}"' for item in escaped) + "]"
