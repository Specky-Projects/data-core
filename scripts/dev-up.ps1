param(
  [switch]$Build
)

$ErrorActionPreference = "Stop"

if ($Build) {
  docker compose up -d --build api scheduler worker
} else {
  docker compose up -d api scheduler worker
}

docker compose ps
