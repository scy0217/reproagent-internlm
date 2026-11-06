import json
import re

from core.extractor import parse_json_result
from core.internlm_client import call_model
from core.tool_registry import list_tools

AVAILABLE_TOOLS = {
    tool["name"]: {
        "description": tool["description"],
        "input_keys": tool["input_keys"],
        "output_keys": tool["output_keys"],
    }
    for tool in list_tools()
}


PLAN_SCHEMA = {
    "document_type": "",
    "goal": "",
    "execution_policy": {
        "numeric_verification": "auto",
        "evidence_depth": "standard",
        "max_reflections": 2,
    },
    "constraints": [],
    "risks": [],
    "steps": [
        {
            "id": "S1",
            "tool": "experiment_extractor",
            "reason": "",
            "depends_on": [],
            "required": True,
        }
    ],
    "success_criteria": [],
}


def build_document_profile(
    pages: list[dict],
) -> dict:
    """使用普通Python生成论文基础特征。"""

    page_count = len(pages)

    total_characters = sum(
        len(page.get("text", ""))
        for page in pages
    )

    empty_pages = [
        page.get("page_number")
        for page in pages
        if not page.get("text", "").strip()
    ]

    full_text = "\n".join(
        page.get("text", "")
        for page in pages
    )

    number_count = len(
        re.findall(
            r"\d+(?:\.\d+)?%?",
            full_text,
        )
    )

    formula_keywords = [
        "公式",
        "方程",
        "theorem",
        "equation",
    ]

    table_keywords = [
        "表1",
        "表2",
        "表3",
        "table",
    ]

    code_keywords = [
        "python",
        "matlab",
        "代码",
        "程序",
        "github",
    ]

    experiment_keywords = [
        "实验",
        "试验",
        "参数",
        "数据集",
        "评价指标",
        "结果",
    ]

    lower_text = full_text.lower()

    signals = {
        "has_formula_signal": any(
            keyword in lower_text
            for keyword in formula_keywords
        ),
        "has_table_signal": any(
            keyword in lower_text
            for keyword in table_keywords
        ),
        "has_code_signal": any(
            keyword in lower_text
            for keyword in code_keywords
        ),
        "has_experiment_signal": any(
            keyword in lower_text
            for keyword in experiment_keywords
        ),
        "number_count": number_count,
    }

    # 只给Planner少量文档片段，避免消耗太多Token
    candidate_indexes = {
        0,
        1,
        max(0, page_count // 2),
        max(0, page_count - 2),
        max(0, page_count - 1),
    }

    excerpts = []

    for index in sorted(candidate_indexes):
        if index >= page_count:
            continue

        page = pages[index]
        text = page.get("text", "").strip()

        if not text:
            continue

        excerpts.append(
            {
                "page": page.get("page_number"),
                "text": text[:1200],
            }
        )

    return {
        "page_count": page_count,
        "total_characters": total_characters,
        "empty_page_count": len(empty_pages),
        "empty_pages": empty_pages[:20],
        "signals": signals,
        "excerpts": excerpts,
    }


def create_fallback_plan(
    goal: str,
    warning: str = "",
) -> dict:
    """当模型规划失败时使用安全的默认计划。"""

    return {
        "document_type": "scientific_paper",
        "goal": goal,
        "execution_policy": {
            "numeric_verification": "auto",
            "evidence_depth": "standard",
            "max_reflections": 2,
        },
        "constraints": [
            "所有问题必须提供原文证据",
            "禁止执行未注册工具",
        ],
        "risks": [
            "自动规划失败，已采用默认安全计划"
        ],
                "steps": [
            {
                "id": "S1",
                "tool": "experiment_extractor",
                "reason": "提取论文实验要素",
                "depends_on": [],
                "required": True,
            },
            {
                "id": "S2",
                "tool": "reproducibility_auditor",
                "reason": "检查复现风险和内容矛盾",
                "depends_on": ["S1"],
                "required": True,
            },
            {
                "id": "S3",
                "tool": "numeric_verifier",
                "reason": "使用Python核验数值主张",
                "depends_on": ["S2"],
                "required": False,
            },
            {
                "id": "S4",
                "tool": "evidence_verifier",
                "reason": "结合原文和计算结果过滤误报",
                "depends_on": [
                    "S1",
                    "S2",
                ],
                "required": True,
            },
            {
                "id": "S5",
                "tool": "pdf_report_generator",
                "reason": "生成正式审计报告",
                "depends_on": ["S4"],
                "required": True,
            },
        ],
        "success_criteria": [
        "所有确认问题均有页码证据",
        "所有数值主张均由Python工具核验",
        "合理近似不会被判定为矛盾",
        "重复问题已合并",
        "生成最终评分和PDF报告",
        ],
        "planner_source": "fallback",
        "planning_warning": warning,
    }


def validate_plan(plan: dict) -> dict:
    """验证并清理模型生成的执行计划。"""

    if not isinstance(plan, dict):
        raise ValueError("Planner返回结果不是对象。")

    raw_steps = plan.get("steps", [])

    if not isinstance(raw_steps, list):
        raise ValueError("Planner的steps不是列表。")

    valid_steps = []
    seen_ids = set()

    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            continue

        step_id = str(
            raw_step.get("id", "")
        ).strip()

        tool_name = str(
            raw_step.get("tool", "")
        ).strip()

        if not step_id:
            continue

        if step_id in seen_ids:
            continue

        if tool_name not in AVAILABLE_TOOLS:
            continue

        dependencies = raw_step.get(
            "depends_on",
            [],
        )

        if not isinstance(dependencies, list):
            dependencies = []

        # 依赖只能指向已经出现的步骤
        dependencies = [
            dependency
            for dependency in dependencies
            if dependency in seen_ids
        ]

        valid_steps.append(
            {
                "id": step_id,
                "tool": tool_name,
                "reason": str(
                    raw_step.get("reason", "")
                ),
                "depends_on": dependencies,
                "required": bool(
                    raw_step.get("required", True)
                ),
            }
        )

        seen_ids.add(step_id)

    if not valid_steps:
        raise ValueError("Planner没有生成有效步骤。")

    plan["steps"] = valid_steps
    plan["planner_source"] = "intern-s2"

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
    if evidence_depth not in {"focused", "standard", "deep"}:
        evidence_depth = "standard"

    try:
        max_reflections = int(
            raw_policy.get("max_reflections", 2)
        )
    except (TypeError, ValueError):
        max_reflections = 2

    plan["execution_policy"] = {
        "numeric_verification": numeric_policy,
        "evidence_depth": evidence_depth,
        "max_reflections": max(0, min(max_reflections, 2)),
    }

    document_type = str(
        plan.get("document_type", "scientific_paper")
    ).strip()
    plan["document_type"] = document_type or "scientific_paper"

    if not isinstance(
        plan.get("constraints"),
        list,
    ):
        plan["constraints"] = []

    if not isinstance(
        plan.get("risks"),
        list,
    ):
        plan["risks"] = []

    if not isinstance(
        plan.get("success_criteria"),
        list,
    ):
        plan["success_criteria"] = []

    return plan


def create_audit_plan(
    pages: list[dict],
    user_goal: str = "评估论文的实验可复现性",
) -> dict:
    """调用Intern-S2生成论文审计计划。"""

    profile = build_document_profile(pages)

    tools_json = json.dumps(
        AVAILABLE_TOOLS,
        ensure_ascii=False,
        indent=2,
    )

    profile_json = json.dumps(
        profile,
        ensure_ascii=False,
        indent=2,
    )

    schema_json = json.dumps(
        PLAN_SCHEMA,
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = """
你是科研智能体的任务规划器。

你需要根据用户目标和论文特征，
从允许的工具中选择工具并生成执行计划。

规则：
1. 只能选择工具列表中存在的工具。
2. 不得虚构工具。
3. 每个步骤必须说明选择理由。
4. depends_on只能引用前面的步骤。
5. 根据论文特征决定是否需要某项工具。
6. 计划必须包含清晰的成功标准。
7. 只输出合法JSON，不输出解释或思考过程。
8. 初始状态只包含pages和source_filename。
9. 工具需要的输入必须由初始状态或前面的步骤产生。
10. 完整科研审计必须最终生成verified_result。
11. 如果用户要求正式报告，必须调用pdf_report_generator。
12. 推荐标准顺序为提取、初审、复核、报告，
    但可以根据任务目标跳过不必要的可选工具。
13. 如果论文包含百分比、差值、变化率或比例，
    应在reproducibility_auditor之后调用numeric_verifier。
14. numeric_verifier必须依赖reproducibility_auditor。
15. evidence_verifier应在numeric_verifier之后运行，
    但没有数值主张时可以跳过numeric_verifier。
16. execution_policy.numeric_verification只能是auto、required或skip。
17. execution_policy.evidence_depth只能是focused、standard或deep。
18. execution_policy.max_reflections只能是0到2的整数。
19. 对长论文、公式或表格较多的论文优先选择deep；
    对短且结构清晰的论文可选择focused。
20. skip仅表示Planner认为不需要数值工具；若运行时发现明确数值主张，
    安全路由仍可覆盖该决定并调用确定性核验。
"""

    user_prompt = f"""
用户目标：

{user_goal}

论文特征：

{profile_json}

允许调用的工具：

{tools_json}

请按照以下JSON结构生成执行计划：

{schema_json}
"""

    try:
        model_output = call_model(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            thinking_mode=False,
        )

        plan = parse_json_result(model_output)
        plan = validate_plan(plan)

        return plan

    except Exception as error:
        return create_fallback_plan(
            goal=user_goal,
            warning=str(error),
        )
