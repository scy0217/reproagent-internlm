from core.tool_registry import (
    execute_tool,
    get_tool,
    list_tools,
)


print("已经注册的工具：")

for tool in list_tools():
    print(
        f"- {tool['name']}: "
        f"{tool['description']}"
    )


print("\n测试获取工具：")

extractor = get_tool(
    "experiment_extractor"
)

print("工具名称：", extractor.name)
print("输入：", extractor.input_keys)
print("输出：", extractor.output_keys)


print("\n测试未知工具拦截：")

try:
    get_tool("dangerous_tool")
except ValueError as error:
    print("成功拦截：", error)


print("\n测试PDF报告工具：")

sample_state = {
    "source_filename": "测试论文.pdf",
    "extraction_result": {
        "title": "测试科研论文",
        "research_goal": "验证工具注册表",
        "research_object": "科研审计工具",
        "methods": [
            "工具注册",
            "状态管理",
        ],
        "main_results": [
            "工具注册表工作正常"
        ],
    },
    "verified_result": {
        "reproducibility_score": 90,
        "verification_summary": (
            "测试报告生成正常。"
        ),
        "verified_issues": [],
        "rejected_issues": [],
        "verified_strengths": [
            "工具输出结构清晰"
        ],
    },
}

output = execute_tool(
    "pdf_report_generator",
    sample_state,
)

pdf_bytes = output["pdf_bytes"]

print(
    "PDF文件名：",
    output["pdf_filename"],
)

print(
    "PDF字节数：",
    len(pdf_bytes),
)

print(
    "PDF文件头正确：",
    pdf_bytes.startswith(b"%PDF"),
)