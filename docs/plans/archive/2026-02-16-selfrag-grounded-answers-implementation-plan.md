# Self-RAG Grounded Answers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Self-RAG so documentation answers are verifiable, citation-grounded, and safely handled when evidence is weak or missing.

**Architecture:** Add a deterministic Self-RAG loop in the RAG path: retrieve evidence, draft answer with citations, run critic/judge, then choose `FINAL`, `RETRY`, `CLARIFY`, or `ESCALATE`. Enforce grounding checks in code (citation format and citation validity), and preserve decisions in state/audit logs.

**Tech Stack:** Python 3.11, LangGraph, LangChain, ChromaDB, pytest, ruff

---

## Priorities

1. P0: Self-RAG loop in `rag_agent_node` with deterministic decision parsing.
2. P0: Citation enforcement and grounding checks in code (not prompt-only).
3. P1: Scope retrieval to uploaded/session docs and include traceable chunk metadata.
4. P1: Add tests and deterministic harness for retry/fallback behavior.
5. P2: Extend ingestion for incremental upload metadata and stronger verifiability metrics.

---

### Task 1 (P0): Add Self-RAG Decision and Grounding Helpers

**Files:**
- Create: `src/security_agent/assistant/selfrag.py`
- Test: `tests/assistant/test_selfrag.py`

**Step 1: Write failing tests**

```python
def test_parse_selfrag_decision_accepts_allowed_tokens():
    assert parse_selfrag_decision("FINAL: grounded")[0] == "FINAL"
    assert parse_selfrag_decision("retry: weak evidence")[0] == "RETRY"


def test_citation_guardrail_rejects_missing_citations():
    ok, reason = validate_answer_citations("No citation answer", evidence_count=3, min_citations=1)
    assert ok is False
    assert "citation" in reason.lower()
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/assistant/test_selfrag.py -q`
Expected: FAIL (module missing).

**Step 3: Implement minimal helper module**

- Decision parser with strict allowlist: `FINAL|RETRY|CLARIFY|ESCALATE`
- Citation extractor for numeric markers like `[1]`, `[2]`
- Citation validator ensuring:
  - at least `min_citations`
  - all citation indexes are within retrieved evidence range

**Step 4: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/assistant/test_selfrag.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/assistant/selfrag.py tests/assistant/test_selfrag.py
git commit -m "feat: add self-rag decision and citation guardrail helpers"
```

---

### Task 2 (P0): Implement Self-RAG Loop in `rag_agent_node`

**Files:**
- Modify: `src/security_agent/assistant/graph.py`
- Modify: `src/security_agent/llm/prompts.py`
- Create: `src/security_agent/llm/prompts/selfrag_critic.txt`
- Modify: `src/security_agent/config.py`
- Modify: `src/security_agent/assistant/state.py`
- Test: `tests/assistant/test_selfrag.py`

**Step 1: Write failing tests**

```python
def test_rag_agent_retries_then_returns_grounded_answer(...):
    # first critic says RETRY, second says FINAL
    # final answer includes valid citation markers
```

```python
def test_rag_agent_clarifies_when_no_evidence(...):
    # retrieval returns []
    # assistant asks user to refine/upload docs
```

**Step 2: Run test to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/assistant/test_selfrag.py -q`
Expected: FAIL.

**Step 3: Implement minimal loop**

- In `rag_agent_node`, run up to `max_attempts`:
  1. retrieve evidence
  2. generate draft answer from evidence
  3. judge with critic prompt
  4. apply deterministic guardrails (`validate_answer_citations`)
- Decision handling:
  - `FINAL`: return grounded answer
  - `RETRY`: increase retrieval depth and retry
  - `CLARIFY`: ask user clarifying question
  - `ESCALATE`: state cannot verify from docs
- Store trace in `context["selfrag"]` with attempts and decisions.

