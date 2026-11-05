from core.langgraph_runner import (
    run_langgraph_audit,
)


pages = [
    {
        "page_number": 1,
        "text": (
            "本文建立圆柱形药材烘干过程的"
            "一维径向热湿传递模型。"
            "药材初始温度为28摄氏度，"
            "初始水分浓度为2.55 kg/kg。"
        ),
    },
    {
        "page_number": 2,
        "text": (
            "模型采用有限体积法进行空间离散，"
            "使用隐式时间推进。"
            "数值计算使用Python和NumPy完成。"
        ),
    },
    {
        "page_number": 3,
        "text": (
            "固定半径条件下烘干时间为"
            "129.8623小时，考虑尺寸收缩后"
            "烘干时间为51.0934小时，"
            "烘干时间缩短约60.7%。"
        ),
    },
]


print(
    "开始运行LangGraph审计流程……"
)


result = run_langgraph_audit(
    pages=pages,
    source_filename=(
        "LangGraph测试论文.pdf"
    ),
)


print(
    "\n流程状态：",
    result.get("status"),
)

print(
    "提取结果存在：",
    "extraction_result" in result,
)

print(
    "初审结果存在：",
    "audit_result" in result,
)

print(
    "数值核验存在：",
    "numeric_verification_result"
    in result,
)

print(
    "复核结果存在：",
    "verified_result" in result,
)

print(
    "PDF生成成功：",
    bool(
        result.get("pdf_bytes")
    ),
)


print("\n执行轨迹：")

for item in result.get(
    "execution_trace",
    [],
):
    print(
        "-",
        item.get("event"),
        item.get("tool"),
    )