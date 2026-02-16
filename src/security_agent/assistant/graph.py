"""LangGraph supervisor graph for Lumina — the AI security assistant.

The supervisor routes engineer requests to specialist nodes:
- monitor: Traffic monitoring
- log_analyst: Attack log analysis
- config_manager: WAF configuration
- threat_intel: CVE/threat analysis
- tuner: False positive tuning
- reporter: Incident reports
- rag_agent: Documentation queries
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from security_agent.assistant.actions import (
    action_from_pending,
    action_preview,
    infer_config_action,
    is_confirmation_message,
)
from security_agent.assistant.state import AssistantState
from security_agent.llm.prompts import (
    CONFIG_MANAGER_SYSTEM,
    LOG_ANALYST_SYSTEM,
    MONITOR_SYSTEM,
    RAG_SYSTEM,
    REPORTER_SYSTEM,
    SUPERVISOR_SYSTEM,
    THREAT_INTEL_SYSTEM,
    TUNER_SYSTEM,
)
from security_agent.llm.provider import get_llm
from security_agent.tools.cve_lookup import tool_cve_lookup
from security_agent.tools.parsers import parse_events, parse_qps
from security_agent.tools.rag_search import tool_rag_search
from security_agent.tools.safeline_api import (
    tool_get_attack_events,
    tool_get_system_info,
    tool_get_traffic_stats,
    tool_manage_ip_blacklist,
    tool_set_protection_mode,
)

SPECIALIST_NODES = [
    "monitor", "log_analyst", "config_manager",
    "threat_intel", "tuner", "reporter", "rag_agent",
]


def supervisor_node(state: AssistantState) -> AssistantState:
    """Route the engineer's request to the appropriate specialist."""
    llm = get_llm(temperature=0.0)

    # Build the routing prompt
    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                "Based on the user's message, respond with ONLY the specialist name "
                "to route to. Options: monitor, log_analyst, config_manager, "
                "threat_intel, tuner, reporter, rag_agent. "
                "If this is a simple greeting or general question, respond with 'direct'."
            )
        ),
    ]

    response = llm.invoke(messages)
    route = response.content.strip().lower()

    # Clean up the route — extract just the node name
    for node in SPECIALIST_NODES:
        if node in route:
            return {**state, "next_node": node}

    # Default: respond directly via supervisor
    return {**state, "next_node": "direct"}


def _format_qps_summary(raw_stats: str) -> str:
    """Pre-format QPS data into a concise summary."""
    try:
        parsed = parse_qps(raw_stats)
        latest_qps = parsed["current_qps"]
        total_attacks = parsed["total_attacks"]
        active = parsed["active_qps"]

        lines = [f"Current QPS: {latest_qps:g}"]
        lines.append(f"Total attacks detected (cumulative): {total_attacks}")
        if active:
            lines.append(
                "Active QPS in window: " + ", ".join(f"{t}={q:g}" for t, q in active[-10:])
            )
        else:
            lines.append("No active traffic in this window — system is idle.")
        return "\n".join(lines)
    except Exception:
        return raw_stats


def monitor_node(state: AssistantState) -> AssistantState:
    """Traffic monitoring specialist."""
    llm = get_llm(temperature=0.0)

    # Get live stats and pre-format
    raw_stats = tool_get_traffic_stats()
    summary = _format_qps_summary(raw_stats)

    messages = [
        SystemMessage(content=MONITOR_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                "Current SafeLine traffic summary:\n\n"
                f"{summary}\n\n"
                "Present this concisely to the engineer."
            )
        ),
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def _format_events_summary(raw_events: str) -> str:
    """Pre-format attack events into a concise text summary."""
    try:
        parsed = parse_events(raw_events)
        events = parsed["events"]
        total = parsed["total"]

        if not events:
            return f"Total events: {total}\nNo events in this page."

        lines = [f"Total events: {total}", ""]
        for e in events:
            event_target = f"{e.get('host', '?')}:{e.get('dst_port', '?')}"
            lines.append(
                f"Event #{e['id']}: IP={e.get('ip','?')} → {event_target} "
                f"| blocked={e.get('deny_count',0)} passed={e.get('pass_count',0)} "
                f"| status={e.get('status','unknown')} | time={e.get('time','unknown')} "
                f"| country={e.get('country','')} | finished={e.get('finished', True)}"
            )
        return "\n".join(lines)
    except Exception:
        return raw_events


