from typing import Any
from typing import TypedDict
from collections.abc import Callable

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from core.tool_registry import (
    execute_tool,
)


class ReproAgentState(
    TypedDict,
    total=False,
):
    """ReproAgent在LangGraph中的共享状态。"""

    pages: list[dict]
    source_filename: str
    supplement_analysis: dict

    extraction_result: dict
    selected_pages: list[int]

    audit_result: dict
    numeric_verification_result: dict
    verified_result: dict

    pdf_bytes: bytes
    pdf_filename: str

    document_type: str
    status: str
    execution_trace: list[dict]
    has_numeric_claims: bool
    run_numeric_verifier: bool
    numeric_route_reason: str

    audit_confidence: int
    reflection_count: int
    max_reflections: int

    agent_plan: dict
    planned_tools: list[str]
    execution_policy: dict
    audit_page_limit: int
    evidence_page_limit: int
    agent_execution: dict

    error: str


MANDATORY_SAFE_TOOLS = {
    "experiment_extractor",
    "reproducibility_auditor",
    "evidence_verifier",
    "pdf_report_generator",
}

EVIDENCE_LIMITS = {
    "focused": (20, 25),
    "standard": (30, 35),
    "deep": (50, 60),
}


def prepare_plan_controls(plan: dict | None) -> dict[str, Any]:
    """Convert a validated Planner result into bounded runtime controls."""

    if not isinstance(plan, dict):
        plan = {}

    raw_steps = plan.get("steps", [])
    if not isinstance(raw_steps, list):
        raw_steps = []

    planned_tools = []
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        tool_name = str(step.get("tool", "")).strip()
        if tool_name and tool_name not in planned_tools:
            planned_tools.append(tool_name)

    raw_policy = plan.get("execution_policy", {})
    if not isinstance(raw_policy, dict):
        raw_policy = {}

    numeric_policy = str(
        raw_policy.get("numeric_verification", "auto")
    ).strip().lower()
    if numeric_policy not in {"auto", "required", "skip"}:
        numeric_policy = "auto"

    evidence_depth = str(
        raw_policy.get("evidence_depth", "standard")
    ).strip().lower()
    if evidence_depth not in EVIDENCE_LIMITS:
        evidence_depth = "standard"

    try:
        max_reflections = int(
            raw_policy.get("max_reflections", 2)
        )
    except (TypeError, ValueError):
        max_reflections = 2
    max_reflections = max(0, min(max_reflections, 2))

    audit_limit, evidence_limit = EVIDENCE_LIMITS[evidence_depth]

    return {
        "agent_plan": plan,
        "planned_tools": planned_tools,
        "execution_policy": {
            "numeric_verification": numeric_policy,
            "evidence_depth": evidence_depth,
            "max_reflections": max_reflections,
        },
        "document_type": str(
            plan.get("document_type", "scientific_paper")
        ).strip() or "scientific_paper",
        "max_reflections": max_reflections,
        "audit_page_limit": audit_limit,
        "evidence_page_limit": evidence_limit,
    }


def create_tool_node(
    tool_name: str,
):
    """将现有注册工具包装成LangGraph节点。"""

    def tool_node(
        state: ReproAgentState,
    ) -> dict[str, Any]:
        trace = list(
            state.get(
                "execution_trace",
                [],
            )
        )

        trace.append(
            {
                "event": "tool_started",
                "tool": tool_name,
            }
        )

        try:
            output = execute_tool(
                tool_name=tool_name,
                state=dict(state),
            )

            trace.append(
                {
                    "event": "tool_completed",
                    "tool": tool_name,
                    "outputs": list(
                        output.keys()
                    ),
                }
            )

            return {
                **output,
                "execution_trace": trace,
            }

        except Exception as error:
            trace.append(
                {
                    "event": "tool_failed",
                    "tool": tool_name,
                    "error": str(error),
                }
            )

            raise

    return tool_node

