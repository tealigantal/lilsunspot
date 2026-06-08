from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "smoke_lilsunspot_installed_app.ps1"


def test_installed_app_smoke_script_exists():
    assert SCRIPT.exists()


def test_installed_app_smoke_script_uses_isolated_runtime_data():
    text = SCRIPT.read_text(encoding="utf-8")

    required_fragments = [
        'Join-Path ([System.IO.Path]::GetTempPath()) "lilsunspot-installed-app-smoke"',
        'Join-Path $Root "ignored\\installed-app-smoke"',
        "LILSUNSPOT_DATA_DIR",
        '"daemon-runtime.json"',
        '"runtime-token.json"',
        '"X-Lilsunspot-Token"',
        'Invoke-RestMethod -Method Get -Uri "$baseUrl/health"',
        'Invoke-RestMethod -Method Get -Uri "$baseUrl/providers"',
    ]

    for fragment in required_fragments:
        assert fragment in text


def test_installed_app_smoke_script_covers_installed_sidecar_launch():
    text = SCRIPT.read_text(encoding="utf-8")

    required_fragments = [
        '"Lilsunspot_*_x64-setup.exe"',
        'Invoke-Process "silent install" $InstallerPath @("/S", "/D=$InstallDir")',
        'Assert-Path $appPath "仓库外 Lilsunspot.exe"',
        'Assert-Path $sidecarPath "仓库外 lilsunspotd.exe"',
        'Get-ProcessByExecutablePath "Lilsunspot.exe" $appPath',
        'Get-ProcessByExecutablePath "lilsunspotd.exe" $sidecarPath',
        '$runtimePayload.host -ne "127.0.0.1"',
        'Invoke-Process "silent uninstall" $uninstallerPath @("/S")',
    ]

    for fragment in required_fragments:
        assert fragment in text


def test_installed_app_smoke_script_guards_secret_and_cleanup_handling():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "Assert-SafeCleanupPath" in text
    assert "Remove-Item -LiteralPath $Path -Recurse -Force" in text
    assert "$logText.Contains($token)" in text
    assert "Write-Host $token" not in text
    assert "Write-Output $token" not in text
    assert "ConvertTo-Json $token" not in text
