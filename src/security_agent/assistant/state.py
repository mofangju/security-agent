"""LangGraph state definition for Lumina assistant."""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AssistantState(TypedDict):
    """State for Lumina's LangGraph assistant graph.

    Attributes:
        messages: Conversation history (LangGraph message format)
        next_node: The next specialist node to route to
        context: Additional context from tool calls
    """

    messages: Annotated[list, add_messages]
    next_node: str
    context: dict[str, Any]
