from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
PROVIDER_REGISTRY_FILE = RESOURCE_DIR / "provider_registry.yaml"
MODE_PROFILES_FILE = RESOURCE_DIR / "default_mode_profiles.yaml"
SAFETY_POLICY_FILE = RESOURCE_DIR / "default_safety_policy.yaml"


def load_yaml_resource(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_provider_registry() -> list[dict[str, Any]]:
    data = load_yaml_resource(PROVIDER_REGISTRY_FILE)
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, list):
        raise ValueError("provider_registry.yaml must contain a providers list")
    return [dict(provider) for provider in providers if isinstance(provider, dict)]


def provider_by_id(provider_id: str) -> dict[str, Any] | None:
    normalized = provider_id.strip().lower()
    for provider in load_provider_registry():
        if str(provider.get("id", "")).strip().lower() == normalized:
            return provider
    return None


def required_resource_files() -> list[Path]:
    return [PROVIDER_REGISTRY_FILE, MODE_PROFILES_FILE, SAFETY_POLICY_FILE]
