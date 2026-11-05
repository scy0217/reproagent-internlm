import json

from core.planner import (
    build_document_profile,
    create_audit_plan,
)


sample_pages = [
    {
        "page_number": 1,
        "text": (
            "本文研究药材烘干过程，"
            "建立热湿传递模型并进行数值实验。"
        ),
    },
    {
        "page_number": 2,
        "text": (
            "实验使用Python进行计算，"
            "设置初始温度28摄氏度，"
            "使用有限体积法求解方程。"
        ),
    },
    {
        "page_number": 3,
        "text": (
            "表1给出了不同条件下的烘干时间，"
            "结果分别为57.48小时和51.09小时。"
        ),
    },
]


profile = build_document_profile(sample_pages)

print("文档特征：")
print(
    json.dumps(
        profile,
        ensure_ascii=False,
        indent=2,
    )
)

plan = create_audit_plan(
    pages=sample_pages,
    user_goal=(
        "检查实验参数、数值结论和证据是否支持复现"
    ),
)

print("\n智能体计划：")
print(
    json.dumps(
        plan,
        ensure_ascii=False,
        indent=2,
    )
)