def log_analyst_node(state: AssistantState) -> AssistantState:
    """Attack log analysis specialist."""
    llm = get_llm(temperature=0.0)

    # Get recent attack events and pre-format
    raw_events = tool_get_attack_events(page=1, page_size=50)
    summary = _format_events_summary(raw_events)

    messages = [
        SystemMessage(content=LOG_ANALYST_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                f"Recent SafeLine attack events:\n\n{summary}\n\n"
                "Analyze these events concisely. Use short bullet points, not wide tables."
            )
        ),
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def config_manager_node(state: AssistantState) -> AssistantState:
    """WAF configuration specialist."""
    context = dict(state.get("context", {}))
    last_user_message = ""
    if state.get("messages"):
        last_user_message = str(state["messages"][-1].content)

    intent = infer_config_action(last_user_message)
    pending_intent = action_from_pending(context.get("pending_action"))

    if pending_intent.action != "none" and is_confirmation_message(last_user_message):
        intent = pending_intent
        context["confirmed"] = True

    if pending_intent.action != "none" and "cancel" in last_user_message.lower():
        context.pop("pending_action", None)
        context["confirmed"] = False
        return {
            **state,
            "context": context,
            "messages": [AIMessage(content="Cancelled pending configuration action.")],
        }

    if intent.action != "none":
        if not bool(context.get("confirmed", False)):
            context["pending_action"] = {
                "action": intent.action,
                "mode": intent.mode,
                "ip": intent.ip,
                "comment": intent.comment,
            }
            context["confirmed"] = False
            return {
                **state,
                "context": context,
                "messages": [
                    AIMessage(
                        content=(
                            f"Please confirm before I apply this change: {action_preview(intent)}. "
                            "Reply with 'confirm' to proceed or 'cancel' to abort."
                        )
                    )
                ],
            }

        if intent.action == "set_mode":
            result = tool_set_protection_mode(intent.mode or "detect")
            content = (
                f"✅ Executed: Set protection mode to {str(intent.mode or 'detect').upper()}\n"
                f"Result: {result}"
            )
        elif intent.action == "blacklist_ip":
            result = tool_manage_ip_blacklist(
                "add",
                intent.ip or "",
                intent.comment or "Blocked by Lumina",
            )
            content = f"✅ Executed: Added {intent.ip} to blacklist\nResult: {result}"
        else:
            content = "No supported configuration action detected."

        context.pop("pending_action", None)
        context["confirmed"] = False
        return {**state, "context": context, "messages": [AIMessage(content=content)]}

    llm = get_llm(temperature=0.0)
    system_info = tool_get_system_info()
    messages = [
        SystemMessage(content=CONFIG_MANAGER_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                f"Current SafeLine system info:\n{system_info}\n\n"
                "Answer the engineer's configuration question concisely."
            )
        ),
    ]
    response = llm.invoke(messages)
    return {**state, "context": context, "messages": [AIMessage(content=response.content)]}


