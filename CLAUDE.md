# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

InfoHub is a multi-tenant SaaS news aggregation and AI processing platform. It fetches news from RSS feeds (via Miniflux/RSSHub) and Chinese platform hotlists, then uses AI (LiteLLM) to filter, score, translate, and summarize — delivering results via web UI and push notifications.

## Architecture

**7-service Docker stack:** postgres, postgres-miniflux, redis, rsshub, miniflux, api, worker, beat

```
Browser → React SPA (served by FastAPI at :8500)
            ↓ JWT auth
         FastAPI (orchestrator/api/) → /api/v1/*
            ↓ task dispatch
         Redis (broker) → Celery Beat (every 60s checks tenant cron schedules)
            ↓
         Celery Worker → run_pipeline(tenant_id)
            → orchestrator/main.py 10-step pipeline:
              load config → fetch hotlists → pull RSS → dedup → AI filter →
              AI translate → AI summarize → save to DB → notify → mark read
```

**Two Dockerfiles:**
- `Dockerfile.api` — multi-stage: Bun builds frontend → Python serves API + SPA static files
- `orchestrator/Dockerfile` — Python only, `entrypoint.sh` switches mode via `APP_MODE` env (api/worker/beat)

**Multi-tenancy:** All data is tenant-isolated in PostgreSQL. Secrets are Fernet-encrypted in `tenant_secrets`. Each tenant gets their own Miniflux user. The `APP_MODE=api` container auto-bootstraps a tenant on first start using `BOOTSTRAP_EMAIL`/`BOOTSTRAP_PASSWORD` from `.env`.

**Database:** SQLAlchemy async with `create_all()` on startup (no Alembic migrations yet). Tables: `tenants`, `tenant_configs`, `tenant_secrets`, `usage_records`, `news`, `run_history`.

## Common Commands

```bash
# First-time setup (generates ENCRYPTION_KEY, creates .env)
bash init.sh

# Start/rebuild all services
docker compose up -d
docker compose up -d --build

# Single-tenant/private mode
docker compose -f docker-compose.private.yml up -d

# Frontend dev
cd frontend && bun install && bun run dev

# Backend dev (outside Docker)
cd orchestrator
pip install -r requirements.txt   # or: uv pip install -r requirements.txt
uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 2

# Celery worker/beat
celery -A tasks worker --loglevel=info --concurrency=4
celery -A tasks beat --loglevel=info
```

## Key Files

| File | Purpose |
|------|---------|
| `orchestrator/main.py` | Core 10-step pipeline, the central business logic |
| `orchestrator/tasks.py` | Celery task definitions + beat schedule dispatcher |
| `orchestrator/db.py` | Async SQLAlchemy engine, session factory, `init_db()` |
| `orchestrator/models_db.py` | ORM models (Tenant, TenantConfig, News, etc.) |
| `orchestrator/api/app.py` | FastAPI app setup, router mounts, SPA static serving |
| `orchestrator/api/auth.py` | JWT register/login/me endpoints |
| `orchestrator/ai_processor.py` | LiteLLM calls: filter, summarize, translate |
| `orchestrator/metering.py` | Per-tenant monthly usage quota tracking |
| `orchestrator/config_loader.py` | DB-based tenant config with YAML fallback |
| `orchestrator/crypto.py` | Fernet encryption for tenant secrets |
| `config/config.yaml` | Default runtime config (AI params, cron, platforms) |
| `config/sources.yaml` | RSS feed definitions |
| `frontend/src/api.ts` | All REST API calls with JWT token handling |
| `frontend/src/auth.ts` | JWT token storage helpers |

## Tech Stack

- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS + Recharts (built with Bun)
- **Backend:** Python 3.12 + FastAPI + SQLAlchemy (async) + Celery + Redis
- **AI:** LiteLLM (default model: `deepseek/deepseek-chat`)
- **Data stores:** PostgreSQL 16 (app + Miniflux), Redis 7 (Celery broker + RSSHub cache)
- **RSS:** Miniflux 2.2.5 (aggregator) + RSSHub (route generator)
- **Auth:** PyJWT + passlib/bcrypt
- **Ports:** API at 8500, Miniflux at 8480 (localhost only)

## Important Patterns

- The backend uses `asyncpg` — all DB operations are async. The Celery worker bridges sync→async via `asyncio.run()` in task handlers.
- Hotlist data comes from external API `newsnow.busiyi.world/api/s` — not under project control.
- `entrypoint.sh` in the orchestrator container reads `APP_MODE` to decide whether to start uvicorn, celery worker, or celery beat. The same image serves all three roles.
- Frontend is built into the API container and served as static files with an SPA fallback route — no separate web server.
- No test suite or CI/CD pipeline exists yet.
