#!/usr/bin/env python3
"""Run the Lumina AI assistant evaluation suite.

Usage:
    python scripts/run_eval.py
"""

from security_agent.eval.evaluator import Evaluator


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run Lumina evaluation suite")
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Run deterministic offline evaluation without live model/tool calls",
    )
    args = parser.parse_args()

    print("🧪 Lumina AI Assistant Evaluation")
    print("=" * 50)
    print()

    graph = None
    if not args.deterministic:
        from security_agent.assistant.graph import build_assistant_graph

        # Build the assistant graph
        print("⏳ Building assistant graph...")
        graph = build_assistant_graph()
        print("✅ Graph ready\n")
    else:
        print("⚙️ Deterministic mode enabled (offline)")
        print()

    # Run evaluation
    evaluator = Evaluator()
    print(f"📝 Running {len(evaluator.test_cases)} test cases...\n")
    results = evaluator.run_evaluation(graph=graph, deterministic=args.deterministic)

    # Save results
    import json
    output = [
        {
            "test_id": r.test_id,
            "query": r.query,
            "expected_route": r.expected_route,
            "actual_route": r.actual_route,
            "route_correct": r.route_correct,
            "keyword_score": r.keyword_score,
            "keywords_found": r.keywords_found,
            "keywords_missing": r.keywords_missing,
        }
        for r in results
    ]

    with open("data/eval/results.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\n📁 Results saved to data/eval/results.json")


if __name__ == "__main__":
    main()
