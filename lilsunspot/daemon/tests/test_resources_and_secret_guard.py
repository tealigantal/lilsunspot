from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_required_resources_parse():
    for relative in [
        "lilsunspot/resources/provider_registry.yaml",
        "lilsunspot/resources/default_mode_profiles.yaml",
        "lilsunspot/resources/default_safety_policy.yaml",
    ]:
        path = ROOT / relative
        assert path.exists()
        assert yaml.safe_load(path.read_text(encoding="utf-8")) is not None


def test_secret_guard_runs():
    result = subprocess.run(
        [sys.executable, "scripts/guard_no_secrets.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
