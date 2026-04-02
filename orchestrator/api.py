"""InfoHub REST API — 轻量 FastAPI 层，读取 pipeline 产出的数据"""

import hmac
import os
import re
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import FastAPI, Query, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="InfoHub API", version="0.1.0")

# ---- CORS ----
_cors_origins = os.environ.get("CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- DB 连接 ----

def _get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url), True
    else:
        import sqlite3
        db_path = os.environ.get("SQLITE_PATH", "/app/output/infohub.db")
        return sqlite3.connect(db_path), False


@contextmanager
def get_db():
    conn, is_pg = _get_conn()
    try:
        yield conn, is_pg
    finally:
        conn.close()


# ---- 响应模型 ----

class NewsOut(BaseModel):
    id: str
    title: str
    url: str
    source: str
    source_type: str
    rank: int
    score: float
    tags: str
    summary: str
    pushed: bool
    created_at: str


class RunOut(BaseModel):
    id: int
    started_at: str
    finished_at: Optional[str]
    hotlist_count: int
    rss_count: int
    dedup_count: int
    new_count: int
    matched_count: int
    pushed_count: int
    errors: str


class StatsOut(BaseModel):
    total_news: int
    total_runs: int
    latest_run: Optional[str]
    hotlist_total: int
    rss_total: int


# ---- PUT /api/config Pydantic 模型 ----

class RSSHubFeedModel(BaseModel):
    route: str
    name: str
    category: str


class ExternalFeedModel(BaseModel):
    url: str
    name: str
    category: str


class SourcesInput(BaseModel):
    rsshub_feeds: List[RSSHubFeedModel] = []
    external_feeds: List[ExternalFeedModel] = []


class AIInput(BaseModel):
    model: str = ""
    api_key: str = ""
    api_base: str = ""
    timeout: int = 120
    max_tokens: int = 5000
    batch_size: int = 200
    batch_interval: int = 2
    min_score: float = 0.7
    summary_enabled: bool = True


class NotificationInput(BaseModel):
    batch_interval: int = 2
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    feishu_webhook_url: str = ""
    dingtalk_webhook_url: str = ""
    email_from: str = ""
    email_password: str = ""
    email_to: str = ""
    slack_webhook_url: str = ""


class ConfigInput(BaseModel):
    platforms: List[str] = []
    interests: List[str] = []
    ai: AIInput = AIInput()
    notification: NotificationInput = NotificationInput()
    sources: SourcesInput = SourcesInput()
    cron_schedule: str = ""
    rsshub_url: str = ""
    miniflux_url: str = ""
    obsidian_vault_path: str = ""


# ---- 路由 ----

@app.get("/api/news", response_model=List[NewsOut])
def list_news(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=1),
    max_score: Optional[float] = Query(None, ge=0, le=1),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """查询新闻列表，支持分页和筛选"""
    with get_db() as (conn, is_pg):
        ph = "%s" if is_pg else "?"
        sql = "SELECT id, title, url, source, source_type, rank, score, tags, summary, pushed, created_at FROM news"
        conditions, params = [], []

        if source_type:
            conditions.append(f"source_type = {ph}")
            params.append(source_type)
        if source:
            conditions.append(f"source = {ph}")
            params.append(source)
        if tag:
            conditions.append(f"tags LIKE {ph}")
            params.append(f"%{tag}%")
        if min_score is not None:
            conditions.append(f"score >= {ph}")
            params.append(min_score)
        if max_score is not None:
            conditions.append(f"score <= {ph}")
            params.append(max_score)
        if start_date:
            conditions.append(f"created_at >= {ph}")
            params.append(start_date)
        if end_date:
            conditions.append(f"created_at <= {ph}")
            params.append(end_date)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += f" ORDER BY created_at DESC LIMIT {ph} OFFSET {ph}"
        params.extend([limit, offset])

        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()

    return [
        NewsOut(
            id=r[0], title=r[1], url=r[2], source=r[3],
            source_type=r[4], rank=r[5], score=r[6], tags=r[7],
            summary=r[8], pushed=bool(r[9]),
            created_at=str(r[10]) if r[10] else "",
        )
        for r in rows
    ]


@app.get("/api/news/sources")
def list_sources():
    """返回所有不重复的 source 值"""
    with get_db() as (conn, is_pg):
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT source FROM news ORDER BY source")
        rows = cur.fetchall()
        cur.close()
    return [r[0] for r in rows]


@app.get("/api/runs", response_model=List[RunOut])
def list_runs(limit: int = Query(20, ge=1, le=100)):
    """查询运行历史"""
    with get_db() as (conn, is_pg):
        ph = "%s" if is_pg else "?"
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, started_at, finished_at, hotlist_count, rss_count, "
            f"dedup_count, new_count, matched_count, pushed_count, errors "
            f"FROM run_history ORDER BY id DESC LIMIT {ph}",
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()

    return [
        RunOut(
            id=r[0], started_at=str(r[1]), finished_at=str(r[2]) if r[2] else None,
            hotlist_count=r[3], rss_count=r[4], dedup_count=r[5],
            new_count=r[6], matched_count=r[7], pushed_count=r[8],
            errors=r[9] or "",
        )
        for r in rows
    ]


