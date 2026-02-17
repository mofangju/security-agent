#!/usr/bin/env bash
set -euo pipefail

STOP_SAFELINE=0
if [[ "${1:-}" == "--with-safeline" ]]; then
  STOP_SAFELINE=1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[demo-deps] missing required command: docker" >&2
  exit 1
fi

echo "[demo-deps] stopping Pet Shop"
docker compose down --remove-orphans

if [[ $STOP_SAFELINE -eq 1 ]]; then
  echo "[demo-deps] stopping SafeLine"
  bash scripts/safeline.sh down
else
  echo "[demo-deps] SafeLine left running (pass --with-safeline to stop it)"
fi
