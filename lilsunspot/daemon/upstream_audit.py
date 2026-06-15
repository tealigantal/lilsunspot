from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_UPSTREAM_REF = "upstream/main"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_git(repo_root: Path, args: list[str], *, allow_failure: bool = False) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 and not allow_failure:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _git_file(repo_root: Path, revision: str, path: str) -> str:
    return _run_git(repo_root, ["show", f"{revision}:{path}"])


def _local_file(repo_root: Path, path: str) -> str:
    return (repo_root / path).read_text(encoding="utf-8")


def _assignment_value(source: str, assignment_name: str) -> ast.AST | None:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == assignment_name:
                return node.value
    return None


def _dict_assignment_keys(source: str, assignment_name: str) -> set[str]:
    value = _assignment_value(source, assignment_name)
    if not isinstance(value, ast.Dict):
        return set()
    keys: set[str] = set()
    for key in value.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return keys


def _configurable_toolset_names(source: str) -> set[str]:
    value = _assignment_value(source, "CONFIGURABLE_TOOLSETS")
    if not isinstance(value, (ast.List, ast.Tuple)):
        return set()
    names: set[str] = set()
    for item in value.elts:
        if not isinstance(item, (ast.List, ast.Tuple)) or not item.elts:
            continue
        first = item.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names.add(first.value)
    return names


def _read_recorded_base(repo_root: Path) -> str:
    path = repo_root / "lilsunspot" / "UPSTREAM_COMMIT.txt"
    try:
        return next(
            (line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()),
            "",
        )
    except OSError:
        return ""


def _dirty_status(repo_root: Path) -> list[str]:
    output = _run_git(repo_root, ["status", "--short"], allow_failure=True)
    return [line for line in output.splitlines() if line.strip()]


def build_upstream_capability_audit(
    repo_root: Path | None = None,
    *,
    upstream_ref: str = DEFAULT_UPSTREAM_REF,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    recorded_base = _read_recorded_base(root)
    latest_commit = _run_git(root, ["rev-parse", "--verify", f"{upstream_ref}^{{commit}}"])

    current_toolsets_source = _local_file(root, "toolsets.py")
    upstream_toolsets_source = _git_file(root, upstream_ref, "toolsets.py")
    current_tools_config_source = _local_file(root, "hermes_cli/tools_config.py")
    upstream_tools_config_source = _git_file(root, upstream_ref, "hermes_cli/tools_config.py")
    current_config_source = _local_file(root, "hermes_cli/config.py")
    upstream_config_source = _git_file(root, upstream_ref, "hermes_cli/config.py")

    current_toolsets = _dict_assignment_keys(current_toolsets_source, "TOOLSETS")
    upstream_toolsets = _dict_assignment_keys(upstream_toolsets_source, "TOOLSETS")
    current_configurable = _configurable_toolset_names(current_tools_config_source)
    upstream_configurable = _configurable_toolset_names(upstream_tools_config_source)
    current_default_config = _dict_assignment_keys(current_config_source, "DEFAULT_CONFIG")
    upstream_default_config = _dict_assignment_keys(upstream_config_source, "DEFAULT_CONFIG")

    dirty_entries = _dirty_status(root)
    missing_toolsets = sorted(upstream_toolsets - current_toolsets)
    missing_configurable = sorted(upstream_configurable - current_configurable)
    missing_default_config = sorted(upstream_default_config - current_default_config)
    missing_capability_mappings = sorted(set(missing_toolsets) | set(missing_configurable))

    return {
        "available": True,
        "remote_ref": upstream_ref,
        "latest_commit": latest_commit,
        "recorded_base": recorded_base,
        "recorded_base_matches_latest": bool(recorded_base and recorded_base == latest_commit),
        "working_tree_dirty": bool(dirty_entries),
        "dirty_entry_count": len(dirty_entries),
        "sync_eligible": bool((not dirty_entries) and recorded_base and recorded_base != latest_commit),
        "missing_toolsets": missing_toolsets,
        "missing_configurable_toolsets": missing_configurable,
        "missing_capability_mappings": missing_capability_mappings,
        "missing_default_config_keys": missing_default_config,
        "missing_config_mappings": missing_default_config,
        "current_counts": {
            "toolsets": len(current_toolsets),
            "configurable_toolsets": len(current_configurable),
            "default_config_keys": len(current_default_config),
        },
        "upstream_counts": {
            "toolsets": len(upstream_toolsets),
            "configurable_toolsets": len(upstream_configurable),
            "default_config_keys": len(upstream_default_config),
        },
    }


def safe_upstream_capability_audit(
    repo_root: Path | None = None,
    *,
    upstream_ref: str = DEFAULT_UPSTREAM_REF,
) -> dict[str, Any]:
    try:
        return build_upstream_capability_audit(repo_root, upstream_ref=upstream_ref)
    except Exception as exc:  # noqa: BLE001 - this powers a diagnostic endpoint
        return {
            "available": False,
            "remote_ref": upstream_ref,
            "latest_commit": "",
            "recorded_base": _read_recorded_base(repo_root or _repo_root()),
            "recorded_base_matches_latest": False,
            "working_tree_dirty": None,
            "dirty_entry_count": None,
            "sync_eligible": False,
            "missing_toolsets": [],
            "missing_configurable_toolsets": [],
            "missing_capability_mappings": [],
            "missing_default_config_keys": [],
            "missing_config_mappings": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare local lilsunspot capability surface with cached Hermes upstream.")
    parser.add_argument("--repo-root", default="", help="Repository root. Defaults to the current lilsunspot checkout.")
    parser.add_argument("--upstream-ref", default=DEFAULT_UPSTREAM_REF, help="Git ref to compare against.")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else _repo_root()
    payload = build_upstream_capability_audit(root, upstream_ref=args.upstream_ref)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
