import json

from core.numeric_verifier import (
    verify_numeric_claims,
)


claims = [
    {
        "claim_id": "N001",
        "claim": (
            "以129.8623小时为基准，"
            "51.0934小时缩短约60.7%"
        ),
        "operation": "relative_decrease",
        "baseline": 129.8623,
        "result": 51.0934,
        "claimed_value": 60.7,
        "tolerance": 0.1,
        "page": 28,
        "unit": "%",
    },
    {
        "claim_id": "N002",
        "claim": (
            "以57.4796小时为基准，"
            "51.0934小时缩短约60.7%"
        ),
        "operation": "relative_decrease",
        "baseline": 57.4796,
        "result": 51.0934,
        "claimed_value": 60.7,
        "tolerance": 0.1,
        "page": 1,
        "unit": "%",
    },
    {
        "claim_id": "N003",
        "claim": (
            "57.4796小时变化0.4436小时，"
            "相对变化约0.7717%"
        ),
        "operation": "relative_increase",
        "baseline": 57.4796,
        "result": 57.9232,
        "claimed_value": 0.7717,
        "tolerance": 0.01,
        "page": 27,
        "unit": "%",
    },
]


result = verify_numeric_claims(
    claims
)


print(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )
)