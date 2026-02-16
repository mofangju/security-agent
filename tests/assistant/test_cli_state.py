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
    assert context == {}
