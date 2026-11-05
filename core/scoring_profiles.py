from __future__ import annotations

import re


SEVERITY_RATIOS = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.2,
}


PROFILES = {
    "general": {
        "label": "通用科研论文",
        "weights": {
            "data_materials": 20,
            "methods": 25,
            "parameters": 20,
            "environment": 10,
            "consistency": 25,
        },
    },
    "numerical_simulation": {
        "label": "数值模拟论文",
        "weights": {
            "data_materials": 10,
            "methods": 25,
            "parameters": 25,
            "environment": 10,
            "consistency": 30,
        },
    },
    "machine_learning": {
        "label": "机器学习论文",
        "weights": {
            "data_materials": 20,
            "methods": 20,
            "parameters": 20,
            "environment": 10,
            "consistency": 30,
        },
    },
    "experimental": {
        "label": "实验研究论文",
        "weights": {
            "data_materials": 25,
            "methods": 25,
            "parameters": 20,
            "environment": 5,
            "consistency": 25,
        },
    },
    "theoretical": {
        "label": "理论研究论文",
        "weights": {
            "data_materials": 5,
            "methods": 40,
            "parameters": 10,
            "environment": 0,
            "consistency": 45,
        },
    },
}


DIMENSION_LABELS = {
    "data_materials": "数据与材料",
    "methods": "方法描述",
    "parameters": "参数完整性",
    "environment": "运行环境",
    "consistency": "结果一致性",
}


def normalize_issue_scopes(verified_result: dict) -> None:
    """用确定性规则约束模型给出的影响范围，避免代码项误伤科学分。"""

    valid_scopes = {
        "scientific_reproducibility",
        "resource_openness",
        "both",
    }
    reconstruction_terms = (
        "无法重建", "不能重建", "关键实现未描述", "核心算法未描述",
        "仅在代码", "依赖缺失代码", "正文未给出算法", "不可由正文复现",
    )
    for issue in verified_result.get("verified_issues", []):
        dimension = infer_dimension(issue)
        scope = str(issue.get("impact_scope", ""))
        if dimension == "code":
            evidence = issue.get("evidence", []) or []
            if isinstance(evidence, str):
                evidence = [evidence]
            text = " ".join([
                str(issue.get("title", "")),
                str(issue.get("reason", "")),
                " ".join(map(str, evidence)),
            ])
            blocks_reconstruction = any(term in text for term in reconstruction_terms)
            issue["impact_scope"] = (
                "both" if blocks_reconstruction else "resource_openness"
            )
        elif scope not in valid_scopes:
            issue["impact_scope"] = "scientific_reproducibility"


def infer_document_type(
    extraction_result: dict,
    declared_type: str = "",
) -> str:
    """结合Planner类型和论文内容选择评分标准。"""

    declared = str(declared_type or "").lower()
    aliases = {
        "numerical_simulation": "numerical_simulation",
        "simulation": "numerical_simulation",
        "数值模拟": "numerical_simulation",
        "machine_learning": "machine_learning",
        "机器学习": "machine_learning",
        "experimental": "experimental",
        "实验研究": "experimental",
        "theoretical": "theoretical",
        "理论研究": "theoretical",
    }
    for keyword, profile in aliases.items():
        if keyword in declared:
            return profile

    text = " ".join(
        [
            str(extraction_result.get("title", "")),
            str(extraction_result.get("research_goal", "")),
            " ".join(map(str, extraction_result.get("methods", []))),
            " ".join(map(str, extraction_result.get("models_or_algorithms", []))),
        ]
    ).lower()

    if any(word in text for word in ["有限体积", "有限元", "仿真", "模拟", "数值求解"]):
        return "numerical_simulation"
    if any(word in text for word in ["机器学习", "深度学习", "神经网络", "训练集", "模型训练"]):
        return "machine_learning"
    if any(word in text for word in ["理论证明", "定理", "推论", "解析解"]):
        return "theoretical"
    if any(word in text for word in ["临床实验", "实验组", "对照组", "样本采集"]):
        return "experimental"
    return "general"


