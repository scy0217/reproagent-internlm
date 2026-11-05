import json

from core.auditor import (
    audit_reproducibility,
)


pages = [
    {
        "page_number": 1,
        "text": (
            "固定半径条件下，烘干时间为"
            "129.8623小时。考虑尺寸收缩后，"
            "烘干时间为51.0934小时。"
            "论文声称烘干时间缩短约60.7%。"
        ),
    },
    {
        "page_number": 2,
        "text": (
            "另一组实验中，固定半径烘干时间"
            "为57.4796小时，收缩后为"
            "51.0934小时。"
        ),
    },
]


extraction_result = {
    "title": "药材烘干数值实验",
    "research_goal": (
        "研究尺寸收缩对烘干时间的影响"
    ),
    "research_object": "圆柱形药材",
    "materials_or_datasets": [],
    "methods": [
        "有限体积法",
    ],
    "models_or_algorithms": [
        "热湿传递模型",
    ],
    "key_parameters": [],
    "evaluation_metrics": [
        "烘干时间",
    ],
    "software_environment": [
        "Python",
    ],
    "hardware_environment": [],
    "code_availability": {
        "status": "unknown",
    },
    "main_results": [
        "烘干时间缩短约60.7%",
    ],
    "evidence": [],
}


result = audit_reproducibility(
    pages=pages,
    extraction_result=extraction_result,
)


print("数值主张：")

print(
    json.dumps(
        result.get(
            "numeric_claims",
            [],
        ),
        ensure_ascii=False,
        indent=2,
    )
)