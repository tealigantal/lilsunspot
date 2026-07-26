from __future__ import annotations

from pathlib import Path
import hashlib
import json
import tarfile

import pytest

from lilsunspot.daemon.upstream_audit import build_upstream_capability_audit, require_complete_parity


def _write(root: Path, relative: str, text: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_local_fixture(root: Path) -> None:
    _write(root, "lilsunspot/UPSTREAM_COMMIT.txt", "old-base\n")
    _write(root, "toolsets.py", "TOOLSETS = {'file': {}}\n")
    _write(root, "hermes_cli/tools_config.py", "CONFIGURABLE_TOOLSETS = [('file', 'File', 'Files')]\n")
    _write(root, "hermes_cli/config.py", "DEFAULT_CONFIG = {'agent': {}}\n")


def _build_upstream_fixture(root: Path) -> None:
    _write(root, "toolsets.py", "TOOLSETS = {'file': {}, 'context_engine': {}}\n")
    _write(
        root,
        "hermes_cli/tools_config.py",
        "CONFIGURABLE_TOOLSETS = [('file', 'File', 'Files'), ('context_engine', 'Context', 'Context')]\n",
    )
    _write(root, "hermes_cli/config.py", "DEFAULT_CONFIG = {'agent': {}, 'gateway': {}}\n")
    _write(
        root,
        "tools/file_tools.py",
        "registry.register(name='read_file', toolset='file', schema={}, handler=handle)\n"
        "registry.register(name=dynamic_name, toolset='file', schema={}, handler=handle)\n",
    )
    _write(root, "plugins/model-providers/openai/plugin.yaml", "name: openai\nkind: provider\n")
    _write(root, "plugins/platforms/slack/plugin.yaml", "name: slack\nkind: platform\n")
    _write(
        root,
        "plugins/platforms/slack/adapter.py",
        "def register(ctx):\n    ctx.register_platform(name='slack', adapter_factory=factory)\n",
    )
    _write(root, "skills/productivity/docx/SKILL.md", "---\nname: docx\n---\n# docx\n")
    _write(root, "optional-skills/research/arxiv/SKILL.md", "---\nname: arxiv\n---\n# arxiv\n")
    _write(root, "optional-mcps/linear/manifest.yaml", "name: linear\n")
    _write(root, "gateway/config.py", "class Platform:\n    WEIXIN = 'weixin'\n")
    _write(
        root,
        "gateway/platforms/weixin.py",
        "class WeixinAdapter(BasePlatformAdapter):\n"
        "    def __init__(self, config):\n"
        "        super().__init__(config, Platform.WEIXIN)\n",
    )
    _write(root, "gateway/platforms/helpers.py", "# helper only\n")
    _write(root, "agent/transports/codex.py", "class ResponsesApiTransport(ProviderTransport):\n    pass\n")


def _archive_fixture(snapshot_root: Path, archive_path: Path, record_path: Path, target_commit: str) -> str:
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(snapshot_root, arcname=snapshot_root.name)
    archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest().upper()
    record_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repository": "NousResearch/hermes-agent",
                "target_commit": target_commit,
                "archive_root": snapshot_root.name,
                "archive_sha256": archive_sha256,
            }
        ),
        encoding="utf-8",
    )
    return archive_sha256


