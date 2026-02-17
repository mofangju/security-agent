# Kind Demo Environment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a reproducible local demo using a Kind cluster for Security Agent while keeping SafeLine/PetShop on Docker, with demo operation through `kubectl exec` into the Security Agent pod.

**Architecture:** Run SafeLine + PetShop outside Kubernetes (existing Docker workflow), run Security Agent inside Kind, and bridge connectivity from pods to host-side SafeLine endpoint. Add a lightweight observability baseline focused on app health, metrics, and logs in the Kind cluster.

**Tech Stack:** Kind, kubectl, Helm, Docker Compose, Bash, Prometheus-style `/metrics`, OpenTelemetry Collector

---

## Scope and Constraints

- SafeLine full Kubernetes deployment is out of scope for this phase.
- Demo path is CLI-first via `kubectl exec -it <pod> -- python -m security_agent.assistant`.
- Security Agent HTTP API remains deployed for probes/metrics, but not required for the CLI demo interaction.
- All scripts must be idempotent and safe to re-run.

---

### Task 1: Add Kind Cluster Bootstrap Config and Scripts

**Files:**
- Create: `kind/kind-config.yaml`
- Create: `scripts/kind_demo_up.sh`
- Create: `scripts/kind_demo_down.sh`
- Test: `tests/smoke/test_kind_assets.py`

**Step 1: Write failing tests**

```python
def test_kind_config_exists_and_has_control_plane():
    ...

def test_kind_scripts_are_present():
    ...
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/smoke/test_kind_assets.py -q`
Expected: FAIL (files missing).

**Step 3: Implement minimal bootstrap**

- `kind/kind-config.yaml`:
  - single control-plane node
  - optional `extraPortMappings` for API demo (`8081`)
- `scripts/kind_demo_up.sh`:
  1. verify `kind`, `kubectl`, `docker`, `helm`
  2. create cluster if missing
  3. create namespace `security-agent`
  4. print next actions
- `scripts/kind_demo_down.sh`:
  - delete Kind cluster and optionally namespace artifacts.

**Step 4: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/smoke/test_kind_assets.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add kind/kind-config.yaml scripts/kind_demo_up.sh scripts/kind_demo_down.sh tests/smoke/test_kind_assets.py
git commit -m "feat: add kind bootstrap scripts and cluster config"
```

---

### Task 2: Add Demo Deployment Overlay for Kind

**Files:**
- Create: `kind/security-agent-values-kind.yaml`
- Modify: `charts/security-agent/values.yaml` (only if needed for defaults)
- Modify: `charts/security-agent/README.md`
- Test: `tests/smoke/test_kind_helm_values.py`

**Step 1: Write failing test**

```python
def test_kind_values_sets_demo_safe_defaults():
    # SAFELINE_URL targets host bridge endpoint
    # single replica
    # autoscaling disabled for demo
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/smoke/test_kind_helm_values.py -q`
Expected: FAIL.

**Step 3: Implement Kind overlay**

- `kind/security-agent-values-kind.yaml` should set:
  - `replicaCount: 1`
  - `autoscaling.enabled: false`
  - `pdb.enabled: false`
  - `networkPolicy.enabled: false` for local demo simplicity
  - `env.SAFELINE_URL` to host-reachable endpoint (`https://host.docker.internal:9443`) with fallback notes
  - `env.SAFELINE_VERIFY_TLS: "false"` for self-signed local cert demo
  - persistence optional (`false`) for quick local spin-up

**Step 4: Validate Helm render**

Run:

```bash
helm template security-agent charts/security-agent -f kind/security-agent-values-kind.yaml >/tmp/sa-kind.yaml
```

Expected: Render succeeds.

**Step 5: Commit**

```bash
git add kind/security-agent-values-kind.yaml charts/security-agent/README.md tests/smoke/test_kind_helm_values.py
git commit -m "feat: add kind demo helm overlay values"
```

---

### Task 3: Build/Load Image and Deploy Script for Kind Demo

**Files:**
- Create: `scripts/kind_demo_deploy.sh`
- Create: `scripts/kind_demo_status.sh`
- Modify: `docs/k8s-deployment-observability.md`
- Test: `tests/smoke/test_kind_scripts.py`

**Step 1: Write failing tests**

```python
def test_kind_deploy_script_contains_required_steps():
    # build image, kind load, create secret, helm upgrade/install
```

**Step 2: Run test**

