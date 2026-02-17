#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${KIND_CLUSTER_NAME:-security-agent-demo}"
CONFIG_PATH="${KIND_CONFIG_PATH:-kind/kind-config.yaml}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[kind-demo] missing required command: $1" >&2
    exit 1
  }
}

require_cmd kind
require_cmd kubectl
require_cmd docker
require_cmd helm

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "[kind-demo] kind config not found: $CONFIG_PATH" >&2
  exit 1
fi

if kind get clusters | grep -qx "$CLUSTER_NAME"; then
  echo "[kind-demo] cluster '$CLUSTER_NAME' already exists"
else
  echo "[kind-demo] creating cluster '$CLUSTER_NAME' with $CONFIG_PATH"
  kind create cluster --name "$CLUSTER_NAME" --config "$CONFIG_PATH"
fi

KCTX="kind-$CLUSTER_NAME"
kubectl --context "$KCTX" cluster-info >/dev/null

kubectl --context "$KCTX" create namespace security-agent --dry-run=client -o yaml | kubectl --context "$KCTX" apply -f -
kubectl --context "$KCTX" create namespace observability --dry-run=client -o yaml | kubectl --context "$KCTX" apply -f -

echo "[kind-demo] ready"
echo "[kind-demo] next: bash scripts/kind_demo_deploy.sh"
