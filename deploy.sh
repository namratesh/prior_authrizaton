#!/usr/bin/env bash
# One-click deploy for any Docker-capable host (local, EC2, DigitalOcean, etc).
# Not tied to a specific PaaS — just needs Docker + Docker Compose installed.
#
# Production secrets: set SSM_PARAM_PREFIX (e.g. "/agentic-pa/prod/") to pull
# POSTGRES_PASSWORD, REDIS_PASSWORD, and GEMINI_API_KEY as SecureString
# params from AWS SSM Parameter Store at deploy time instead of hand-editing
# .env. Requires the instance role to have ssm:GetParameter on that prefix.
# Local/dev deploys with no SSM_PARAM_PREFIX set are unaffected.
set -euo pipefail
cd "$(dirname "$0")"

if [ -n "${SSM_PARAM_PREFIX:-}" ]; then
  echo "SSM_PARAM_PREFIX set — fetching secrets from AWS SSM Parameter Store (${SSM_PARAM_PREFIX})..."
  [ -f .env ] || cp .env.example .env
  for var in POSTGRES_PASSWORD REDIS_PASSWORD GEMINI_API_KEY; do
    value=$(aws ssm get-parameter --name "${SSM_PARAM_PREFIX}${var}" --with-decryption --query 'Parameter.Value' --output text)
    if grep -q "^${var}=" .env; then
      sed -i.bak "s|^${var}=.*|${var}=${value}|" .env && rm -f .env.bak
    else
      echo "${var}=${value}" >> .env
    fi
  done
elif [ ! -f .env ]; then
  echo "No .env found — copying from .env.example. Edit .env with real values (API keys, passwords) before rerunning if this is a fresh deploy."
  cp .env.example .env
fi

chmod 600 .env

# EC2 public IPs change across stop/start, so detect the current one on every
# deploy and refresh FRONTEND_ORIGIN in .env — the backend's CORS check
# (FRONTEND_ORIGIN in backend/app/main.py) must match whatever origin the
# browser actually sends, or API calls get rejected.
detect_public_ip() {
  local token
  token=$(curl -s -m 2 -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null || true)
  if [ -n "$token" ]; then
    curl -s -m 2 -H "X-aws-ec2-metadata-token: ${token}" \
      "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true
  fi
}

PUBLIC_IP=$(detect_public_ip)
if [ -z "$PUBLIC_IP" ]; then
  # Not on EC2 (or metadata service unreachable) — fall back to an external
  # "what's my IP" service for local/other-cloud deploys.
  PUBLIC_IP=$(curl -s -m 3 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)
fi

if [ -n "$PUBLIC_IP" ]; then
  FRONTEND_PORT_VAL=$(grep -E '^FRONTEND_PORT=' .env | cut -d= -f2)
  FRONTEND_PORT_VAL=${FRONTEND_PORT_VAL:-5173}
  DETECTED_ORIGIN="http://${PUBLIC_IP}:${FRONTEND_PORT_VAL}"
  echo "Detected public IP: ${PUBLIC_IP} — setting FRONTEND_ORIGIN=${DETECTED_ORIGIN}"
  if grep -q "^FRONTEND_ORIGIN=" .env; then
    sed -i.bak "s|^FRONTEND_ORIGIN=.*|FRONTEND_ORIGIN=${DETECTED_ORIGIN}|" .env && rm -f .env.bak
  else
    echo "FRONTEND_ORIGIN=${DETECTED_ORIGIN}" >> .env
  fi
else
  echo "Could not auto-detect public IP — leaving FRONTEND_ORIGIN as-is in .env."
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
if [ -n "${PUBLIC_IP:-}" ]; then
  echo "                 http://${PUBLIC_IP}:${FRONTEND_PORT}"
fi
