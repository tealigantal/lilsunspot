from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_PATHS = [
    ROOT / "AGENTS.md",
    ROOT / "TASKS.md",
    ROOT / "lilsunspot",
    ROOT / "scripts" / "check.ps1",
    ROOT / "scripts" / "guard_no_secrets.py",
]
EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "target",
}
EXCLUDED_RELATIVE_PREFIXES = {
    ("lilsunspot", "desktop", "src-tauri", "binaries"),
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".exe", ".dll"}
EXCLUDED_PREFIXES = {
    Path("lilsunspot/desktop/src-tauri/binaries/lilsunspotd/_internal"),
}

PATTERNS = [
    ("openai_style_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[opsu]_[A-Za-z0-9_]{30,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("lilsunspot_runtime_token", re.compile(r'"token"\s*:\s*"[A-Za-z0-9_-]{32,}"')),
]


def iter_files(path: Path):
    if not path.exists():
        return
    if path.is_file():
        yield path
        return
    for child in path.rglob("*"):
        if child.is_dir():
            continue
        relative_path = child.relative_to(ROOT)
        if any(relative_path == prefix or prefix in relative_path.parents for prefix in EXCLUDED_PREFIXES):
            continue
        relative_parts = set(relative_path.parts)
        if relative_parts & EXCLUDED_DIRS:
            continue
        if any(relative_path.parts[: len(prefix)] == prefix for prefix in EXCLUDED_RELATIVE_PREFIXES):
            continue
        if child.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield child


def scan_file(path: Path) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append((line_no, name))
    return findings


def main() -> int:
    findings: list[tuple[Path, int, str]] = []
    for scan_path in SCAN_PATHS:
        for file_path in iter_files(scan_path):
            for line_no, pattern_name in scan_file(file_path):
                findings.append((file_path, line_no, pattern_name))

    if findings:
        print("Secret-like values were found. Values are not printed.")
        for file_path, line_no, pattern_name in findings:
            print(f"{file_path.relative_to(ROOT)}:{line_no}: {pattern_name}")
        return 1

    print("No secret-like values found in lilsunspot task scope.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
