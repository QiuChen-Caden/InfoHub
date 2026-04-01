#!/bin/bash
set -e

# Create the infohub database and user on the same postgres instance
# This runs automatically on first postgres init via docker-entrypoint-initdb.d

INFOHUB_PASS="${INFOHUB_DB_PASSWORD:-infohub_secret}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=infohub_pass="$INFOHUB_PASS" <<-'EOSQL'
    CREATE USER infohub WITH PASSWORD :'infohub_pass';
    CREATE DATABASE infohub OWNER infohub;
    GRANT ALL PRIVILEGES ON DATABASE infohub TO infohub;
EOSQL

echo "InfoHub database created successfully"