def infer_dimension(issue: dict) -> str:
    dimension = str(issue.get("dimension", ""))
    if dimension in {*DIMENSION_LABELS, "code"}:
        return dimension

    text = " ".join(
        [
            str(issue.get("category", "")),
            str(issue.get("title", "")),
            str(issue.get("reason", "")),
        ]
    ).lower()
    groups = [
        ("code", ["代码", "仓库", "脚本", "运行命令", "repository"]),
        ("environment", ["环境", "硬件", "软件版本", "依赖", "cpu", "gpu"]),
        ("parameters", ["参数", "随机种子", "初始条件", "边界条件", "超参数"]),
        ("data_materials", ["数据", "材料", "样本", "数据集", "数据来源", "数据划分"]),
        ("methods", ["方法", "算法", "模型流程", "实验流程"]),
        ("consistency", ["矛盾", "一致", "数值", "基准", "比例", "证据"]),
    ]
    for name, keywords in groups:
        if any(keyword in text for keyword in keywords):
            return name
    return "consistency"


def calculate_scientific_score(
    verified_result: dict,
    profile_key: str,
) -> tuple[int, dict]:
    """代码开放性不直接进入科学可复现性分数。"""

    weights = PROFILES[profile_key]["weights"]
    highest_risk = {dimension: 0.0 for dimension in weights}

    for issue in verified_result.get("verified_issues", []):
        scope = issue.get("impact_scope", "")
        dimension = infer_dimension(issue)

        if dimension == "code" and scope not in {
            "scientific_reproducibility",
            "both",
        }:
            continue
        if dimension == "code":
            # 仅当未提供代码导致关键方法无法重建时，
            # 才把它视为方法完整性问题。
            dimension = "methods"
        if scope == "resource_openness":
            continue
        if dimension not in highest_risk:
            continue

        ratio = SEVERITY_RATIOS.get(issue.get("severity", "low"), 0.2)
        highest_risk[dimension] = max(highest_risk[dimension], ratio)

    dimensions = {}
    for dimension, max_score in weights.items():
        deduction = int(max_score * highest_risk[dimension] + 0.5)
        dimensions[dimension] = {
            "label": DIMENSION_LABELS[dimension],
            "score": max_score - deduction,
            "max_score": max_score,
        }

    return sum(item["score"] for item in dimensions.values()), dimensions


def calculate_openness_score(
    extraction_result: dict,
    verified_result: dict,
) -> tuple[int, dict]:
    """资源开放性独立计分，不伪装成科学复现性。"""

    code_info = extraction_result.get("code_availability", {}) or {}
    code_status = str(code_info.get("status", "unknown")).lower()
    code_url = str(code_info.get("url", ""))
    if code_status in {"available", "yes", "public", "公开", "true"}:
        code_score = 60 if code_url else 50
    elif code_status in {"partial", "部分"}:
        code_score = 30
    else:
        code_score = 0

    materials = extraction_result.get("materials_or_datasets", [])
    material_text = " ".join(map(str, materials)).lower()
    has_data_link = bool(re.search(r"https?://|doi|仓库|repository", material_text))
    data_score = 25 if has_data_link else 10 if materials else 0

    software = extraction_result.get("software_environment", [])
    hardware = extraction_result.get("hardware_environment", [])
    environment_score = 0
    if software:
        environment_score += 8
        if re.search(r"\d+(?:\.\d+)+", " ".join(map(str, software))):
            environment_score += 4
    if hardware:
        environment_score += 3
    environment_score = min(environment_score, 15)

    for issue in verified_result.get("verified_issues", []):
        if issue.get("impact_scope") not in {"resource_openness", "both"}:
            continue
        dimension = infer_dimension(issue)
        severity = issue.get("severity", "low")
        ratio = SEVERITY_RATIOS.get(severity, 0.2)
        if dimension == "code":
            code_score = min(code_score, int(60 * (1 - ratio)))
        elif dimension == "data_materials":
            data_score = min(data_score, int(25 * (1 - ratio)))
        elif dimension == "environment":
            environment_score = min(environment_score, int(15 * (1 - ratio)))

    dimensions = {
        "code": {"label": "代码开放", "score": code_score, "max_score": 60},
        "data": {"label": "数据开放", "score": data_score, "max_score": 25},
        "environment": {
            "label": "环境说明",
            "score": environment_score,
            "max_score": 15,
        },
    }
    return code_score + data_score + environment_score, dimensions


