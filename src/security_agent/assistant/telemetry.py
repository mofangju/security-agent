"""Agent-level metrics and trace-event telemetry helpers."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from security_agent.config import config

_TOOL_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
_TURN_LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)


def _labels_key(labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(labels.items())


def _labels_text(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{k}="{v}"' for k, v in labels.items()]
    return "{" + ",".join(parts) + "}"


@dataclass
class _Histogram:
    """Prometheus-style histogram data for one metric."""

    buckets: tuple[float, ...]
    sum: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)
    count: dict[tuple[tuple[str, str], ...], int] = field(default_factory=dict)
    bucket_counts: dict[tuple[tuple[str, str], ...], list[int]] = field(default_factory=dict)

    def observe(self, labels: dict[str, str], value: float) -> None:
        key = _labels_key(labels)
        self.sum[key] = self.sum.get(key, 0.0) + value
        self.count[key] = self.count.get(key, 0) + 1

        counts = self.bucket_counts.get(key)
        if counts is None:
            counts = [0 for _ in self.buckets]
            self.bucket_counts[key] = counts

        for idx, bound in enumerate(self.buckets):
            if value <= bound:
                counts[idx] += 1


class AgentTelemetry:
    """In-process telemetry registry for multi-agent signals."""

    def __init__(
        self,
        *,
        namespace: str,
        trace_jsonl_path: Path | str | None = None,
        enabled: bool = True,
    ) -> None:
        self.namespace = namespace.strip() or "security_agent"
        self.enabled = enabled
        self.trace_jsonl_path = Path(trace_jsonl_path) if trace_jsonl_path else None

        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], int]] = {
            "agent_route_total": {},
            "agent_handoff_total": {},
            "agent_tool_calls_total": {},
            "agent_guardrail_total": {},
            "agent_selfrag_decision_total": {},
            "agent_trace_events_total": {},
        }
        self._histograms: dict[str, _Histogram] = {
            "agent_tool_latency_seconds": _Histogram(buckets=_TOOL_LATENCY_BUCKETS),
            "agent_turn_latency_seconds": _Histogram(buckets=_TURN_LATENCY_BUCKETS),
        }

    def _inc_counter(self, metric: str, labels: dict[str, str]) -> None:
        if not self.enabled:
            return
        with self._lock:
            slot = self._counters[metric]
            key = _labels_key(labels)
            slot[key] = slot.get(key, 0) + 1

    def _observe_hist(self, metric: str, labels: dict[str, str], value: float) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._histograms[metric].observe(labels, max(0.0, float(value)))

    def inc_route(self, selected_agent: str) -> None:
        self._inc_counter(
            "agent_route_total",
            {"selected_agent": str(selected_agent)},
        )

    def inc_handoff(self, from_agent: str, to_agent: str) -> None:
        self._inc_counter(
            "agent_handoff_total",
            {"from_agent": str(from_agent), "to_agent": str(to_agent)},
        )

    def observe_tool_call(
        self,
        agent: str,
        tool: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        labels = {"agent": str(agent), "tool": str(tool)}
        self._inc_counter("agent_tool_calls_total", {**labels, "status": str(status)})
        self._observe_hist("agent_tool_latency_seconds", labels, duration_seconds)

    def observe_guardrail(self, gate: str, decision: str, reason: str) -> None:
        self._inc_counter(
            "agent_guardrail_total",
            {
                "gate": str(gate),
                "decision": str(decision),
                "reason": str(reason),
            },
        )

    def observe_selfrag_decision(self, decision: str, reason: str) -> None:
        self._inc_counter(
            "agent_selfrag_decision_total",
            {
                "decision": str(decision),
                "reason": str(reason),
            },
        )

    def observe_turn(self, duration_seconds: float) -> None:
        self._observe_hist("agent_turn_latency_seconds", {}, duration_seconds)

    def emit_event(
        self,
        event: str,
        *,
        trace_id: str,
        session_id: str,
        turn_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return

        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": str(event),
            "trace_id": str(trace_id),
            "session_id": str(session_id),
            "turn_id": str(turn_id),
            "metadata": metadata or {},
        }

        self._inc_counter("agent_trace_events_total", {"event": str(event)})

        if self.trace_jsonl_path is None:
            return

        self.trace_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_jsonl_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def render_prometheus(self) -> str:
        if not self.enabled:
            return ""

        with self._lock:
            lines: list[str] = []

            for metric, values in self._counters.items():
                full = f"{self.namespace}_{metric}"
                lines.append(f"# HELP {full} Counter {metric}")
                lines.append(f"# TYPE {full} counter")
                for key, value in sorted(values.items()):
                    labels = dict(key)
                    lines.append(f"{full}{_labels_text(labels)} {value}")

            for metric, hist in self._histograms.items():
                full = f"{self.namespace}_{metric}"
                lines.append(f"# HELP {full} Histogram {metric}")
                lines.append(f"# TYPE {full} histogram")

                for key, counts in sorted(hist.bucket_counts.items()):
                    labels = dict(key)
                    cumulative = 0
                    for idx, bound in enumerate(hist.buckets):
                        cumulative += counts[idx]
                        bucket_labels = {**labels, "le": str(bound)}
                        lines.append(f"{full}_bucket{_labels_text(bucket_labels)} {cumulative}")
                    total = hist.count.get(key, 0)
                    inf_labels = {**labels, "le": "+Inf"}
                    lines.append(f"{full}_bucket{_labels_text(inf_labels)} {total}")
                    lines.append(f"{full}_sum{_labels_text(labels)} {hist.sum.get(key, 0.0)}")
                    lines.append(f"{full}_count{_labels_text(labels)} {total}")

            return "\n".join(lines) + "\n"


@lru_cache(maxsize=1)
def get_agent_telemetry() -> AgentTelemetry:
    """Return singleton telemetry registry based on runtime config."""
    return AgentTelemetry(
        namespace=config.observability.metrics_namespace,
        trace_jsonl_path=config.observability.trace_jsonl_path,
        enabled=config.observability.enabled,
    )


def monotonic_now() -> float:
    """Light wrapper used for testability around latency measurements."""
    return time.perf_counter()