def inspect_numeric_claims_node(
    state: ReproAgentState,
) -> dict:
    """判断论文是否存在可确定性核验的数值主张。"""

    audit_result = state.get(
        "audit_result",
        {},
    )

    numeric_claims = (
        audit_result.get(
            "numeric_claims",
            [],
        )
        or []
    )

    has_numeric_claims = bool(
        numeric_claims
    )

    policy = state.get("execution_policy", {})
    numeric_policy = str(
        policy.get("numeric_verification", "auto")
    )
    planned_tools = state.get("planned_tools", [])
    planner_selected = "numeric_verifier" in planned_tools

    if numeric_policy == "required":
        run_numeric_verifier = True
        route_reason = "Planner要求执行确定性数值核验"
    elif has_numeric_claims:
        run_numeric_verifier = True
        if numeric_policy == "skip" and not planner_selected:
            route_reason = (
                "运行时发现明确数值主张，安全路由覆盖Planner跳过决定"
            )
        elif planner_selected:
            route_reason = "Planner选择数值工具且运行时发现数值主张"
        else:
            route_reason = "自动路由发现可确定性核验的数值主张"
    else:
        run_numeric_verifier = False
        route_reason = "未发现具有完整操作数的数值主张，条件跳过"

    trace = list(
        state.get(
            "execution_trace",
            [],
        )
    )

    trace.append(
        {
            "event": (
                "numeric_check_required"
                if run_numeric_verifier
                else "numeric_check_skipped"
            ),
            "tool": "numeric_router",
            "claim_count": len(
                numeric_claims
            ),
            "planner_selected": planner_selected,
            "numeric_policy": numeric_policy,
            "reason": route_reason,
        }
    )

    return {
        "has_numeric_claims": (
            has_numeric_claims
        ),
        "run_numeric_verifier": run_numeric_verifier,
        "numeric_route_reason": route_reason,
        "execution_trace": trace,
    }


def route_numeric_check(
    state: ReproAgentState,
) -> str:
    """选择是否调用Python数值核验工具。"""

    if state.get("run_numeric_verifier", False):
        return "verify_numbers"

    return "verify_evidence"


def inspect_confidence_node(
    state: ReproAgentState,
) -> dict[str, Any]:
    """确定性评估本轮证据核验的充分程度。"""

    audit_result = state.get(
        "audit_result",
        {},
    )
    verified_result = state.get(
        "verified_result",
        {},
    )

    original_issues = []

    for key in (
        "missing_items",
        "contradictions",
        "evidence_issues",
    ):
        values = audit_result.get(key, [])

        if isinstance(values, list):
            original_issues.extend(values)

    verified_issues = verified_result.get(
        "verified_issues",
        [],
    )
    rejected_issues = verified_result.get(
        "rejected_issues",
        [],
    )

    if not isinstance(verified_issues, list):
        verified_issues = []

    if not isinstance(rejected_issues, list):
        rejected_issues = []

    original_count = len(original_issues)
    resolved_count = (
        len(verified_issues)
        + len(rejected_issues)
    )

    if original_count == 0:
        confidence = 100
    else:
        coverage = min(
            resolved_count / original_count,
            1.0,
        )
        quality_count = 0

        for issue in verified_issues:
            if not isinstance(issue, dict):
                continue

            has_reason = bool(
                issue.get("reason")
            )
            has_evidence = bool(
                issue.get("evidence")
                or issue.get("pages")
            )

            if has_reason and has_evidence:
                quality_count += 1

        for issue in rejected_issues:
            if (
                isinstance(issue, dict)
                and issue.get("reason")
            ):
                quality_count += 1

        resolution_quality = (
            quality_count / resolved_count
            if resolved_count
            else 0.0
        )

        confidence = round(
            coverage * 70
            + resolution_quality * 30
        )

    trace = list(
        state.get(
            "execution_trace",
            [],
        )
    )
    trace.append(
        {
            "event": "confidence_evaluated",
            "tool": "confidence_gate",
            "confidence": confidence,
            "reflection_count": state.get(
                "reflection_count",
                0,
            ),
        }
    )

    return {
        "audit_confidence": confidence,
        "execution_trace": trace,
    }


def route_after_confidence(
    state: ReproAgentState,
) -> str:
    """低置信度时重新核验，达到上限后生成报告。"""

    confidence = state.get(
        "audit_confidence",
        0,
    )
    reflection_count = state.get(
        "reflection_count",
        0,
    )
    max_reflections = state.get(
        "max_reflections",
        2,
    )

    if (
        confidence < 75
        and reflection_count < max_reflections
    ):
        return "expand_evidence"

    return "summarize_plan"