@app.get("/api/stats", response_model=StatsOut)
def get_stats():
    """获取总体统计"""
    with get_db() as (conn, is_pg):
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM news")
        total_news = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM run_history")
        total_runs = cur.fetchone()[0]
        cur.execute("SELECT MAX(started_at) FROM run_history")
        latest = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM news WHERE source_type='hotlist'")
        hotlist_total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM news WHERE source_type='rss'")
        rss_total = cur.fetchone()[0]
        cur.close()

    return StatsOut(
        total_news=total_news,
        total_runs=total_runs,
        latest_run=str(latest) if latest else None,
        hotlist_total=hotlist_total,
        rss_total=rss_total,
    )


@app.get("/api/health")
def health():
    """健康检查"""
    try:
        with get_db() as (conn, _):
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---- 配置端点 ----

_SENSITIVE_KEYS = {
    "api_key", "telegram_bot_token", "telegram_chat_id",
    "feishu_webhook_url", "dingtalk_webhook_url",
    "email_password", "slack_webhook_url",
}


def _mask(val: str) -> str:
    """脱敏：保留前4字符，其余用 * 替代"""
    if not val or len(val) <= 4:
        return "****"
    return val[:4] + "*" * (len(val) - 4)


def _is_masked(val: str) -> bool:
    """判断值是否为脱敏占位（空字符串视为未修改）"""
    return not val


_CONFIG_SECRET = os.environ.get("CONFIG_SECRET", "")


def _check_config_auth(x_config_secret: str = Header("", alias="X-Config-Secret")):
    """校验配置写入权限：需要 CONFIG_SECRET 环境变量和请求头匹配"""
    if not _CONFIG_SECRET:
        raise HTTPException(status_code=403, detail="CONFIG_SECRET not set on server, config write disabled")
    if not hmac.compare_digest(x_config_secret, _CONFIG_SECRET):
        raise HTTPException(status_code=403, detail="Invalid config secret")


def _load_raw_config(config_dir: Path):
    """加载并解析 config.yaml（解析环境变量占位符）"""
    config_path = config_dir / "config.yaml"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")
    raw = config_path.read_text(encoding="utf-8")

    def _resolve(m: re.Match) -> str:
        var, default = m.group(1), m.group(3) or ""
        val = os.environ.get(var, default)
        if val and any(c in val for c in '*{}[]&!|>%@`'):
            return '"' + val.replace('"', '\\"') + '"'
        return val

    resolved = re.sub(r"\$\{(\w+)(:-([^}]*))?\}", _resolve, raw)
    return yaml.safe_load(resolved) or {}


@app.get("/api/config")
def get_config():
    """返回脱敏后的完整配置信息"""
    config_dir = Path(os.environ.get("CONFIG_DIR", "/app/config"))
    cfg = _load_raw_config(config_dir)

    interests_path = config_dir / "interests.txt"
    interests: list[str] = []
    if interests_path.exists():
        interests = [l.strip() for l in interests_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    sources_path = config_dir / "sources.yaml"
    sources_data = {}
    if sources_path.exists():
        sources_data = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}

    # 通知渠道列表（兼容旧前端）
    notif = cfg.get("notification", {})
    channels = []
    channel_keys = {
        "telegram_bot_token": "Telegram",
        "feishu_webhook_url": "Feishu",
        "dingtalk_webhook_url": "DingTalk",
        "email_from": "Email",
        "slack_webhook_url": "Slack",
    }
    for key, name in channel_keys.items():
        if notif.get(key):
            channels.append(name)

    ai = cfg.get("ai", {})
    return {
        "platforms": cfg.get("platforms", []),
        "interests": interests,
        "ai": {
            "model": ai.get("model", ""),
            "api_key": _mask(ai.get("api_key", "")),
            "api_base": ai.get("api_base", ""),
            "timeout": ai.get("timeout", 0),
            "max_tokens": ai.get("max_tokens", 0),
            "batch_size": ai.get("batch_size", 0),
            "batch_interval": ai.get("batch_interval", 0),
            "min_score": ai.get("min_score", 0),
            "summary_enabled": ai.get("summary_enabled", False),
        },
        "notification": {
            "channels": channels,
            "batch_interval": notif.get("batch_interval", 0),
            "telegram_bot_token": _mask(notif.get("telegram_bot_token", "")),
            "telegram_chat_id": _mask(notif.get("telegram_chat_id", "")),
            "feishu_webhook_url": _mask(notif.get("feishu_webhook_url", "")),
            "dingtalk_webhook_url": _mask(notif.get("dingtalk_webhook_url", "")),
            "email_from": notif.get("email_from", ""),
            "email_password": _mask(notif.get("email_password", "")),
            "email_to": notif.get("email_to", ""),
            "slack_webhook_url": _mask(notif.get("slack_webhook_url", "")),
        },
        "sources": {
            "rsshub_feeds": sources_data.get("rsshub_feeds", []),
            "external_feeds": sources_data.get("external_feeds", []),
        },
        "cron_schedule": cfg.get("cron_schedule", ""),
        "rsshub_url": cfg.get("rsshub_url", ""),
        "miniflux_url": cfg.get("miniflux_url", ""),
        "obsidian_vault_path": cfg.get("obsidian_vault_path", ""),
    }


