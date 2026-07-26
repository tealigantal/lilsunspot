from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any, Iterator

import yaml

from .config_paths import RuntimePaths


class HermesConfigMigrationError(RuntimeError):
    """Raised when the installed user's Hermes data cannot be migrated safely."""


_MIGRATION_LOCK = threading.RLock()
_SNAPSHOT_NAMES = ("config.yaml", ".env", "auth.json", "provider_models_cache.json")


def _current_schema_version() -> int:
    from hermes_cli.config import DEFAULT_CONFIG

    value = DEFAULT_CONFIG.get("_config_version", 1)
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise HermesConfigMigrationError("Hermes 当前配置版本无效，无法安全启动。") from exc
    if version < 1:
        raise HermesConfigMigrationError("Hermes 当前配置版本无效，无法安全启动。")
    return version


def _raw_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        value = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HermesConfigMigrationError("Hermes 配置文件无法解析，原文件已保留，请先修复配置。") from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HermesConfigMigrationError("Hermes 配置文件顶层必须是对象，原文件已保留。")
    return value


def _version(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _capture(paths: RuntimePaths) -> dict[Path, bytes | None]:
    result: dict[Path, bytes | None] = {}
    for name in _SNAPSHOT_NAMES:
        path = paths.hermes_home / name
        result[path] = path.read_bytes() if path.exists() else None
    return result


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.lilsunspot-tmp-{os.getpid()}-{threading.get_ident()}")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _restore(snapshot: dict[Path, bytes | None]) -> None:
    errors: list[str] = []
    for path, data in snapshot.items():
        try:
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                _atomic_write(path, data)
        except Exception as exc:
            errors.append(f"{path.name}:{type(exc).__name__}")
    if errors:
        raise HermesConfigMigrationError("Hermes 配置迁移失败，且自动回滚未完全成功：" + ", ".join(errors))


def _write_backup(paths: RuntimePaths, snapshot: dict[Path, bytes | None], current: int, latest: int) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_dir = paths.data_dir / "migration-backups" / f"hermes-config-v{current}-to-v{latest}-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    files: list[dict[str, Any]] = []
    for source, data in snapshot.items():
        if data is None:
            files.append({"name": source.name, "present": False})
            continue
        destination = backup_dir / source.name
        destination.write_bytes(data)
        files.append({"name": source.name, "present": True, "sha256": _sha256(data), "size": len(data)})
    manifest = {
        "schema": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "from_version": current,
        "to_version": latest,
        "files": files,
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return backup_dir


@contextmanager
def _hermes_home(paths: RuntimePaths) -> Iterator[None]:
    # Upstream resolves its config path from a context-local override.  Mutating
    # HERMES_HOME here would leak one user's migration into concurrent turns.
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    token = set_hermes_home_override(paths.hermes_home)
    try:
        yield
    finally:
        reset_hermes_home_override(token)


def _validate_migrated(config: dict[str, Any], latest: int) -> None:
    if _version(config.get("_config_version")) != latest:
        raise HermesConfigMigrationError("Hermes 配置迁移没有到达当前版本，已自动回滚。")
    from hermes_cli.config import validate_config_structure

    errors = [issue.message for issue in validate_config_structure(config) if issue.severity == "error"]
    if errors:
        raise HermesConfigMigrationError("Hermes 配置迁移后校验失败，已自动回滚：" + "；".join(errors[:3]))


def ensure_hermes_config_ready(paths: RuntimePaths) -> dict[str, Any]:
    """Upgrade one installed Hermes home to the current schema, or fail closed."""
    config_path = paths.hermes_home / "config.yaml"
    paths.hermes_home.mkdir(parents=True, exist_ok=True)
    with _MIGRATION_LOCK:
        latest = _current_schema_version()
        raw = _raw_config(config_path)
        if not config_path.exists():
            return {"migrated": False, "from_version": latest, "to_version": latest, "backup_dir": ""}
        current = _version(raw.get("_config_version"))
        if current > latest:
            raise HermesConfigMigrationError(
                f"配置版本 {current} 高于当前程序支持的 {latest}，为避免数据损坏已拒绝降级启动。"
            )
        if current == latest:
            _validate_migrated(raw, latest)
            return {"migrated": False, "from_version": current, "to_version": latest, "backup_dir": ""}

        snapshot = _capture(paths)
        backup_dir = _write_backup(paths, snapshot, current, latest)
        try:
            with _hermes_home(paths):
                from hermes_cli.config import migrate_config

                migrate_config(interactive=False, quiet=True)
            migrated = _raw_config(config_path)
            _validate_migrated(migrated, latest)
        except Exception as exc:
            try:
                _restore(snapshot)
            except HermesConfigMigrationError as rollback_exc:
                raise rollback_exc from exc
            if isinstance(exc, HermesConfigMigrationError):
                raise
            raise HermesConfigMigrationError("Hermes 配置升级失败，已从备份自动恢复原数据。") from exc
        return {
            "migrated": True,
            "from_version": current,
            "to_version": latest,
            "backup_dir": str(backup_dir),
        }


def prepare_config_for_write(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise HermesConfigMigrationError("Hermes 配置必须是对象。")
    latest = _current_schema_version()
    prepared = dict(config)
    current = _version(prepared.get("_config_version"))
    if current > latest:
        raise HermesConfigMigrationError(
            f"配置版本 {current} 高于当前程序支持的 {latest}，已拒绝覆盖。"
        )
    prepared["_config_version"] = latest
    _validate_migrated(prepared, latest)
    return prepared
