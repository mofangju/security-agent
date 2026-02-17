# Kind Demo Walkthrough (CLI in Pod)

This walkthrough runs Security Agent in a local Kind cluster while SafeLine and Pet Shop stay on Docker.

## 1. Start external dependencies (Docker)

```bash
bash scripts/demo_dependencies_up.sh
```

If SafeLine is already running, you can skip re-bootstrap:

```bash
bash scripts/demo_dependencies_up.sh --skip-safeline
```

## 2. Create Kind cluster

```bash
bash scripts/kind_demo_up.sh
```

## 3. Build, load, and deploy Security Agent

```bash
export OPENAI_API_KEY=<your-key>
export SAFELINE_API_TOKEN=<your-safeline-token>
bash scripts/kind_demo_deploy.sh
bash scripts/kind_demo_status.sh
```

## 4. Demo via CLI in pod

```bash
kubectl --context kind-security-agent-demo -n security-agent \
  exec -it deploy/security-agent-security-agent -- \
  python -m security_agent.assistant
```

Suggested prompts:

1. `what is current qps`
2. `show recent attacks`
3. `switch waf to block mode`
4. `how do i configure rate limiting`

## 5. Optional: check API metrics

```bash
kubectl --context kind-security-agent-demo -n security-agent \
  port-forward svc/security-agent-security-agent 8081:8081

curl -s http://localhost:8081/healthz
curl -s http://localhost:8081/readyz
curl -s http://localhost:8081/metrics
```

## 6. Optional: start local observability collector

```bash
kubectl --context kind-security-agent-demo create namespace observability --dry-run=client -o yaml | \
  kubectl --context kind-security-agent-demo apply -f -
kubectl --context kind-security-agent-demo apply -f k8s/observability/otel-collector.yaml
```

## 7. Tear down

```bash
bash scripts/kind_demo_down.sh
bash scripts/demo_dependencies_down.sh
```