def _atomic_write(path: Path, content: str):
    """原子写入：先写临时文件再 rename"""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        fd = -1
        os.replace(tmp, str(path))
    except Exception:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


@app.put("/api/config", dependencies=[Depends(_check_config_auth)])
def update_config(body: ConfigInput):
    """保存配置，敏感字段为空或脱敏值时保留原值"""
    config_dir = Path(os.environ.get("CONFIG_DIR", "/app/config"))
    cfg = _load_raw_config(config_dir)

    # ---- 合并 config.yaml ----
    ai_orig = cfg.get("ai", {})
    notif_orig = cfg.get("notification", {})

    # 敏感字段：空值或脱敏格式 → 保留原值
    def _merge_sensitive(new_val: str, orig_val) -> str:
        if _is_masked(new_val):
            return orig_val if orig_val else ""
        return new_val

    new_cfg = {
        "platforms": body.platforms,
        "miniflux_url": body.miniflux_url or cfg.get("miniflux_url", ""),
        "miniflux_api_key": cfg.get("miniflux_api_key", ""),
        "rsshub_url": body.rsshub_url or cfg.get("rsshub_url", ""),
        "ai": {
            "model": body.ai.model,
            "api_key": _merge_sensitive(body.ai.api_key, ai_orig.get("api_key", "")),
            "api_base": body.ai.api_base,
            "timeout": body.ai.timeout,
            "max_tokens": body.ai.max_tokens,
            "batch_size": body.ai.batch_size,
            "batch_interval": body.ai.batch_interval,
            "min_score": body.ai.min_score,
            "summary_enabled": body.ai.summary_enabled,
        },
        "notification": {
            "batch_interval": body.notification.batch_interval,
            "telegram_bot_token": _merge_sensitive(
                body.notification.telegram_bot_token, notif_orig.get("telegram_bot_token", "")),
            "telegram_chat_id": _merge_sensitive(
                body.notification.telegram_chat_id, notif_orig.get("telegram_chat_id", "")),
            "feishu_webhook_url": _merge_sensitive(
                body.notification.feishu_webhook_url, notif_orig.get("feishu_webhook_url", "")),
            "dingtalk_webhook_url": _merge_sensitive(
                body.notification.dingtalk_webhook_url, notif_orig.get("dingtalk_webhook_url", "")),
            "email_from": body.notification.email_from,
            "email_password": _merge_sensitive(
                body.notification.email_password, notif_orig.get("email_password", "")),
            "email_to": body.notification.email_to,
            "slack_webhook_url": _merge_sensitive(
                body.notification.slack_webhook_url, notif_orig.get("slack_webhook_url", "")),
        },
        "output_dir": cfg.get("output_dir", "/app/output"),
        "obsidian_vault_path": body.obsidian_vault_path or cfg.get("obsidian_vault_path", ""),
        "cron_schedule": body.cron_schedule,
    }

    try:
        # 写 config.yaml
        _atomic_write(config_dir / "config.yaml", yaml.dump(new_cfg, allow_unicode=True, default_flow_style=False))

        # 写 sources.yaml
        sources_dict = {
            "rsshub_feeds": [f.model_dump() for f in body.sources.rsshub_feeds],
            "external_feeds": [f.model_dump() for f in body.sources.external_feeds],
        }
        _atomic_write(config_dir / "sources.yaml", yaml.dump(sources_dict, allow_unicode=True, default_flow_style=False))

        # 写 interests.txt
        _atomic_write(config_dir / "interests.txt", "\n".join(body.interests) + "\n" if body.interests else "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")

    return {"message": "Config saved"}


# ---- 手动触发运行 ----

_run_lock = threading.Lock()
_run_status = {"running": False, "last_error": "", "last_triggered": ""}


@app.get("/api/trigger/status")
def trigger_status():
    """查询当前触发状态"""
    return _run_status


@app.post("/api/trigger")
def trigger_run():
    """手动触发一次 pipeline 运行（后台执行）"""

    def _do_run():
        try:
            result = subprocess.run(
                ["python", "main.py"],
                cwd="/app",
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                _run_status["last_error"] = result.stderr[-500:] if result.stderr else "Unknown error"
        except subprocess.TimeoutExpired:
            _run_status["last_error"] = "Run timed out (600s)"
        except Exception as e:
            _run_status["last_error"] = str(e)
        finally:
            _run_status["running"] = False

    with _run_lock:
        if _run_status["running"]:
            raise HTTPException(status_code=409, detail="A run is already in progress")
        _run_status["running"] = True
        _run_status["last_error"] = ""
        _run_status["last_triggered"] = datetime.now().isoformat()
        thread = threading.Thread(target=_do_run, daemon=True)
        thread.start()

    return {"message": "Run triggered", "triggered_at": _run_status["last_triggered"]}


# ---- 静态文件（SPA）——放在最后，API 路由优先匹配 ----

_frontend_dir = Path("/app/frontend")
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
