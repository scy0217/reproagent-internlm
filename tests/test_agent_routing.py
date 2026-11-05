import unittest

from core.langgraph_runner import (
    inspect_confidence_node,
    inspect_numeric_claims_node,
    route_after_confidence,
    route_numeric_check,
)


class AgentRoutingTests(unittest.TestCase):
    def test_numeric_branch_is_selected(self):
        state = inspect_numeric_claims_node({
            "audit_result": {"numeric_claims": [{"claim": "x"}]},
            "execution_trace": [],
        })
        self.assertTrue(state["has_numeric_claims"])
        self.assertEqual(route_numeric_check(state), "verify_numbers")

    def test_numeric_branch_is_skipped_without_claims(self):
        state = inspect_numeric_claims_node({
            "audit_result": {"numeric_claims": []},
            "execution_trace": [],
        })
        self.assertFalse(state["has_numeric_claims"])
        self.assertEqual(route_numeric_check(state), "verify_evidence")

    def test_low_confidence_triggers_reflection(self):
        route = route_after_confidence({
            "audit_confidence": 50,
            "reflection_count": 0,
            "max_reflections": 2,
        })
        self.assertEqual(route, "expand_evidence")

    def test_reflection_limit_terminates_loop(self):
        route = route_after_confidence({
            "audit_confidence": 50,
            "reflection_count": 2,
            "max_reflections": 2,
        })
        self.assertEqual(route, "generate_report")

    def test_confidence_is_deterministic(self):
        result = inspect_confidence_node({
            "audit_result": {
                "missing_items": [{"title": "缺失"}],
                "contradictions": [],
                "evidence_issues": [],
            },
            "verified_result": {
                "verified_issues": [{
                    "reason": "原文未披露",
                    "evidence": ["第3页未给出版本"],
                }],
                "rejected_issues": [],
            },
            "execution_trace": [],
        })
        self.assertEqual(result["audit_confidence"], 100)


if __name__ == "__main__":
    unittest.main()
