FROM python:3.12-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

HEALTHCHECK --interval=60s --timeout=5s --start-period=120s --retries=3 \
  CMD pgrep -f "cron_runner.py" > /dev/null || exit 1

CMD ["/app/entrypoint.sh"]
