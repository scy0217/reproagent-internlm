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

    audit_confidence: int
    reflection_count: int
    max_reflections: int

    error: str


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
                if has_numeric_claims
                else "numeric_check_skipped"
            ),
            "tool": "numeric_router",
            "claim_count": len(
                numeric_claims
            ),
        }
    )

    return {
        "has_numeric_claims": (
            has_numeric_claims
        ),
        "execution_trace": trace,
    }


def route_numeric_check(
    state: ReproAgentState,
) -> str:
    """选择是否调用Python数值核验工具。"""

    if state.get(
        "has_numeric_claims",
        False,
    ):
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

    return "generate_report"


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
    current_limit = audit_result.get(
        "max_verification_pages",
        35,
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
        "reflection_count": reflection_count,
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

    return {
        "status": "completed",
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
            "generate_report": (
                "generate_report"
            ),
        },
    )

    builder.add_edge(
        "expand_evidence",
        "verify_evidence",
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
    supplement_analysis: dict | None = None,
    progress_callback: Callable[
        [dict[str, Any]],
        None,
    ] | None = None,
) -> ReproAgentState:
    """流式运行LangGraph科研审计流程。"""

    initial_state: ReproAgentState = {
        "pages": pages,
        "source_filename": source_filename,
        "supplement_analysis": (
            supplement_analysis
            or {}
        ),
        "document_type": "scientific_paper",
        "status": "running",
        "execution_trace": [],
        "audit_confidence": 0,
        "reflection_count": 0,
        "max_reflections": 2,
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
