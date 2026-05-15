$ErrorActionPreference = "Stop"

docker compose --profile test run --rm tests