Run: `PYTHONPATH=src .venv/bin/pytest tests/smoke/test_kind_scripts.py -q`
Expected: FAIL.

**Step 3: Implement deployment scripts**

- `scripts/kind_demo_deploy.sh`:
  1. build local Docker image (`security-agent:kind-demo`)
  2. `kind load docker-image security-agent:kind-demo`
  3. create/update `security-agent-secrets` (from env vars)
  4. `helm upgrade --install` using Kind overlay values
  5. wait for rollout
- `scripts/kind_demo_status.sh`:
  - show pods/services/events
  - run `kubectl get` checks for readiness.

**Step 4: Verification**

Run:

```bash
bash scripts/kind_demo_deploy.sh
bash scripts/kind_demo_status.sh
```

Expected: Deployment ready in `security-agent` namespace.

**Step 5: Commit**

```bash
git add scripts/kind_demo_deploy.sh scripts/kind_demo_status.sh docs/k8s-deployment-observability.md tests/smoke/test_kind_scripts.py
git commit -m "feat: add kind demo deploy and status scripts"
```

---

### Task 4: Add SafeLine/PetShop External Dependency Script for Demo

**Files:**
- Create: `scripts/demo_dependencies_up.sh`
- Create: `scripts/demo_dependencies_down.sh`
- Modify: `README.md`
- Test: `tests/smoke/test_demo_dependencies_script.py`

**Step 1: Write failing tests**

```python
def test_demo_dependencies_script_mentions_safeline_and_petshop_steps():
    ...
```

**Step 2: Run test**

Run: `PYTHONPATH=src .venv/bin/pytest tests/smoke/test_demo_dependencies_script.py -q`
Expected: FAIL.

**Step 3: Implement dependency scripts**

- `scripts/demo_dependencies_up.sh`:
  1. run `bash scripts/safeline.sh up`
  2. run `docker compose up -d petshop`
  3. verify endpoints (`9443`, `8080`)
  4. print reminder for API token and `setup_site`
- `scripts/demo_dependencies_down.sh`:
  - stop petshop and optionally SafeLine via script.

**Step 4: Verification**

Run:

```bash
bash scripts/demo_dependencies_up.sh
python -m security_agent.setup_site
```

Expected: SafeLine and PetShop available for Security Agent.

**Step 5: Commit**

```bash
git add scripts/demo_dependencies_up.sh scripts/demo_dependencies_down.sh README.md tests/smoke/test_demo_dependencies_script.py
git commit -m "feat: add external dependency bootstrap for kind demo"
```

---

### Task 5: Add CLI Demo Workflow and Observability Runbook

**Files:**
- Modify: `docs/k8s-deployment-observability.md`
- Modify: `k8s/observability/README.md`
- Create: `docs/kind-demo-walkthrough.md`

**Step 1: Write doc-check test**

```python
def test_kind_demo_walkthrough_includes_cli_exec_flow():
    # includes kubectl exec command and sample prompts
```

**Step 2: Run test**

Run: `PYTHONPATH=src .venv/bin/pytest tests/smoke/test_kind_demo_docs.py -q`
Expected: FAIL.

**Step 3: Write walkthrough**

Include exact sequence:

1. `bash scripts/demo_dependencies_up.sh`
2. `bash scripts/kind_demo_up.sh`
3. `bash scripts/kind_demo_deploy.sh`
4. `kubectl -n security-agent exec -it deploy/security-agent-security-agent -- python -m security_agent.assistant`
5. run sample queries and expected responses
6. inspect metrics:
   - `kubectl -n security-agent port-forward svc/security-agent-security-agent 8081:8081`
   - `curl http://localhost:8081/metrics`
7. optional collector deployment:
   - `kubectl apply -f k8s/observability/otel-collector.yaml`

**Step 4: Commit**

```bash
git add docs/k8s-deployment-observability.md k8s/observability/README.md docs/kind-demo-walkthrough.md tests/smoke/test_kind_demo_docs.py
git commit -m "docs: add kind demo and observability walkthrough"
```

---

## Final Verification

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q
bash -n scripts/kind_demo_up.sh scripts/kind_demo_down.sh scripts/kind_demo_deploy.sh scripts/demo_dependencies_up.sh scripts/demo_dependencies_down.sh
helm template security-agent charts/security-agent -f kind/security-agent-values-kind.yaml >/tmp/security-agent-kind.yaml
```

Expected:
- all tests pass
- scripts parse successfully
- helm template renders
- full demo path works via `kubectl exec` CLI.
