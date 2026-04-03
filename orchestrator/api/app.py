"""FastAPI 入口 — InfoHub SaaS API"""

import os
import time
import logging
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from db import init_db, SessionLocal, engine
from bootstrap import bootstrap_from_yaml
from api.auth import router as auth_router
from api.routes.config import router as config_router
from api.routes.news import router as news_router
from api.routes.runs import router as runs_router
from api.routes.usage import router as usage_router
from api.routes.secrets import router as secrets_router
from api.routes.logs import router as logs_router

log = logging.getLogger("infohub.api")

_ENV = os.environ.get("ENVIRONMENT", "production")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("数据库初始化完成")
    async with SessionLocal() as session:
        await bootstrap_from_yaml(session)
    log.info("引导检查完成")
    yield


# 生产环境禁用 OpenAPI 文档
_docs_url = "/docs" if _ENV == "dev" else None
_redoc_url = "/redoc" if _ENV == "dev" else None

app = FastAPI(
    title="InfoHub API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# CORS
_cors_origins = os.environ.get("CORS_ORIGINS", "")
if _cors_origins:
    _cors_list = [o.strip() for o in _cors_origins.split(",") if o.strip()]
else:
    if _ENV == "dev":
        _cors_list = ["*"]
        log.warning("CORS_ORIGINS 未设置，开发模式允许所有来源")
    else:
        _cors_list = []
        log.warning("CORS_ORIGINS 未设置，生产模式不允许跨域请求")

if _cors_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_list,
        allow_credentials=False if "*" in _cors_list else True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


# 请求日志中间件
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    client_ip = request.client.host if request.client else "unknown"
    log.info(
        f"{client_ip} {request.method} {request.url.path} {response.status_code} {duration_ms:.0f}ms"
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# 速率限制
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(config_router, prefix="/api/v1/config", tags=["config"])
app.include_router(news_router, prefix="/api/v1/news", tags=["news"])
app.include_router(runs_router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(usage_router, prefix="/api/v1/usage", tags=["usage"])
app.include_router(secrets_router, prefix="/api/v1/secrets", tags=["secrets"])
app.include_router(logs_router, prefix="/api/v1/logs", tags=["logs"])


@app.get("/health")
@limiter.exempt
async def health():
    """健康检查 — 验证数据库连接"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        log.warning(f"健康检查失败: {type(e).__name__}")
        return JSONResponse(status_code=503, content={"status": "unhealthy"})


# 挂载前端静态文件 + SPA fallback
_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.is_dir():
    _frontend_dir = _frontend_dir.resolve()
    _frontend_index = _frontend_dir / "index.html"

    def _resolve_frontend_path(full_path: str) -> Path | None:
        normalized_path = PurePosixPath(full_path.replace("\\", "/"))
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            return None

        candidate = (_frontend_dir / normalized_path).resolve(strict=False)
        try:
            candidate.relative_to(_frontend_dir)
        except ValueError:
            return None
        return candidate

    # 静态资源（js/css/images）
    _assets_dir = _frontend_dir / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        """SPA fallback: 非 API 路径都返回 index.html"""
        if request.url.path == "/api" or request.url.path.startswith("/api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        if not full_path:
            return FileResponse(_frontend_index)

        file_path = _resolve_frontend_path(full_path)
        if file_path is None:
            log.warning(f"路径遍历尝试: {full_path}")
            raise HTTPException(status_code=404, detail="Not Found")

        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_frontend_index)
