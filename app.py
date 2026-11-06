from pathlib import Path
from html import escape as html_escape
import hmac
import inspect
import os
import time

import streamlit as st

from core.auditor import audit_reproducibility
from core.extractor import extract_research_info
from core.pdf_parser import extract_pdf
from core.report_generator import generate_pdf_report
from core.verifier import verify_audit
from core.numeric_verifier import verify_numeric_claims
from core.langgraph_runner import run_langgraph_audit
from core.planner import create_audit_plan
from core.supplement_analyzer import (
    analyze_supplements,
    merge_supplement_analysis,
)
from core.text_normalizer import (
    normalize_scientific_text,
    normalize_structure,
    quarantine_broken_symbol_issues,
)
from core.scoring_profiles import apply_scoring

st.set_page_config(page_title="ReproAgent", page_icon="🔬", layout="wide")


def get_app_setting(name: str, default: str = "") -> str:
    """Read local environment variables or Streamlit Cloud secrets."""

    value = os.getenv(name)
    if value:
        return value.strip()
    try:
        value = st.secrets.get(name, default)
    except (FileNotFoundError, KeyError, RuntimeError):
        value = default
    return str(value).strip()


DEMO_ACCESS_CODE = get_app_setting("DEMO_ACCESS_CODE")
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_SUPPLEMENT_BYTES = 20 * 1024 * 1024
APP_VERSION = "1.1.1"

st.markdown(
    """
    <style>
    .block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem;}
    [data-testid="stMetric"] {background:#f8fafc; border:1px solid #e2e8f0;
        border-radius:14px; padding:14px 16px;}
    .hero {padding:1.5rem 1.7rem; border:1px solid #dbe7ff; border-radius:18px;
        background:linear-gradient(135deg,#f8fbff,#edf4ff); margin-bottom:1.2rem;}
    .hero h1 {margin:0; color:#172554; font-size:2.1rem;}
    .hero p {margin:.6rem 0 0; color:#475569;}
    .section-title {margin:1.8rem 0 .7rem; font-size:1.35rem; font-weight:700; color:#172033;}
    .paper-title {padding:1rem 1.2rem; border-left:5px solid #2563eb;
        border-radius:10px; background:#f8fafc; margin-bottom:1rem;}
    .paper-title small {color:#64748b;}
    .paper-title h3 {margin:.25rem 0 0; color:#1e293b;}
    .list-card {padding:.75rem .9rem; margin:.5rem 0; border:1px solid #e2e8f0;
        border-radius:10px; background:#fff;}
    .agent-flow {display:flex; flex-wrap:wrap; align-items:center; gap:.45rem;
        padding:1rem; border:1px solid #dbeafe; border-radius:14px;
        background:#f8fbff; margin:.5rem 0 1rem;}
    .agent-node {padding:.55rem .75rem; border-radius:10px; color:#1e3a8a;
        background:#fff; border:1px solid #bfdbfe; font-weight:600;}
    .agent-node.decision {color:#854d0e; background:#fffbeb; border-color:#fde68a;}
    .agent-node.reflection {color:#7e22ce; background:#faf5ff; border-color:#e9d5ff;}
    .agent-arrow {color:#64748b; font-weight:700;}
    </style>
    """,
    unsafe_allow_html=True,
)

if DEMO_ACCESS_CODE and not st.session_state.get(
    "demo_authenticated",
    False,
):
    st.title("🔬 ReproAgent 体验验证")
    st.caption("请输入技术文档中提供的应用体验码。")
    entered_code = st.text_input(
        "体验码",
        type="password",
        key="demo_access_code_input",
    )

    if st.button(
        "进入应用",
        type="primary",
        use_container_width=True,
    ):
        if hmac.compare_digest(
            entered_code,
            DEMO_ACCESS_CODE,
        ):
            st.session_state[
                "demo_authenticated"
            ] = True
            st.rerun()
        else:
            st.error("体验码不正确。")

    st.stop()


with st.sidebar:
    st.markdown("### 运行状态")
    st.success("服务正常")
    st.caption(f"ReproAgent v{APP_VERSION}")
    st.markdown("**模型底座**")
    st.code(get_app_setting("INTERNLM_MODEL", "intern-s2"), language=None)
    st.markdown("**智能体 Harness**")
    st.code("LangGraph", language=None)
    st.markdown("**安全策略**")
    st.caption("不执行上传代码 · 输入规模限制 · 原文按不可信数据处理")


def format_pages(pages: list) -> str:
    values = [str(page) for page in pages if page not in (None, 0, "")]
    return "、".join(values) if values else "未标注"


def render_list(items: list, empty_text: str = "暂未提取到相关信息。") -> None:
    if not items:
        st.caption(empty_text)
        return
    for index, item in enumerate(items, start=1):
        if isinstance(item, dict):
            text = item.get("name") or item.get("title") or str(item)
        else:
            text = str(item)
        text = html_escape(normalize_scientific_text(text))
        st.markdown(
            f'<div class="list-card"><b>{index:02d}</b>&nbsp;&nbsp;{text}</div>',
            unsafe_allow_html=True,
        )


