#!/usr/bin/env bash
set -euo pipefail

create_project_db() {
  local db_name="$1"
  local db_user="$2"
  local db_password="$3"

  if [[ -z "$db_name" || -z "$db_user" || -z "$db_password" ]]; then
    echo "Skipping incomplete database config: db='$db_name' user='$db_user'"
    return
  fi

  psql \
    -v ON_ERROR_STOP=1 \
    -v db_name="$db_name" \
    -v db_user="$db_user" \
    -v db_password="$db_password" \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = :'db_user'
)\gexec
ALTER ROLE :"db_user" WITH LOGIN PASSWORD :'db_password';
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = :'db_name'
)\gexec
GRANT ALL PRIVILEGES ON DATABASE :"db_name" TO :"db_user";
SQL

  psql \
    -v ON_ERROR_STOP=1 \
    -v db_user="$db_user" \
    --username "$POSTGRES_USER" \
    --dbname "$db_name" <<'SQL'
GRANT ALL ON SCHEMA public TO :"db_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO :"db_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO :"db_user";
SQL
}

create_project_db "$POUPI_BABY_DB" "$POUPI_BABY_DB_USER" "$POUPI_BABY_DB_PASSWORD"
create_project_db "$DATA_CORE_DB" "$DATA_CORE_DB_USER" "$DATA_CORE_DB_PASSWORD"
create_project_db "$TRADING_BOT_DB" "$TRADING_BOT_DB_USER" "$TRADING_BOT_DB_PASSWORD"
create_project_db "$ANALYTICS_DB" "$ANALYTICS_DB_USER" "$ANALYTICS_DB_PASSWORD"
