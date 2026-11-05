from __future__ import annotations


SUPPORTED_OPERATIONS = {
    "relative_decrease",
    "relative_increase",
    "percent_change",
    "difference",
    "absolute_difference",
    "ratio",
}


def to_number(value) -> float:
    """把模型输出的数字转换为float。"""

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        raise ValueError(
            f"无法转换为数字：{value}"
        )

    cleaned = (
        value.strip()
        .replace(",", "")
        .replace("%", "")
        .replace("小时", "")
        .replace("h", "")
        .strip()
    )

    return float(cleaned)


def calculate_value(
    operation: str,
    baseline: float,
    result: float,
) -> float:
    """使用Python执行确定性计算。"""

    if operation not in SUPPORTED_OPERATIONS:
        raise ValueError(
            f"不支持的计算类型：{operation}"
        )

    if operation in {
        "relative_decrease",
        "relative_increase",
        "percent_change",
        "ratio",
    }:
        if baseline == 0:
            raise ValueError(
                "基准值为0，无法进行相对计算。"
            )

    if operation == "relative_decrease":
        return (
            (baseline - result)
            / abs(baseline)
            * 100
        )

    if operation == "relative_increase":
        return (
            (result - baseline)
            / abs(baseline)
            * 100
        )

    if operation == "percent_change":
        return (
            (result - baseline)
            / abs(baseline)
            * 100
        )

    if operation == "difference":
        return result - baseline

    if operation == "absolute_difference":
        return abs(result - baseline)

    if operation == "ratio":
        return result / baseline

    raise ValueError(
        f"无法执行计算：{operation}"
    )


def verify_numeric_claim(
    claim: dict,
) -> dict:
    """核验一条数值主张。"""

    operation = str(
        claim.get("operation", "")
    ).strip()

    baseline = to_number(
        claim.get("baseline")
    )

    result = to_number(
        claim.get("result")
    )

    claimed_value = to_number(
        claim.get("claimed_value")
    )

    tolerance = to_number(
        claim.get("tolerance", 0.1)
    )

    calculated_value = calculate_value(
        operation=operation,
        baseline=baseline,
        result=result,
    )

    absolute_error = abs(
        calculated_value - claimed_value
    )

    passed = absolute_error <= tolerance

    return {
        "claim": claim.get(
            "claim",
            "",
        ),
        "operation": operation,
        "baseline": baseline,
        "result": result,
        "claimed_value": claimed_value,
        "calculated_value": round(
            calculated_value,
            6,
        ),
        "absolute_error": round(
            absolute_error,
            6,
        ),
        "tolerance": tolerance,
        "passed": passed,
        "status": (
            "consistent"
            if passed
            else "inconsistent"
        ),
        "page": claim.get(
            "page",
            0,
        ),
        "unit": claim.get(
            "unit",
            "",
        ),
    }


def verify_numeric_claims(
    claims: list[dict],
) -> dict:
    """批量核验数值主张。"""

    results = []

    for index, claim in enumerate(
        claims,
        start=1,
    ):
        try:
            result = verify_numeric_claim(
                claim
            )

            result["claim_id"] = (
                claim.get(
                    "claim_id",
                    f"N{index:03d}",
                )
            )

            results.append(result)

        except Exception as error:
            results.append(
                {
                    "claim_id": claim.get(
                        "claim_id",
                        f"N{index:03d}",
                    ),
                    "claim": claim.get(
                        "claim",
                        "",
                    ),
                    "status": "error",
                    "passed": False,
                    "error": str(error),
                    "page": claim.get(
                        "page",
                        0,
                    ),
                }
            )

    consistent_count = sum(
        1
        for result in results
        if result.get("status")
        == "consistent"
    )

    inconsistent_count = sum(
        1
        for result in results
        if result.get("status")
        == "inconsistent"
    )

    error_count = sum(
        1
        for result in results
        if result.get("status")
        == "error"
    )

    return {
        "total": len(results),
        "consistent_count": (
            consistent_count
        ),
        "inconsistent_count": (
            inconsistent_count
        ),
        "error_count": error_count,
        "results": results,
    }