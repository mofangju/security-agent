"""Interactive CLI chat for the AI security assistant."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from security_agent.assistant.graph import build_assistant_graph


WELCOME_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║            🛡️  SafeLine AI Security Assistant  🛡️            ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
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


def run_chat():
    """Run the interactive chat loop."""
    print(WELCOME_BANNER)

    # Build the assistant graph
    print("⏳ Loading AI assistant...")
    try:
        graph = build_assistant_graph()
        print("✅ Assistant ready!\n")
    except Exception as e:
        print(f"❌ Failed to initialize assistant: {e}")
        print("   Make sure LLM_PROVIDER and API keys are set in .env")
        return

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
            state = {
                "messages": [HumanMessage(content=user_input)],
                "next_node": "",
                "context": {},
            }
            result = graph.invoke(state)

            # Extract the assistant's response
            if result["messages"]:
                last_msg = result["messages"][-1]
                print(f"🤖 Assistant: {last_msg.content}")
            else:
                print("🤖 Assistant: I couldn't process that request. Please try again.")

        except Exception as e:
            print(f"🤖 Assistant: ❌ Error processing your request: {e}")
            print("   This may be due to SafeLine API connectivity or LLM issues.")

        print()


if __name__ == "__main__":
    run_chat()
