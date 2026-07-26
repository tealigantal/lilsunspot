$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DesktopDir = Join-Path $Root "lilsunspot\desktop"
$TauriConfigPath = Join-Path $DesktopDir "src-tauri\tauri.conf.json"
$SidecarPath = Join-Path $DesktopDir "src-tauri\binaries\lilsunspotd\lilsunspotd.exe"
$NsisDir = Join-Path $DesktopDir "src-tauri\target\release\bundle\nsis"

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required for release checks."
    }
}

function Assert-Path {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Description not found: $Path"
    }
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label,

        [Parameter(Mandatory = $true)]
        [string] $FilePath,

        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $Arguments
    )

    Write-Host "== $Label =="
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed. Exit code: $LASTEXITCODE."
    }
}

function Test-UpdaterArtifactsEnabled {
    $TauriConfigRaw = [System.IO.File]::ReadAllText($TauriConfigPath, [System.Text.Encoding]::UTF8)
    $TauriConfig = $TauriConfigRaw | ConvertFrom-Json
    return [bool] $TauriConfig.bundle.createUpdaterArtifacts
}

Push-Location $Root
try {
    Assert-Command "git"
    Assert-Command "python"
    Assert-Command "npm"
    Assert-Command "uv"
    Assert-Path (Join-Path $DesktopDir "package.json") "desktop package.json"
    Assert-Path (Join-Path $DesktopDir "node_modules") "desktop dependencies"

    Invoke-Native "git diff check" "git" @("diff", "--check")
    Invoke-Native "daemon tests" "python" @(
        "-m",
        "pytest",
        "lilsunspot/daemon/tests",
        "--basetemp",
        ".tmp-pytest-lilsunspot-daemon-release"
    )
    Invoke-Native "product tests" "python" @("-m", "pytest", "lilsunspot/tests", "--basetemp", ".tmp-pytest-lilsunspot")
    Invoke-Native "secret guard" "python" @("scripts/guard_no_secrets.py")
    Invoke-Native "desktop build" "npm" @("run", "build", "--prefix", $DesktopDir)
    Invoke-Native "daemon sidecar build" (Join-Path $Root "scripts\build_lilsunspotd_sidecar.ps1") @()
    Assert-Path $SidecarPath "daemon sidecar"

    Invoke-Native "desktop NSIS build" "npm" @("run", "tauri:build", "--prefix", $DesktopDir)
    $Installer = Get-ChildItem -Path $NsisDir -Filter "Lilsunspot_*_x64-setup.exe" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $Installer) {
        throw "NSIS installer not found in $NsisDir."
    }
    $UpdaterSignature = "$($Installer.FullName).sig"
    if ((Test-UpdaterArtifactsEnabled) -and -not (Test-Path -LiteralPath $UpdaterSignature)) {
        throw "Updater signature not found for $($Installer.FullName)."
    }

    Write-Host "Release check passed."
    Write-Host "Sidecar: $SidecarPath"
    Write-Host "Installer: $($Installer.FullName)"
    if (Test-UpdaterArtifactsEnabled) {
        Write-Host "Updater signature: $UpdaterSignature"
    }
    else {
        Write-Host "Updater artifacts disabled for local release check."
    }
}
finally {
    Pop-Location
}
