#!/bin/bash
set -e

MODE="${APP_MODE:-cron}"

case "$MODE" in
  cron)
    # 原有模式：cron 调度 pipeline
    SCHEDULE="${CRON_SCHEDULE:-*/30 * * * *}"
    echo "${SCHEDULE} cd /app && python main.py >> /var/log/orchestrator.log 2>&1" > /app/crontab

    echo "[entrypoint] 调度配置: ${SCHEDULE}"
    echo "[entrypoint] 先执行一次..."
    cd /app && python main.py || true

    echo "[entrypoint] 启动定时调度..."
    exec supercronic /app/crontab
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
