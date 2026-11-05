"""Run the deterministic numeric-verification benchmark."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.numeric_verifier import verify_numeric_claims  # noqa: E402


def main() -> None:
    case_path = ROOT / "benchmarks" / "numeric_cases.json"
    cases = json.loads(case_path.read_text(encoding="utf-8"))
    claims = []
    for item in cases:
        claim = dict(item["claim"])
        claim["claim_id"] = item["id"]
        claims.append(claim)

    started_at = time.perf_counter()
    result = verify_numeric_claims(claims)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    observed = {
        item["claim_id"]: item["status"]
        for item in result["results"]
    }
    details = []
    passed = 0
    for case in cases:
        actual = observed.get(case["id"], "missing")
        matched = actual == case["expected_status"]
        passed += int(matched)
        details.append({
            "id": case["id"],
            "expected": case["expected_status"],
            "actual": actual,
            "matched": matched,
        })

    total = len(cases)
    report = {
        "benchmark": "deterministic_numeric_verifier",
        "case_count": total,
        "passed": passed,
        "failed": total - passed,
        "status_accuracy": round(passed / total, 4) if total else 0,
        "duration_ms": duration_ms,
        "scope_note": (
            "本结果仅评价Python数值核验工具，不代表完整智能体的提取、"
            "证据定位或问题发现准确率。"
        ),
        "details": details,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
