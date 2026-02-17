"""HTTP API wrapper for Security Agent (Kubernetes-friendly runtime)."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from flask import Flask, Response, jsonify, request

from security_agent.assistant.cli import run_turn
from security_agent.assistant.graph import build_assistant_graph
from security_agent.assistant.telemetry import get_agent_telemetry
from security_agent.config import config


@dataclass
class SessionState:
    """In-memory chat session state."""

    messages: list
    context: dict[str, Any]
    updated_at: float


class Metrics:
    """Minimal Prometheus-compatible in-process metrics store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.chat_requests_total = 0
        self.chat_failures_total = 0
        self.chat_latency_sum_seconds = 0.0
        self.chat_latency_count = 0
        self.health_checks_total = 0
        self.readiness_checks_total = 0

    def observe_chat(self, duration_seconds: float, ok: bool) -> None:
        with self._lock:
            self.chat_requests_total += 1
            self.chat_latency_sum_seconds += duration_seconds
            self.chat_latency_count += 1
            if not ok:
                self.chat_failures_total += 1

    def observe_health(self) -> None:
        with self._lock:
            self.health_checks_total += 1

    def observe_readiness(self) -> None:
        with self._lock:
            self.readiness_checks_total += 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP security_agent_chat_requests_total Total chat requests",
                "# TYPE security_agent_chat_requests_total counter",
                f"security_agent_chat_requests_total {self.chat_requests_total}",
                "# HELP security_agent_chat_failures_total Total failed chat requests",
                "# TYPE security_agent_chat_failures_total counter",
                f"security_agent_chat_failures_total {self.chat_failures_total}",
                "# HELP security_agent_chat_latency_seconds_sum Chat latency sum in seconds",
                "# TYPE security_agent_chat_latency_seconds_sum counter",
                f"security_agent_chat_latency_seconds_sum {self.chat_latency_sum_seconds}",
                "# HELP security_agent_chat_latency_seconds_count Chat latency sample count",
                "# TYPE security_agent_chat_latency_seconds_count counter",
                f"security_agent_chat_latency_seconds_count {self.chat_latency_count}",
                "# HELP security_agent_health_checks_total Health endpoint requests",
                "# TYPE security_agent_health_checks_total counter",
                f"security_agent_health_checks_total {self.health_checks_total}",
                "# HELP security_agent_readiness_checks_total Readiness endpoint requests",
                "# TYPE security_agent_readiness_checks_total counter",
                f"security_agent_readiness_checks_total {self.readiness_checks_total}",
            ]
        return "\n".join(lines) + "\n"


def create_app(
    *,
    graph_factory: Callable[[], Any] = build_assistant_graph,
    turn_runner: Callable[..., tuple[dict, list, dict]] = run_turn,
) -> Flask:
    """Create Flask app exposing health and chat endpoints."""
    app = Flask(__name__)
    lock = threading.Lock()
    sessions: dict[str, SessionState] = {}
    metrics = Metrics()
    agent_telemetry = get_agent_telemetry()
    graph: Any | None = None

    def _get_graph() -> Any:
        nonlocal graph
        if graph is None:
            graph = graph_factory()
        return graph

    def _prune_sessions(now: float) -> None:
        ttl = max(60, config.assistant_api.session_ttl_seconds)
        max_sessions = max(1, config.assistant_api.max_sessions)

        stale = [sid for sid, s in sessions.items() if now - s.updated_at > ttl]
        for sid in stale:
            sessions.pop(sid, None)

        if len(sessions) <= max_sessions:
            return

        # Drop oldest sessions first to enforce cap.
        oldest = sorted(sessions.items(), key=lambda kv: kv[1].updated_at)
        to_drop = len(sessions) - max_sessions
        for sid, _ in oldest[:to_drop]:
            sessions.pop(sid, None)

    @app.get("/healthz")
    def healthz() -> Response:
        metrics.observe_health()
        return jsonify({"status": "ok"})

    @app.get("/readyz")
    def readyz() -> Response:
        metrics.observe_readiness()
        try:
            _get_graph()
            return jsonify({"status": "ready"})
        except Exception as exc:  # pragma: no cover - defensive
            return jsonify({"status": "not_ready", "error": str(exc)}), 503

    @app.get("/metrics")
    def metrics_endpoint() -> Response:
        payload = metrics.render_prometheus() + agent_telemetry.render_prometheus()
        return Response(payload, mimetype="text/plain; version=0.0.4")

    @app.post("/v1/chat")
    def chat() -> Response:
        started = time.perf_counter()
        ok = False
        try:
            body = request.get_json(force=True, silent=False)
        except Exception:
            metrics.observe_chat(time.perf_counter() - started, ok=False)
            return jsonify({"error": "invalid_json"}), 400

        if not isinstance(body, dict):
            metrics.observe_chat(time.perf_counter() - started, ok=False)
            return jsonify({"error": "invalid_body"}), 400

        message = str(body.get("message", "")).strip()
        if not message:
            metrics.observe_chat(time.perf_counter() - started, ok=False)
            return jsonify({"error": "message_required"}), 400

        session_id = str(body.get("session_id", "")).strip() or uuid.uuid4().hex
        now = time.time()

        with lock:
            _prune_sessions(now)
            session = sessions.get(
                session_id,
                SessionState(messages=[], context={}, updated_at=now),
            )

        req_context = dict(session.context)
        req_context.setdefault("session_id", session_id)

        try:
            result, messages, context = turn_runner(
                graph=_get_graph(),
                messages=session.messages,
                context=req_context,
                user_input=message,
            )
            reply = ""
            if result.get("messages"):
                reply = str(result["messages"][-1].content)

            with lock:
                sessions[session_id] = SessionState(
                    messages=messages,
                    context=context,
                    updated_at=now,
                )

            ok = True
            return jsonify(
                {
                    "session_id": session_id,
                    "reply": reply,
                    "message_count": len(messages),
                    "context": context,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive
            return jsonify({"error": "chat_failed", "detail": str(exc)}), 500
        finally:
            duration = time.perf_counter() - started
            metrics.observe_chat(duration, ok=ok)
            agent_telemetry.observe_turn(duration)

    return app


def main() -> None:
    """Run assistant HTTP API server."""
    app = create_app()
    app.run(
        host=config.assistant_api.host,
        port=config.assistant_api.port,
        debug=config.assistant_api.debug,
    )


if __name__ == "__main__":
    main()