def calculate_audit_confidence(
    verified_result: dict,
    context: dict,
) -> tuple[int, dict]:
    """评估本次审计证据是否充分，而不是论文质量。"""

    page_count = max(1, int(context.get("page_count", 0) or 1))
    selected_pages = set(context.get("selected_pages", []) or [])
    coverage_ratio = min(1.0, len(selected_pages) / page_count)
    coverage_score = int(40 * min(1.0, coverage_ratio / 0.5) + 0.5)

    issues = verified_result.get("verified_issues", [])
    if issues:
        evidenced = sum(
            1
            for issue in issues
            if (issue.get("pages") or issue.get("page")) and issue.get("evidence")
        )
        evidence_score = int(30 * evidenced / len(issues) + 0.5)
    else:
        evidence_score = 24

    numeric = verified_result.get("numeric_verification_result", {}) or {}
    numeric_total = int(numeric.get("total", 0) or 0)
    numeric_errors = int(numeric.get("error_count", 0) or 0)
    numeric_score = 15 if numeric_total == 0 else int(
        20 * max(0.0, 1 - numeric_errors / numeric_total) + 0.5
    )

    empty_count = int(context.get("empty_page_count", 0) or 0)
    corrupt_count = int(context.get("corrupt_page_count", 0) or 0)
    unreadable_count = min(page_count, empty_count + corrupt_count)
    readable_ratio = max(0.0, 1 - unreadable_count / page_count)
    readability_score = int(10 * readable_ratio + 0.5)

    total = min(100, coverage_score + evidence_score + numeric_score + readability_score)
    breakdown = {
        "page_coverage": {"label": "页面覆盖", "score": coverage_score, "max_score": 40},
        "evidence_quality": {"label": "证据完整", "score": evidence_score, "max_score": 30},
        "numeric_validation": {"label": "数值核验", "score": numeric_score, "max_score": 20},
        "text_readability": {"label": "文本可读", "score": readability_score, "max_score": 10},
    }
    return total, breakdown


def apply_scoring(
    verified_result: dict,
    extraction_result: dict,
    context: dict | None = None,
) -> dict:
    """应用三分制评分并保留旧字段兼容现有页面。"""

    context = context or {}
    normalize_issue_scopes(verified_result)
    profile_key = infer_document_type(
        extraction_result,
        str(context.get("document_type", "")),
    )
    scientific_score, scientific_dimensions = calculate_scientific_score(
        verified_result, profile_key
    )
    openness_score, openness_dimensions = calculate_openness_score(
        extraction_result, verified_result
    )
    confidence_score, confidence_dimensions = calculate_audit_confidence(
        verified_result, context
    )

    verified_result["score_breakdown"] = {
        "profile": profile_key,
        "profile_label": PROFILES[profile_key]["label"],
        "scientific_reproducibility": scientific_score,
        "resource_openness": openness_score,
        "audit_confidence": confidence_score,
        "scientific_dimensions": scientific_dimensions,
        "openness_dimensions": openness_dimensions,
        "confidence_dimensions": confidence_dimensions,
    }
    verified_result["reproducibility_score"] = scientific_score
    verified_result["resource_openness_score"] = openness_score
    verified_result["audit_confidence_score"] = confidence_score
    verified_result["dimension_scores"] = scientific_dimensions
    return verified_result
