#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${KIND_CLUSTER_NAME:-security-agent-demo}"
KCTX="kind-$CLUSTER_NAME"
NAMESPACE="${KIND_NAMESPACE:-security-agent}"
RELEASE_NAME="${HELM_RELEASE_NAME:-security-agent}"
DEPLOYMENT_NAME="${HELM_DEPLOYMENT_NAME:-${RELEASE_NAME}-security-agent}"
VALUES_FILE="${KIND_VALUES_FILE:-kind/security-agent-values-kind.yaml}"
IMAGE="${KIND_DEMO_IMAGE:-security-agent:kind-demo}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[kind-demo] missing required command: $1" >&2
    exit 1
  }
}

require_cmd docker
require_cmd kind
require_cmd kubectl
require_cmd helm

if ! kind get clusters | grep -qx "$CLUSTER_NAME"; then
  echo "[kind-demo] cluster '$CLUSTER_NAME' not found. Run scripts/kind_demo_up.sh first." >&2
  exit 1
fi

if [[ ! -f "$VALUES_FILE" ]]; then
  echo "[kind-demo] values file not found: $VALUES_FILE" >&2
  exit 1
fi

IMAGE_REPO="${IMAGE%:*}"
IMAGE_TAG="${IMAGE##*:}"

echo "[kind-demo] building image: $IMAGE"
docker build -t "$IMAGE" .

echo "[kind-demo] loading image into kind: $IMAGE"
kind load docker-image "$IMAGE" --name "$CLUSTER_NAME"

kubectl --context "$KCTX" create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl --context "$KCTX" apply -f -

echo "[kind-demo] creating/updating secret: security-agent-secrets"
kubectl --context "$KCTX" -n "$NAMESPACE" create secret generic security-agent-secrets \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  --from-literal=GOOGLE_API_KEY="${GOOGLE_API_KEY:-}" \
  --from-literal=SAFELINE_API_TOKEN="${SAFELINE_API_TOKEN:-}" \
  --dry-run=client -o yaml | kubectl --context "$KCTX" apply -f -

echo "[kind-demo] deploying helm release: $RELEASE_NAME"
helm upgrade --install "$RELEASE_NAME" charts/security-agent \
  --kube-context "$KCTX" \
  -n "$NAMESPACE" \
  -f "$VALUES_FILE" \
  --set image.repository="$IMAGE_REPO" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=IfNotPresent

echo "[kind-demo] waiting for rollout: deploy/$DEPLOYMENT_NAME"
kubectl --context "$KCTX" -n "$NAMESPACE" rollout status "deploy/$DEPLOYMENT_NAME" --timeout=180s

echo "[kind-demo] deployment ready"
echo "[kind-demo] next: bash scripts/kind_demo_status.sh"
