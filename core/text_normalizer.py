from __future__ import annotations

import re
import unicodedata
import json


SUPERSCRIPT_MAP = str.maketrans({
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁺": "+", "⁻": "-", "⁼": "=", "⁽": "(", "⁾": ")",
})
SUBSCRIPT_MAP = str.maketrans({
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "₊": "+", "₋": "-", "₌": "=", "₍": "(", "₎": ")",
})

SUPERSCRIPT_PATTERN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾]+")
SUBSCRIPT_PATTERN = re.compile(r"[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎]+")
BROKEN_GLYPH = r"[□�▯]"


def normalize_scientific_text(value: object) -> str:
    """将容易缺字的科学符号转换为跨字体稳定的纯文本。"""

    text = unicodedata.normalize("NFC", str(value))
    text = SUPERSCRIPT_PATTERN.sub(
        lambda match: "^" + match.group(0).translate(SUPERSCRIPT_MAP),
        text,
    )
    text = SUBSCRIPT_PATTERN.sub(
        lambda match: "_" + match.group(0).translate(SUBSCRIPT_MAP),
        text,
    )
    text = text.translate(str.maketrans({
        "−": "-",  # 数学负号
        "–": "-",  # en dash
        "◦": "°",  # 常见PDF温度符号误用
        "µ": "μ",  # 统一微符号
        "\u00a0": " ",
    }))
    # 某些PDF缺少ToUnicode映射，指数负号会被提取成真正的方框。
    # 仅修复上下文能够唯一确定的形式；不猜测缺失的指数数字。
    text = re.sub(
        rf"10{BROKEN_GLYPH}\^(\d+)",
        r"10^(-\1)",
        text,
    )
    text = re.sub(
        rf"10{BROKEN_GLYPH}(\d+)",
        r"10^(-\1)",
        text,
    )
    text = re.sub(
        rf"(10\^\(-\d+\)){BROKEN_GLYPH}(?=10\^\(-\d+\))",
        r"\1~",
        text,
    )
    text = re.sub(
        rf"(10\^-\d+){BROKEN_GLYPH}(?=10\^-\d+)",
        r"\1~",
        text,
    )
    text = re.sub(
        rf"10{BROKEN_GLYPH}+",
        "10^[指数识别失败]",
        text,
    )
    text = re.sub(BROKEN_GLYPH, "[符号识别失败]", text)
    text = re.sub(
        r"(?<!\d)10-(\d{1,3})(?=\s*(?:[A-Za-zμ°/]|$))",
        r"10^(-\1)",
        text,
    )
    return "".join(
        character
        for character in text
        if character in "\n\t" or unicodedata.category(character) != "Cc"
    )


def normalize_structure(value):
    """递归规范模型JSON中的字符串，同时保持数字与布尔值类型。"""

    if isinstance(value, str):
        return normalize_scientific_text(value)
    if isinstance(value, list):
        return [normalize_structure(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_structure(item) for item in value)
    if isinstance(value, dict):
        return {
            key: normalize_structure(item)
            for key, item in value.items()
        }
    return value


def quarantine_broken_symbol_issues(result: dict) -> dict:
    """把依赖损坏字符的问题移出“已确认”，防止乱码被当作证据。"""

    normalized = normalize_structure(result)
    reliable = []
    rejected = list(normalized.get("rejected_issues", []) or [])
    for issue in normalized.get("verified_issues", []) or []:
        issue_text = json.dumps(issue, ensure_ascii=False)
        if any(
            marker in issue_text
            for marker in ("[指数识别失败]", "[符号识别失败]")
        ):
            rejected.append({
                "title": issue.get("title", "含损坏符号的问题"),
                "reason": (
                    "原文字符映射损坏，当前证据不足以确认该问题；"
                    "需要回看原PDF或进行公式OCR。"
                ),
            })
        else:
            reliable.append(issue)
    normalized["verified_issues"] = reliable
    normalized["rejected_issues"] = rejected
    return normalized
