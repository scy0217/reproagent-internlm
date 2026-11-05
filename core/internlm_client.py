import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# 项目根目录下的 .env 文件
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

API_KEY = os.getenv("INTERNLM_API_KEY")
BASE_URL = os.getenv(
    "INTERNLM_BASE_URL",
    "https://chat.intern-ai.org.cn/api/v1/",
)
MODEL_NAME = os.getenv(
    "INTERNLM_MODEL",
    "intern-s2",
)


def call_model(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    thinking_mode: bool = False,
) -> str:
    """调用书生大模型并返回文本结果。"""

    if not API_KEY:
        raise RuntimeError(
            "没有找到 INTERNLM_API_KEY，请检查项目根目录的 .env 文件。"
        )

    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=120.0,
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.2,
        max_tokens=max_tokens,
        extra_body={
            "thinking_mode": thinking_mode,
        },
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError("模型返回了空内容。")

    return content