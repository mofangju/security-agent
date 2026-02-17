#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${KIND_CLUSTER_NAME:-security-agent-demo}"
KCTX="kind-$CLUSTER_NAME"
NAMESPACE="${KIND_NAMESPACE:-security-agent}"
RELEASE_NAME="${HELM_RELEASE_NAME:-security-agent}"
DEPLOYMENT_NAME="${HELM_DEPLOYMENT_NAME:-${RELEASE_NAME}-security-agent}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "[kind-demo] missing required command: kubectl" >&2
  exit 1
fi

echo "[kind-demo] pods"
kubectl --context "$KCTX" -n "$NAMESPACE" get pods -o wide

echo
echo "[kind-demo] services"
kubectl --context "$KCTX" -n "$NAMESPACE" get svc

echo
echo "[kind-demo] autoscaling"
kubectl --context "$KCTX" -n "$NAMESPACE" get hpa 2>/dev/null || true

echo
echo "[kind-demo] recent events"
kubectl --context "$KCTX" -n "$NAMESPACE" get events --sort-by=.lastTimestamp | tail -n 20

echo
echo "[kind-demo] demo CLI command:"
echo "kubectl --context $KCTX -n $NAMESPACE exec -it deploy/$DEPLOYMENT_NAME -- python -m security_agent.assistant"

echo
echo "[kind-demo] API probe:"
echo "kubectl --context $KCTX -n $NAMESPACE port-forward svc/${RELEASE_NAME}-security-agent 8081:8081"
