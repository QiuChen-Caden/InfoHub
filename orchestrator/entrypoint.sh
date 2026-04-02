#!/bin/sh
set -e

MODE="${APP_MODE:-cron}"

case "$MODE" in
  cron)
    echo "[entrypoint] 启动 Python 调度模式..."
    cd /app && exec python cron_runner.py
    ;;
  api)
    echo "[entrypoint] 启动 API 服务..."
    exec uvicorn api:app --host 0.0.0.0 --port 8000
    ;;
  *)
    echo "[entrypoint] 未知模式: $MODE (可选: cron, api)"
    exit 1
    ;;
esac
