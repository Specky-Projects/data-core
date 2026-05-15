$ErrorActionPreference = "Stop"

docker compose exec -T api python -m app.documentation.generate