def test_snapshot_audit_enumerates_fixed_capability_surfaces(tmp_path: Path) -> None:
    local_root = tmp_path / "local"
    target_commit = "a" * 40
    upstream_root = tmp_path / f"NousResearch-hermes-agent-{target_commit[:7]}"
    _build_local_fixture(local_root)
    _build_upstream_fixture(upstream_root)
    archive_path = tmp_path / f"{target_commit}.tar.gz"
    record_path = tmp_path / "snapshot-record.json"
    archive_sha256 = _archive_fixture(upstream_root, archive_path, record_path, target_commit)

    result = build_upstream_capability_audit(
        local_root,
        upstream_root=upstream_root,
        target_commit=target_commit,
        snapshot_archive=archive_path,
        snapshot_record=record_path,
    )

    assert result["source_kind"] == "snapshot"
    assert result["latest_commit"] == target_commit
    assert result["missing_toolsets"] == ["context_engine"]
    assert result["missing_configurable_toolsets"] == ["context_engine"]
    assert result["missing_default_config_keys"] == ["gateway"]
    assert result["inventory_counts"] == {
        "builtin_tools": 1,
        "builtin_tools_with_literal_toolset": 1,
        "plugin_manifests": 2,
        "builtin_skills": 1,
        "optional_skills": 1,
        "optional_mcp_manifests": 1,
        "gateway_builtin_adapters": 1,
        "transport_modules": 1,
    }
    assert result["inventory"]["builtin_tools"] == [
        {"name": "read_file", "toolset": "file", "source": "tools/file_tools.py"}
    ]
    assert result["inventory"]["plugin_categories"] == {"model-providers": 1, "platforms": 1}
    assert result["inventory"]["gateway_builtin_adapters"] == [
        {
            "platform": "weixin",
            "class": "WeixinAdapter",
            "module": "weixin",
            "source": "gateway/platforms/weixin.py",
        }
    ]
    assert result["inventory"]["transport_modules"] == ["codex"]
    assert result["manifest"]["target_commit"] == target_commit
    assert result["manifest"]["source_binding"]["archive_sha256"] == archive_sha256
    assert result["manifest"]["source_binding"]["assurance"] == "operator_recorded_archive_integrity"
    assert result["manifest"]["toolsets"] == ["context_engine", "file"]
    assert result["manifest"]["inventory"] == result["inventory"]
    assert result["manifest"]["parity"]["mapping_complete"] is False
    assert result["manifest"]["parity"]["ready_complete"] is False
    assert result["manifest"]["parity"]["summary"] == {
        "total": 13,
        "design_mapped": 0,
        "unspecified": 13,
        "validated": 0,
        "needs_validation": 13,
        "by_kind": {
            "builtin_tool": 1,
            "config_surface": 2,
            "gateway_adapter": 2,
            "optional_mcp": 1,
            "plugin": 2,
            "skill": 2,
            "toolset": 2,
            "provider_transport": 1,
        },
    }
    assert len({row["id"] for row in result["manifest"]["parity"]["rows"]}) == 13
    assert {row["id"] for row in result["manifest"]["parity"]["rows"]} >= {
        "gateway:slack",
        "gateway:weixin",
        "plugin:platforms:slack",
        "skill:builtin:docx",
        "skill:optional:arxiv",
        "transport:responses_api",
    }
    assert result["manifest"]["parity"]["unspecified_ids"] == sorted(
        result["manifest"]["parity"]["unspecified_ids"]
    )
    with pytest.raises(ValueError, match="13 mapping-unspecified rows"):
        require_complete_parity(result["manifest"])


def test_snapshot_audit_requires_fixed_target_sha(tmp_path: Path) -> None:
    local_root = tmp_path / "local"
    upstream_root = tmp_path / "NousResearch-hermes-agent-invalid"
    _build_local_fixture(local_root)
    _build_upstream_fixture(upstream_root)

    with pytest.raises(ValueError, match="target_commit is required"):
        build_upstream_capability_audit(local_root, upstream_root=upstream_root)


def test_snapshot_audit_rejects_unbound_target_and_safe_error_is_redacted(tmp_path: Path) -> None:
    from lilsunspot.daemon.upstream_audit import safe_upstream_capability_audit

    local_root = tmp_path / "local"
    upstream_root = tmp_path / "private-user-path"
    _build_local_fixture(local_root)
    _build_upstream_fixture(upstream_root)

    result = safe_upstream_capability_audit(
        local_root,
        upstream_root=upstream_root,
        target_commit="not-a-commit",
    )

    assert result["available"] is False
    assert result["source_kind"] == "snapshot"
    assert result["remote_ref"] == ""
    assert "private-user-path" not in result["error"]
    assert result["inventory"] == {}
    assert result["manifest"] == {}


def test_snapshot_audit_rejects_archive_with_unrecorded_root(tmp_path: Path) -> None:
    local_root = tmp_path / "local"
    target_commit = "b" * 40
    upstream_root = tmp_path / f"NousResearch-hermes-agent-{target_commit[:7]}"
    _build_local_fixture(local_root)
    _build_upstream_fixture(upstream_root)
    archive_path = tmp_path / "snapshot.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(upstream_root, arcname="forged-root")
    record_path = tmp_path / "snapshot-record.json"
    record_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repository": "NousResearch/hermes-agent",
                "target_commit": target_commit,
                "archive_root": upstream_root.name,
                "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest().upper(),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="archive root"):
        build_upstream_capability_audit(
            local_root,
            upstream_root=upstream_root,
            target_commit=target_commit,
            snapshot_archive=archive_path,
            snapshot_record=record_path,
        )


