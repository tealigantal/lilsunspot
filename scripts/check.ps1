$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $Root

try {
    Write-Host "== pytest: lilsunspot daemon =="
    python -m pytest lilsunspot/daemon/tests
    if ($LASTEXITCODE -ne 0) {
        throw "lilsunspot daemon pytest failed with exit code $LASTEXITCODE."
    }

    Write-Host "== secret guard =="
    python scripts/guard_no_secrets.py
    if ($LASTEXITCODE -ne 0) {
        throw "secret guard failed with exit code $LASTEXITCODE."
    }

    if ((Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path "lilsunspot/desktop/node_modules")) {
        Write-Host "== desktop build =="
        npm run build --prefix lilsunspot/desktop
        if ($LASTEXITCODE -ne 0) {
            throw "desktop build failed with exit code $LASTEXITCODE."
        }
    }
    else {
        Write-Warning "npm or lilsunspot/desktop/node_modules not found; desktop build skipped."
    }

    Write-Host "lilsunspot check passed."
}
finally {
    Pop-Location
}
