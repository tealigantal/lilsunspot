from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_macos_tauri_config_only_overrides_platform_packaging():
    config = json.loads(
        (ROOT / "lilsunspot" / "desktop" / "src-tauri" / "tauri.macos.conf.json").read_text(encoding="utf-8")
    )

    assert config["build"] == {"beforeBuildCommand": "npm run build"}
    assert config["bundle"]["targets"] == ["dmg"]
    assert config["bundle"]["icon"] == ["icons/icon.icns"]
    assert config["bundle"]["macOS"] == {"minimumSystemVersion": "15.0", "signingIdentity": "-"}
    assert "plugins" not in config


def test_macos_sidecar_keeps_windows_hidden_import_and_collect_surface():
    windows_script = (ROOT / "scripts" / "build_lilsunspotd_sidecar.ps1").read_text(encoding="utf-8")
    macos_script = (ROOT / "scripts" / "build_lilsunspotd_sidecar_macos.sh").read_text(encoding="utf-8")

    windows_hidden = set(re.findall(r'--hidden-import", "([^"]+)"', windows_script))
    macos_hidden = set(re.findall(r"--hidden-import ([^ \\\n]+)", macos_script))
    windows_collect = set(re.findall(r'--collect-submodules", "([^"]+)"', windows_script))
    macos_collect = set(re.findall(r"--collect-submodules ([^ \\\n]+)", macos_script))

    assert macos_hidden == windows_hidden
    assert macos_collect == windows_collect
    assert "--onedir" in macos_script
    assert "--target-arch" in macos_script
    assert "--noconsole" not in macos_script
    assert "lilsunspot/resources" in macos_script
    assert "UPSTREAM_COMMIT.txt" in macos_script


def test_macos_workflow_has_two_native_artifacts_and_windows_regression():
    workflow = (ROOT / ".github" / "workflows" / "lilsunspot-macos-artifacts.yml").read_text(encoding="utf-8")

    for expected in (
        "macos-15",
        "macos-15-intel",
        "aarch64-apple-darwin",
        "x86_64-apple-darwin",
        "lilsunspot-macos-arm64-dmg",
        "lilsunspot-macos-x86_64-dmg",
        "scripts/check_release.ps1",
        "scripts/smoke_lilsunspot_installed_app.ps1",
        "scripts/smoke_lilsunspot_macos.py",
        "retention-days: 14",
        "permissions:",
        "contents: read",
    ):
        assert expected in workflow
    mac_sidecar = workflow.index("- name: Build native macOS sidecar")
    mac_icon = workflow.index("- name: Prepare independent macOS icon")
    mac_rust_tests = workflow.index("- name: Run Rust tests")
    assert mac_sidecar < mac_rust_tests
    assert mac_icon < mac_rust_tests
    windows_release = workflow.index("- name: Rebuild existing Windows release path")
    windows_rust_tests = workflow.index("- name: Run Rust tests", mac_rust_tests + 1)
    assert windows_release < windows_rust_tests
    assert "actions/create-release" not in workflow
    assert "${{ secrets." not in workflow


def test_macos_installed_app_smoke_covers_complete_product_surface():
    smoke = (ROOT / "scripts" / "smoke_lilsunspot_macos.py").read_text(encoding="utf-8")

    for endpoint in (
        "/app/bootstrap",
        "/providers/capabilities",
        "/capability-graph",
        "/conversations",
        "/modes/current",
        "/gateway/weixin/status",
        "/product/capabilities",
        "/safety/policy",
        "/safety/approvals",
        "/tasks",
        "/memory",
        "/attachments/",
    ):
        assert endpoint in smoke
    for command in ("hdiutil", "codesign", "lipo", "ditto"):
        assert f'"{command}"' in smoke
    assert "LILSUNSPOT_DATA_DIR" in smoke
    assert 'env.pop("LILSUNSPOT_DATA_DIR", None)' in smoke
    assert "Contents" in smoke and "Resources" in smoke