def test_parity_overrides_require_complete_fields_and_known_ids(tmp_path: Path) -> None:
    local_root = tmp_path / "local"
    target_commit = "c" * 40
    upstream_root = tmp_path / f"NousResearch-hermes-agent-{target_commit[:7]}"
    _build_local_fixture(local_root)
    _build_upstream_fixture(upstream_root)
    archive_path = tmp_path / "snapshot.tar.gz"
    record_path = tmp_path / "snapshot-record.json"
    _archive_fixture(upstream_root, archive_path, record_path, target_commit)
    overrides_path = tmp_path / "parity.json"
    overrides_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_commit": target_commit,
                "mapping_groups": [
                    {
                        "ids": ["toolset:context_engine"],
                        "mapping": {
                            "owner": "lilsunspot capability graph",
                            "product_entry": ["lilsunspot agent tool loop"],
                            "config_source": ["Hermes toolsets config"],
                            "safety_policy": ["lilsunspot runtime boundary"],
                            "packaging_status": "blocked_not_merged",
                            "validation_method": ["installed sidecar context smoke"],
                        },
                    }
                ],
                "mappings": {
                    "toolset:file": {
                        "owner": "official Hermes tool registry",
                        "product_entry": ["lilsunspot agent tool loop"],
                        "config_source": ["Hermes toolsets config"],
                        "safety_policy": ["lilsunspot file approval boundary"],
                        "packaging_status": "blocked_not_merged",
                        "validation_method": ["installed sidecar file-tool smoke"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = build_upstream_capability_audit(
        local_root,
        upstream_root=upstream_root,
        target_commit=target_commit,
        snapshot_archive=archive_path,
        snapshot_record=record_path,
        parity_overrides=overrides_path,
    )

    parity = result["manifest"]["parity"]
    assert parity["summary"]["design_mapped"] == 2
    assert parity["summary"]["unspecified"] == 11
    mapped_row = next(row for row in parity["rows"] if row["id"] == "toolset:file")
    assert mapped_row["mapping_status"] == "design_mapped"
    assert mapped_row["parity_status"] is None
    assert mapped_row["readiness"] == "needs_validation"
    with pytest.raises(ValueError, match="11 mapping-unspecified rows"):
        require_complete_parity(result["manifest"])

    payload = json.loads(overrides_path.read_text(encoding="utf-8"))
    payload["mappings"]["toolset:not-in-target"] = payload["mappings"]["toolset:file"]
    overrides_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="absent from the target"):
        build_upstream_capability_audit(
            local_root,
            upstream_root=upstream_root,
            target_commit=target_commit,
            snapshot_archive=archive_path,
            snapshot_record=record_path,
            parity_overrides=overrides_path,
        )

    payload["mappings"].pop("toolset:not-in-target")
    payload["mapping_groups"].append(
        {"ids": ["toolset:file"], "mapping": payload["mappings"]["toolset:file"]}
    )
    overrides_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="more than one parity mapping override"):
        build_upstream_capability_audit(
            local_root,
            upstream_root=upstream_root,
            target_commit=target_commit,
            snapshot_archive=archive_path,
            snapshot_record=record_path,
            parity_overrides=overrides_path,
        )


def test_parity_completion_gate_accepts_only_a_complete_ledger() -> None:
    manifest = {
        "parity": {
            "mapping_complete": True,
            "ready_complete": True,
            "summary": {"unspecified": 0, "needs_validation": 0},
        }
    }
    require_complete_parity(manifest)

    with pytest.raises(ValueError, match="1 rows need validation"):
        require_complete_parity(
            {
                "parity": {
                    "mapping_complete": True,
                    "ready_complete": False,
                    "summary": {"unspecified": 0, "needs_validation": 1},
                }
            }
        )

    with pytest.raises(ValueError, match="does not contain a parity ledger"):
        require_complete_parity({})
