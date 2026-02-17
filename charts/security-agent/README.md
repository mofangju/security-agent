# security-agent Helm Chart

Deploys Security Agent as a Kubernetes HTTP service.

## Install

```bash
helm upgrade --install security-agent charts/security-agent \
  -n security-agent --create-namespace \
  --set image.repository=<REGISTRY>/security-agent \
  --set image.tag=<TAG>
```

## Kind local demo install

```bash
helm upgrade --install security-agent charts/security-agent \
  -n security-agent --create-namespace \
  -f kind/security-agent-values-kind.yaml \
  --set image.repository=security-agent \
  --set image.tag=kind-demo
```

## Required secret

Create secret referenced by `secretEnv.name` (default: `security-agent-secrets`):

```bash
kubectl -n security-agent create secret generic security-agent-secrets \
  --from-literal=OPENAI_API_KEY=... \
  --from-literal=GOOGLE_API_KEY=... \
  --from-literal=SAFELINE_API_TOKEN=...
```

## Key values

- `env.SAFELINE_URL`: SafeLine management API URL.
- `persistence.enabled`: Persist Chroma vector index.
- `autoscaling.enabled`: Enable HPA.
- `observability.serviceMonitor.enabled`: Emit ServiceMonitor for Prometheus Operator.
- `networkPolicy.enabled`: Restrict ingress/egress traffic.
