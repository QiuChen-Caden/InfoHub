#!/bin/sh
set -e

INFOHUB_PASS="${INFOHUB_DB_PASSWORD:?INFOHUB_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=infohub_pass="$INFOHUB_PASS" <<-'EOSQL'
    CREATE USER infohub WITH PASSWORD :'infohub_pass';
    CREATE DATABASE infohub OWNER infohub;
    GRANT ALL PRIVILEGES ON DATABASE infohub TO infohub;
EOSQL

echo "InfoHub database created successfully"
