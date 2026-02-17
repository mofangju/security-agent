# Multi-Agent Observability Runbook

This runbook covers production observability for Security Agent's multi-agent workflow.

## 1. Metrics to track

Core service metrics:
- `security_agent_chat_requests_total`
- `security_agent_chat_failures_total`
- `security_agent_chat_latency_seconds_*`

Agent workflow metrics:
- `security_agent_agent_route_total{selected_agent}`
- `security_agent_agent_handoff_total{from_agent,to_agent}`
- `security_agent_agent_tool_calls_total{agent,tool,status}`
- `security_agent_agent_tool_latency_seconds_*{agent,tool}`
- `security_agent_agent_guardrail_total{gate,decision,reason}`
- `security_agent_agent_selfrag_decision_total{decision,reason}`
- `security_agent_agent_trace_events_total{event}`

## 2. Trace event schema

Agent trace events are written as JSONL records (default: `AGENT_TRACE_JSONL_PATH`).

Required fields:
- `ts`
- `event`
- `trace_id`
- `session_id`
- `turn_id`
- `metadata`

Use `trace_id` + `session_id` + `turn_id` to correlate route decisions, guardrail outcomes, and tool calls for one user turn.

## 3. PromQL checks

Tool failure ratio:

```promql
sum(rate(security_agent_agent_tool_calls_total{status="error"}[5m]))
/
clamp_min(sum(rate(security_agent_agent_tool_calls_total[5m])), 1)
```

Self-RAG escalation rate:

```promql
sum(rate(security_agent_agent_selfrag_decision_total{decision="ESCALATE"}[10m]))
```

Guardrail deny rate:

```promql
sum(rate(security_agent_agent_guardrail_total{decision="deny"}[5m]))
```

Route skew (dominant route share):

```promql
topk(1, sum by (selected_agent) (rate(security_agent_agent_route_total[10m])))
/
clamp_min(sum(rate(security_agent_agent_route_total[10m])), 1)
```

Handoff loop risk (route churn):

```promql
sum(rate(security_agent_agent_handoff_total[5m]))
```

## 4. Incident triage flow

1. If tool failure ratio spikes:
   - Inspect `security_agent_agent_tool_calls_total{status="error"}` by `tool`.
   - Check SafeLine API reachability and provider credentials.
2. If Self-RAG escalations spike:
   - Inspect retrieval freshness and indexed docs.
   - Review citation failures and guardrail reasons.
3. If guardrail denies spike:
   - Segment by `gate`/`reason` for policy drift vs malicious prompts.
4. If route skew is abnormal:
   - Review supervisor prompt/router behavior and recent model changes.

## 5. Alert resources

Apply:

```bash
kubectl apply -f k8s/observability/prometheus-rules-agent.yaml
```

Key alerts:
- `SecurityAgentToolFailureHigh`
- `SecurityAgentSelfRagEscalationHigh`
- `SecurityAgentGuardrailDenySpike`
- `SecurityAgentReadinessAndChatFailure`