def threat_intel_node(state: AssistantState) -> AssistantState:
    """Threat intelligence specialist."""
    llm = get_llm(temperature=0.0)

    # Get events + CVE data
    events = tool_get_attack_events(page=1, page_size=20)

    # Look up CVEs for common attack types
    cve_sqli = tool_cve_lookup("sqli")
    cve_xss = tool_cve_lookup("xss")
    cve_traversal = tool_cve_lookup("traversal")
    cve_cmdi = tool_cve_lookup("cmdi")

    messages = [
        SystemMessage(content=THREAT_INTEL_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                f"Recent attack events:\n{events}\n\n"
                f"CVE/CWE data for SQLi:\n{cve_sqli}\n\n"
                f"CVE/CWE data for XSS:\n{cve_xss}\n\n"
                f"CVE/CWE data for Path Traversal:\n{cve_traversal}\n\n"
                f"CVE/CWE data for Command Injection:\n{cve_cmdi}\n\n"
                "Correlate the attacks with the vulnerability data and provide threat analysis."
            )
        ),
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def tuner_node(state: AssistantState) -> AssistantState:
    """Rule tuning / false positive specialist."""
    llm = get_llm(temperature=0.0)

    # Get recent events and current policies
    events = tool_get_attack_events(page=1, page_size=20)
    rag_results = tool_rag_search("false positive tuning whitelist rules SafeLine")

    messages = [
        SystemMessage(content=TUNER_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                f"Recent attack events (check for false positives):\n{events}\n\n"
                f"Relevant documentation:\n{rag_results}\n\n"
                "Analyze the situation and recommend tuning actions."
            )
        ),
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def reporter_node(state: AssistantState) -> AssistantState:
    """Incident report generator."""
    llm = get_llm(temperature=0.0)

    # Gather all available data
    events = tool_get_attack_events(page=1, page_size=50)
    stats = tool_get_traffic_stats()
    playbook = tool_rag_search("incident report template security")

    messages = [
        SystemMessage(content=REPORTER_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                f"Attack events:\n{events}\n\n"
                f"Traffic statistics:\n{stats}\n\n"
                f"Report template reference:\n{playbook}\n\n"
                "Generate a structured incident report."
            )
        ),
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def rag_agent_node(state: AssistantState) -> AssistantState:
    """Documentation query specialist (RAG)."""
    llm = get_llm(temperature=0.0)

    # Extract the question from the last message
    last_msg = str(state["messages"][-1].content) if state["messages"] else ""
    rag_results = tool_rag_search(last_msg, n_results=5)

    messages = [
        SystemMessage(content=RAG_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                f"Here are relevant documents from the knowledge base:\n\n{rag_results}\n\n"
                "Use this information to answer the engineer's question."
            )
        ),
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def direct_response_node(state: AssistantState) -> AssistantState:
    """Direct response for simple greetings/questions (no specialist needed)."""
    llm = get_llm(temperature=0.3)

    messages = [
        SystemMessage(
            content=(
                "You are Lumina, the AI Security Assistant for SafeLine WAF. "
                "Respond helpfully to the engineer's greeting or general question. "
                "Introduce yourself as Lumina and mention that you can help with: "
                "monitoring traffic, analyzing attacks, "
                "configuring the WAF, looking up threats, tuning rules, generating reports, "
                "and answering questions about SafeLine."
            )
        ),
        *state["messages"],
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def route_to_specialist(state: AssistantState) -> str:
    """Routing function — determines next node based on supervisor decision."""
    next_node = state.get("next_node", "direct")
    if next_node in SPECIALIST_NODES:
        return next_node
    return "direct"


def build_assistant_graph() -> StateGraph:
    """Build and compile the LangGraph assistant graph."""
    graph = StateGraph(AssistantState)

    # Add nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("monitor", monitor_node)
    graph.add_node("log_analyst", log_analyst_node)
    graph.add_node("config_manager", config_manager_node)
    graph.add_node("threat_intel", threat_intel_node)
    graph.add_node("tuner", tuner_node)
    graph.add_node("reporter", reporter_node)
    graph.add_node("rag_agent", rag_agent_node)
    graph.add_node("direct", direct_response_node)

    # Set entry point
    graph.set_entry_point("supervisor")

    # Conditional routing from supervisor to specialists
    graph.add_conditional_edges(
        "supervisor",
        route_to_specialist,
        {
            "monitor": "monitor",
            "log_analyst": "log_analyst",
            "config_manager": "config_manager",
            "threat_intel": "threat_intel",
            "tuner": "tuner",
            "reporter": "reporter",
            "rag_agent": "rag_agent",
            "direct": "direct",
        },
    )

    # All specialist nodes end after responding
    for node in SPECIALIST_NODES + ["direct"]:
        graph.add_edge(node, END)

    return graph.compile()
