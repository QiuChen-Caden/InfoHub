#!/bin/bash
set -e

MODE="${APP_MODE:-api}"

case "$MODE" in
  api)
    echo "[entrypoint] 启动 FastAPI API 服务..."
    exec uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 2
    ;;
  worker)
    echo "[entrypoint] 启动 Celery Worker..."
    exec celery -A tasks worker --loglevel=info --concurrency=4
    ;;
  beat)
    echo "[entrypoint] 启动 Celery Beat 调度器..."
    exec celery -A tasks beat --loglevel=info
    ;;
  *)
    echo "[entrypoint] 未知模式: $MODE (可选: api, worker, beat)"
    exit 1
    ;;
esac