def render_extraction(result: dict, selected_pages: list[int]) -> None:
    result = normalize_structure(result)
    methods = result.get("methods", [])
    parameters = result.get("key_parameters", [])
    evidence = result.get("evidence", [])
    title = html_escape(result.get("title") or "未识别论文标题")

    st.markdown(
        f'<div class="paper-title"><small>论文识别结果</small><h3>{title}</h3></div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(4)
    columns[0].metric("重点分析页", len(selected_pages))
    columns[1].metric("研究方法", len(methods))
    columns[2].metric("关键参数", len(parameters))
    columns[3].metric("证据条目", len(evidence))
    st.caption("重点分析页码：" + format_pages(selected_pages))

    overview_tab, method_tab, parameter_tab, result_tab = st.tabs(
        ["研究概览", "数据与方法", "参数与环境", "结果与证据"]
    )

    with overview_tab:
        left, right = st.columns(2)
        with left:
            st.markdown("#### 研究目标")
            st.info(result.get("research_goal") or "暂未提取到研究目标。")
        with right:
            st.markdown("#### 研究对象")
            st.info(result.get("research_object") or "暂未提取到研究对象。")
        st.markdown("#### 评价指标")
        render_list(result.get("evaluation_metrics", []))

    with method_tab:
        left, right = st.columns(2)
        with left:
            st.markdown("#### 材料或数据集")
            render_list(result.get("materials_or_datasets", []))
        with right:
            st.markdown("#### 模型或算法")
            render_list(result.get("models_or_algorithms", []))
        st.markdown("#### 研究方法")
        render_list(methods)

    with parameter_tab:
        st.markdown("#### 关键参数")
        if parameters:
            rows = [
                {
                    "参数": item.get("name", ""),
                    "取值": item.get("value", ""),
                    "页码": item.get("page", ""),
                    "原文证据": item.get("evidence", ""),
                }
                for item in parameters
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.caption("暂未提取到关键参数。")

        left, right = st.columns(2)
        with left:
            st.markdown("#### 软件环境")
            render_list(result.get("software_environment", []))
        with right:
            st.markdown("#### 硬件环境")
            render_list(result.get("hardware_environment", []))

        code_info = result.get("code_availability", {}) or {}
        if code_info.get("status") in ("available", "yes", True):
            st.success("论文提供了代码获取信息。")
        else:
            st.warning(
                "暂未确认完整代码的公开或获取方式；该项影响资源开放性，"
                "不自动降低科学可复现性。"
            )

    with result_tab:
        st.markdown("#### 主要研究结果")
        render_list(result.get("main_results", []))
        st.markdown("#### 原文证据")
        if not evidence:
            st.caption("暂未提取到证据。")
        for index, item in enumerate(evidence, start=1):
            field = item.get("field") or f"证据 {index}"
            page = item.get("page", "未标注")
            quote = item.get("quote") or item.get("evidence") or "未提供原文"
            with st.expander(f"{field} · 第 {page} 页"):
                st.write(quote)

    with st.expander("开发调试：查看结构化原始数据"):
        st.json(result)


def render_issue(issue: dict, index: int, prefix: str = "问题") -> None:
    issue = normalize_structure(issue)
    severity = issue.get("severity", "low")
    title = (
        issue.get("title")
        or issue.get("description")
        or issue.get("item")
        or issue.get("claim")
        or f"{prefix} {index}"
    )
    label = {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(
        severity, "低风险"
    )
    header = f"{prefix} {index}｜{label}｜{title}"
    if severity == "high":
        st.error(header)
    elif severity == "medium":
        st.warning(header)
    else:
        st.info(header)

    pages = issue.get("pages", []) or ([issue.get("page")] if issue.get("page") else [])
    st.caption("证据页码：" + format_pages(pages))
    scope_names = {
        "scientific_reproducibility": "科学可复现性",
        "resource_openness": "资源开放性",
        "both": "科学可复现性与资源开放性",
    }
    if issue.get("impact_scope"):
        st.caption(
            "影响范围："
            + scope_names.get(
                issue.get("impact_scope"),
                str(issue.get("impact_scope")),
            )
        )
    if issue.get("reason"):
        st.markdown(f"**判断依据：** {issue['reason']}")
    if issue.get("calculation"):
        st.markdown(f"**核算过程：** {issue['calculation']}")

    evidence = issue.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if evidence:
        with st.expander("查看原文证据"):
            for item in evidence:
                st.markdown(f"- {item}")
    if issue.get("suggestion"):
        st.markdown(f"**改进建议：** {issue['suggestion']}")


def render_audit(result: dict) -> None:
    result = normalize_structure(result)
    score = int(result.get("reproducibility_score", 0))
    missing = result.get("missing_items", [])
    contradictions = result.get("contradictions", [])
    evidence_issues = result.get("evidence_issues", [])
    strengths = result.get("strengths", [])

    columns = st.columns(4)
    columns[0].metric("初审状态", "待复核")
    columns[1].metric("信息缺失", len(missing))
    columns[2].metric("潜在矛盾", len(contradictions))
    columns[3].metric("证据疑点", len(evidence_issues))
    
    st.caption("初审可能包含误报，最终结果以审计复核为准。")
    if result.get("summary"):
        st.info(result["summary"])

    tabs = st.tabs(["信息缺失", "潜在矛盾", "证据疑点", "研究优点"])
    groups = [missing, contradictions, evidence_issues]
    labels = ["缺失项", "矛盾", "疑点"]
    empty_messages = [
        "未发现明显的信息缺失。",
        "未发现明显的数值或表述矛盾。",
        "未发现明显的证据问题。",
    ]
    for tab, group, label, empty in zip(tabs[:3], groups, labels, empty_messages):
        with tab:
            if not group:
                st.success(empty)
            for index, issue in enumerate(group, start=1):
                with st.container(border=True):
                    render_issue(issue, index, label)
    with tabs[3]:
        render_list(strengths, "暂未提取到研究优点。")

    with st.expander("开发调试：查看初审原始数据"):
        st.json(result)


def render_numeric_verification(
    result: dict,
) -> None:
    """展示Python确定性数值核验结果。"""

    result = normalize_structure(result)

    st.markdown(
        '<div class="section-title">Python数值核验</div>',
        unsafe_allow_html=True,
    )

    total = result.get("total", 0)
    consistent_count = result.get("consistent_count", 0)
    inconsistent_count = result.get("inconsistent_count", 0)
    error_count = result.get("error_count", 0)

    columns = st.columns(4)
    columns[0].metric("数值主张", total)
    columns[1].metric("计算一致", consistent_count)
    columns[2].metric("计算不一致", inconsistent_count)
    columns[3].metric("计算失败", error_count)

    results = result.get("results", [])
    if not results:
        st.info("论文中没有识别到可进行确定性计算的数值主张。")
        return

    status_names = {
        "consistent": "✅ 一致",
        "inconsistent": "❌ 不一致",
        "error": "⚠️ 计算失败",
    }
    rows = []
    for item in results:
        rows.append(
            {
                "状态": status_names.get(
                    item.get("status"),
                    item.get("status", ""),
                ),
                "编号": item.get("claim_id", ""),
                "数值主张": item.get("claim", ""),
                "基准值": item.get("baseline", ""),
                "结果值": item.get("result", ""),
                "论文主张": item.get("claimed_value", ""),
                "Python计算": item.get("calculated_value", ""),
                "绝对误差": item.get("absolute_error", ""),
                "容差": item.get("tolerance", ""),
                "页码": item.get("page", ""),
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    if inconsistent_count:
        st.error(
            f"发现{inconsistent_count}条无法通过Python计算验证的数值主张。"
        )
    else:
        st.success("所有可计算的数值主张均通过Python核验。")

    with st.expander("查看数值工具原始结果"):
        st.json(result)


def render_verified(result: dict) -> None:
    result = quarantine_broken_symbol_issues(result)
    pages = st.session_state.get("paper_pages", [])
    result = apply_scoring(
        result,
        st.session_state.get("extraction_result", {}),
        context={
            "page_count": len(pages),
            "selected_pages": st.session_state.get("selected_pages", []),
            "empty_page_count": sum(
                1 for page in pages if not str(page.get("text", "")).strip()
            ),
            "corrupt_page_count": sum(
                1
                for page in pages
                if "识别失败" in normalize_scientific_text(
                    page.get("text", "")
                )
            ),
        },
    )
    breakdown = result.get("score_breakdown", {}) or {}
    score = int(
        breakdown.get(
            "scientific_reproducibility",
            result.get("reproducibility_score", 0),
        )
    )
    openness_score = int(
        breakdown.get(
            "resource_openness",
            result.get("resource_openness_score", 0),
        )
    )
    confidence_score = int(
        breakdown.get(
            "audit_confidence",
            result.get("audit_confidence_score", 0),
        )
    )
    issues = result.get("verified_issues", [])
    rejected = result.get("rejected_issues", [])
    strengths = result.get("verified_strengths", [])
    risk = "较低" if score >= 85 else "中等" if score >= 70 else "较高"

    columns = st.columns(4)
    columns[0].metric("科学可复现性", f"{score}/100")
    columns[1].metric("资源开放性", f"{openness_score}/100")
    columns[2].metric("审计置信度", f"{confidence_score}/100")
    columns[3].metric("确认问题", len(issues))
    st.progress(max(0.0, min(score / 100, 1.0)))
    profile_label = breakdown.get("profile_label", "通用科研论文")
    st.caption(
        f"评分标准：{profile_label}｜科学风险：{risk}。"
        "未公开代码只计入资源开放性；只有关键方法无法由论文重建时，"
        "才会影响科学可复现性。"
    )

    dimension_scores = breakdown.get(
        "scientific_dimensions",
        result.get("dimension_scores", {}),
    )
    if dimension_scores:
        st.markdown("#### 科学可复现性分项")
        score_columns = st.columns(3)
        for index, item in enumerate(dimension_scores.values()):
            score_columns[index % 3].metric(
                item.get("label", "未命名维度"),
                f"{item.get('score', 0)}/{item.get('max_score', 0)}",
            )

    with st.expander("查看开放性与审计置信度明细"):
        detail_col_1, detail_col_2 = st.columns(2)
        with detail_col_1:
            st.markdown("**资源开放性**")
            for item in breakdown.get("openness_dimensions", {}).values():
                st.write(
                    f"{item.get('label', '未命名')}："
                    f"{item.get('score', 0)}/{item.get('max_score', 0)}"
                )
        with detail_col_2:
            st.markdown("**审计置信度**")
            for item in breakdown.get("confidence_dimensions", {}).values():
                st.write(
                    f"{item.get('label', '未命名')}："
                    f"{item.get('score', 0)}/{item.get('max_score', 0)}"
                )

    if result.get("verification_summary"):
        st.info(result["verification_summary"])

    issue_tab, rejected_tab, strength_tab = st.tabs(["确认问题", "过滤误报", "研究优点"])
    with issue_tab:
        if not issues:
            st.success("没有发现经过验证的复现问题。")
        for index, issue in enumerate(issues, start=1):
            with st.container(border=True):
                render_issue(issue, index)
    with rejected_tab:
        if not rejected:
            st.caption("本次没有被过滤的误报。")
        for issue in rejected:
            with st.container(border=True):
                st.success("已过滤｜" + issue.get("title", "未命名问题"))
                st.write(issue.get("reason", "未提供过滤理由。"))
    with strength_tab:
        render_list(strengths, "暂未提取到研究优点。")

    with st.expander("开发调试：查看复核原始数据"):
        st.json(result)


def render_pdf_download(
    extraction_result: dict,
    verified_result: dict,
    source_filename: str,
) -> None:
    st.markdown('<div class="section-title">导出正式报告</div>', unsafe_allow_html=True)
    try:
        pdf_bytes = generate_pdf_report(
            extraction_result=extraction_result,
            verified_result=verified_result,
            source_filename=source_filename,
        )
        stem = Path(source_filename).stem if source_filename else "论文"
        st.download_button(
            "⑤ 下载 PDF 审计报告",
            data=pdf_bytes,
            file_name=f"{stem}_可复现性审计报告.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
        st.caption("报告包含最终评分、确认问题、原文证据、过滤误报和改进建议。")
    except Exception as error:
        st.error(f"PDF 报告生成失败：{error}")

def render_agent_plan(
    plan: dict,
) -> None:
    """展示智能体自主生成的计划。"""

    st.markdown("#### 智能体执行计划")

    goal = plan.get(
        "goal",
        "未提供目标",
    )

    document_type = plan.get(
        "document_type",
        "unknown",
    )

    source = plan.get(
        "planner_source",
        "unknown",
    )

    columns = st.columns(3)

    columns[0].metric(
        "文档类型",
        document_type,
    )

    columns[1].metric(
        "计划步骤",
        len(plan.get("steps", [])),
    )

    columns[2].metric(
        "规划来源",
        source,
    )

    st.info(f"任务目标：{goal}")

    policy = plan.get("execution_policy", {})
    if isinstance(policy, dict):
        policy_columns = st.columns(3)
        policy_columns[0].metric(
            "数值工具策略",
            {
                "auto": "自动判断",
                "required": "强制执行",
                "skip": "计划跳过",
            }.get(
                policy.get("numeric_verification", "auto"),
                "自动判断",
            ),
        )
        policy_columns[1].metric(
            "证据检查深度",
            {
                "focused": "聚焦",
                "standard": "标准",
                "deep": "深入",
            }.get(
                policy.get("evidence_depth", "standard"),
                "标准",
            ),
        )
        policy_columns[2].metric(
            "最大反思轮数",
            policy.get("max_reflections", 2),
        )

    plan_rows = []

    for step in plan.get("steps", []):
        plan_rows.append(
            {
                "步骤": step.get("id", ""),
                "工具": step.get("tool", ""),
                "选择理由": step.get(
                    "reason",
                    "",
                ),
                "依赖": "、".join(
                    step.get(
                        "depends_on",
                        [],
                    )
                ) or "无",
                "必要步骤": (
                    "是"
                    if step.get(
                        "required",
                        True,
                    )
                    else "否"
                ),
            }
        )

    if plan_rows:
        st.dataframe(
            plan_rows,
            use_container_width=True,
            hide_index=True,
        )

    criteria = plan.get(
        "success_criteria",
        [],
    )

    if criteria:
        st.markdown("**成功标准：**")

        for item in criteria:
            st.markdown(f"- {item}")

    warning = plan.get(
        "planning_warning",
        "",
    )

    if warning:
        st.warning(
            f"规划器已采用安全降级计划：{warning}"
        )


def render_plan_execution(summary: dict) -> None:
    """展示Planner计划与LangGraph实际执行的一致性。"""

    st.markdown("#### 计划—实际执行对照")
    columns = st.columns(4)
    columns[0].metric(
        "计划执行一致率",
        f"{summary.get('consistency_rate', 0)}%",
    )
    columns[1].metric(
        "计划步骤",
        summary.get("planned_step_count", 0),
    )
    columns[2].metric(
        "对齐步骤",
        summary.get("aligned_step_count", 0),
    )
    columns[3].metric(
        "安全补充工具",
        len(summary.get("safety_added_tools", [])),
    )

    status_labels = {
        "completed": "已完成",
        "conditionally_skipped": "条件跳过",
        "scheduled": "已调度",
        "failed": "失败",
        "not_run": "未执行",
    }
    rows = []
    for step in summary.get("steps", []):
        rows.append({
            "步骤": step.get("id", ""),
            "计划工具": step.get("tool", ""),
            "计划理由": step.get("reason", ""),
            "实际状态": status_labels.get(
                step.get("status", ""),
                step.get("status", "未知"),
            ),
        })
    if rows:
        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

    route_reason = summary.get("numeric_route_reason", "")
    if route_reason:
        st.caption(f"数值工具路由：{route_reason}")

    safety_tools = summary.get("safety_added_tools", [])
    if safety_tools:
        st.caption(
            "安全编排自动补充：" + "、".join(safety_tools)
        )


def render_agent_architecture() -> None:
    """展示比赛演示用的智能体编排架构。"""

    with st.expander(
        "查看 InternLM + LangGraph 智能体架构",
        expanded=False,
    ):
        st.markdown(
            """
            <div class="agent-flow">
                <span class="agent-node">论文与复现材料</span>
                <span class="agent-arrow">→</span>
                <span class="agent-node">InternLM Planner</span>
                <span class="agent-arrow">→</span>
                <span class="agent-node">实验要素提取</span>
                <span class="agent-arrow">→</span>
                <span class="agent-node">可复现性初审</span>
                <span class="agent-arrow">→</span>
                <span class="agent-node decision">数值条件路由</span>
                <span class="agent-arrow">→</span>
                <span class="agent-node">Python数值核验</span>
                <span class="agent-arrow">→</span>
                <span class="agent-node">原文证据复核</span>
                <span class="agent-arrow">→</span>
                <span class="agent-node decision">置信度门控</span>
                <span class="agent-arrow">↺</span>
                <span class="agent-node reflection">反思与证据扩展</span>
                <span class="agent-arrow">→</span>
                <span class="agent-node">PDF审计报告</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Intern-S2 Planner会选择数值工具策略、证据检查深度和反思上限；"
            "LangGraph按计划执行并保留安全兜底，最后输出计划—实际对照。"
        )


def collection_size(value) -> int:
    """安全统计列表或字典型结果的条目数量。"""

    if isinstance(value, (list, tuple, set)):
        return len(value)

    if isinstance(value, dict):
        for key in (
            "results",
            "claims",
            "verified_claims",
            "items",
        ):
            nested = value.get(key)
            if isinstance(nested, list):
                return len(nested)

        return len(value)

    return 0


def render_node_io_summary(
    state: dict,
) -> None:
    """以安全摘要展示各节点的实际输入输出。"""

    pages = state.get("pages", [])
    extraction = state.get(
        "extraction_result",
        {},
    )
    audit = state.get(
        "audit_result",
        {},
    )
    numeric = state.get(
        "numeric_verification_result",
        {},
    )
    verified = state.get(
        "verified_result",
        {},
    )

    character_count = sum(
        len(str(page.get("text", "")))
        for page in pages
        if isinstance(page, dict)
    )
    issue_count = sum(
        len(audit.get(key, []))
        for key in (
            "missing_items",
            "contradictions",
            "evidence_issues",
        )
        if isinstance(audit.get(key, []), list)
    )

    rows = [
        {
            "节点": "experiment_extractor",
            "输入摘要": f"{len(pages)}页，{character_count:,}字符",
            "输出摘要": (
                f"{len(extraction.get('methods', []))}种方法，"
                f"{len(extraction.get('key_parameters', []))}项参数"
            ),
        },
        {
            "节点": "reproducibility_auditor",
            "输入摘要": "论文原文与结构化实验信息",
            "输出摘要": (
                f"{issue_count}个候选问题，"
                f"{len(audit.get('numeric_claims', []))}条数值主张"
            ),
        },
        {
            "节点": "numeric_verifier",
            "输入摘要": f"{len(audit.get('numeric_claims', []))}条数值主张",
            "输出摘要": f"{collection_size(numeric)}条工具核验结果",
        },
        {
            "节点": "evidence_verifier",
            "输入摘要": (
                f"候选问题与最多"
                f"{state.get('evidence_page_limit', 35)}页证据"
            ),
            "输出摘要": (
                f"确认{len(verified.get('verified_issues', []))}项，"
                f"过滤{len(verified.get('rejected_issues', []))}项"
            ),
        },
        {
            "节点": "confidence_gate",
            "输入摘要": "问题覆盖率与证据完整度",
            "输出摘要": (
                f"置信度{state.get('audit_confidence', 0)}分，"
                f"反思{state.get('reflection_count', 0)}次"
            ),
        },
    ]

    st.markdown("#### 节点输入输出摘要")
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


def render_execution_trace(
    trace: list[dict],
) -> None:
    """同时兼容旧运行时和LangGraph的工具调用轨迹。"""

    st.markdown("#### 工具调用轨迹")

    if not trace:
        st.caption("暂时没有执行轨迹。")
        return

    event_labels = {
        "tool_started": "⏳ 开始执行",
        "tool_completed": "✅ 执行完成",
        "tool_failed": "❌ 执行失败",
        "numeric_check_required": "🔢 进入数值核验",
        "numeric_check_skipped": "⏭️ 跳过数值核验",
        "confidence_evaluated": "🎯 置信度评估",
        "reflection_triggered": "🔁 触发反思复核",
        "plan_execution_summarized": "🧭 计划执行已对照",
        "graph_completed": "🏁 流程完成",
    }

    rows = []

    for index, item in enumerate(trace, start=1):
        event = item.get("event", "")
        legacy_status = item.get("status", "")
        display_status = event_labels.get(
            event,
            legacy_status or event or "未知事件",
        )

        details = item.get("reason", "")

        if event == "confidence_evaluated":
            details = (
                f"证据置信度 {item.get('confidence', 0)} 分"
            )
        elif event == "reflection_triggered":
            details = (
                f"第 {item.get('reflection_count', 0)} 次反思，"
                f"核验范围扩大到 {item.get('page_limit', 0)} 页"
            )
        elif event == "numeric_check_required":
            details = (
                f"{item.get('reason', '')}；"
                f"主张数 {item.get('claim_count', 0)}"
            )
        elif event == "numeric_check_skipped":
            details = item.get(
                "reason",
                "未发现可确定性计算的数值主张",
            )
        elif event == "plan_execution_summarized":
            details = (
                f"计划{item.get('planned_step_count', 0)}步，"
                f"一致率{item.get('consistency_rate', 0)}%"
            )

        rows.append(
            {
                "序号": index,
                "状态": display_status,
                "工具": item.get(
                    "tool",
                    "",
                ),
                "说明": details,
                "错误": item.get(
                    "error",
                    "",
                ),
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    success_count = sum(
        1
        for item in trace
        if (
            item.get("event") == "tool_completed"
            or item.get("status") == "success"
        )
    )

    failed_count = sum(
        1
        for item in trace
        if (
            item.get("event") == "tool_failed"
            or item.get("status") == "failed"
        )
    )

    reflection_count = sum(
        1
        for item in trace
        if item.get("event") == "reflection_triggered"
    )

    columns = st.columns(3)

    columns[0].metric(
        "成功工具",
        success_count,
    )

    columns[1].metric(
        "失败工具",
        failed_count,
    )

    columns[2].metric(
        "自主反思次数",
        reflection_count,
    )
st.markdown(
    """
    <div class="hero">
        <h1>🔬 ReproAgent</h1>
        <p>科研论文可复现性审计智能体 · 提取实验要素、核查证据并过滤误报</p>
    </div>
    """,
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "上传论文 PDF",
    type=["pdf"],
)

supplement_files = st.file_uploader(
    "可选：上传复现材料（代码、README、依赖清单或ZIP）",
    type=["zip", "py", "ipynb", "m", "r", "cpp", "c", "java",
          "txt", "md", "yml", "yaml", "toml", "lock"],
    accept_multiple_files=True,
    help="系统只检查文件清单，不会执行或导入上传的代码。",
)

if uploaded_file is not None:
    if uploaded_file.size > MAX_PDF_BYTES:
        st.error("论文PDF不能超过50 MB。")
        st.stop()

    supplement_total_bytes = sum(
        item.size
        for item in supplement_files
    )

    if supplement_total_bytes > MAX_SUPPLEMENT_BYTES:
        st.error("复现材料总大小不能超过20 MB。")
        st.stop()

    st.success(
        f"已选择：{uploaded_file.name}"
    )

    if st.button(
        "① 解析论文",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner(
                "正在解析 PDF……"
            ):
                pages = extract_pdf(
                    uploaded_file.getvalue()
                )
                supplement_analysis = analyze_supplements([
                    {
                        "name": item.name,
                        "content": item.getvalue(),
                    }
                    for item in supplement_files
                ])

            st.session_state[
                "paper_pages"
            ] = pages
            st.session_state[
                "supplement_analysis"
            ] = supplement_analysis

            for key in (
                "extraction_result",
                "selected_pages",
                "audit_result",
                "numeric_verification_result",
                "verified_result",
                "agent_plan",
                "agent_result",
                "pdf_bytes",
                "pdf_filename",
            ):
                st.session_state.pop(
                    key,
                    None,
                )

            st.success(
                "PDF 解析完成。"
            )

        except Exception as error:
            st.error(
                f"PDF 解析失败：{error}"
            )

if "paper_pages" in st.session_state:
    pages = st.session_state["paper_pages"]
    total_characters = sum(len(page["text"]) for page in pages)

    st.markdown('<div class="section-title">文档概览</div>', unsafe_allow_html=True)
    columns = st.columns(3)
    columns[0].metric("PDF 页数", len(pages))
    columns[1].metric("提取字符", f"{total_characters:,}")
    stage = (
        "已复核" if "verified_result" in st.session_state else
        "已初审" if "audit_result" in st.session_state else
        "已提取" if "extraction_result" in st.session_state else "已解析"
    )
    columns[2].metric("当前阶段", stage)

    supplement_analysis = st.session_state.get("supplement_analysis", {})
    if supplement_analysis.get("provided"):
        material_columns = st.columns(4)
        material_columns[0].metric(
            "复现材料包",
            supplement_analysis.get("package_count", 0),
        )
        material_columns[1].metric(
            "代码文件",
            supplement_analysis.get("code_file_count", 0),
        )
        material_columns[2].metric(
            "README",
            "有" if supplement_analysis.get("has_readme") else "无",
        )
        material_columns[3].metric(
            "依赖清单",
            "有" if supplement_analysis.get("has_dependencies") else "无",
        )
        st.caption("复现材料仅进行静态文件清单检查，系统不会运行其中代码。")
    st.markdown(
        '<div class="section-title">'
        '智能体自主审计'
        '</div>',
        unsafe_allow_html=True,
    )

    render_agent_architecture()

    agent_goal = st.text_area(
        "审计目标",
        value=(
            "检查论文的实验信息完整性、"
            "数值一致性、证据可靠性和可复现性，"
            "并生成正式PDF审计报告。"
        ),
        height=90,
        key="agent_goal",
    )

    if "agent_result" in st.session_state:
        if st.button(
            "↻ 重新运行智能审计",
            use_container_width=True,
        ):
            for key in (
                "extraction_result",
                "selected_pages",
                "audit_result",
                "numeric_verification_result",
                "verified_result",
                "agent_plan",
                "agent_result",
                "pdf_bytes",
                "pdf_filename",
            ):
                st.session_state.pop(key, None)

            st.rerun()

    if st.button(
        "🤖 启动智能审计",
        type="primary",
        use_container_width=True,
        disabled=(
            "agent_result"
            in st.session_state
        ),
    ):
        progress_bar = st.progress(0)
        status_box = st.empty()

        try:
            run_started_at = time.perf_counter()
            status_box.info(
                "Planner正在分析文档并生成任务计划……"
            )

            plan = create_audit_plan(
                pages=pages,
                user_goal=agent_goal,
            )

            st.session_state[
                "agent_plan"
            ] = plan

            progress_bar.progress(0.15)
            status_box.info(
                "LangGraph正在编排提取、审计、数值核验和证据复核……"
            )

            node_labels = {
                "extract_experiment": "实验要素提取",
                "audit_reproducibility": "可复现性初审",
                "inspect_numeric_claims": "数值主张条件判断",
                "verify_numbers": "Python确定性数值核验",
                "verify_evidence": "原文证据复核",
                "inspect_confidence": "证据置信度评估",
                "expand_evidence": "反思与证据范围扩展",
                "summarize_plan": "计划与实际执行对照",
                "generate_report": "PDF审计报告生成",
                "finalize": "流程收尾",
            }
            node_progress = {
                "extract_experiment": 0.28,
                "audit_reproducibility": 0.42,
                "inspect_numeric_claims": 0.48,
                "verify_numbers": 0.58,
                "verify_evidence": 0.70,
                "inspect_confidence": 0.78,
                "expand_evidence": 0.80,
                "summarize_plan": 0.88,
                "generate_report": 0.92,
                "finalize": 0.98,
            }
            live_events = []
            progress_state = {
                "value": 0.15,
            }

            def handle_graph_progress(
                event: dict,
            ) -> None:
                live_events.append(event)

                if event.get("event") != "node_completed":
                    return

                node_name = event.get("node", "")
                target = node_progress.get(
                    node_name,
                    progress_state["value"] + 0.05,
                )
                target = max(
                    progress_state["value"],
                    min(target, 0.98),
                )
                progress_state["value"] = target
                progress_bar.progress(target)

                label = node_labels.get(
                    node_name,
                    node_name,
                )
                message = f"已完成：{label}"

                if node_name == "inspect_confidence":
                    message += (
                        "，当前置信度"
                        f"{event.get('audit_confidence', 0)}分"
                    )
                elif node_name == "expand_evidence":
                    message += (
                        "，正在进行第"
                        f"{event.get('reflection_count', 0)}次反思"
                    )

                status_box.info(message)

            runtime_kwargs = {
                "pages": pages,
                "source_filename": (
                    uploaded_file.name
                    if uploaded_file
                    else "论文.pdf"
                ),
                "supplement_analysis": st.session_state.get(
                    "supplement_analysis",
                    {},
                ),
                "progress_callback": handle_graph_progress,
            }
            if "plan" in inspect.signature(
                run_langgraph_audit
            ).parameters:
                runtime_kwargs["plan"] = plan
            else:
                status_box.warning(
                    "云端正在更新智能体运行时，"
                    "本次将使用兼容模式继续执行。"
                )

            final_state = run_langgraph_audit(
                **runtime_kwargs
            )

            duration_seconds = round(
                time.perf_counter()
                - run_started_at,
                2,
            )

            agent_result = {
                "status": final_state.get(
                    "status",
                    "failed",
                ),
                "state": final_state,
                "execution_trace": final_state.get(
                    "execution_trace",
                    [],
                ),
                "harness": "LangGraph",
                "duration_seconds": duration_seconds,
                "orchestration_events": live_events,
            }

            st.session_state[
                "agent_result"
            ] = agent_result

            # 将智能体结果同步到原来的页面状态
            result_keys = [
                "extraction_result",
                "selected_pages",
                "audit_result",
                "numeric_verification_result",
                "verified_result",
                "pdf_bytes",
                "pdf_filename",
            ]

            for key in result_keys:
                if key in final_state:
                    st.session_state[
                        key
                    ] = final_state[key]

            progress_bar.progress(1.0)

            if agent_result["status"] == "completed":
                status_box.success(
                    "LangGraph智能体已完成全部任务。"
                )
            else:
                status_box.error(
                    "智能体执行失败，"
                    "请查看执行轨迹。"
                )

        except Exception as error:
            status_box.error(
                f"智能体运行失败：{error}"
            )

    if "agent_plan" in st.session_state:
        with st.expander(
            "查看智能体自主规划",
            expanded=True,
        ):
            render_agent_plan(
                st.session_state[
                    "agent_plan"
                ]
            )

    if "agent_result" in st.session_state:
        agent_result = st.session_state["agent_result"]
        agent_state = agent_result.get("state", {})

        summary_columns = st.columns(4)
        summary_columns[0].metric(
            "执行框架",
            agent_result.get("harness", "LangGraph"),
        )
        summary_columns[1].metric(
            "证据核验置信度",
            f"{agent_state.get('audit_confidence', 0)} / 100",
        )
        summary_columns[2].metric(
            "自主反思次数",
            agent_state.get("reflection_count", 0),
        )
        summary_columns[3].metric(
            "总运行时间",
            f"{agent_result.get('duration_seconds', 0):.1f} 秒",
        )

        with st.expander(
            "查看工具调用轨迹",
            expanded=True,
        ):
            render_execution_trace(
                agent_result.get(
                    "execution_trace",
                    [],
                )
            )

        if agent_state.get("agent_execution"):
            with st.expander(
                "查看计划—实际执行对照",
                expanded=True,
            ):
                render_plan_execution(
                    agent_state["agent_execution"]
                )

        with st.expander(
            "查看节点输入输出摘要",
            expanded=True,
        ):
            render_node_io_summary(
                agent_state
            )
    st.markdown('<div class="section-title">实验要素提取</div>', unsafe_allow_html=True)
    if st.button(
        "② 提取实验信息",
        type="primary",
        use_container_width=True,
        disabled="extraction_result" in st.session_state,
    ):
        try:
            with st.spinner("Intern-S2 正在提取实验信息，可能需要 1～2 分钟……"):
                result, selected_pages = extract_research_info(pages)
                result = merge_supplement_analysis(
                    result,
                    st.session_state.get("supplement_analysis"),
                )
            st.session_state["extraction_result"] = result
            st.session_state["selected_pages"] = selected_pages
            st.session_state.pop("audit_result", None)
            st.session_state.pop("verified_result", None)
            st.success("实验信息提取完成。")
        except Exception as error:
            st.error(f"提取失败：{error}")

    if "extraction_result" in st.session_state:
        result = st.session_state["extraction_result"]
        render_extraction(result, st.session_state.get("selected_pages", []))

        st.markdown('<div class="section-title">可复现性初审</div>', unsafe_allow_html=True)
        if st.button(
            "③ 开始可复现性审计",
            type="primary",
            use_container_width=True,
            disabled="audit_result" in st.session_state,
        ):
            try:
                with st.spinner("审计智能体正在检查缺失项、矛盾和证据……"):
                    audit_result = audit_reproducibility(pages, result)
                st.session_state["audit_result"] = audit_result
                st.session_state.pop("verified_result", None)
                st.success("可复现性初审完成。")
            except Exception as error:
                st.error(f"审计失败：{error}")

        if "audit_result" in st.session_state:
            audit_result = st.session_state["audit_result"]
            render_audit(audit_result)

            if "numeric_verification_result" in st.session_state:
                render_numeric_verification(
                    st.session_state["numeric_verification_result"]
                )

            st.markdown('<div class="section-title">审计复核</div>', unsafe_allow_html=True)
            if st.button(
                "④ 验证审计结论",
                type="primary",
                use_container_width=True,
                disabled="verified_result" in st.session_state,
            ):
                try:
                    with st.spinner("验证智能体正在回查证据并过滤误报……"):
                        numeric_result = verify_numeric_claims(
                            audit_result.get("numeric_claims", [])
                        )
                        audit_for_verification = dict(audit_result)
                        audit_for_verification[
                            "numeric_verification_result"
                        ] = numeric_result
                        verified_result = verify_audit(
                            pages,
                            result,
                            audit_for_verification,
                        )
                    st.session_state[
                        "numeric_verification_result"
                    ] = numeric_result
                    st.session_state["verified_result"] = verified_result
                    st.success("审计复核完成。")
                except Exception as error:
                    st.error(f"复核失败：{error}")

            if "verified_result" in st.session_state:
                verified_result = st.session_state["verified_result"]
                render_verified(verified_result)
                render_pdf_download(
                    extraction_result=result,
                    verified_result=verified_result,
                    source_filename=uploaded_file.name if uploaded_file else "",
                )

    st.markdown('<div class="section-title">PDF 原文</div>', unsafe_allow_html=True)
    st.caption("原文默认折叠，只有核对证据时才需要展开。")
    for page in pages:
        with st.expander(f"第 {page['page_number']} 页"):
            if page["text"]:
                st.text(normalize_scientific_text(page["text"]))
            else:
                st.warning("这一页没有提取到文字，可能是扫描图片。")