def expand_evidence_node(
    state: ReproAgentState,
) -> dict[str, Any]:
    """扩大证据范围并发起下一轮核验。"""

    reflection_count = (
        state.get(
            "reflection_count",
            0,
        )
        + 1
    )
    audit_result = dict(
        state.get(
            "audit_result",
            {},
        )
    )
    current_limit = state.get(
        "evidence_page_limit",
        audit_result.get("max_verification_pages", 35),
    )

    try:
        current_limit = int(current_limit)
    except (TypeError, ValueError):
        current_limit = 35

    new_limit = min(
        current_limit + 20,
        80,
    )
    audit_result[
        "max_verification_pages"
    ] = new_limit
    audit_result[
        "verification_instruction"
    ] = (
        "上一轮核验证据不足。请扩大原文范围，"
        "重新检查相关表格、公式、附录、参数定义和前后文，"
        "不得只依据摘要。"
    )

    trace = list(
        state.get(
            "execution_trace",
            [],
        )
    )
    trace.append(
        {
            "event": "reflection_triggered",
            "tool": "evidence_expander",
            "reflection_count": reflection_count,
            "previous_confidence": state.get(
                "audit_confidence",
                0,
            ),
            "page_limit": new_limit,
        }
    )

    return {
        "audit_result": audit_result,
        "evidence_page_limit": new_limit,
        "reflection_count": reflection_count,
        "execution_trace": trace,
    }


def build_plan_execution_summary(
    state: ReproAgentState,
    include_report: bool = False,
) -> dict[str, Any]:
    """Compare the Planner's steps with the tools actually executed."""

    plan = state.get("agent_plan", {})
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    if not isinstance(steps, list):
        steps = []

    trace = state.get("execution_trace", [])
    completed_tools = [
        item.get("tool")
        for item in trace
        if item.get("event") == "tool_completed"
        and item.get("tool")
    ]
    failed_tools = {
        item.get("tool")
        for item in trace
        if item.get("event") == "tool_failed"
    }
    numeric_skipped = any(
        item.get("event") == "numeric_check_skipped"
        for item in trace
    )

    rows = []
    aligned_count = 0
    planned_tool_names = []

    for step in steps:
        if not isinstance(step, dict):
            continue
        tool_name = str(step.get("tool", "")).strip()
        if not tool_name:
            continue
        planned_tool_names.append(tool_name)

        if tool_name in completed_tools:
            status = "completed"
        elif tool_name in failed_tools:
            status = "failed"
        elif tool_name == "numeric_verifier" and numeric_skipped:
            status = "conditionally_skipped"
        elif tool_name == "pdf_report_generator" and not include_report:
            status = "scheduled"
        else:
            status = "not_run"

        if status in {
            "completed",
            "conditionally_skipped",
            "scheduled",
        }:
            aligned_count += 1

        rows.append({
            "id": step.get("id", ""),
            "tool": tool_name,
            "reason": step.get("reason", ""),
            "status": status,
        })

    planned_count = len(rows)
    consistency_rate = (
        round(aligned_count * 100 / planned_count)
        if planned_count
        else 100
    )
    safety_added_tools = [
        tool_name
        for tool_name in completed_tools
        if tool_name not in planned_tool_names
        and tool_name in MANDATORY_SAFE_TOOLS
    ]

    return {
        "planner_source": plan.get("planner_source", "unknown")
        if isinstance(plan, dict)
        else "unknown",
        "document_type": state.get("document_type", "scientific_paper"),
        "execution_policy": state.get("execution_policy", {}),
        "planned_step_count": planned_count,
        "aligned_step_count": aligned_count,
        "consistency_rate": consistency_rate,
        "numeric_route_reason": state.get("numeric_route_reason", ""),
        "safety_added_tools": safety_added_tools,
        "steps": rows,
    }


def summarize_plan_execution_node(
    state: ReproAgentState,
) -> dict[str, Any]:
    """Make the Planner-to-runtime relationship visible before reporting."""

    summary = build_plan_execution_summary(state)
    verified_result = dict(state.get("verified_result", {}))
    verified_result["agent_execution"] = summary

    trace = list(state.get("execution_trace", []))
    trace.append({
        "event": "plan_execution_summarized",
        "tool": "plan_runtime_guard",
        "consistency_rate": summary["consistency_rate"],
        "planned_step_count": summary["planned_step_count"],
    })

    return {
        "agent_execution": summary,
        "verified_result": verified_result,
        "execution_trace": trace,
    }


def finalize_node(
    state: ReproAgentState,
) -> dict:
    """标记整个智能体流程完成。"""

    trace = list(
        state.get(
            "execution_trace",
            [],
        )
    )

    trace.append(
        {
            "event": "graph_completed",
            "tool": "langgraph",
        }
    )

    final_execution = build_plan_execution_summary(
        {
            **state,
            "execution_trace": trace,
        },
        include_report=True,
    )

    return {
        "status": "completed",
        "agent_execution": final_execution,
        "execution_trace": trace,
    }


