#!/usr/bin/env bash
set -euo pipefail

INFRA_DIR="${INFRA_DIR:-/opt/infra}"

cd "$INFRA_DIR"

find . -type d -exec chmod 755 {} \;
find . -name "*.sh" -exec sed -i 's/\r$//' {} \; -exec chmod +x {} \;

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

set_secret() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

replace_if_placeholder() {
  local key="$1"
  local current
  current="$(grep "^${key}=" .env | cut -d= -f2- || true)"
  if [[ -z "$current" || "$current" == change-me* ]]; then
    set_secret "$key" "$(openssl rand -hex 32)"
  fi
}

replace_if_placeholder POSTGRES_ADMIN_PASSWORD
replace_if_placeholder POUPI_BABY_DB_PASSWORD
replace_if_placeholder DATA_CORE_DB_PASSWORD
replace_if_placeholder TRADING_BOT_DB_PASSWORD
replace_if_placeholder ANALYTICS_DB_PASSWORD
replace_if_placeholder REDIS_PASSWORD

chmod 600 .env

docker compose --env-file .env -f docker-compose.prod.yml up -d

docker compose --env-file .env -f docker-compose.prod.yml ps
