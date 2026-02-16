"""Interactive CLI chat for Lumina — the AI-powered security assistant.

Lumina is the intelligent WAF co-pilot for SafeLine. It understands
natural language and routes requests to 7 specialist capabilities:
traffic monitoring, attack analysis, configuration, threat intel,
rule tuning, incident reporting, and documentation Q&A.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from security_agent.assistant.graph import build_assistant_graph

WELCOME_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║              🛡️  Lumina — SafeLine AI Assistant  🛡️           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Hi! I'm Lumina, your AI-powered WAF co-pilot.              ║
║  I help you manage and troubleshoot SafeLine WAF.            ║
║                                                              ║
║  I can:                                                      ║
║  📊 Monitor traffic and stats                                ║
║  🔍 Analyze attack logs                                      ║
║  ⚙️  Configure WAF settings                                  ║
║  🕵️  Look up threat intelligence                              ║
║  🔧 Tune rules and fix false positives                       ║
║  📋 Generate incident reports                                ║
║  📚 Answer questions from documentation                      ║
║                                                              ║
║  Type 'quit' or 'exit' to leave.                             ║
╚══════════════════════════════════════════════════════════════╝
"""


MAX_HISTORY_MESSAGES = 20


def run_turn(graph, messages: list, context: dict, user_input: str):
    """Run a single chat turn while preserving conversation state."""
    state = {
        "messages": [*messages, HumanMessage(content=user_input)],
        "next_node": "",
        "context": context,
    }
    result = graph.invoke(state)

    next_messages = state["messages"]
    if result.get("messages"):
        next_messages = [*state["messages"], result["messages"][-1]]
    next_messages = next_messages[-MAX_HISTORY_MESSAGES:]

    next_context = result.get("context", context)
    return result, next_messages, next_context


def run_chat():
    """Run the interactive chat loop."""
    print(WELCOME_BANNER)

    # Build the assistant graph
    print("⏳ Loading Lumina...")
    try:
        graph = build_assistant_graph()
        print("✅ Lumina is ready!\n")
    except Exception as e:
        print(f"❌ Failed to initialize Lumina: {e}")
        print("   Make sure LLM_PROVIDER and API keys are set in .env")
        return

    conversation_messages = []
    conversation_context = {}

    while True:
        try:
            user_input = input("👷 Engineer: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("\n👋 Goodbye!")
            break

        # Invoke the graph
        print()
        try:
            result, conversation_messages, conversation_context = run_turn(
                graph=graph,
                messages=conversation_messages,
                context=conversation_context,
                user_input=user_input,
            )

            # Extract the assistant's response
            if result["messages"]:
                last_msg = result["messages"][-1]
                print(f"🤖 Lumina: {last_msg.content}")
            else:
                print("🤖 Lumina: I couldn't process that request. Please try again.")

        except Exception as e:
            print(f"🤖 Lumina: ❌ Error processing your request: {e}")
            print("   This may be due to SafeLine API connectivity or LLM issues.")

        print()


if __name__ == "__main__":
    run_chat()
