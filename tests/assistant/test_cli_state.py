from __future__ import annotations

from langchain_core.messages import AIMessage

from security_agent.assistant.cli import run_turn


class _GraphStub:
    def __init__(self):
        self.calls = []

    def invoke(self, state):
        self.calls.append(state)
        return {
            "messages": [AIMessage(content=f"reply:{state['messages'][-1].content}")],
            "context": state.get("context", {}),
        }


def test_run_turn_preserves_prior_messages():
    graph = _GraphStub()
    messages = []
    context = {}

    _, messages, context = run_turn(graph, messages, context, "first")
    _, messages, context = run_turn(graph, messages, context, "follow-up")

    second_call_contents = [str(m.content) for m in graph.calls[1]["messages"]]
    assert "first" in second_call_contents
    assert "follow-up" in second_call_contents
    assert len(messages) == 4
    assert context["session_id"]
    assert context["turn_id"] == "2"
    assert context["trace_id"]


def test_run_turn_stamps_trace_and_turn_ids():
    graph = _GraphStub()
    messages = []
    context = {}

    _, messages, context = run_turn(graph, messages, context, "first")
    first_trace = context.get("trace_id")
    assert context.get("session_id")
    assert context.get("turn_id") == "1"
    assert first_trace

    _, messages, context = run_turn(graph, messages, context, "second")
    assert context.get("session_id")
    assert context.get("turn_id") == "2"
    assert context.get("trace_id")
    assert context.get("trace_id") != first_trace
