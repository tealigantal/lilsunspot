$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DesktopDir = Join-Path $Root "lilsunspot\desktop"
$TauriConfigPath = Join-Path $DesktopDir "src-tauri\tauri.conf.json"
$NsisDir = Join-Path $DesktopDir "src-tauri\target\release\bundle\nsis"

function Move-StaleNsisArtifacts {
    if (-not (Test-Path -LiteralPath $NsisDir)) {
        return
    }

    $ResolvedNsisDir = (Resolve-Path -LiteralPath $NsisDir).Path
    $ResolvedRoot = (Resolve-Path -LiteralPath $Root).Path
    if (-not $ResolvedNsisDir.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to move NSIS artifacts outside repository: $ResolvedNsisDir"
    }

    $StaleDir = Join-Path $ResolvedNsisDir "stale"
    New-Item -ItemType Directory -Force -Path $StaleDir | Out-Null
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Get-ChildItem -Path $ResolvedNsisDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "Lilsunspot_*_x64-setup.exe" -or $_.Name -like "Lilsunspot_*_x64-setup.exe.sig" } |
        ForEach-Object {
            $Destination = Join-Path $StaleDir "$Stamp-$($_.Name)"
            Move-Item -LiteralPath $_.FullName -Destination $Destination -Force
            Write-Host "Moved stale NSIS artifact: $Destination"
        }
}

function Test-UpdaterArtifactsEnabled {
    $TauriConfigRaw = [System.IO.File]::ReadAllText($TauriConfigPath, [System.Text.Encoding]::UTF8)
    $TauriConfig = $TauriConfigRaw | ConvertFrom-Json
    return [bool] $TauriConfig.bundle.createUpdaterArtifacts
}

function Assert-UpdaterSigningEnv {
    if (-not (Test-UpdaterArtifactsEnabled)) {
        return
    }

    $HasInlineKey = -not [string]::IsNullOrWhiteSpace($env:TAURI_SIGNING_PRIVATE_KEY)
    $HasKeyPath = -not [string]::IsNullOrWhiteSpace($env:TAURI_SIGNING_PRIVATE_KEY_PATH)
    if (-not ($HasInlineKey -or $HasKeyPath)) {
        throw "Tauri updater artifacts are enabled. Set TAURI_SIGNING_PRIVATE_KEY or TAURI_SIGNING_PRIVATE_KEY_PATH before building NSIS."
    }
    if ($HasKeyPath -and -not (Test-Path -LiteralPath $env:TAURI_SIGNING_PRIVATE_KEY_PATH)) {
        throw "TAURI_SIGNING_PRIVATE_KEY_PATH does not exist."
    }
    if (-not $HasInlineKey -and $HasKeyPath) {
        $env:TAURI_SIGNING_PRIVATE_KEY = [System.IO.File]::ReadAllText(
            $env:TAURI_SIGNING_PRIVATE_KEY_PATH,
            [System.Text.Encoding]::UTF8
        ).Trim()
    }
}

Move-StaleNsisArtifacts
$UpdaterArtifactsEnabled = Test-UpdaterArtifactsEnabled
if ($UpdaterArtifactsEnabled) {
    Assert-UpdaterSigningEnv
}

Push-Location $DesktopDir
try {
    npx tauri build --bundles nsis
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri NSIS build failed. Exit code: $LASTEXITCODE."
    }
    $Installer = Get-ChildItem -Path $NsisDir -Filter "Lilsunspot_*_x64-setup.exe" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $Installer) {
        throw "NSIS installer not found in $NsisDir."
    }
    if ($UpdaterArtifactsEnabled -and -not (Test-Path -LiteralPath "$($Installer.FullName).sig")) {
        throw "Updater signature not found for $($Installer.FullName)."
    }
    Write-Host "Built NSIS installer: $($Installer.FullName)"
    if ($UpdaterArtifactsEnabled) {
        Write-Host "Built updater signature: $($Installer.FullName).sig"
    }
    else {
        Write-Host "Updater artifacts disabled for local NSIS build."
    }
}
finally {
    Pop-Location
}
