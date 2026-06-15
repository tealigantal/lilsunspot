import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TAURI_CONFIG = ROOT / "lilsunspot" / "desktop" / "src-tauri" / "tauri.conf.json"
NSIS_BUILD_SCRIPT = ROOT / "scripts" / "build_lilsunspot_desktop_nsis.ps1"
RELEASE_SCRIPT = ROOT / "scripts" / "build_lilsunspot_release.ps1"
SYNC_SCRIPT = ROOT / "scripts" / "hermes_upstream_sync.ps1"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "lilsunspot-release.yml"


def test_tauri_local_build_disables_updater_artifacts_by_default():
    config = json.loads(TAURI_CONFIG.read_text(encoding="utf-8"))

    assert config["bundle"]["targets"] == ["nsis"]
    assert config["bundle"]["createUpdaterArtifacts"] is False
    window = config["app"]["windows"][0]
    assert window["width"] == 960
    assert window["height"] == 680
    assert window["minWidth"] == 960
    assert window["minHeight"] == 680
    updater = config["plugins"]["updater"]
    assert updater["endpoints"] == ["https://updates.lilsunspot.com/lilsunspot/windows/latest.json"]
    assert updater["pubkey"].strip()
    assert updater["windows"]["installMode"] == "passive"


def test_nsis_build_keeps_updater_signing_key_optional_for_local_build():
    text = NSIS_BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "Move-StaleNsisArtifacts" in text
    assert "Refusing to move NSIS artifacts outside repository" in text
    assert 'Join-Path $ResolvedNsisDir "stale"' in text
    assert "Test-UpdaterArtifactsEnabled" in text
    assert "Assert-UpdaterSigningEnv" in text
    assert text.index("Move-StaleNsisArtifacts") < text.index("Assert-UpdaterSigningEnv")
    assert 'if ($UpdaterArtifactsEnabled)' in text
    assert "Updater artifacts disabled for local NSIS build." in text
    assert "TAURI_SIGNING_PRIVATE_KEY" in text
    assert "TAURI_SIGNING_PRIVATE_KEY_PATH" in text
    assert "ReadAllText" in text
    assert "Updater signature not found" in text


def test_release_script_emits_manifest_checksum_and_authenticode_gate():
    text = RELEASE_SCRIPT.read_text(encoding="utf-8")

    required = [
        'MirrorBaseUrl = "https://updates.lilsunspot.com/lilsunspot/windows"',
        "Assert-UpdaterSigningEnv",
        "Set-UpdaterArtifactsEnabled",
        "$OriginalTauriConfig = Set-UpdaterArtifactsEnabled $true",
        "Set-Content -LiteralPath $TauriConfigPath -Value $OriginalTauriConfig",
        "ReadAllText",
        "Get-AuthenticodeSignature",
        "Production release requires a valid Windows Authenticode signature",
        '"windows-x86_64"',
        "latest.json",
        "Get-FileHash -Algorithm SHA256",
        "Updater signature not found",
    ]
    for fragment in required:
        assert fragment in text


def test_upstream_sync_script_refuses_dirty_tree_and_updates_marker_after_merge():
    text = SYNC_SCRIPT.read_text(encoding="utf-8")

    required = [
        'Get-GitOutput @("status", "--short")',
        "Working tree is dirty",
        'codex/upstream-sync-$(Get-Date -Format',
        'Invoke-Native "pre-merge upstream report"',
        'Invoke-Native "merge official Hermes upstream"',
        'Set-Content -LiteralPath $UpstreamCommitFile -Value $RemoteCommit',
        'Invoke-Native "post-merge upstream report"',
    ]
    for fragment in required:
        assert fragment in text


def test_release_workflow_uses_signing_secret_and_mirror_upload_gate():
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    required = [
        "TAURI_SIGNING_PRIVATE_KEY",
        "scripts/build_lilsunspot_release.ps1",
        "actions/upload-artifact@v4",
        "LILSUNSPOT_RCLONE_CONFIG",
        "LILSUNSPOT_RCLONE_REMOTE",
        "Production release requires LILSUNSPOT_RCLONE_CONFIG",
    ]
    for fragment in required:
        assert fragment in text
