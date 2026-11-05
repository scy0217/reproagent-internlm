import json

from core.agent_runtime import (
    run_agent_plan,
)
from core.planner import (
    create_fallback_plan,
)


sample_pages = [
    {
        "page_number": 1,
        "text": (
            "本文建立药材烘干模型。"
            "初始温度为28摄氏度，"
            "初始水分浓度为2.55 kg/kg。"
        ),
    },
    {
        "page_number": 2,
        "text": (
            "采用有限体积法和隐式时间推进，"
            "使用Python进行数值计算。"
        ),
    },
    {
        "page_number": 3,
        "text": (
            "固定半径烘干时间为57.48小时，"
            "考虑收缩后为51.09小时。"
        ),
    },
]


plan = create_fallback_plan(
    goal="检查论文实验可复现性"
)


def print_progress(event: dict):
    event_type = event.get(
        "event",
        "",
    )

    if event_type == "step_started":
        print(
            f"开始：{event['step_id']} "
            f"{event['tool']}"
        )

    elif event_type == "step_completed":
        print(
            f"完成：{event['step_id']} "
            f"耗时{event['duration_seconds']}秒"
        )

    elif event_type == "step_retry":
        print(
            f"重试：{event['step_id']} "
            f"{event['error']}"
        )

    elif event_type == "step_failed":
        print(
            f"失败：{event['step_id']} "
            f"{event['error']}"
        )

    elif event_type == "agent_finished":
        print(
            f"智能体结束："
            f"{event['status']}"
        )


initial_state = {
    "pages": sample_pages,
    "source_filename": "测试论文.pdf",
}


print("执行计划：")

print(
    json.dumps(
        plan,
        ensure_ascii=False,
        indent=2,
    )
)


print("\n开始运行智能体：")

result = run_agent_plan(
    plan=plan,
    initial_state=initial_state,
    max_retries=1,
    progress_callback=print_progress,
)


print("\n最终状态：")
print("status =", result["status"])

print(
    "completed_steps =",
    result["completed_steps"],
)

print(
    "failed_steps =",
    result["failed_steps"],
)


state = result["state"]

if "verified_result" in state:
    score = state[
        "verified_result"
    ].get(
        "reproducibility_score"
    )

    print(
        "最终评分 =",
        score,
    )


if "pdf_bytes" in state:
    print(
        "PDF字节数 =",
        len(state["pdf_bytes"]),
    )

    print(
        "PDF文件头正确 =",
        state["pdf_bytes"].startswith(
            b"%PDF"
        ),
    )


print("\n执行轨迹：")

for trace in result["execution_trace"]:
    print(
        json.dumps(
            trace,
            ensure_ascii=False,
            indent=2,
        )
    )