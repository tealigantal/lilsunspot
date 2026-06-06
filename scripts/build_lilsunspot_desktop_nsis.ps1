$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DesktopDir = Join-Path $Root "lilsunspot\desktop"

Push-Location $DesktopDir
try {
    npx tauri build --bundles nsis
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri NSIS build failed. Exit code: $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
