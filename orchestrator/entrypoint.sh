#!/bin/bash
set -e

# 从环境变量动态生成 crontab
SCHEDULE="${CRON_SCHEDULE:-*/30 * * * *}"
echo "${SCHEDULE} cd /app && python main.py >> /var/log/orchestrator.log 2>&1" > /app/crontab

echo "[entrypoint] 调度配置: ${SCHEDULE}"
echo "[entrypoint] 先执行一次..."

# 启动时立即跑一次
cd /app && python main.py || true

echo "[entrypoint] 启动定时调度..."
exec supercronic /app/crontab
