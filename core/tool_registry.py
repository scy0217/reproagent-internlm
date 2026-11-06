from dataclasses import dataclass
from typing import Callable
from core.numeric_verifier import (
    verify_numeric_claims,
)
from core.auditor import audit_reproducibility
from core.extractor import extract_research_info
from core.report_generator import generate_pdf_report
from core.verifier import verify_audit
from core.supplement_analyzer import merge_supplement_analysis


@dataclass(frozen=True)
class ToolDefinition:
    """智能体工具定义。"""

    name: str
    description: str
    input_keys: tuple[str, ...]
    output_keys: tuple[str, ...]
    handler: Callable[[dict], dict]


def require_state(
    state: dict,
    key: str,
):
    """检查工具需要的状态是否存在。"""

    if key not in state:
        raise ValueError(
            f"工具缺少必要输入：{key}"
        )

    value = state[key]

    if value is None:
        raise ValueError(
            f"工具输入为空：{key}"
        )

    return value


def run_experiment_extractor(
    state: dict,
) -> dict:
    """运行实验要素提取工具。"""

    pages = require_state(
        state,
        "pages",
    )

    result, selected_pages = (
        extract_research_info(pages)
    )
    result = merge_supplement_analysis(
        result,
        state.get("supplement_analysis"),
    )

    return {
        "extraction_result": result,
        "selected_pages": selected_pages,
    }


def run_reproducibility_auditor(
    state: dict,
) -> dict:
    """运行可复现性初审工具。"""

    pages = require_state(
        state,
        "pages",
    )

    extraction_result = require_state(
        state,
        "extraction_result",
    )

    audit_result = audit_reproducibility(
        pages=pages,
        extraction_result=extraction_result,
        max_pages=state.get(
            "audit_page_limit",
            30,
        ),
    )

    return {
        "audit_result": audit_result,
    }

def run_numeric_verifier(
    state: dict,
) -> dict:
    """使用Python核验审计结果中的数值主张。"""

    audit_result = require_state(
        state,
        "audit_result",
    )

    numeric_claims = audit_result.get(
        "numeric_claims",
        [],
    )

    if not isinstance(
        numeric_claims,
        list,
    ):
        numeric_claims = []

    numeric_result = verify_numeric_claims(
        numeric_claims
    )

    return {
        "numeric_verification_result": (
            numeric_result
        ),
    }

def run_evidence_verifier(
    state: dict,
) -> dict:
    """运行证据验证与误报过滤工具。"""

    pages = require_state(
        state,
        "pages",
    )

    extraction_result = require_state(
        state,
        "extraction_result",
    )

    audit_result = require_state(
        state,
        "audit_result",
    )

    audit_for_verification = dict(
        audit_result
    )

    numeric_result = state.get(
        "numeric_verification_result"
    )

    if numeric_result is not None:
        audit_for_verification[
            "numeric_tool_results"
        ] = numeric_result
        audit_for_verification[
            "numeric_verification_result"
        ] = numeric_result

    audit_for_verification["document_type"] = state.get(
        "document_type",
        "",
    )

    verified_result = verify_audit(
        pages=pages,
        extraction_result=extraction_result,
        audit_result=audit_for_verification,
        max_pages=state.get(
            "evidence_page_limit",
            35,
        ),
    )

    if numeric_result is not None:
        verified_result[
            "numeric_verification_result"
        ] = numeric_result

    return {
        "verified_result": verified_result,
    }


def run_pdf_report_generator(
    state: dict,
) -> dict:
    """运行PDF报告生成工具。"""

    extraction_result = require_state(
        state,
        "extraction_result",
    )

    verified_result = require_state(
        state,
        "verified_result",
    )

    source_filename = state.get(
        "source_filename",
        "论文.pdf",
    )

    report_result = dict(verified_result)
    if state.get("agent_execution"):
        report_result["agent_execution"] = state[
            "agent_execution"
        ]

    pdf_bytes = generate_pdf_report(
        extraction_result=extraction_result,
        verified_result=report_result,
        source_filename=source_filename,
    )

    return {
        "pdf_bytes": pdf_bytes,
        "pdf_filename": (
            f"{source_filename.rsplit('.', 1)[0]}"
            "_可复现性审计报告.pdf"
        ),
    }


TOOL_REGISTRY = {
    "experiment_extractor": ToolDefinition(
        name="experiment_extractor",
        description=(
            "提取论文研究目标、数据、方法、"
            "参数、指标和原文证据"
        ),
        input_keys=("pages",),
        output_keys=(
            "extraction_result",
            "selected_pages",
        ),
        handler=run_experiment_extractor,
    ),
    "reproducibility_auditor": ToolDefinition(
        name="reproducibility_auditor",
        description=(
            "检查论文信息缺失、数值矛盾"
            "和可复现性风险"
        ),
        input_keys=(
            "pages",
            "extraction_result",
        ),
        output_keys=("audit_result",),
        handler=run_reproducibility_auditor,
    ),
        "numeric_verifier": ToolDefinition(
        name="numeric_verifier",
        description=(
            "使用Python确定性计算核验论文中的"
            "百分比、差值、变化率和比例主张"
        ),
        input_keys=(
            "audit_result",
        ),
        output_keys=(
            "numeric_verification_result",
        ),
        handler=run_numeric_verifier,
    ),
    "evidence_verifier": ToolDefinition(
        name="evidence_verifier",
        description=(
            "回查原文证据、过滤误报、"
            "合并重复问题并计算最终评分"
        ),
        input_keys=(
            "pages",
            "extraction_result",
            "audit_result",
        ),
        output_keys=("verified_result",),
        handler=run_evidence_verifier,
    ),
    "pdf_report_generator": ToolDefinition(
        name="pdf_report_generator",
        description=(
            "根据提取结果和复核结果"
            "生成正式PDF审计报告"
        ),
        input_keys=(
            "extraction_result",
            "verified_result",
        ),
        output_keys=(
            "pdf_bytes",
            "pdf_filename",
        ),
        handler=run_pdf_report_generator,
    ),
}


def list_tools() -> list[dict]:
    """返回Planner可读取的工具说明。"""

    tools = []

    for tool in TOOL_REGISTRY.values():
        tools.append(
            {
                "name": tool.name,
                "description": tool.description,
                "input_keys": list(tool.input_keys),
                "output_keys": list(tool.output_keys),
            }
        )

    return tools


def get_tool(
    tool_name: str,
) -> ToolDefinition:
    """根据名称获取工具。"""

    if tool_name not in TOOL_REGISTRY:
        available = "、".join(
            TOOL_REGISTRY.keys()
        )

        raise ValueError(
            f"未注册工具：{tool_name}。"
            f"可用工具：{available}"
        )

    return TOOL_REGISTRY[tool_name]


def execute_tool(
    tool_name: str,
    state: dict,
) -> dict:
    """执行指定工具并返回状态更新。"""

    tool = get_tool(tool_name)

    for key in tool.input_keys:
        require_state(state, key)

    output = tool.handler(state)

    if not isinstance(output, dict):
        raise TypeError(
            f"工具 {tool_name} "
            "没有返回字典。"
        )

    missing_outputs = [
        key
        for key in tool.output_keys
        if key not in output
    ]

    if missing_outputs:
        raise ValueError(
            f"工具 {tool_name} "
            f"缺少输出：{missing_outputs}"
        )

    return output
