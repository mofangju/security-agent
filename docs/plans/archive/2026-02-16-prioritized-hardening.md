# Security Agent Prioritized Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce highest-risk security and reliability gaps first (unsafe auto-actions, stateless chat, brittle parsing, no tests), while keeping demo UX and SafeLine workflows intact.

**Architecture:** Introduce explicit action-guardrails and deterministic parsing in the assistant layer, then harden integration boundaries (SafeLine API transport + setup scripts), and finally establish test/CI gates so regressions are caught automatically.

**Tech Stack:** Python 3.11, LangGraph, LangChain, requests, pytest, ruff, ChromaDB

---

## Prioritization Strategy

1. P0 (Immediate): Prevent unintended destructive/config-changing behavior.
2. P0 (Immediate): Make assistant behavior stateful and predictable.
3. P1 (Near-term): Fix parsing/data-quality bugs that can mislead operators.
4. P1 (Near-term): Add deterministic tests and CI gates.
5. P2 (Follow-up): Improve deployment robustness and observability.

---

### Task 1 (P0): Replace Implicit Auto-Actions With Explicit Guardrails

**Files:**
- Create: `src/security_agent/assistant/actions.py`
- Modify: `src/security_agent/assistant/graph.py`
- Modify: `src/security_agent/assistant/state.py`
- Test: `tests/assistant/test_actions.py`

**Step 1: Write the failing test**

```python
def test_no_config_change_without_explicit_confirm():
    state = {
        "messages": [HumanMessage(content="switch to block mode")],
        "next_node": "config_manager",
        "context": {"confirmed": False},
    }
    out = config_manager_node(state)
    assert "Executed:" not in out["messages"][-1].content
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/assistant/test_actions.py::test_no_config_change_without_explicit_confirm -v`
Expected: FAIL (current logic executes based on keyword match).

**Step 3: Write minimal implementation**

- Add an action interpreter that returns structured intent (`set_mode`, `add_blacklist_ip`, `none`).
- Execute side-effecting tools only when `state["context"]["confirmed"] is True`.
- If not confirmed, return a confirmation prompt with exact action preview.

**Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/assistant/test_actions.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/assistant/actions.py src/security_agent/assistant/graph.py src/security_agent/assistant/state.py tests/assistant/test_actions.py
git commit -m "fix: require explicit confirmation before config actions"
```

---

### Task 2 (P0): Make CLI Chat Stateful Across Turns

**Files:**
- Modify: `src/security_agent/assistant/cli.py`
- Modify: `src/security_agent/assistant/state.py`
- Test: `tests/assistant/test_cli_state.py`

**Step 1: Write the failing test**

```python
def test_chat_preserves_prior_messages():
    state = {"messages": [HumanMessage(content="first")], "next_node": "", "context": {}}
    state["messages"].append(AIMessage(content="reply"))
    state["messages"].append(HumanMessage(content="follow-up"))
    assert len(state["messages"]) >= 3
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/assistant/test_cli_state.py -v`
Expected: FAIL or missing behavior assertion against current loop reset.

**Step 3: Write minimal implementation**

- Persist a `conversation_messages` list outside the loop.
- Append new user message each turn, invoke graph with full history, append assistant reply.
- Add bounded memory (for example last 20 messages) to control token growth.

**Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/assistant/test_cli_state.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/assistant/cli.py src/security_agent/assistant/state.py tests/assistant/test_cli_state.py
git commit -m "feat: preserve bounded conversation history in CLI"
```

---

### Task 3 (P1): Correct Monitoring/Event Parsing and Add Structured Validation

**Files:**
- Create: `src/security_agent/tools/parsers.py`
- Modify: `src/security_agent/assistant/graph.py`
- Test: `tests/tools/test_parsers.py`

**Step 1: Write failing tests**

```python
def test_extracts_latest_qps_metric_not_timestamp():
    payload = {"qps": {"data": {"nodes": [{"time": "10:00", "value": 12}]}}}
    assert parse_qps(payload)["current_qps"] == 12
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/tools/test_parsers.py::test_extracts_latest_qps_metric_not_timestamp -v`
Expected: FAIL with current `list(n.values())[0]` behavior.

**Step 3: Write minimal implementation**

