"""Run deterministic deployment checks without calling the model API."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FILES = (
    "app.py",
    "requirements.txt",
    "packages.txt",
    ".streamlit/config.toml",
    "README.md",
)
SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|secret)\s*=\s*['\"][A-Za-z0-9_-]{20,}['\"]"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
)


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def main() -> None:
    for relative_path in REQUIRED_FILES:
        if not (ROOT / relative_path).is_file():
            fail(f"缺少部署文件：{relative_path}")

    python_files = sorted(
        path for path in ROOT.rglob("*.py")
        if not any(part.startswith(".") for part in path.relative_to(ROOT).parts)
    )
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            fail(f"Python语法错误：{path.relative_to(ROOT)}:{error.lineno}")
    print(f"[OK] Python语法检查：{len(python_files)}个文件")

    scanned_files = [
        path for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and path.suffix.lower() in {".py", ".md", ".txt", ".toml", ".yml", ".yaml"}
    ]
    for path in scanned_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.name == ".env.example":
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            fail(f"疑似硬编码密钥：{path.relative_to(ROOT)}")
    print(f"[OK] 密钥扫描：{len(scanned_files)}个文本文件")

    if (ROOT / ".git").exists():
        for secret_path in (".env", ".streamlit/secrets.toml"):
            result = subprocess.run(
                ["git", "check-ignore", "-q", secret_path],
                cwd=ROOT,
                check=False,
            )
            if result.returncode != 0:
                fail(f"敏感文件未被Git忽略：{secret_path}")
        print("[OK] Git敏感文件忽略规则")

    if not os.getenv("INTERNLM_API_KEY"):
        print("[WARN] 当前未设置INTERNLM_API_KEY；部署时必须通过Secrets注入")
    else:
        print("[OK] INTERNLM_API_KEY已通过环境变量提供（值未显示）")

    print("[PASS] ReproAgent部署预检完成")


if __name__ == "__main__":
    main()
