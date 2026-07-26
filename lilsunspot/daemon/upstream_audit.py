from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_UPSTREAM_REF = "upstream/main"
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ARCHIVE_SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
PARITY_MAPPING_FIELDS = (
    "owner",
    "product_entry",
    "config_source",
    "safety_policy",
    "packaging_status",
    "validation_method",
)
PARITY_REFERENCE_FIELDS = {"product_entry", "config_source", "safety_policy", "validation_method"}
PARITY_PACKAGING_STATES = {
    "not_assessed",
    "blocked_not_merged",
    "not_packaged",
    "packaged_unverified",
    "verified_installed",
}
PARITY_EVIDENCE_STATES = {"unassessed", "not_required", "verified"}
PARITY_FINAL_STATES = {
    "verified_available",
    "verified_after_configuration",
    "platform_limited_with_solution",
    "upstream_unavailable",
}


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


def _source_file(repo_root: Path, revision: str, snapshot_root: Path | None, path: str) -> str:
    if snapshot_root is not None:
        return _local_file(snapshot_root, path)
    return _git_file(repo_root, revision, path)


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


def _relative_matches(root: Path, pattern: str) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.glob(pattern) if path.is_file())


def _literal_keyword(call: ast.Call, name: str) -> str:
    for keyword in call.keywords:
        if keyword.arg != name:
            continue
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return ""