def build_graph():
    """构建科研可复现性审计状态图。"""

    builder = StateGraph(
        ReproAgentState
    )

    builder.add_node(
        "extract_experiment",
        create_tool_node(
            "experiment_extractor"
        ),
    )

    builder.add_node(
        "audit_reproducibility",
        create_tool_node(
            "reproducibility_auditor"
        ),
    )
    builder.add_node(
        "inspect_numeric_claims",
        inspect_numeric_claims_node,
    )
    builder.add_node(
        "verify_numbers",
        create_tool_node(
            "numeric_verifier"
        ),
    )

    builder.add_node(
        "verify_evidence",
        create_tool_node(
            "evidence_verifier"
        ),
    )

    builder.add_node(
        "inspect_confidence",
        inspect_confidence_node,
    )

    builder.add_node(
        "expand_evidence",
        expand_evidence_node,
    )

    builder.add_node(
        "summarize_plan",
        summarize_plan_execution_node,
    )

    builder.add_node(
        "generate_report",
        create_tool_node(
            "pdf_report_generator"
        ),
    )

    builder.add_node(
        "finalize",
        finalize_node,
    )

    builder.add_edge(
        START,
        "extract_experiment",
    )

    builder.add_edge(
        "extract_experiment",
        "audit_reproducibility",
    )

    builder.add_edge(
        "audit_reproducibility",
        "inspect_numeric_claims",
    )

    builder.add_conditional_edges(
        "inspect_numeric_claims",
        route_numeric_check,
        {
            "verify_numbers": (
                "verify_numbers"
            ),
            "verify_evidence": (
                "verify_evidence"
            ),
        },
    )
    builder.add_edge(
        "verify_numbers",
        "verify_evidence",
    )

    builder.add_edge(
        "verify_evidence",
        "inspect_confidence",
    )

    builder.add_conditional_edges(
        "inspect_confidence",
        route_after_confidence,
        {
            "expand_evidence": (
                "expand_evidence"
            ),
            "summarize_plan": (
                "summarize_plan"
            ),
        },
    )

    builder.add_edge(
        "expand_evidence",
        "verify_evidence",
    )

    builder.add_edge(
        "summarize_plan",
        "generate_report",
    )

    builder.add_edge(
        "generate_report",
        "finalize",
    )

    builder.add_edge(
        "finalize",
        END,
    )

    return builder.compile()


graph = build_graph()


def run_langgraph_audit(
    pages: list[dict],
    source_filename: str,
    plan: dict | None = None,
    supplement_analysis: dict | None = None,
    progress_callback: Callable[
        [dict[str, Any]],
        None,
    ] | None = None,
) -> ReproAgentState:
    """流式运行LangGraph科研审计流程。"""

    plan_controls = prepare_plan_controls(plan)

    initial_state: ReproAgentState = {
        "pages": pages,
        "source_filename": source_filename,
        "supplement_analysis": (
            supplement_analysis
            or {}
        ),
        **plan_controls,
        "status": "running",
        "execution_trace": [],
        "audit_confidence": 0,
        "reflection_count": 0,
    }

    final_state: ReproAgentState = dict(
        initial_state
    )

    def notify(event: dict[str, Any]) -> None:
        if progress_callback is None:
            return

        try:
            progress_callback(event)
        except Exception:
            # 页面刷新失败不应中断审计主流程。
            pass

    notify(
        {
            "event": "graph_started",
            "node": "START",
        }
    )

    for graph_update in graph.stream(
        initial_state,
        config={
            "recursion_limit": 30,
        },
        stream_mode="updates",
    ):
        if not isinstance(graph_update, dict):
            continue

        for node_name, node_update in graph_update.items():
            if isinstance(node_update, dict):
                final_state.update(node_update)
                output_keys = list(
                    node_update.keys()
                )
            else:
                output_keys = []

            notify(
                {
                    "event": "node_completed",
                    "node": node_name,
                    "outputs": output_keys,
                    "audit_confidence": final_state.get(
                        "audit_confidence",
                        0,
                    ),
                    "reflection_count": final_state.get(
                        "reflection_count",
                        0,
                    ),
                }
            )

    notify(
        {
            "event": "graph_finished",
            "node": "END",
        }
    )

    return final_state
