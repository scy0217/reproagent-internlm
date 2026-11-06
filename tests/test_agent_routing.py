import unittest

from core.langgraph_runner import (
    build_plan_execution_summary,
    inspect_confidence_node,
    inspect_numeric_claims_node,
    prepare_plan_controls,
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

    def test_planner_can_require_numeric_tool_without_claims(self):
        state = inspect_numeric_claims_node({
            "audit_result": {"numeric_claims": []},
            "execution_policy": {
                "numeric_verification": "required",
            },
            "planned_tools": ["numeric_verifier"],
            "execution_trace": [],
        })
        self.assertTrue(state["run_numeric_verifier"])
        self.assertEqual(route_numeric_check(state), "verify_numbers")

    def test_runtime_claims_override_unsafe_planner_skip(self):
        state = inspect_numeric_claims_node({
            "audit_result": {"numeric_claims": [{"claim": "x"}]},
            "execution_policy": {
                "numeric_verification": "skip",
            },
            "planned_tools": [],
            "execution_trace": [],
        })
        self.assertTrue(state["run_numeric_verifier"])
        self.assertIn("安全路由覆盖", state["numeric_route_reason"])

    def test_plan_controls_change_evidence_depth_and_reflections(self):
        controls = prepare_plan_controls({
            "document_type": "experimental_paper",
            "steps": [{"tool": "experiment_extractor"}],
            "execution_policy": {
                "numeric_verification": "auto",
                "evidence_depth": "deep",
                "max_reflections": 1,
            },
        })
        self.assertEqual(controls["audit_page_limit"], 50)
        self.assertEqual(controls["evidence_page_limit"], 60)
        self.assertEqual(controls["max_reflections"], 1)

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
        self.assertEqual(route, "summarize_plan")

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

    def test_plan_execution_summary_matches_trace(self):
        summary = build_plan_execution_summary({
            "agent_plan": {
                "planner_source": "intern-s2",
                "steps": [
                    {"id": "S1", "tool": "experiment_extractor"},
                    {"id": "S2", "tool": "numeric_verifier"},
                    {"id": "S3", "tool": "pdf_report_generator"},
                ],
            },
            "execution_trace": [
                {"event": "tool_completed", "tool": "experiment_extractor"},
                {"event": "numeric_check_skipped", "tool": "numeric_router"},
            ],
        })
        self.assertEqual(summary["consistency_rate"], 100)
        self.assertEqual(
            summary["steps"][1]["status"],
            "conditionally_skipped",
        )


if __name__ == "__main__":
    unittest.main()
