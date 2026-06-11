$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$SidecarDir = Join-Path $Root "lilsunspot\desktop\src-tauri\binaries"
$SidecarBundleDir = Join-Path $SidecarDir "lilsunspotd"
$WorkDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\build"
$SpecDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\spec"
$DistDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\dist"
$SidecarName = "lilsunspotd-x86_64-pc-windows-msvc.exe"
$SidecarPath = Join-Path $SidecarDir $SidecarName
$SidecarExePath = Join-Path $SidecarBundleDir "lilsunspotd.exe"
$ResourceSource = Join-Path $Root "lilsunspot\resources"
$UpstreamCommitSource = Join-Path $Root "lilsunspot\UPSTREAM_COMMIT.txt"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required to run the pinned PyInstaller build."
}

New-Item -ItemType Directory -Force -Path $SidecarDir, $WorkDir, $SpecDir, $DistDir | Out-Null
if (Test-Path -LiteralPath $SidecarBundleDir) {
    Remove-Item -LiteralPath $SidecarBundleDir -Recurse -Force
}
if (Test-Path -LiteralPath $SidecarPath) {
    Remove-Item -LiteralPath $SidecarPath -Force
}

Push-Location $Root
try {
    $PyInstallerArgs = @(
        "run",
        "--extra", "web",
        "--with", "pyinstaller==6.16.0",
        "--with", "aiohttp==3.13.3",
        "--with", "qrcode==7.4.2",
        "--with", "pypdf==6.13.1",
        "--with", "python-docx==1.2.0",
        "--with", "openpyxl==3.1.5",
        "pyinstaller",
        "--onedir",
        "--clean",
        "--noconsole",
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
        "--hidden-import", "gateway.platforms.weixin",
        "--hidden-import", "aiohttp",
        "--hidden-import", "qrcode",
        "--hidden-import", "qrcode.image.svg",
        "--hidden-import", "pypdf",
        "--hidden-import", "docx",
        "--hidden-import", "openpyxl",
        "--hidden-import", "openpyxl.cell._writer",
        "--hidden-import", "openpyxl.worksheet._reader",
        "--hidden-import", "run_agent",
        "--hidden-import", "hermes_state",
        "--hidden-import", "gateway.session_context",
        "--hidden-import", "tools.approval",
        "--collect-submodules", "lilsunspot.daemon",
        "--collect-submodules", "agent",
        "--collect-submodules", "model_tools",
        "--collect-submodules", "tools",
        "--collect-submodules", "hermes_cli",
        "--add-data", "$ResourceSource;lilsunspot\resources",
        "--add-data", "$UpstreamCommitSource;lilsunspot",
        "lilsunspot\daemon\sidecar_main.py"
    )

    & uv @PyInstallerArgs

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build lilsunspotd. Exit code: $LASTEXITCODE."
    }

    $BuiltDir = Join-Path $DistDir "lilsunspotd"
    $BuiltExe = Join-Path $BuiltDir "lilsunspotd.exe"
    if (-not (Test-Path $BuiltExe)) {
        throw "PyInstaller did not create $BuiltExe."
    }

    Copy-Item -Force -Recurse -LiteralPath $BuiltDir -Destination $SidecarBundleDir
    if (-not (Test-Path $SidecarExePath)) {
        throw "Sidecar bundle copy did not create $SidecarExePath."
    }
    Write-Host "Built daemon sidecar directory: $SidecarBundleDir"
}
finally {
    Pop-Location
}
