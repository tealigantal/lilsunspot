from __future__ import annotations

import json

import pytest
import yaml


def test_legacy_config_migrates_to_current_with_backup_and_is_idempotent(daemon_client):
    paths = daemon_client.config_paths.get_runtime_paths()
    paths.hermes_home.mkdir(parents=True, exist_ok=True)
    config_path = paths.hermes_home / "config.yaml"
    env_path = paths.hermes_home / ".env"
    original_config = (
        "_config_version: 32\n"
        "delegation:\n"
        "  max_async_children: 9\n"
        "  max_concurrent_children: 4\n"
        "lilsunspot:\n"
        "  provider: deepseek\n"
    ).encode()
    original_env = b"DEEPSEEK_API_KEY=test-only-placeholder\n"
    config_path.write_bytes(original_config)
    env_path.write_bytes(original_env)

    migrated = daemon_client.hermes_runtime.read_hermes_config(paths)

    from hermes_cli.config import DEFAULT_CONFIG

    assert migrated["_config_version"] == DEFAULT_CONFIG["_config_version"]
    assert migrated["delegation"]["max_concurrent_children"] == 9
    assert "max_async_children" not in migrated["delegation"]
    assert migrated["lilsunspot"]["provider"] == "deepseek"
    backups = list((paths.data_dir / "migration-backups").glob("hermes-config-v32-to-v33-*"))
    assert len(backups) == 1
    assert (backups[0] / "config.yaml").read_bytes() == original_config
    assert (backups[0] / ".env").read_bytes() == original_env
    manifest_text = (backups[0] / "manifest.json").read_text(encoding="utf-8")
    assert "test-only-placeholder" not in manifest_text
    assert json.loads(manifest_text)["to_version"] == DEFAULT_CONFIG["_config_version"]

    daemon_client.hermes_runtime.read_hermes_config(paths)
    assert len(list((paths.data_dir / "migration-backups").iterdir())) == 1


def test_failed_official_migration_restores_exact_source(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    paths.hermes_home.mkdir(parents=True, exist_ok=True)
    config_path = paths.hermes_home / "config.yaml"
    env_path = paths.hermes_home / ".env"
    original_config = b"_config_version: 32\nlilsunspot:\n  marker: keep\n"
    original_env = b"OPENAI_API_KEY=test-only-placeholder\n"
    config_path.write_bytes(original_config)
    env_path.write_bytes(original_env)

    import hermes_cli.config as upstream_config

    def fail_after_write(*_args, **_kwargs):
        config_path.write_text("_config_version: 33\nlilsunspot: {}\n", encoding="utf-8")
        env_path.write_text("OPENAI_API_KEY=changed\n", encoding="utf-8")
        raise RuntimeError("injected failure")

    monkeypatch.setattr(upstream_config, "migrate_config", fail_after_write)

    with pytest.raises(daemon_client.hermes_runtime.HermesRuntimeError, match="已从备份自动恢复"):
        daemon_client.hermes_runtime.read_hermes_config(paths)

    assert config_path.read_bytes() == original_config
    assert env_path.read_bytes() == original_env


def test_newer_config_refuses_downgrade_without_mutation(daemon_client):
    paths = daemon_client.config_paths.get_runtime_paths()
    paths.hermes_home.mkdir(parents=True, exist_ok=True)
    config_path = paths.hermes_home / "config.yaml"
    original = b"_config_version: 999\nlilsunspot:\n  marker: keep\n"
    config_path.write_bytes(original)

    with pytest.raises(daemon_client.hermes_runtime.HermesRuntimeError, match="拒绝降级启动"):
        daemon_client.hermes_runtime.read_hermes_config(paths)

    assert config_path.read_bytes() == original
    assert not (paths.data_dir / "migration-backups").exists()


def test_product_config_writes_current_schema_version(daemon_client):
    paths = daemon_client.config_paths.get_runtime_paths()
    daemon_client.hermes_runtime.write_hermes_config({"lilsunspot": {"marker": "kept"}}, paths)

    raw = yaml.safe_load((paths.hermes_home / "config.yaml").read_text(encoding="utf-8"))
    from hermes_cli.config import DEFAULT_CONFIG

    assert raw["_config_version"] == DEFAULT_CONFIG["_config_version"]
    assert raw["lilsunspot"]["marker"] == "kept"
