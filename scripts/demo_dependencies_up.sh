#!/usr/bin/env bash
set -euo pipefail

START_SAFELINE=1
if [[ "${1:-}" == "--skip-safeline" ]]; then
  START_SAFELINE=0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[demo-deps] missing required command: docker" >&2
  exit 1
fi

if [[ $START_SAFELINE -eq 1 ]]; then
  echo "[demo-deps] starting SafeLine via scripts/safeline.sh"
  bash scripts/safeline.sh up --platform auto
else
  echo "[demo-deps] skipping SafeLine bootstrap (--skip-safeline)"
fi

echo "[demo-deps] starting Pet Shop from docker-compose.yml"
docker compose up -d petshop

echo "[demo-deps] petshop container:"
docker compose ps petshop

if [[ $START_SAFELINE -eq 1 ]]; then
  echo
  echo "[demo-deps] SafeLine post-install reminders:"
  echo "  1) sudo docker exec safeline-mgt resetadmin"
  echo "  2) Generate SAFELINE_API_TOKEN in SafeLine UI"
  echo "  3) Update .env and run: python -m security_agent.setup_site"
fi