**Step 4: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/assistant/test_selfrag.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/assistant/graph.py src/security_agent/llm/prompts.py src/security_agent/llm/prompts/selfrag_critic.txt src/security_agent/config.py src/security_agent/assistant/state.py tests/assistant/test_selfrag.py
git commit -m "feat: add self-rag loop with retry clarify escalate decisions"
```

---

### Task 3 (P1): Add Scoped Retrieval and Traceable Evidence Metadata

**Files:**
- Modify: `src/security_agent/tools/rag_search.py`
- Modify: `src/security_agent/rag/retriever.py`
- Modify: `src/security_agent/assistant/graph.py`
- Test: `tests/tools/test_rag_guardrails.py`

**Step 1: Write failing tests**

```python
def test_rag_search_returns_chunk_ids_for_citation_traceability():
    # each result includes id/source/section/chunk_index
```

```python
def test_retriever_respects_where_filter_in_hybrid_results():
    # results outside scope are filtered out
```

**Step 2: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/tools/test_rag_guardrails.py -q`
Expected: FAIL.

**Step 3: Implement minimal scope**

- `tool_rag_search(query, n_results, where=None)`
- Include evidence fields: `id`, `source`, `section`, `chunk_index`, `score`, `text`
- Ensure hybrid results respect `where` filter
- Pass `context["doc_scope"]` from `rag_agent_node` to retrieval

**Step 4: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/tools/test_rag_guardrails.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/tools/rag_search.py src/security_agent/rag/retriever.py src/security_agent/assistant/graph.py tests/tools/test_rag_guardrails.py
git commit -m "feat: add scoped retrieval and evidence metadata for self-rag grounding"
```

---

### Task 4 (P1): Add Deterministic Self-RAG Regression Tests

**Files:**
- Create: `tests/assistant/test_selfrag.py`
- Modify: `tests/assistant/test_guardrails_e2e.py`
- Modify: `scripts/run_eval.py`

**Step 1: Write failing test cases**

```python
def test_selfrag_escalates_when_critic_keeps_retrying_without_grounding(...):
    ...
```

```python
def test_selfrag_rejects_final_decision_without_valid_citations(...):
    ...
```

**Step 2: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/assistant/test_selfrag.py tests/assistant/test_guardrails_e2e.py -q`
Expected: FAIL before full wiring.

**Step 3: Implement minimal behavior**

- Ensure code-level citation check can override critic `FINAL` decision
- Ensure max-attempt fallback to `ESCALATE`
- Add deterministic test hooks via monkeypatch/stubs

**Step 4: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/assistant/test_selfrag.py tests/assistant/test_guardrails_e2e.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/assistant/test_selfrag.py tests/assistant/test_guardrails_e2e.py scripts/run_eval.py
git commit -m "test: add deterministic self-rag regression coverage"
```

---

### Task 5 (P2): Incremental Upload-Aware Ingestion Metadata

**Files:**
- Modify: `src/security_agent/rag/ingest.py`
- Modify: `src/security_agent/rag/store.py`
- Modify: `src/security_agent/config.py`
- Test: `tests/integration/test_rag_ingest.py`

**Step 1: Write failing tests**

```python
def test_ingest_can_append_without_reset_and_sets_upload_metadata():
    # metadata includes upload_id/doc_id/checksum
```

**Step 2: Run test**

Run: `PYTHONPATH=src .venv/bin/pytest tests/integration/test_rag_ingest.py -q`
Expected: FAIL.

**Step 3: Implement minimal ingestion changes**

- `ingest_documents(..., reset_collection=False, upload_id=None, doc_id=None)`
- Add metadata keys for verifiability
- Keep previous default behavior for existing workflows

**Step 4: Run tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/integration/test_rag_ingest.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/security_agent/rag/ingest.py src/security_agent/rag/store.py src/security_agent/config.py tests/integration/test_rag_ingest.py
git commit -m "feat: add upload-aware ingestion metadata for scoped grounding"
```

---

## Final Verification

Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q
.venv/bin/ruff check src tests scripts
```

Expected:
- Self-RAG tests pass deterministically.
- RAG answers include valid evidence citations.
- No grounded answer returned without in-range citations.
- Weak/absent evidence paths produce clarify/escalate responses.

