"""LangGraph supervisor graph for Security agent — the AI security assistant.

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
    PENDING_ACTION_TTL_SECONDS,
    action_from_pending,
    action_preview,
    build_pending_action,
    extract_confirmation_nonce,
    infer_config_action,
    is_pending_action_valid,
)
from security_agent.assistant.audit import get_guardrail_audit_logger
from security_agent.assistant.guardrails import (
    ALLOWED_ROUTES,
    parse_supervisor_route,
    parse_tool_result,
)
from security_agent.assistant.selfrag import (
    format_evidence_for_prompt,
    parse_evidence_payload,
    parse_selfrag_decision,
    validate_answer_citations,
)
from security_agent.assistant.state import AssistantState
from security_agent.assistant.telemetry import get_agent_telemetry, monotonic_now
from security_agent.config import config
from security_agent.llm.prompts import (
    CONFIG_MANAGER_SYSTEM,
    LOG_ANALYST_SYSTEM,
    MONITOR_SYSTEM,
    RAG_SYSTEM,
    REPORTER_SYSTEM,
    SELF_RAG_CRITIC_SYSTEM,
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
from security_agent.tools.validators import normalize_mode, validate_ip_or_cidr

SPECIALIST_NODES = [
    "monitor", "log_analyst", "config_manager",
    "threat_intel", "tuner", "reporter", "rag_agent",
]
AUDIT_LOGGER = get_guardrail_audit_logger()
TELEMETRY = get_agent_telemetry()


def _context_ids(context: dict | None) -> tuple[str, str, str]:
    ctx = context or {}
    session_id = str(ctx.get("session_id", ""))
    turn_id = str(ctx.get("turn_id", ""))
    trace_id = str(ctx.get("trace_id", ""))
    return session_id, turn_id, trace_id


def _audit(
    *,
    gate: str,
    decision: str,
    reason: str,
    metadata: dict | None = None,
    context: dict | None = None,
) -> None:
    AUDIT_LOGGER.log(
        gate=gate,
        decision=decision,
        reason=reason,
        metadata=metadata or {},
    )
    TELEMETRY.observe_guardrail(gate, decision, reason)

    session_id, turn_id, trace_id = _context_ids(context)
    TELEMETRY.emit_event(
        "guardrail.decision",
        trace_id=trace_id,
        session_id=session_id,
        turn_id=turn_id,
        metadata={
            "gate": gate,
            "decision": decision,
            "reason": reason,
            "metadata": metadata or {},
        },
    )


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
    raw_route = str(response.content or "")
    normalized_route = raw_route.strip().lower()
    route = parse_supervisor_route(raw_route)
    if normalized_route in ALLOWED_ROUTES:
        _audit(
            gate="route_parse",
            decision="allow",
            reason="allowed_token",
            metadata={"raw": raw_route, "selected": route},
            context=state.get("context", {}),
        )
    else:
        _audit(
            gate="route_parse",
            decision="deny",
            reason="invalid_token",
            metadata={"raw": raw_route, "fallback": route},
            context=state.get("context", {}),
        )

    context = dict(state.get("context", {}))
    session_id, turn_id, trace_id = _context_ids(context)
    TELEMETRY.inc_route(route)
    TELEMETRY.emit_event(
        "route.selected",
        trace_id=trace_id,
        session_id=session_id,
        turn_id=turn_id,
        metadata={"selected_agent": route, "raw_route": raw_route},
    )
    return {**state, "next_node": route}


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
    pending_raw = context.get("pending_action")
    pending_intent = action_from_pending(pending_raw)
    confirm_nonce = extract_confirmation_nonce(last_user_message)

    if pending_intent.action != "none" and "cancel" in last_user_message.lower():
        context.pop("pending_action", None)
        context["confirmed"] = False
        _audit(
            gate="action_confirmation",
            decision="deny",
            reason="user_cancelled",
            metadata={"action": pending_intent.action},
            context=context,
        )
        return {
            **state,
            "context": context,
            "messages": [AIMessage(content="Cancelled pending configuration action.")],
        }

    if pending_intent.action != "none":
        pending_ok, pending_reason = is_pending_action_valid(pending_raw)
        if not pending_ok:
            context.pop("pending_action", None)
            context["confirmed"] = False
            _audit(
                gate="action_confirmation",
                decision="deny",
                reason=pending_reason,
                metadata={"action": pending_intent.action},
                context=context,
            )
            if pending_reason == "expired":
                return {
                    **state,
                    "context": context,
                    "messages": [
                        AIMessage(
                            content=(
                                "Pending configuration action expired. "
                                "Please submit the change again."
                            )
                        )
                    ],
                }
            return {
                **state,
                "context": context,
                "messages": [
                    AIMessage(
                        content=(
                            "Pending configuration action is invalid. "
                            "Please submit the change again."
                        )
                    )
                ],
            }

        expected_nonce = str((pending_raw or {}).get("nonce", ""))
        if confirm_nonce is not None:
            if confirm_nonce != expected_nonce:
                _audit(
                    gate="action_confirmation",
                    decision="deny",
                    reason="nonce_mismatch",
                    metadata={"action": pending_intent.action},
                    context=context,
                )
                return {
                    **state,
                    "context": context,
                    "messages": [
                        AIMessage(
                            content=(
                                "Invalid confirmation token. Reply with the exact token "
                                "shown in the prompt."
                            )
                        )
                    ],
                }
            intent = pending_intent
            context["confirmed"] = True
            _audit(
                gate="action_confirmation",
                decision="allow",
                reason="nonce_match",
                metadata={"action": pending_intent.action},
                context=context,
            )
        elif intent.action == "none":
            return {
                **state,
                "context": context,
                "messages": [
                    AIMessage(
                        content=(
                            f"Pending change: {action_preview(pending_intent)}. "
                            f"Reply with 'confirm {expected_nonce}' within "
                            f"{PENDING_ACTION_TTL_SECONDS} seconds "
                            "or 'cancel'."
                        )
                    )
                ],
            }
        else:
            return {
                **state,
                "context": context,
                "messages": [
                    AIMessage(
                        content=(
                            f"You already have a pending action: {action_preview(pending_intent)}. "
                            f"Reply with 'confirm {expected_nonce}' or 'cancel' before "
                            "sending a new change."
                        )
                    )
                ],
            }

    if intent.action != "none":
        if not bool(context.get("confirmed", False)):
            if intent.action == "blacklist_ip":
                valid_ip = validate_ip_or_cidr(intent.ip)
                if valid_ip is None:
                    _audit(
                        gate="pre_tool_validation",
                        decision="deny",
                        reason="invalid_ip",
                        metadata={"action": intent.action, "ip": intent.ip},
                        context=context,
                    )
                    return {
                        **state,
                        "context": context,
                        "messages": [
                            AIMessage(content="Invalid IP or CIDR value for blacklist action.")
                        ],
                    }
            if intent.action == "set_mode" and normalize_mode(intent.mode) is None:
                _audit(
                    gate="pre_tool_validation",
                    decision="deny",
                    reason="invalid_mode",
                    metadata={"action": intent.action, "mode": intent.mode},
                    context=context,
                )
                return {
                    **state,
                    "context": context,
                    "messages": [
                        AIMessage(content="Invalid protection mode. Use block, detect, or off.")
                    ],
                }

            context["pending_action"] = build_pending_action(intent)
            context["confirmed"] = False
            nonce = context["pending_action"]["nonce"]
            _audit(
                gate="action_confirmation",
                decision="challenge",
                reason="confirmation_required",
                metadata={"action": intent.action},
                context=context,
            )
            return {
                **state,
                "context": context,
                "messages": [
                    AIMessage(
                        content=(
                            f"Please confirm before I apply this change: {action_preview(intent)}. "
                            f"Reply with 'confirm {nonce}' within "
                            f"{PENDING_ACTION_TTL_SECONDS} seconds "
                            "or 'cancel' to abort."
                        )
                    )
                ],
            }

        if intent.action == "set_mode":
            normalized_mode = normalize_mode(intent.mode)
            if normalized_mode is None:
                _audit(
                    gate="pre_tool_validation",
                    decision="deny",
                    reason="invalid_mode",
                    metadata={"action": intent.action, "mode": intent.mode},
                    context=context,
                )
                content = "❌ Change failed: invalid protection mode."
            else:
                _audit(
                    gate="pre_tool_validation",
                    decision="allow",
                    reason="mode_valid",
                    metadata={"action": intent.action, "mode": normalized_mode},
                    context=context,
                )
                started = monotonic_now()
                result = tool_set_protection_mode(normalized_mode)
                ok, reason = parse_tool_result(result)
                duration = monotonic_now() - started
                TELEMETRY.observe_tool_call(
                    "config_manager",
                    "tool_set_protection_mode",
                    "ok" if ok else "error",
                    duration,
                )
                session_id, turn_id, trace_id = _context_ids(context)
                TELEMETRY.emit_event(
                    "tool.call",
                    trace_id=trace_id,
                    session_id=session_id,
                    turn_id=turn_id,
                    metadata={
                        "agent": "config_manager",
                        "tool": "tool_set_protection_mode",
                        "status": "ok" if ok else "error",
                        "duration_seconds": duration,
                    },
                )
                _audit(
                    gate="post_tool_result",
                    decision="allow" if ok else "deny",
                    reason="tool_ok" if ok else reason,
                    metadata={"action": intent.action},
                    context=context,
                )
                if ok:
                    content = (
                        f"✅ Executed: Set protection mode to {normalized_mode.upper()}\n"
                        f"Result: {result}"
                    )
                else:
                    content = f"❌ Change failed: {reason}\nResult: {result}"
        elif intent.action == "blacklist_ip":
            valid_ip = validate_ip_or_cidr(intent.ip)
            if valid_ip is None:
                _audit(
                    gate="pre_tool_validation",
                    decision="deny",
                    reason="invalid_ip",
                    metadata={"action": intent.action, "ip": intent.ip},
                    context=context,
                )
                content = "❌ Change failed: invalid IP or CIDR value."
            else:
                _audit(
                    gate="pre_tool_validation",
                    decision="allow",
                    reason="ip_valid",
                    metadata={"action": intent.action, "ip": valid_ip},
                    context=context,
                )
                started = monotonic_now()
                result = tool_manage_ip_blacklist(
                    "add",
                    valid_ip,
                    intent.comment or "Blocked by Security agent",
                )
                ok, reason = parse_tool_result(result)
                duration = monotonic_now() - started
                TELEMETRY.observe_tool_call(
                    "config_manager",
                    "tool_manage_ip_blacklist",
                    "ok" if ok else "error",
                    duration,
                )
                session_id, turn_id, trace_id = _context_ids(context)
                TELEMETRY.emit_event(
                    "tool.call",
                    trace_id=trace_id,
                    session_id=session_id,
                    turn_id=turn_id,
                    metadata={
                        "agent": "config_manager",
                        "tool": "tool_manage_ip_blacklist",
                        "status": "ok" if ok else "error",
                        "duration_seconds": duration,
                    },
                )
                _audit(
                    gate="post_tool_result",
                    decision="allow" if ok else "deny",
                    reason="tool_ok" if ok else reason,
                    metadata={"action": intent.action, "ip": valid_ip},
                    context=context,
                )
                if ok:
                    content = f"✅ Executed: Added {valid_ip} to blacklist\nResult: {result}"
                else:
                    content = f"❌ Change failed: {reason}\nResult: {result}"
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
    """Documentation query specialist with Self-RAG grounding loop."""
    llm = get_llm(temperature=0.0)
    context = dict(state.get("context", {}))
    question = str(state["messages"][-1].content) if state.get("messages") else ""
    doc_scope = context.get("doc_scope")
    where = doc_scope if isinstance(doc_scope, dict) and doc_scope else None

    max_attempts = max(1, config.rag.selfrag_max_attempts)
    min_citations = max(1, config.rag.selfrag_min_citations)
    n_results = 5
    trace: list[dict] = []

    for attempt in range(1, max_attempts + 1):
        rag_raw = tool_rag_search(question, n_results=n_results, where=where)
        evidence, parse_reason = parse_evidence_payload(rag_raw)

        if not evidence:
            _audit(
                gate="selfrag_retrieval",
                decision="deny",
                reason=parse_reason or "no_evidence",
                metadata={"attempt": attempt, "where": where or {}},
                context=context,
            )
            TELEMETRY.observe_selfrag_decision("ESCALATE", parse_reason or "no_evidence")
            trace.append(
                {
                    "attempt": attempt,
                    "decision": "ESCALATE",
                    "reason": parse_reason or "no_evidence",
                }
            )
            context["selfrag"] = {"trace": trace, "grounded": False}
            return {
                **state,
                "context": context,
                "messages": [
                    AIMessage(
                        content=(
                            "I could not find grounded evidence for this question in the "
                            "indexed documents. Please refine the question or provide "
                            "relevant documents."
                        )
                    )
                ],
            }

        evidence_block = format_evidence_for_prompt(evidence)
        draft_messages = [
            SystemMessage(content=RAG_SYSTEM),
            HumanMessage(
                content=(
                    f"Question:\n{question}\n\n"
                    f"Evidence (numbered):\n{evidence_block}\n\n"
                    "Answer using only the evidence above. "
                    "Cite factual claims with numeric citations like [1], [2]. "
                    "If evidence is insufficient, say INSUFFICIENT_EVIDENCE."
                )
            ),
        ]
        draft = str(llm.invoke(draft_messages).content).strip()

        critic_messages = [
            SystemMessage(content=SELF_RAG_CRITIC_SYSTEM),
            HumanMessage(
                content=(
                    f"Question:\n{question}\n\n"
                    f"Draft answer:\n{draft}\n\n"
                    f"Evidence count: {len(evidence)}\n\n"
                    "Evaluate grounding and output one decision line."
                )
            ),
        ]
        critic_raw = str(llm.invoke(critic_messages).content).strip()
        decision, reason = parse_selfrag_decision(critic_raw)
        cites_ok, cite_reason = validate_answer_citations(
            draft,
            evidence_count=len(evidence),
            min_citations=min_citations,
        )

        if decision == "FINAL" and not cites_ok:
            decision = "RETRY"
            reason = f"citation_guardrail:{cite_reason}"

        TELEMETRY.observe_selfrag_decision(decision, reason or "none")
        session_id, turn_id, trace_id = _context_ids(context)
        TELEMETRY.emit_event(
            "selfrag.decision",
            trace_id=trace_id,
            session_id=session_id,
            turn_id=turn_id,
            metadata={
                "attempt": attempt,
                "decision": decision,
                "reason": reason,
                "citations_ok": cites_ok,
                "where": where or {},
            },
        )
        _audit(
            gate="selfrag_decision",
            decision=decision.lower(),
            reason=reason or "none",
            metadata={"attempt": attempt, "citations_ok": cites_ok, "where": where or {}},
            context=context,
        )
        trace.append(
            {
                "attempt": attempt,
                "decision": decision,
                "reason": reason,
                "citations_ok": cites_ok,
            }
        )

        if decision == "FINAL":
            context["selfrag"] = {"trace": trace, "grounded": True}
            return {**state, "context": context, "messages": [AIMessage(content=draft)]}

        if decision == "CLARIFY":
            context["selfrag"] = {"trace": trace, "grounded": False}
            return {
                **state,
                "context": context,
                "messages": [
                    AIMessage(
                        content=(
                            "I need a bit more detail to ground this answer in your documents. "
                            "Please clarify the exact SafeLine feature or endpoint."
                        )
                    )
                ],
            }

        if decision == "ESCALATE":
            context["selfrag"] = {"trace": trace, "grounded": False}
            return {
                **state,
                "context": context,
                "messages": [
                    AIMessage(
                        content=(
                            "I can't verify a grounded answer from the current evidence. "
                            "Please upload relevant documentation or rephrase the request."
                        )
                    )
                ],
            }

        n_results = min(12, n_results + 2)

    context["selfrag"] = {"trace": trace, "grounded": False}
    return {
        **state,
        "context": context,
        "messages": [
            AIMessage(
                content=(
                    "I could not produce a verifiable grounded answer after multiple attempts. "
                    "Please refine the question or provide additional documentation."
                )
            )
        ],
    }


def direct_response_node(state: AssistantState) -> AssistantState:
    """Direct response for simple greetings/questions (no specialist needed)."""
    llm = get_llm(temperature=0.3)

    messages = [
        SystemMessage(
            content=(
                "You are Security agent, the AI Security Assistant for SafeLine WAF. "
                "Respond helpfully to the engineer's greeting or general question. "
                "Introduce yourself as Security agent and mention that you can help with: "
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
        TELEMETRY.inc_handoff("supervisor", next_node)
        session_id, turn_id, trace_id = _context_ids(dict(state.get("context", {})))
        TELEMETRY.emit_event(
            "route.handoff",
            trace_id=trace_id,
            session_id=session_id,
            turn_id=turn_id,
            metadata={"from_agent": "supervisor", "to_agent": next_node},
        )
        return next_node
    TELEMETRY.inc_handoff("supervisor", "direct")
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
