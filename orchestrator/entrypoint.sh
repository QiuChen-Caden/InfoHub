#!/bin/bash
set -e

MODE="${APP_MODE:-api}"
WORKERS="${UVICORN_WORKERS:-2}"
CONCURRENCY="${CELERY_CONCURRENCY:-4}"
MAX_TASKS="${CELERY_MAX_TASKS_PER_CHILD:-100}"

case "$MODE" in
  api)
    echo "[entrypoint] 启动 FastAPI API 服务..."
    exec uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers "$WORKERS"
    ;;
  worker)
    echo "[entrypoint] 启动 Celery Worker..."
    exec celery -A tasks worker --loglevel=info --concurrency="$CONCURRENCY" --max-tasks-per-child="$MAX_TASKS"
    ;;
  beat)
    echo "[entrypoint] 启动 Celery Beat 调度器..."
    exec celery -A tasks beat --loglevel=info --pidfile=/tmp/celerybeat.pid
    ;;
  *)
    echo "[entrypoint] 未知模式: $MODE (可选: api, worker, beat)"
    exit 1
    ;;
esac
