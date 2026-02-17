#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${KIND_CLUSTER_NAME:-security-agent-demo}"

if ! command -v kind >/dev/null 2>&1; then
  echo "[kind-demo] missing required command: kind" >&2
  exit 1
fi

if kind get clusters | grep -qx "$CLUSTER_NAME"; then
  echo "[kind-demo] deleting cluster '$CLUSTER_NAME'"
  kind delete cluster --name "$CLUSTER_NAME"
else
  echo "[kind-demo] cluster '$CLUSTER_NAME' does not exist"
fi
