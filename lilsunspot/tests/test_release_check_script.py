from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_release.ps1"


def test_release_check_script_exists():
    assert SCRIPT.exists()


def test_release_check_has_no_silent_desktop_build_skip_path():
    text = SCRIPT.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "Write-Warning" not in text
    assert "skipped" not in lowered
    assert "skip desktop" not in lowered
    assert 'Invoke-Native "desktop build" "npm" @("run", "build", "--prefix", $DesktopDir)' in text


def test_release_check_covers_release_artifacts():
    text = SCRIPT.read_text(encoding="utf-8")

    required_fragments = [
        'Invoke-Native "git diff check" "git" @("diff", "--check")',
        'Invoke-Native "daemon tests" "python" @(',
        '"lilsunspot/daemon/tests"',
        '".tmp-pytest-lilsunspot-daemon-release"',
        'Invoke-Native "product tests" "python" @("-m", "pytest", "lilsunspot/tests", "--basetemp", ".tmp-pytest-lilsunspot")',
        'Invoke-Native "secret guard" "python" @("scripts/guard_no_secrets.py")',
        'Invoke-Native "daemon sidecar build" (Join-Path $Root "scripts\\build_lilsunspotd_sidecar.ps1") @()',
        'Invoke-Native "desktop NSIS build" "npm" @("run", "tauri:build", "--prefix", $DesktopDir)',
        'Assert-Path $SidecarPath "daemon sidecar"',
        '$SidecarPath = Join-Path $DesktopDir "src-tauri\\binaries\\lilsunspotd\\lilsunspotd.exe"',
        'throw "NSIS installer not found in $NsisDir."',
        "Test-UpdaterArtifactsEnabled",
        'throw "Updater signature not found for $($Installer.FullName)."',
        "Updater artifacts disabled for local release check.",
    ]

    for fragment in required_fragments:
        assert fragment in text