- Parse known keys (`qps`, `value`, fallback numeric fields excluding `time`).
- Normalize event summaries with defensive defaults.
- Return typed dicts for monitor/log nodes instead of raw string munging.

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/tools/test_parsers.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/tools/parsers.py src/security_agent/assistant/graph.py tests/tools/test_parsers.py
git commit -m "fix: robust qps and event parsing with tests"
```

---

### Task 4 (P1): Harden SafeLine API Transport Defaults

**Files:**
- Modify: `src/security_agent/config.py`
- Modify: `src/security_agent/tools/safeline_api.py`
- Modify: `.env.example`
- Test: `tests/tools/test_safeline_api.py`

**Step 1: Write failing tests**

```python
def test_verify_tls_default_true():
    api = SafeLineAPI()
    assert api.verify_tls is True
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/tools/test_safeline_api.py::test_verify_tls_default_true -v`
Expected: FAIL (current code hardcodes `verify=False`).

**Step 3: Write minimal implementation**

- Add config: `SAFELINE_VERIFY_TLS`, `SAFELINE_CA_BUNDLE`, `SAFELINE_TIMEOUT`, `SAFELINE_RETRIES`.
- Use `requests.Session` with retry/backoff adapter.
- Keep local-demo escape hatch (`verify=false`) but explicit and documented.

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/tools/test_safeline_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/config.py src/security_agent/tools/safeline_api.py .env.example tests/tools/test_safeline_api.py
git commit -m "hardening: configurable tls verification and retries for safeline api"
```

---

### Task 5 (P1): Make Evaluation Deterministic and Offline-Capable

**Files:**
- Modify: `src/security_agent/eval/evaluator.py`
- Modify: `scripts/run_eval.py`
- Create: `tests/eval/test_evaluator.py`

**Step 1: Write failing tests**

```python
def test_evaluator_can_run_with_stubbed_graph():
    graph = StubGraph(route="monitor", response="traffic is normal")
    results = Evaluator().run_evaluation(graph)
    assert len(results) > 0
```

**Step 2: Run test**

Run: `.venv/bin/pytest tests/eval/test_evaluator.py -v`
Expected: FAIL until harness decouples external dependencies.

**Step 3: Write minimal implementation**

- Add deterministic test mode for evaluator (stub route/response path).
- Keep existing live mode as optional integration run.
- Separate routing-accuracy checks from response-keyword checks.

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/eval/test_evaluator.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/eval/evaluator.py scripts/run_eval.py tests/eval/test_evaluator.py
git commit -m "test: deterministic evaluator mode for local and ci usage"
```

---

### Task 6 (P2): Improve `setup_site` Robustness and Idempotency

**Files:**
- Modify: `src/security_agent/setup_site.py`
- Test: `tests/integration/test_setup_site_payload.py`

**Step 1: Write failing tests**

```python
def test_setup_site_uses_discovered_container_or_fallback():
    payload = build_site_payload(petshop_ip="172.18.0.5", petshop_port=8080)
    assert payload["upstreams"] == ["http://172.18.0.5:8080"]
```

**Step 2: Run test**

Run: `.venv/bin/pytest tests/integration/test_setup_site_payload.py -v`
Expected: FAIL until payload construction is isolated/testable.

**Step 3: Write minimal implementation**

- Extract payload construction into pure helper functions.
- Avoid fixed container name; resolve by compose service/container labels.
- Handle “already exists” responses as success with clear message.

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/integration/test_setup_site_payload.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/setup_site.py tests/integration/test_setup_site_payload.py
git commit -m "fix: resilient and idempotent site registration flow"
```

---

### Task 7 (P2): Establish Baseline Quality Gates

**Files:**
- Modify: `pyproject.toml`
- Create: `.github/workflows/ci.yml`
- Create: `tests/smoke/test_imports.py`
- Modify: `README.md`

**Step 1: Write failing test**

```python
def test_core_modules_import():
    import security_agent.assistant.graph
    import security_agent.tools.safeline_api
```

**Step 2: Run test**

Run: `.venv/bin/pytest tests/smoke/test_imports.py -v`
Expected: FAIL if import-time regressions are present.

**Step 3: Write minimal implementation**

- Add CI steps: install, `ruff check .`, `pytest -q`.
- Document local verify command in README.

**Step 4: Run tests and lint**

Run: `.venv/bin/ruff check . && .venv/bin/pytest -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml .github/workflows/ci.yml tests/smoke/test_imports.py README.md
git commit -m "chore: add baseline ci quality gates"
```

---

## Recommended Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7

This order reduces immediate blast radius first, then correctness, then long-term maintainability.
