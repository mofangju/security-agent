# Multi-Agent Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add production-grade multi-agent observability (agent-specific metrics + trace events) so routing quality, tool reliability, grounding quality, and guardrail behavior are measurable in Kubernetes.

**Architecture:** Keep existing `/metrics` endpoint and extend it with a dedicated in-process agent telemetry registry. Instrument the LangGraph execution path (`supervisor -> specialist -> tools -> selfrag`) with counters, latency metrics, and correlated trace events carrying `session_id`, `turn_id`, and `trace_id`. Emit trace events to JSONL by default and support optional OTLP export via existing env wiring.

**Tech Stack:** Python 3.11, Flask, LangGraph, Prometheus text exposition, JSONL structured events, optional OpenTelemetry OTLP env configuration, Helm, Kubernetes

---

### Task 1: Add Observability Config Surface

**Files:**
- Modify: `src/security_agent/config.py`
- Modify: `.env.example`
- Test: `tests/assistant/test_observability_config.py`

**Step 1: Write the failing test**

```python
from security_agent.config import AppConfig


def test_observability_defaults():
    cfg = AppConfig()
    assert cfg.observability.enabled is True
    assert cfg.observability.trace_jsonl_path.endswith("agent-traces.jsonl")
    assert cfg.observability.metrics_namespace == "security_agent"
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/assistant/test_observability_config.py`
Expected: FAIL (`AppConfig` has no `observability`).

**Step 3: Implement minimal configuration**

Add a new dataclass in `src/security_agent/config.py`:

```python
@dataclass
class ObservabilityConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("AGENT_OBSERVABILITY_ENABLED", True))
    metrics_namespace: str = field(default_factory=lambda: os.getenv("AGENT_METRICS_NAMESPACE", "security_agent"))
    trace_jsonl_path: str = field(default_factory=lambda: os.getenv("AGENT_TRACE_JSONL_PATH", str(_PROJECT_ROOT / "data" / "logs" / "agent-traces.jsonl")))
```

Wire it into `AppConfig` and expose matching keys in `.env.example`.

**Step 4: Run test to verify pass**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/assistant/test_observability_config.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/config.py .env.example tests/assistant/test_observability_config.py
git commit -m "feat: add observability config for agent telemetry"
```

---

### Task 2: Build Multi-Agent Metrics + Trace Event Registry

**Files:**
- Create: `src/security_agent/assistant/telemetry.py`
- Test: `tests/assistant/test_agent_telemetry.py`

**Step 1: Write the failing tests**

```python
from security_agent.assistant.telemetry import AgentTelemetry


def test_route_and_tool_metrics_render_with_labels():
    t = AgentTelemetry(namespace="security_agent")
    t.inc_route("monitor")
    t.observe_tool_call("config_manager", "tool_set_protection_mode", "ok", 0.12)
    text = t.render_prometheus()
    assert 'security_agent_agent_route_total{selected_agent="monitor"} 1' in text
    assert 'security_agent_agent_tool_calls_total{agent="config_manager",tool="tool_set_protection_mode",status="ok"} 1' in text


def test_trace_event_is_written_with_correlation_ids(tmp_path):
    p = tmp_path / "agent-traces.jsonl"
    t = AgentTelemetry(namespace="security_agent", trace_jsonl_path=p, enabled=True)
    t.emit_event("route.selected", trace_id="tr1", session_id="s1", turn_id="u1", metadata={"selected_agent": "monitor"})
    row = p.read_text(encoding="utf-8").strip()
    assert '"trace_id": "tr1"' in row
    assert '"event": "route.selected"' in row
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/assistant/test_agent_telemetry.py`
Expected: FAIL (module missing).

**Step 3: Implement telemetry registry**

Create `AgentTelemetry` with:
- Counters:
  - `agent_route_total{selected_agent}`
  - `agent_handoff_total{from_agent,to_agent}`
  - `agent_tool_calls_total{agent,tool,status}`
  - `agent_guardrail_total{gate,decision,reason}`
  - `agent_selfrag_decision_total{decision,reason}`
- Histograms (sum/count + bucket lines):
  - `agent_tool_latency_seconds{agent,tool}`
  - `agent_turn_latency_seconds`
- Event sink:
  - `emit_event(event, trace_id, session_id, turn_id, metadata)`
  - append JSON lines to `trace_jsonl_path`.

**Step 4: Run test to verify pass**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/assistant/test_agent_telemetry.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/assistant/telemetry.py tests/assistant/test_agent_telemetry.py
git commit -m "feat: add multi-agent telemetry registry and trace event sink"
```

---

### Task 3: Instrument LangGraph Routing, Guardrails, Tools, and Self-RAG

**Files:**
- Modify: `src/security_agent/assistant/graph.py`
- Test: `tests/assistant/test_graph_observability.py`

**Step 1: Write the failing tests**

```python
def test_supervisor_emits_route_metric(monkeypatch):
    # monkeypatch telemetry singleton + llm response "monitor"
    # assert inc_route("monitor") and emit_event("route.selected", ...)
    ...


def test_config_manager_tool_call_emits_tool_metrics(monkeypatch):
    # trigger confirmed set_mode path
    # assert tool metric status=ok and latency observed
    ...


def test_selfrag_emits_decision_metric(monkeypatch):
    # run rag_agent_node through FINAL + citations path
    # assert selfrag decision metric recorded
    ...
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/assistant/test_graph_observability.py`
Expected: FAIL (no telemetry calls).

**Step 3: Add instrumentation points in graph**

In `src/security_agent/assistant/graph.py`:
- Add telemetry singleton import:

```python
from security_agent.assistant.telemetry import get_agent_telemetry
TELEMETRY = get_agent_telemetry()
```

