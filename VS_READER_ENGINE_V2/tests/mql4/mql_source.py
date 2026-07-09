from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MQL4_INCLUDE_DIR = REPO_ROOT / "mql4" / "Include"
MQL4_EXPERTS_DIR = REPO_ROOT / "mql4" / "Experts"


def load_mqh(filename: str) -> str:
    path = MQL4_INCLUDE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"missing mql4 include file: {path}")
    return path.read_text(encoding="utf-8")


def load_mq4(filename: str) -> str:
    path = MQL4_EXPERTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"missing mql4 expert file: {path}")
    return path.read_text(encoding="utf-8")


def parse_define(source: str, name: str) -> str:
    match = re.search(rf"#define\s+{re.escape(name)}\s+\"([^\"]*)\"", source)
    if match is None:
        raise ValueError(f"missing define: {name}")
    return match.group(1).replace("\\\\", "\\")


def public_function_names(source: str) -> list[str]:
    pattern = re.compile(
        r"^(?:void|bool|string|int|double|datetime)\s+(SYSTEM_[A-Za-z0-9_]+)\s*\(",
        re.MULTILINE,
    )
    return pattern.findall(source)


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?:void|bool|string|int|double|datetime)\s+{re.escape(name)}\s*\([^{{]*\)\s*\{{",
        source,
    )
    if match is None:
        raise ValueError(f"missing function: {name}")

    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise ValueError(f"unterminated function body: {name}")
