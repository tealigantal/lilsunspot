$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$SidecarDir = Join-Path $Root "lilsunspot\desktop\src-tauri\binaries"
$WorkDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\build"
$SpecDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\spec"
$DistDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\dist"
$SidecarName = "lilsunspotd-x86_64-pc-windows-msvc.exe"
$SidecarPath = Join-Path $SidecarDir $SidecarName
$ResourceSource = Join-Path $Root "lilsunspot\resources"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required to run the pinned PyInstaller build."
}

New-Item -ItemType Directory -Force -Path $SidecarDir, $WorkDir, $SpecDir, $DistDir | Out-Null

Push-Location $Root
try {
    $PyInstallerArgs = @(
        "run",
        "--extra", "web",
        "--with", "pyinstaller==6.16.0",
        "pyinstaller",
        "--onefile",
        "--clean",
        "--noconfirm",
        "--name", "lilsunspotd",
        "--distpath", $DistDir,
        "--workpath", $WorkDir,
        "--specpath", $SpecDir,
        "--hidden-import", "lilsunspot.daemon.app",
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan.on",
        "--collect-submodules", "lilsunspot.daemon",
        "--add-data", "$ResourceSource;lilsunspot\resources",
        "lilsunspot\daemon\sidecar_main.py"
    )

    & uv @PyInstallerArgs

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build lilsunspotd. Exit code: $LASTEXITCODE."
    }

    $BuiltExe = Join-Path $DistDir "lilsunspotd.exe"
    if (-not (Test-Path $BuiltExe)) {
        throw "PyInstaller did not create $BuiltExe."
    }

    Copy-Item -Force -LiteralPath $BuiltExe -Destination $SidecarPath
    Write-Host "Built daemon sidecar: $SidecarPath"
}
finally {
    Pop-Location
}
