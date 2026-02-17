# Observability on Kubernetes

This folder contains a baseline OpenTelemetry Collector deployment for `security-agent`.

## What it gives you

- OTLP ingest endpoint for traces/metrics/logs (`4317`, `4318`)
- Prometheus scrape pipeline for app metrics (`/metrics`)
- Collector Prometheus export endpoint (`9464`)

## Apply

```bash
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/observability/otel-collector.yaml
```

For Kind demo context:

```bash
kubectl --context kind-security-agent-demo create namespace observability --dry-run=client -o yaml | \
  kubectl --context kind-security-agent-demo apply -f -
kubectl --context kind-security-agent-demo apply -f k8s/observability/otel-collector.yaml
```

## Wire app to collector

Set these env vars in your Helm values (or ConfigMap):

```yaml
env:
  OTEL_EXPORTER_OTLP_ENDPOINT: http://security-agent-otel-collector.observability.svc.cluster.local:4318
  OTEL_EXPORTER_OTLP_PROTOCOL: http/protobuf
  OTEL_SERVICE_NAME: security-agent
```

## Recommended next integrations

1. Prometheus Operator + Grafana for dashboards and alerting.
2. Loki for logs.
3. Tempo for traces.
4. Alert rules on:
   - `security_agent_chat_failures_total`
   - readiness failures
   - Self-RAG escalation rate.
