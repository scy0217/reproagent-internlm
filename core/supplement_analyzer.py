from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile


CODE_SUFFIXES = {
    ".py", ".ipynb", ".m", ".r", ".jl", ".cpp", ".c", ".java",
}
DEPENDENCY_NAMES = {
    "requirements.txt", "environment.yml", "environment.yaml",
    "pyproject.toml", "poetry.lock", "pipfile", "conda.yml",
}
ENTRYPOINT_NAMES = {
    "main.py", "app.py", "run.py", "train.py", "evaluate.py",
    "reproduce.py", "makefile",
}


def _normalise_name(name: str) -> str:
    return str(PurePosixPath(str(name).replace("\\", "/"))).lower()


def _inspect_names(names: list[str]) -> dict:
    normalised = [_normalise_name(name) for name in names if name]
    basenames = [PurePosixPath(name).name for name in normalised]
    code_files = [
        name for name in normalised
        if PurePosixPath(name).suffix in CODE_SUFFIXES
    ]
    return {
        "file_count": len(normalised),
        "code_file_count": len(code_files),
        "has_readme": any(name.startswith("readme") for name in basenames),
        "has_dependencies": any(name in DEPENDENCY_NAMES for name in basenames),
        "has_entrypoint": any(name in ENTRYPOINT_NAMES for name in basenames),
        "has_tests": any(
            "test" in PurePosixPath(name).name or "/tests/" in f"/{name}/"
            for name in normalised
        ),
        "sample_files": normalised[:30],
    }


def analyze_supplements(files: list[dict] | None) -> dict:
    """静态检查用户随附材料；绝不导入、执行或解压其中的代码。"""

    files = files or []
    names: list[str] = []
    warnings: list[str] = []

    for item in files:
        name = str(item.get("name", ""))
        content = item.get("content", b"") or b""
        names.append(name)
        if name.lower().endswith(".zip"):
            try:
                with ZipFile(BytesIO(content)) as archive:
                    archive_names = archive.namelist()
                    names.extend(archive_names[:5000])
                    if len(archive_names) > 5000:
                        warnings.append(
                            f"{name}包含超过5000个条目，仅检查前5000个。"
                        )
            except (BadZipFile, OSError, ValueError):
                warnings.append(f"无法读取压缩包目录：{name}")

    result = _inspect_names(names)
    result.update({
        "provided": bool(files),
        "package_count": len(files),
        "package_names": [str(item.get("name", "")) for item in files],
        "warnings": warnings,
        "inspection_mode": "static_file_listing_only",
    })

    if not files:
        result["completeness"] = "not_provided"
    elif result["code_file_count"] and result["has_readme"] and result["has_dependencies"]:
        result["completeness"] = "substantial"
    elif result["code_file_count"]:
        result["completeness"] = "partial"
    else:
        result["completeness"] = "documents_only"
    return result


def merge_supplement_analysis(
    extraction_result: dict,
    supplement_analysis: dict | None,
) -> dict:
    """把随附材料证据并入提取结果，但不冒充公开仓库。"""

    analysis = supplement_analysis or {}
    extraction_result["supplement_analysis"] = analysis
    if not analysis.get("provided"):
        return extraction_result

    code_info = dict(extraction_result.get("code_availability", {}) or {})
    if analysis.get("code_file_count", 0):
        existing_status = str(code_info.get("status", "unknown")).lower()
        if existing_status not in {"available", "yes", "public", "公开", "true"}:
            code_info["status"] = (
                "available" if analysis.get("completeness") == "substantial"
                else "partial"
            )
        code_info["submission_package"] = True
        code_info["submission_evidence"] = (
            f"用户随附上传{analysis.get('package_count', 0)}个材料包，"
            f"静态识别到{analysis.get('code_file_count', 0)}个代码文件。"
        )
    extraction_result["code_availability"] = code_info
    return extraction_result
