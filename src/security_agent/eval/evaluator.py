"""Evaluation framework for the Security agent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestCase:
    """A single evaluation test case."""

    id: str
    query: str
    expected_route: str  # Which specialist should handle this
    expected_keywords: list[str] = field(default_factory=list)  # Keywords expected in response
    category: str = ""  # e.g., "monitoring", "incident_response"


@dataclass
class EvalResult:
    """Result of evaluating a single test case."""

    test_id: str
    query: str
    expected_route: str
    actual_route: str
    response: str
    route_correct: bool
    keywords_found: list[str] = field(default_factory=list)
    keywords_missing: list[str] = field(default_factory=list)
    keyword_score: float = 0.0


class Evaluator:
    """Evaluate Security agent response quality and routing accuracy."""

    def __init__(self, test_cases_path: str = "data/eval/test_cases.json"):
        self.test_cases = self._load_test_cases(test_cases_path)

    def _load_test_cases(self, path: str) -> list[TestCase]:
        """Load test cases from JSON file."""
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(
                f"Test cases file not found: {filepath}. "
                "Please ensure data/eval/test_cases.json exists."
            )

        with open(filepath) as f:
            data = json.load(f)

        return [TestCase(**tc) for tc in data]

    def evaluate_routing(self, test_case: TestCase, actual_route: str) -> bool:
        """Check if the supervisor routed to the correct specialist."""
        return test_case.expected_route == actual_route

    def evaluate_keywords(self, test_case: TestCase, response: str) -> tuple[float, list, list]:
        """Check if expected keywords are present in the response."""
        response_lower = response.lower()
        found = [kw for kw in test_case.expected_keywords if kw.lower() in response_lower]
        missing = [kw for kw in test_case.expected_keywords if kw.lower() not in response_lower]

        if test_case.expected_keywords:
            score = len(found) / len(test_case.expected_keywords)
        else:
            score = 1.0

        return score, found, missing

    def run_evaluation(self, graph=None, deterministic: bool = False) -> list[EvalResult]:
        """Run all test cases against the assistant graph.

        Args:
            graph: Compiled assistant graph for live evaluation.
            deterministic: If True, run without graph/LLM/tool calls.
        """
        from langchain_core.messages import HumanMessage

        results = []

        for tc in self.test_cases:
            print(f"  📝 {tc.id}: {tc.query[:50]}...")

            if deterministic:
                response = " ".join(tc.expected_keywords) if tc.expected_keywords else "ok"
                route_correct = True
                kw_score, found, missing = self.evaluate_keywords(tc, response)
                results.append(EvalResult(
                    test_id=tc.id,
                    query=tc.query,
                    expected_route=tc.expected_route,
                    actual_route=tc.expected_route,
                    response=response[:200],
                    route_correct=route_correct,
                    keywords_found=found,
                    keywords_missing=missing,
                    keyword_score=kw_score,
                ))
                print(f"    ✅ Route: {tc.expected_route} (deterministic)")
                print(f"    📊 Keyword score: {kw_score:.0%}")
                continue

            if graph is None:
                raise ValueError("graph is required when deterministic=False")

            state = {
                "messages": [HumanMessage(content=tc.query)],
                "next_node": "",
                "context": {},
            }

            try:
                result = graph.invoke(state)
                actual_route = result.get("next_node", "unknown")
                response = result["messages"][-1].content if result["messages"] else ""

                route_correct = self.evaluate_routing(tc, actual_route)
                kw_score, found, missing = self.evaluate_keywords(tc, response)

                eval_result = EvalResult(
                    test_id=tc.id,
                    query=tc.query,
                    expected_route=tc.expected_route,
                    actual_route=actual_route,
                    response=response[:200],
                    route_correct=route_correct,
                    keywords_found=found,
                    keywords_missing=missing,
                    keyword_score=kw_score,
                )
                results.append(eval_result)

                status = "✅" if route_correct else "❌"
                print(f"    {status} Route: {actual_route} (expected: {tc.expected_route})")
                print(f"    📊 Keyword score: {kw_score:.0%}")

            except Exception as e:
                print(f"    ❌ Error: {e}")
                results.append(EvalResult(
                    test_id=tc.id,
                    query=tc.query,
                    expected_route=tc.expected_route,
                    actual_route="error",
                    response=str(e),
                    route_correct=False,
                ))

        # Summary
        correct = sum(1 for r in results if r.route_correct)
        avg_kw = sum(r.keyword_score for r in results) / len(results) if results else 0

        print(f"\n{'═' * 50}")
        print("  Evaluation Summary")
        print(f"{'─' * 50}")
        print(f"  Routing accuracy:  {correct}/{len(results)} ({correct/len(results):.0%})")
        print(f"  Avg keyword score: {avg_kw:.0%}")
        print(f"{'═' * 50}")

        return results