def _registered_builtin_tools(snapshot_root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    tools_root = snapshot_root / "tools"
    registered: dict[str, dict[str, str]] = {}
    duplicate_names: set[str] = set()
    skipped_dynamic_registrations = 0
    if not tools_root.is_dir():
        return [], {
            "method": "static_literal_top_level_registry_register",
            "complete": False,
            "skipped_dynamic_registrations": 0,
            "duplicate_names": [],
            "limitations": ["tools directory is unavailable"],
        }
    for source_path in sorted(tools_root.glob("*.py")):
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "register":
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "registry":
                continue
            tool_name = _literal_keyword(node, "name")
            if not tool_name:
                skipped_dynamic_registrations += 1
                continue
            if tool_name in registered:
                duplicate_names.add(tool_name)
            registered[tool_name] = {
                "name": tool_name,
                "toolset": _literal_keyword(node, "toolset"),
                "source": source_path.relative_to(snapshot_root).as_posix(),
            }
    return [registered[name] for name in sorted(registered)], {
        "method": "static_literal_top_level_registry_register",
        "complete": False,
        "skipped_dynamic_registrations": skipped_dynamic_registrations,
        "duplicate_names": sorted(duplicate_names),
        "limitations": [
            "runtime plugin and MCP registrations are separate inventory surfaces",
            "dynamic or wrapped registry calls require runtime enumeration after merge",
            "an empty literal toolset requires runtime ownership resolution",
        ],
    }


def _plugin_category(relative_manifest: str) -> str:
    parts = Path(relative_manifest).parts
    if len(parts) < 2:
        return "uncategorized"
    if len(parts) >= 3:
        return parts[1]
    return "flat"


def _yaml_scalar(path: Path, field: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""
    match = re.search(rf"(?m)^{re.escape(field)}:\s*['\"]?([^'\"#\r\n]+?)['\"]?\s*$", text)
    return match.group(1).strip() if match else ""


def _named_manifest_records(snapshot_root: Path, relative_paths: list[str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for relative_path in relative_paths:
        path = snapshot_root / relative_path
        name = _yaml_scalar(path, "name")
        if not name:
            raise ValueError("capability manifest source is missing a canonical name")
        records.append(
            {
                "name": name,
                "kind": _yaml_scalar(path, "kind") or _plugin_category(relative_path),
                "category": _plugin_category(relative_path),
                "source": relative_path,
            }
        )
    return records


def _skill_records(snapshot_root: Path, relative_paths: list[str], scope: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for relative_path in relative_paths:
        name = _yaml_scalar(snapshot_root / relative_path, "name")
        if not name:
            raise ValueError("skill frontmatter is missing a canonical name")
        records.append({"name": name, "scope": scope, "source": relative_path})
    return records


def _platform_enum_values(snapshot_root: Path) -> dict[str, str]:
    path = snapshot_root / "gateway" / "config.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "Platform":
            continue
        values: dict[str, str] = {}
        for item in node.body:
            if not isinstance(item, (ast.Assign, ast.AnnAssign)):
                continue
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            value = item.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value.value
        return values
    return {}


def _gateway_builtin_adapters(snapshot_root: Path) -> list[dict[str, str]]:
    platforms_root = snapshot_root / "gateway" / "platforms"
    adapters: list[dict[str, str]] = []
    platform_values = _platform_enum_values(snapshot_root)
    if not platforms_root.is_dir():
        return adapters
    for source_path in sorted(platforms_root.rglob("*.py")):
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name == "BasePlatformAdapter":
                continue
            base_names = {
                base.id
                for base in node.bases
                if isinstance(base, ast.Name)
            }
            if "BasePlatformAdapter" not in base_names:
                continue
            platform_constants = {
                child.attr
                for child in ast.walk(node)
                if isinstance(child, ast.Attribute)
                and isinstance(child.value, ast.Name)
                and child.value.id == "Platform"
                and child.attr in platform_values
            }
            if len(platform_constants) != 1:
                raise ValueError("gateway adapter does not resolve to exactly one canonical platform key")
            platform = platform_values[next(iter(platform_constants))]
            adapters.append(
                {
                    "platform": platform,
                    "class": node.name,
                    "module": source_path.stem,
                    "source": source_path.relative_to(snapshot_root).as_posix(),
                }
            )
    return sorted(adapters, key=lambda item: item["platform"])


def _plugin_gateway_platforms(snapshot_root: Path) -> list[dict[str, str]]:
    platforms_root = snapshot_root / "plugins" / "platforms"
    records: list[dict[str, str]] = []
    if not platforms_root.is_dir():
        return records
    for source_path in sorted(platforms_root.rglob("*.py")):
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function_name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if function_name not in {"PlatformEntry", "register_platform"}:
                continue
            platform = _literal_keyword(node, "name")
            if platform:
                records.append(
                    {
                        "platform": platform,
                        "source": source_path.relative_to(snapshot_root).as_posix(),
                    }
                )
    unique = {record["platform"]: record for record in records}
    if len(unique) != len(records):
        raise ValueError("plugin platform registry contains duplicate canonical keys")
    return [unique[name] for name in sorted(unique)]


def _provider_transports(snapshot_root: Path) -> list[dict[str, str]]:
    transports_root = snapshot_root / "agent" / "transports"
    records: list[dict[str, str]] = []
    if not transports_root.is_dir():
        return records
    for source_path in sorted(transports_root.glob("*.py")):
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name == "ProviderTransport":
                continue
            if not any(isinstance(base, ast.Name) and base.id == "ProviderTransport" for base in node.bases):
                continue
            stem = node.name.removesuffix("Transport")
            key = re.sub(r"(?<!^)(?=[A-Z])", "_", stem).lower()
            records.append(
                {
                    "key": key,
                    "name": node.name,
                    "module": source_path.stem,
                    "source": source_path.relative_to(snapshot_root).as_posix(),
                }
            )
    return sorted(records, key=lambda item: item["name"])


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _update_tree_digest(digest: Any, relative_path: str, handle: Any) -> None:
    digest.update(relative_path.encode("utf-8"))
    digest.update(b"\0")
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    digest.update(b"\0")


def _directory_tree_digest(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    ]
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        with path.open("rb") as handle:
            _update_tree_digest(digest, path.relative_to(root).as_posix(), handle)
    return digest.hexdigest().upper(), len(files)


def _archive_tree_digest(archive_path: Path, expected_root: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    file_count = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        members: list[tuple[str, tarfile.TarInfo]] = []
        roots: set[str] = set()
        for member in archive.getmembers():
            parts = Path(member.name).parts
            if parts:
                roots.add(parts[0])
            if not member.isfile():
                continue
            if len(parts) < 2 or ".git" in parts[1:]:
                continue
            members.append((Path(*parts[1:]).as_posix(), member))
        if roots != {expected_root}:
            raise ValueError("snapshot archive root does not match the recorded target")
        for relative_path, member in sorted(members, key=lambda item: item[0]):
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError("snapshot archive contains an unreadable regular file")
            with handle:
                _update_tree_digest(digest, relative_path, handle)
            file_count += 1
    return digest.hexdigest().upper(), file_count


def _verify_snapshot_binding(
    snapshot_root: Path,
    target_commit: str,
    snapshot_archive: Path | None,
    snapshot_record: Path | None,
) -> dict[str, Any]:
    if not COMMIT_SHA_RE.fullmatch(target_commit):
        raise ValueError("target_commit must be a lowercase 40-character commit SHA")
    if snapshot_archive is None or not snapshot_archive.is_file():
        raise ValueError("snapshot archive is required and must exist")
    if snapshot_record is None or not snapshot_record.is_file():
        raise ValueError("snapshot record is required and must exist")
    try:
        record = json.loads(snapshot_record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("snapshot record is not valid JSON") from exc
    if record.get("schema_version") != 1:
        raise ValueError("snapshot record schema is unsupported")
    if record.get("repository") != "NousResearch/hermes-agent":
        raise ValueError("snapshot record repository is not the Hermes official repository")
    if record.get("target_commit") != target_commit:
        raise ValueError("snapshot record target does not match target_commit")
    expected_root = f"NousResearch-hermes-agent-{target_commit[:7]}"
    if record.get("archive_root") != expected_root:
        raise ValueError("snapshot record archive root does not match target_commit")
    expected_archive_sha256 = str(record.get("archive_sha256", "")).upper()
    if not ARCHIVE_SHA256_RE.fullmatch(expected_archive_sha256):
        raise ValueError("snapshot record archive SHA-256 is invalid")
    if snapshot_root.name != expected_root:
        raise ValueError("snapshot directory does not identify the fixed target")
    actual_archive_sha256 = _sha256_file(snapshot_archive)
    if actual_archive_sha256 != expected_archive_sha256:
        raise ValueError("snapshot archive SHA-256 does not match the operator record")
    archive_tree_sha256, archive_file_count = _archive_tree_digest(snapshot_archive, expected_root)
    directory_tree_sha256, directory_file_count = _directory_tree_digest(snapshot_root)
    if archive_file_count != directory_file_count or archive_tree_sha256 != directory_tree_sha256:
        raise ValueError("extracted snapshot tree does not match the operator-recorded archive")
    return {
        "assurance": "operator_recorded_archive_integrity",
        "repository": record["repository"],
        "archive_root": expected_root,
        "archive_sha256": actual_archive_sha256,
        "tree_sha256": directory_tree_sha256,
        "file_count": directory_file_count,
    }


def _snapshot_inventory(snapshot_root: Path) -> dict[str, Any]:
    plugin_manifests = _relative_matches(snapshot_root, "plugins/**/plugin.yaml")
    builtin_skills = _relative_matches(snapshot_root, "skills/**/SKILL.md")
    optional_skills = _relative_matches(snapshot_root, "optional-skills/**/SKILL.md")
    plugin_categories = Counter(_plugin_category(path) for path in plugin_manifests)
    builtin_tools, builtin_tool_scan = _registered_builtin_tools(snapshot_root)
    provider_transports = _provider_transports(snapshot_root)
    return {
        "builtin_tools": builtin_tools,
        "builtin_tool_scan": builtin_tool_scan,
        "plugin_manifests": plugin_manifests,
        "plugin_records": _named_manifest_records(snapshot_root, plugin_manifests),
        "plugin_categories": dict(sorted(plugin_categories.items())),
        "builtin_skills": builtin_skills,
        "builtin_skill_records": _skill_records(snapshot_root, builtin_skills, "builtin"),
        "optional_skills": optional_skills,
        "optional_skill_records": _skill_records(snapshot_root, optional_skills, "optional"),
        "optional_mcp_manifests": _relative_matches(snapshot_root, "optional-mcps/**/manifest.yaml"),
        "gateway_builtin_adapters": _gateway_builtin_adapters(snapshot_root),
        "gateway_plugin_platforms": _plugin_gateway_platforms(snapshot_root),
        "provider_transports": provider_transports,
        "transport_modules": sorted(record["module"] for record in provider_transports),
    }


def _capability_rows(
    toolsets: set[str],
    configurable_toolsets: set[str],
    default_config_keys: set[str],
    inventory: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(capability_id: str, kind: str, source: str, metadata: dict[str, Any] | None = None) -> None:
        rows.append(
            {
                "id": capability_id,
                "kind": kind,
                "upstream": {"source": source, **(metadata or {})},
                "mapping": {
                    "owner": None,
                    "product_entry": [],
                    "config_source": [],
                    "safety_policy": [],
                    "packaging_status": "not_assessed",
                    "validation_method": [],
                },
                "mapping_status": "unspecified",
                "parity_status": None,
                "readiness": "needs_validation",
                "evidence": {
                    "bundle_contains": False,
                    "installed_discoverable": False,
                    "installed_invocable": False,
                    "configuration": "unassessed",
                    "safety": "unassessed",
                    "negative_test": "unassessed",
                    "verified_at": None,
                    "evidence_ids": [],
                },
            }
        )

    for name in sorted(toolsets):
        add(
            f"toolset:{name}",
            "toolset",
            "toolsets.py",
            {"name": name, "configurable": name in configurable_toolsets},
        )
    for tool in inventory["builtin_tools"]:
        add(
            f"tool:{tool['name']}",
            "builtin_tool",
            tool["source"],
            {"name": tool["name"], "toolset": tool["toolset"] or None},
        )
    for plugin in inventory["plugin_records"]:
        add(
            f"plugin:{plugin['category']}:{plugin['name']}",
            "plugin",
            plugin["source"],
            {
                "name": plugin["name"],
                "plugin_kind": plugin["kind"],
                "category": plugin["category"],
            },
        )
    for key in ("builtin_skill_records", "optional_skill_records"):
        for skill in inventory[key]:
            add(
                f"skill:{skill['scope']}:{skill['name']}",
                "skill",
                skill["source"],
                {"name": skill["name"], "scope": skill["scope"]},
            )
    for path in inventory["optional_mcp_manifests"]:
        relative = path.removeprefix("optional-mcps/").removesuffix("/manifest.yaml")
        add(f"mcp:{relative}", "optional_mcp", path)
    for adapter in inventory["gateway_builtin_adapters"]:
        add(
            f"gateway:{adapter['platform']}",
            "gateway_adapter",
            adapter["source"],
            {
                "platform": adapter["platform"],
                "module": adapter["module"],
                "class": adapter["class"],
                "source_kind": "builtin",
            },
        )
    for platform in inventory["gateway_plugin_platforms"]:
        add(
            f"gateway:{platform['platform']}",
            "gateway_adapter",
            platform["source"],
            {"platform": platform["platform"], "source_kind": "plugin"},
        )
    for transport in inventory["provider_transports"]:
        add(
            f"transport:{transport['key']}",
            "provider_transport",
            transport["source"],
            {"key": transport["key"], "name": transport["name"], "module": transport["module"]},
        )
    for name in sorted(default_config_keys):
        kind = "internal_config_surface" if name.startswith("_") else "config_surface"
        add(f"config:{name}", kind, "hermes_cli/config.py", {"name": name})

    rows.sort(key=lambda row: row["id"])
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        duplicate_ids = sorted(capability_id for capability_id, count in Counter(ids).items() if count > 1)
        raise ValueError(f"capability inventory generated duplicate parity IDs: {', '.join(duplicate_ids)}")
    return rows


def _apply_parity_overrides(
    rows: list[dict[str, Any]],
    target_commit: str,
    parity_overrides: Path | None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if parity_overrides is not None:
        try:
            payload = json.loads(parity_overrides.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("parity override file is not valid JSON") from exc
        if payload.get("schema_version") != 1 or payload.get("target_commit") != target_commit:
            raise ValueError("parity override file does not match the target schema or commit")
        raw_mappings = payload.get("mappings")
        if not isinstance(raw_mappings, dict):
            raise ValueError("parity override mappings must be an object")
        overrides = dict(raw_mappings)
        mapping_groups = payload.get("mapping_groups", [])
        if not isinstance(mapping_groups, list):
            raise ValueError("parity override mapping_groups must be a list")
        for group in mapping_groups:
            if not isinstance(group, dict) or not isinstance(group.get("ids"), list):
                raise ValueError("each parity mapping group must contain an ids list")
            group_mapping = group.get("mapping")
            if not isinstance(group_mapping, dict):
                raise ValueError("each parity mapping group must contain a mapping object")
            for capability_id in group["ids"]:
                if not isinstance(capability_id, str) or not capability_id.strip():
                    raise ValueError("parity mapping group IDs must be non-empty strings")
                capability_id = capability_id.strip()
                if capability_id in overrides:
                    raise ValueError(f"capability ID has more than one parity mapping override: {capability_id}")
                overrides[capability_id] = group_mapping

    known_ids = {row["id"] for row in rows}
    unknown_ids = sorted(set(overrides) - known_ids)
    if unknown_ids:
        raise ValueError("parity override file contains capability IDs absent from the target")

    kind_counts: Counter[str] = Counter()
    mapped_count = 0
    ready_count = 0
    for row in rows:
        kind_counts[row["kind"]] += 1
        override = overrides.get(row["id"], {})
        if not isinstance(override, dict):
            raise ValueError("each parity override must be an object")
        mapping = row["mapping"]
        owner = override.get("owner")
        mapping["owner"] = owner.strip() if isinstance(owner, str) and owner.strip() else None
        for field in PARITY_REFERENCE_FIELDS:
            value = override.get(field, [])
            if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError("parity mapping reference fields must be lists of non-empty strings")
            mapping[field] = [item.strip() for item in value]
        packaging_status = override.get("packaging_status", "not_assessed")
        if packaging_status not in PARITY_PACKAGING_STATES:
            raise ValueError("parity packaging_status is invalid")
        mapping["packaging_status"] = packaging_status
        if (
            mapping["owner"]
            and all(mapping[field] for field in PARITY_REFERENCE_FIELDS)
            and mapping["packaging_status"] != "not_assessed"
        ):
            row["mapping_status"] = "design_mapped"
            mapped_count += 1
        raw_evidence = override.get("evidence", {})
        if not isinstance(raw_evidence, dict):
            raise ValueError("parity override evidence must be an object")
        evidence = row["evidence"]
        for field in ("bundle_contains", "installed_discoverable", "installed_invocable"):
            value = raw_evidence.get(field, False)
            if not isinstance(value, bool):
                raise ValueError("parity packaging evidence flags must be booleans")
            evidence[field] = value
        for field in ("configuration", "safety", "negative_test"):
            value = raw_evidence.get(field, "unassessed")
            if value not in PARITY_EVIDENCE_STATES:
                raise ValueError("parity assessment evidence state is invalid")
            evidence[field] = value
        verified_at = raw_evidence.get("verified_at")
        evidence["verified_at"] = verified_at.strip() if isinstance(verified_at, str) and verified_at.strip() else None
        evidence_ids = raw_evidence.get("evidence_ids", [])
        if not isinstance(evidence_ids, list) or any(not isinstance(item, str) or not item.strip() for item in evidence_ids):
            raise ValueError("parity evidence_ids must be a list of non-empty strings")
        evidence["evidence_ids"] = [item.strip() for item in evidence_ids]
        parity_status = override.get("parity_status")
        if parity_status is not None and parity_status not in PARITY_FINAL_STATES:
            raise ValueError("parity_status is invalid")
        assessed = all(
            evidence[field] in {"not_required", "verified"}
            for field in ("configuration", "safety", "negative_test")
        )
        executed_evidence = bool(evidence["verified_at"] and evidence["evidence_ids"])
        installed_ready = bool(
            evidence["bundle_contains"]
            and evidence["installed_discoverable"]
            and evidence["installed_invocable"]
        )
        status_allows_noninstalled = parity_status in {
            "platform_limited_with_solution",
            "upstream_unavailable",
        }
        if (
            row["mapping_status"] == "design_mapped"
            and parity_status
            and assessed
            and executed_evidence
            and (installed_ready or status_allows_noninstalled)
        ):
            row["parity_status"] = parity_status
            row["readiness"] = "validated"
            ready_count += 1

    unspecified_ids = [row["id"] for row in rows if row["mapping_status"] != "design_mapped"]
    unvalidated_ids = [row["id"] for row in rows if row["readiness"] != "validated"]
    return {
        "schema_version": 1,
        "required_mapping_fields": list(PARITY_MAPPING_FIELDS),
        "mapping_complete": not unspecified_ids,
        "ready_complete": not unvalidated_ids,
        "summary": {
            "total": len(rows),
            "design_mapped": mapped_count,
            "unspecified": len(unspecified_ids),
            "validated": ready_count,
            "needs_validation": len(rows) - ready_count,
            "by_kind": dict(sorted(kind_counts.items())),
        },
        "unspecified_ids": unspecified_ids,
        "unvalidated_ids": unvalidated_ids,
        "rows": rows,
    }


def require_complete_parity(manifest: dict[str, Any]) -> None:
    parity = manifest.get("parity")
    if not isinstance(parity, dict):
        raise ValueError("capability manifest does not contain a parity ledger")
    summary = parity.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("capability parity ledger does not contain a summary")
    unspecified = summary.get("unspecified")
    if not isinstance(unspecified, int) or unspecified < 0:
        raise ValueError("capability parity ledger has an invalid unspecified count")
    needs_validation = summary.get("needs_validation")
    if not isinstance(needs_validation, int) or needs_validation < 0:
        raise ValueError("capability parity ledger has an invalid needs_validation count")
    if not parity.get("mapping_complete") or unspecified:
        raise ValueError(f"capability parity ledger is incomplete: {unspecified} mapping-unspecified rows")
    if not parity.get("ready_complete") or needs_validation:
        raise ValueError(f"capability parity ledger is not validated: {needs_validation} rows need validation")


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
    upstream_root: Path | None = None,
    target_commit: str = "",
    snapshot_archive: Path | None = None,
    snapshot_record: Path | None = None,
    parity_overrides: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    snapshot_root = upstream_root.resolve() if upstream_root is not None else None
    if snapshot_root is not None and not snapshot_root.is_dir():
        raise FileNotFoundError(f"upstream snapshot root not found: {snapshot_root}")
    if snapshot_root is not None and not target_commit.strip():
        raise ValueError("target_commit is required when upstream_root is used")
    snapshot_binding = (
        _verify_snapshot_binding(
            snapshot_root,
            target_commit.strip(),
            snapshot_archive.resolve() if snapshot_archive is not None else None,
            snapshot_record.resolve() if snapshot_record is not None else None,
        )
        if snapshot_root is not None
        else {}
    )
    recorded_base = _read_recorded_base(root)
    latest_commit = (
        target_commit.strip()
        if snapshot_root is not None
        else _run_git(root, ["rev-parse", "--verify", f"{upstream_ref}^{{commit}}"])
    )

    current_toolsets_source = _local_file(root, "toolsets.py")
    upstream_toolsets_source = _source_file(root, upstream_ref, snapshot_root, "toolsets.py")
    current_tools_config_source = _local_file(root, "hermes_cli/tools_config.py")
    upstream_tools_config_source = _source_file(root, upstream_ref, snapshot_root, "hermes_cli/tools_config.py")
    current_config_source = _local_file(root, "hermes_cli/config.py")
    upstream_config_source = _source_file(root, upstream_ref, snapshot_root, "hermes_cli/config.py")

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
    inventory = _snapshot_inventory(snapshot_root) if snapshot_root is not None else None
    parity = (
        _apply_parity_overrides(
            _capability_rows(upstream_toolsets, upstream_configurable, upstream_default_config, inventory),
            latest_commit,
            parity_overrides.resolve() if parity_overrides is not None else None,
        )
        if inventory is not None
        else {}
    )
    manifest = (
        {
            "schema_version": 1,
            "target_commit": latest_commit,
            "source_kind": "operator_recorded_github_archive",
            "source_binding": snapshot_binding,
            "toolsets": sorted(upstream_toolsets),
            "configurable_toolsets": sorted(upstream_configurable),
            "default_config_top_level_keys": sorted(upstream_default_config),
            "inventory": inventory,
            "parity": parity,
        }
        if inventory is not None
        else {}
    )

    return {
        "available": True,
        "source_kind": "snapshot" if snapshot_root is not None else "git_ref",
        "remote_ref": upstream_ref if snapshot_root is None else "",
        "source_label": f"operator_recorded_github_archive:{latest_commit[:12]}" if snapshot_root is not None else upstream_ref,
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
        "inventory_counts": (
            {
                "builtin_tools": len(inventory["builtin_tools"]),
                "builtin_tools_with_literal_toolset": sum(
                    1 for tool in inventory["builtin_tools"] if tool["toolset"]
                ),
                "plugin_manifests": len(inventory["plugin_manifests"]),
                "builtin_skills": len(inventory["builtin_skills"]),
                "optional_skills": len(inventory["optional_skills"]),
                "optional_mcp_manifests": len(inventory["optional_mcp_manifests"]),
                "gateway_builtin_adapters": len(inventory["gateway_builtin_adapters"]),
                "transport_modules": len(inventory["transport_modules"]),
            }
            if inventory is not None
            else {}
        ),
        "inventory": inventory or {},
        "manifest": manifest,
    }


def safe_upstream_capability_audit(
    repo_root: Path | None = None,
    *,
    upstream_ref: str = DEFAULT_UPSTREAM_REF,
    upstream_root: Path | None = None,
    target_commit: str = "",
    snapshot_archive: Path | None = None,
    snapshot_record: Path | None = None,
    parity_overrides: Path | None = None,
) -> dict[str, Any]:
    try:
        return build_upstream_capability_audit(
            repo_root,
            upstream_ref=upstream_ref,
            upstream_root=upstream_root,
            target_commit=target_commit,
            snapshot_archive=snapshot_archive,
            snapshot_record=snapshot_record,
            parity_overrides=parity_overrides,
        )
    except Exception as exc:  # noqa: BLE001 - this powers a diagnostic endpoint
        source_kind = "snapshot" if upstream_root is not None else "git_ref"
        return {
            "available": False,
            "source_kind": source_kind,
            "remote_ref": upstream_ref if source_kind == "git_ref" else "",
            "source_label": "fixed_snapshot" if source_kind == "snapshot" else upstream_ref,
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
            "inventory_counts": {},
            "inventory": {},
            "manifest": {},
            "error": f"{type(exc).__name__}: upstream audit source validation failed",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare local lilsunspot capability surface with cached Hermes upstream.")
    parser.add_argument("--repo-root", default="", help="Repository root. Defaults to the current lilsunspot checkout.")
    parser.add_argument("--upstream-ref", default=DEFAULT_UPSTREAM_REF, help="Git ref to compare against.")
    parser.add_argument("--upstream-root", default="", help="Extracted fixed-SHA upstream source snapshot.")
    parser.add_argument("--target-commit", default="", help="Fixed official SHA for --upstream-root.")
    parser.add_argument("--snapshot-archive", default="", help="Fixed-SHA GitHub tarball used for extraction.")
    parser.add_argument("--snapshot-record", default="", help="Version-controlled operator record for the archive.")
    parser.add_argument("--parity-overrides", default="", help="Version-controlled per-capability lilsunspot mappings.")
    parser.add_argument(
        "--require-parity-complete",
        action="store_true",
        help="Exit non-zero unless every fixed-target capability has all required lilsunspot mappings.",
    )
    parser.add_argument("--manifest-out", default="", help="Write the fixed-snapshot machine manifest as JSON.")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else _repo_root()
    upstream_root = Path(args.upstream_root).resolve() if args.upstream_root else None
    snapshot_archive = Path(args.snapshot_archive).resolve() if args.snapshot_archive else None
    snapshot_record = Path(args.snapshot_record).resolve() if args.snapshot_record else None
    parity_overrides = Path(args.parity_overrides).resolve() if args.parity_overrides else None
    payload = build_upstream_capability_audit(
        root,
        upstream_ref=args.upstream_ref,
        upstream_root=upstream_root,
        target_commit=args.target_commit,
        snapshot_archive=snapshot_archive,
        snapshot_record=snapshot_record,
        parity_overrides=parity_overrides,
    )
    if args.require_parity_complete:
        try:
            require_complete_parity(payload["manifest"])
        except ValueError as exc:
            parser.error(str(exc))
    if args.manifest_out:
        if upstream_root is None:
            parser.error("--manifest-out requires --upstream-root")
        manifest_path = Path(args.manifest_out).resolve()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(payload["manifest"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
