#!/usr/bin/env bash
# One-click deploy for any Docker-capable host (local, EC2, DigitalOcean, etc).
# Not tied to a specific PaaS — just needs Docker + Docker Compose installed.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "No .env found — copying from .env.example. Edit .env with real values (API keys, passwords) before rerunning if this is a fresh deploy."
  cp .env.example .env
fi

echo "Building and starting all services..."
docker compose up -d --build

echo "Waiting for services to become healthy..."
for i in $(seq 1 60); do
  unhealthy=$(docker compose ps --format '{{.Health}}' | grep -vc "healthy" || true)
  if [ "$unhealthy" -eq 0 ]; then
    break
  fi
  sleep 2
done

docker compose ps

FRONTEND_PORT=$(grep -E '^FRONTEND_PORT=' .env | cut -d= -f2)
FRONTEND_PORT=${FRONTEND_PORT:-5173}
echo ""
echo "AgenticPA is up: http://localhost:${FRONTEND_PORT}"
