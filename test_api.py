from core.internlm_client import call_model


result = call_model(
    system_prompt="你是一名严谨的科研助手。",
    user_prompt=(
        "请用不超过50个汉字说明科研论文可复现性为什么重要。"
        "只输出最终中文答案。"
    ),
    max_tokens=512,
    thinking_mode=False,
)

print("书生模型回复：")
print(result)