- In `supervisor_node`:
  - record selected route metric/event.
- In `route_to_specialist`:
  - emit handoff metric (`supervisor -> next_node`).
- Around tool calls in `config_manager_node`:
  - measure duration
  - emit `agent_tool_calls_total` with status.
- Mirror guardrail outcomes:
  - every `AUDIT_LOGGER.log(...)` path also emits guardrail telemetry.
- In `rag_agent_node`:
  - emit retrieval/decision metrics and trace events per attempt.

**Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/assistant/test_graph_observability.py tests/assistant/test_selfrag.py tests/assistant/test_guardrails_e2e.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/assistant/graph.py tests/assistant/test_graph_observability.py
git commit -m "feat: instrument graph routing, tool calls, and selfrag telemetry"
```

---

### Task 4: Propagate Turn Context and Expose Agent Metrics via `/metrics`

**Files:**
- Modify: `src/security_agent/assistant/cli.py`
- Modify: `src/security_agent/assistant/api.py`
- Modify: `tests/assistant/test_cli_state.py`
- Modify: `tests/assistant/test_api.py`

**Step 1: Write failing tests**

```python
def test_run_turn_stamps_trace_and_turn_ids():
    # run_turn should set context["trace_id"] and increment context["turn_id"]
    ...


def test_metrics_endpoint_includes_agent_metrics():
    # /metrics output contains both existing chat counters and new agent counters
    ...
```

**Step 2: Run tests to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/assistant/test_cli_state.py tests/assistant/test_api.py`
Expected: FAIL on new assertions.

**Step 3: Implement context propagation and metric merge**

In `src/security_agent/assistant/cli.py` `run_turn(...)`:
- initialize/propagate:
  - `session_id`
  - `trace_id` (new per turn)
  - `turn_id` (incrementing integer/string).

In `src/security_agent/assistant/api.py`:
- ensure session context carries `session_id`, `turn_id`, `trace_id`.
- in `/metrics`, append telemetry registry output:

```python
payload = metrics.render_prometheus() + agent_telemetry.render_prometheus()
```

**Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/assistant/test_cli_state.py tests/assistant/test_api.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/assistant/cli.py src/security_agent/assistant/api.py tests/assistant/test_cli_state.py tests/assistant/test_api.py
git commit -m "feat: propagate turn correlation ids and expose agent metrics"
```

---

### Task 5: Add Kubernetes/Helm and Alerting Assets for Agent Observability

**Files:**
- Modify: `charts/security-agent/values.yaml`
- Modify: `k8s/observability/otel-collector.yaml`
- Create: `k8s/observability/prometheus-rules-agent.yaml`
- Test: `tests/smoke/test_agent_observability_assets.py`

**Step 1: Write failing smoke test**

```python
def test_observability_assets_include_agent_specific_signals():
    # check new env keys in chart values
    # check rule file contains handoff loop, tool failure, selfrag escalation alerts
    ...
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/smoke/test_agent_observability_assets.py`
Expected: FAIL (rule file/env keys missing).

**Step 3: Implement deploy assets**

- Add env defaults in `charts/security-agent/values.yaml`:
  - `AGENT_OBSERVABILITY_ENABLED`
  - `AGENT_METRICS_NAMESPACE`
  - `AGENT_TRACE_JSONL_PATH`
- Update collector scrape target from hardcoded `security-agent.default...` to namespace-correct service target.
- Add `k8s/observability/prometheus-rules-agent.yaml` alerts:
  - high tool failure ratio
  - selfrag escalation surge
  - guardrail deny surge
  - readiness + chat failure correlation.

**Step 4: Run test to verify pass**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/smoke/test_agent_observability_assets.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add charts/security-agent/values.yaml k8s/observability/otel-collector.yaml k8s/observability/prometheus-rules-agent.yaml tests/smoke/test_agent_observability_assets.py
git commit -m "feat: add k8s assets and alert rules for multi-agent observability"
```

---

### Task 6: Document Production SLOs, Queries, and Incident Triage

**Files:**
- Modify: `docs/k8s-deployment-observability.md`
- Modify: `k8s/observability/README.md`
- Create: `docs/agent-observability-runbook.md`
- Test: `tests/smoke/test_agent_observability_docs.py`

**Step 1: Write failing doc test**

```python
def test_runbook_mentions_agent_specific_metrics_and_queries():
    # must include handoff, tool failure, selfrag, guardrail metrics and sample PromQL
    ...
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/smoke/test_agent_observability_docs.py`
Expected: FAIL.

**Step 3: Write docs**

Add:
- metric dictionary (name, labels, meaning, alert threshold)
- trace event schema (`trace_id`, `session_id`, `turn_id`, `event`, `metadata`)
- PromQL examples for:
  - route skew
  - handoff loops
  - tool failure ratio
  - selfrag escalation rate
  - guardrail deny rate
- on-call triage flow linking metric anomalies to likely root causes.

**Step 4: Run doc tests**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/smoke/test_agent_observability_docs.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/k8s-deployment-observability.md k8s/observability/README.md docs/agent-observability-runbook.md tests/smoke/test_agent_observability_docs.py
git commit -m "docs: add multi-agent observability runbook and production queries"
```

---

## Final Verification

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q
bash -n scripts/kind_demo_up.sh scripts/kind_demo_deploy.sh scripts/kind_demo_status.sh scripts/demo_dependencies_up.sh scripts/demo_dependencies_down.sh
helm template security-agent charts/security-agent -f kind/security-agent-values-kind.yaml >/tmp/security-agent-kind.yaml
```

Expected:
- test suite passes
- shell scripts parse successfully
- Helm render succeeds
- `/metrics` exposes both service-level and agent-level telemetry series.
