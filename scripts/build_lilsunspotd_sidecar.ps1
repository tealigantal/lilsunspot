$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$SidecarDir = Join-Path $Root "lilsunspot\desktop\src-tauri\binaries"
$SidecarBundleDir = Join-Path $SidecarDir "lilsunspotd"
$WorkDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\build"
$SpecDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\spec"
$DistDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\dist"
$FallbackVenvDir = Join-Path $Root "ignored\pyinstaller-lilsunspotd\venv"
$FallbackPython = Join-Path $FallbackVenvDir "Scripts\python.exe"
$SidecarName = "lilsunspotd-x86_64-pc-windows-msvc.exe"
$SidecarPath = Join-Path $SidecarDir $SidecarName
$SidecarExePath = Join-Path $SidecarBundleDir "lilsunspotd.exe"
$ResourceSource = Join-Path $Root "lilsunspot\resources"
$UpstreamCommitSource = Join-Path $Root "lilsunspot\UPSTREAM_COMMIT.txt"
$PluginSource = Join-Path $Root "plugins"
$SkillsSource = Join-Path $Root "skills"
$OptionalSkillsSource = Join-Path $Root "optional-skills"
$OptionalMcpsSource = Join-Path $Root "optional-mcps"

$PyInstallerCliArgs = @(
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
    "--collect-submodules", "gateway",
    "--collect-submodules", "plugins",
    "--collect-submodules", "agent",
    "--collect-submodules", "model_tools",
    "--collect-submodules", "tools",
    "--collect-submodules", "hermes_cli",
    "--add-data", "$ResourceSource;lilsunspot\resources",
    "--add-data", "$UpstreamCommitSource;lilsunspot",
    "--add-data", "$PluginSource;plugins",
    "--add-data", "$SkillsSource;skills",
    "--add-data", "$OptionalSkillsSource;optional-skills",
    "--add-data", "$OptionalMcpsSource;optional-mcps",
    "lilsunspot\daemon\sidecar_main.py"
)

function Invoke-PyInstallerWithUv {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Warning "uv not found; falling back to local PyInstaller venv."
        return $false
    }

    $UvArgs = @(
        "run",
        "--extra", "web",
        "--extra", "lilsunspot",
        "--extra", "messaging",
        "--with", "pyinstaller==6.16.0",
        "pyinstaller"
    ) + $PyInstallerCliArgs

    & uv @UvArgs
    return $LASTEXITCODE -eq 0
}

function Invoke-PyInstallerWithFallbackVenv {
    if (-not (Test-Path -LiteralPath $FallbackPython)) {
        $SystemPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $SystemPython) {
            throw "Python is required to create the fallback PyInstaller build environment."
        }
        & $SystemPython.Source -m venv $FallbackVenvDir
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create fallback PyInstaller venv. Exit code: $LASTEXITCODE."
        }
    }

    $PyInstallerModule = Join-Path $FallbackVenvDir "Lib\site-packages\PyInstaller\__init__.py"
    $ProjectDistInfo = Join-Path $FallbackVenvDir "Lib\site-packages\hermes_agent-0.14.0.dist-info"
    if ((-not (Test-Path -LiteralPath $PyInstallerModule)) -or (-not (Test-Path -LiteralPath $ProjectDistInfo))) {
        Write-Host "Installing pinned PyInstaller build dependencies into fallback venv..."
        $env:PIP_DEFAULT_TIMEOUT = "60"
        & $FallbackPython -m pip install --disable-pip-version-check -e ".[web,lilsunspot,messaging]" "pyinstaller==6.16.0"
        if ($LASTEXITCODE -ne 0) {
            throw "Fallback PyInstaller dependency install failed. Check PyPI/TLS connectivity, then rerun the NSIS build."
        }
    }

    & $FallbackPython -m PyInstaller @PyInstallerCliArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Fallback PyInstaller failed to build lilsunspotd. Exit code: $LASTEXITCODE."
    }
}

New-Item -ItemType Directory -Force -Path $SidecarDir, $WorkDir, $SpecDir, $DistDir | Out-Null

Push-Location $Root
try {
    if (-not (Invoke-PyInstallerWithUv)) {
        Invoke-PyInstallerWithFallbackVenv
    }

    $BuiltDir = Join-Path $DistDir "lilsunspotd"
    $BuiltExe = Join-Path $BuiltDir "lilsunspotd.exe"
    if (-not (Test-Path $BuiltExe)) {
        throw "PyInstaller did not create $BuiltExe."
    }

    if (Test-Path -LiteralPath $SidecarBundleDir) {
        Remove-Item -LiteralPath $SidecarBundleDir -Recurse -Force
    }
    if (Test-Path -LiteralPath $SidecarPath) {
        Remove-Item -LiteralPath $SidecarPath -Force
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
