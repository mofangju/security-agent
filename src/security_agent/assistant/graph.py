"""LangGraph supervisor graph for the AI security assistant.

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

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

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
from security_agent.tools.rag_search import tool_rag_search
from security_agent.tools.safeline_api import (
    tool_get_attack_events,
    tool_get_traffic_stats,
    tool_manage_ip_blacklist,
    tool_set_protection_mode,
    tool_get_system_info,
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


def monitor_node(state: AssistantState) -> AssistantState:
    """Traffic monitoring specialist."""
    llm = get_llm(temperature=0.0)

    # Get live stats
    stats = tool_get_traffic_stats()

    messages = [
        SystemMessage(content=MONITOR_SYSTEM),
        *state["messages"],
        HumanMessage(content=f"Here are the current SafeLine traffic statistics:\n\n{stats}\n\nAnalyze and present these to the engineer."),
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def log_analyst_node(state: AssistantState) -> AssistantState:
    """Attack log analysis specialist."""
    llm = get_llm(temperature=0.0)

    # Get recent attack events
    events = tool_get_attack_events(page=1, page_size=50)

    messages = [
        SystemMessage(content=LOG_ANALYST_SYSTEM),
        *state["messages"],
        HumanMessage(content=f"Here are the recent SafeLine attack events:\n\n{events}\n\nAnalyze these events and present findings to the engineer."),
    ]

    response = llm.invoke(messages)
    return {**state, "messages": [AIMessage(content=response.content)]}


def config_manager_node(state: AssistantState) -> AssistantState:
    """WAF configuration specialist."""
    llm = get_llm(temperature=0.0)

    # Get current mode and system info
    system_info = tool_get_system_info()

    messages = [
        SystemMessage(content=CONFIG_MANAGER_SYSTEM),
        *state["messages"],
        HumanMessage(
            content=(
                f"Current SafeLine system info:\n{system_info}\n\n"
                "Determine what configuration action the engineer wants and execute it. "
                "Available actions:\n"
                "- Set protection mode: tool_set_protection_mode(mode='block'/'detect'/'off')\n"
                "- Manage IP blacklist: tool_manage_ip_blacklist(action, ip, comment)\n"
                "Respond with the action you're taking and the result."
            )
        ),
    ]

    response = llm.invoke(messages)
    content = response.content.lower()

    # Auto-execute common config actions based on LLM response
    result_parts = [response.content]

    if "block" in content and "mode" in content:
        result = tool_set_protection_mode("block")
        result_parts.append(f"\n\n✅ Executed: Set protection mode to BLOCK\nResult: {result}")
    elif "detect" in content and "mode" in content:
        result = tool_set_protection_mode("detect")
        result_parts.append(f"\n\n✅ Executed: Set protection mode to DETECT\nResult: {result}")

    # Check for IP blacklist requests
    import re
    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', str(state["messages"]))
    if ip_match and ("block" in content or "blacklist" in content or "ban" in content):
        ip = ip_match.group(1)
        result = tool_manage_ip_blacklist("add", ip, "Blocked by AI assistant")
        result_parts.append(f"\n\n✅ Executed: Added {ip} to blacklist\nResult: {result}")

    final_content = "\n".join(result_parts)
    return {**state, "messages": [AIMessage(content=final_content)]}


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
                "You are the AI Security Assistant for SafeLine WAF. "
                "Respond helpfully to the engineer's greeting or general question. "
                "Mention that you can help with: monitoring traffic, analyzing attacks, "
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
