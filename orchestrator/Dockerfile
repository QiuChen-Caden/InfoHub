FROM python:3.12-slim-bookworm

ARG SUPERCRONIC_VERSION=0.2.33
ARG TARGETARCH=amd64
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-${TARGETARCH}" \
    -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV CRON_SCHEDULE="*/30 * * * *"

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
