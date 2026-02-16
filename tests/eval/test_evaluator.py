from __future__ import annotations

from security_agent.eval.evaluator import Evaluator


def test_evaluator_deterministic_mode_without_graph():
    evaluator = Evaluator()
    results = evaluator.run_evaluation(graph=None, deterministic=True)

    assert len(results) == len(evaluator.test_cases)
    assert all(r.route_correct for r in results)
