"""FastAPI 入口 — InfoHub SaaS API"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import init_db, SessionLocal
from bootstrap import bootstrap_from_yaml
from api.auth import router as auth_router
from api.routes.config import router as config_router
from api.routes.news import router as news_router
from api.routes.runs import router as runs_router
from api.routes.usage import router as usage_router
from api.routes.secrets import router as secrets_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # 私有化部署：首次启动时从 YAML 引导创建租户
    async with SessionLocal() as session:
        await bootstrap_from_yaml(session)
    yield


app = FastAPI(
    title="InfoHub API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(config_router, prefix="/api/v1/config", tags=["config"])
app.include_router(news_router, prefix="/api/v1/news", tags=["news"])
app.include_router(runs_router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(usage_router, prefix="/api/v1/usage", tags=["usage"])
app.include_router(secrets_router, prefix="/api/v1/secrets", tags=["secrets"])


@app.get("/health")
async def health():
    return {"status": "ok"}


# 挂载前端静态文件（Dockerfile.api 构建时 COPY 到 /app/frontend）
_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True))
