from copy import deepcopy
from time import perf_counter
from typing import Callable

from core.tool_registry import (
    get_tool,
    execute_tool,
)


ProgressCallback = Callable[[dict], None]


def summarize_value(value) -> str:
    """生成适合执行日志展示的摘要。"""

    if isinstance(value, bytes):
        return f"PDF二进制数据，共{len(value)}字节"

    if isinstance(value, dict):
        return (
            f"字典，包含{len(value)}个字段："
            + "、".join(
                list(value.keys())[:8]
            )
        )

    if isinstance(value, list):
        return f"列表，共{len(value)}项"

    if isinstance(value, str):
        text = value.replace(
            "\n",
            " ",
        )

        if len(text) > 100:
            text = text[:100] + "……"

        return text

    return str(value)


def summarize_outputs(
    outputs: dict,
) -> dict:
    """避免把PDF字节等大型数据写进日志。"""

    return {
        key: summarize_value(value)
        for key, value in outputs.items()
    }


def notify(
    callback: ProgressCallback | None,
    event: dict,
) -> None:
    """向界面发送执行进度。"""

    if callback is not None:
        callback(event)


def validate_runtime_plan(
    plan: dict,
) -> list[dict]:
    """执行前检查计划结构和工具安全性。"""

    if not isinstance(plan, dict):
        raise ValueError("执行计划必须是字典。")

    steps = plan.get("steps", [])

    if not isinstance(steps, list):
        raise ValueError(
            "执行计划中的steps必须是列表。"
        )

    if not steps:
        raise ValueError(
            "执行计划中没有任何步骤。"
        )

    validated_steps = []
    seen_ids = set()

    for raw_step in steps:
        if not isinstance(raw_step, dict):
            continue

        step_id = str(
            raw_step.get("id", "")
        ).strip()

        tool_name = str(
            raw_step.get("tool", "")
        ).strip()

        if not step_id:
            raise ValueError(
                "执行步骤缺少id。"
            )

        if step_id in seen_ids:
            raise ValueError(
                f"执行步骤id重复：{step_id}"
            )

        # 确认工具已经安全注册
        get_tool(tool_name)

        dependencies = raw_step.get(
            "depends_on",
            [],
        )

        if not isinstance(
            dependencies,
            list,
        ):
            raise ValueError(
                f"步骤{step_id}的depends_on不是列表。"
            )

        unknown_dependencies = [
            dependency
            for dependency in dependencies
            if dependency not in seen_ids
        ]

        if unknown_dependencies:
            raise ValueError(
                f"步骤{step_id}存在无效依赖："
                f"{unknown_dependencies}"
            )

        validated_steps.append(
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

    if not validated_steps:
        raise ValueError(
            "计划中没有有效步骤。"
        )

    return validated_steps


def run_agent_plan(
    plan: dict,
    initial_state: dict,
    max_retries: int = 1,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """
    按照Planner计划执行工具。

    返回：
    {
        "status": "completed/partial/failed",
        "state": 最终状态,
        "execution_trace": 执行日志,
        "completed_steps": [],
        "failed_steps": []
    }
    """

    steps = validate_runtime_plan(plan)

    state = deepcopy(initial_state)
    state["agent_plan"] = deepcopy(plan)
    state["document_type"] = plan.get(
        "document_type",
        "general",
    )
    execution_trace = []

    completed_steps = set()
    failed_steps = set()

    agent_status = "completed"

    notify(
        progress_callback,
        {
            "event": "agent_started",
            "total_steps": len(steps),
            "goal": plan.get("goal", ""),
        },
    )

    for step_index, step in enumerate(
        steps,
        start=1,
    ):
        step_id = step["id"]
        tool_name = step["tool"]

        missing_dependencies = [
            dependency
            for dependency in step["depends_on"]
            if dependency not in completed_steps
        ]

        if missing_dependencies:
            trace = {
                "step_index": step_index,
                "step_id": step_id,
                "tool": tool_name,
                "reason": step["reason"],
                "status": "skipped",
                "attempts": 0,
                "duration_seconds": 0,
                "error": (
                    "依赖步骤未完成："
                    + "、".join(
                        missing_dependencies
                    )
                ),
            }

            execution_trace.append(trace)
            failed_steps.add(step_id)

            notify(
                progress_callback,
                {
                    "event": "step_skipped",
                    **trace,
                },
            )

            if step["required"]:
                agent_status = "failed"
                break

            agent_status = "partial"
            continue

        tool = get_tool(tool_name)

        notify(
            progress_callback,
            {
                "event": "step_started",
                "step_index": step_index,
                "total_steps": len(steps),
                "step_id": step_id,
                "tool": tool_name,
                "reason": step["reason"],
            },
        )

        step_start = perf_counter()
        step_succeeded = False
        last_error = ""

        for attempt in range(
            1,
            max_retries + 2,
        ):
            try:
                outputs = execute_tool(
                    tool_name=tool_name,
                    state=state,
                )

                state.update(outputs)

                duration = (
                    perf_counter()
                    - step_start
                )

                trace = {
                    "step_index": step_index,
                    "step_id": step_id,
                    "tool": tool_name,
                    "reason": step["reason"],
                    "status": "success",
                    "attempts": attempt,
                    "duration_seconds": round(
                        duration,
                        3,
                    ),
                    "input_keys": list(
                        tool.input_keys
                    ),
                    "output_summary": (
                        summarize_outputs(
                            outputs
                        )
                    ),
                    "error": "",
                }

                execution_trace.append(trace)
                completed_steps.add(step_id)
                step_succeeded = True

                notify(
                    progress_callback,
                    {
                        "event": "step_completed",
                        **trace,
                    },
                )

                break

            except Exception as error:
                last_error = str(error)

                notify(
                    progress_callback,
                    {
                        "event": "step_retry",
                        "step_id": step_id,
                        "tool": tool_name,
                        "attempt": attempt,
                        "error": last_error,
                    },
                )

        if not step_succeeded:
            duration = (
                perf_counter()
                - step_start
            )

            trace = {
                "step_index": step_index,
                "step_id": step_id,
                "tool": tool_name,
                "reason": step["reason"],
                "status": "failed",
                "attempts": max_retries + 1,
                "duration_seconds": round(
                    duration,
                    3,
                ),
                "input_keys": list(
                    tool.input_keys
                ),
                "output_summary": {},
                "error": last_error,
            }

            execution_trace.append(trace)
            failed_steps.add(step_id)

            notify(
                progress_callback,
                {
                    "event": "step_failed",
                    **trace,
                },
            )

            if step["required"]:
                agent_status = "failed"
                break

            agent_status = "partial"

    result = {
        "status": agent_status,
        "state": state,
        "execution_trace": execution_trace,
        "completed_steps": sorted(
            completed_steps
        ),
        "failed_steps": sorted(
            failed_steps
        ),
    }

    notify(
        progress_callback,
        {
            "event": "agent_finished",
            "status": agent_status,
            "completed_steps": result[
                "completed_steps"
            ],
            "failed_steps": result[
                "failed_steps"
            ],
        },
    )

    return result
