"""Cron runner using croniter for full cron expression support."""
import os
import subprocess
import sys
import time
from datetime import datetime

from croniter import croniter


def run_pipeline():
    print(f"[cron_runner] 开始执行 pipeline...", flush=True)
    result = subprocess.run(
        [sys.executable, "/app/main.py"],
        cwd="/app",
    )
    if result.returncode != 0:
        print(f"[cron_runner] pipeline 退出码: {result.returncode}", flush=True)


if __name__ == "__main__":
    cron = os.environ.get("CRON_SCHEDULE", "*/30 * * * *")

    if not croniter.is_valid(cron):
        print(f"[cron_runner] 无效的 cron 表达式: {cron}，使用默认 */30 * * * *", flush=True)
        cron = "*/30 * * * *"

    print(f"[cron_runner] 调度表达式: {cron}", flush=True)
    print(f"[cron_runner] 先执行一次...", flush=True)
    run_pipeline()

    print(f"[cron_runner] 调度已启动，等待下次执行...", flush=True)
    while True:
        now = datetime.now()
        nxt = croniter(cron, now).get_next(datetime)
        wait = (nxt - now).total_seconds()
        print(f"[cron_runner] 下次执行: {nxt.strftime('%H:%M:%S')} (等待 {int(wait)}s)", flush=True)
        time.sleep(max(wait, 1))
        run_pipeline()
