# Kubernetes Deployment and Observability Guide

This guide deploys `security-agent` as an HTTP service on Kubernetes and sets up baseline observability.

## Kind local demo path (recommended for this repo)

```bash
bash scripts/demo_dependencies_up.sh
bash scripts/kind_demo_up.sh
bash scripts/kind_demo_deploy.sh
bash scripts/kind_demo_status.sh
```

CLI demo inside pod:

```bash
kubectl --context kind-security-agent-demo -n security-agent \
  exec -it deploy/security-agent-security-agent -- \
  python -m security_agent.assistant
```

Full walkthrough: `docs/kind-demo-walkthrough.md`

## 1. Build and push image

```bash
docker build -t <REGISTRY>/security-agent:<TAG> .
docker push <REGISTRY>/security-agent:<TAG>
```

## 2. Create namespace and secrets

```bash
kubectl create namespace security-agent --dry-run=client -o yaml | kubectl apply -f -

kubectl -n security-agent create secret generic security-agent-secrets \
  --from-literal=OPENAI_API_KEY="<your-openai-key>" \
  --from-literal=GOOGLE_API_KEY="<your-google-key>" \
  --from-literal=SAFELINE_API_TOKEN="<your-safeline-token>" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## 3. Deploy with Helm

```bash
helm upgrade --install security-agent charts/security-agent \
  -n security-agent \
  --set image.repository=<REGISTRY>/security-agent \
  --set image.tag=<TAG> \
  --set env.SAFELINE_URL=https://<safeline-host>:9443
```

## 4. Validate service

```bash
kubectl -n security-agent port-forward svc/security-agent-security-agent 8081:8081

curl -s http://localhost:8081/healthz
curl -s http://localhost:8081/readyz
curl -s http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"show recent attacks"}'
curl -s http://localhost:8081/metrics
```

## 5. Observability baseline

Apply collector:

```bash
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/observability/otel-collector.yaml
```

Enable ServiceMonitor in Helm values if you use Prometheus Operator:

```yaml
observability:
  serviceMonitor:
    enabled: true
```

## 6. Production hardening checklist

1. Use external secret manager (`ExternalSecrets`/Vault/ASM), not plaintext env files.
2. Restrict egress in `NetworkPolicy` to only SafeLine + LLM endpoints.
3. Set explicit CPU/memory limits and tune HPA thresholds.
4. Enable TLS ingress + authentication in front of `/v1/chat`.
5. Add alert rules:
   - readiness/liveness failures
   - `security_agent_chat_failures_total` increase
   - sustained `selfrag` escalations.
