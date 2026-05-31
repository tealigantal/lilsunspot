$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $Root

try {
    Write-Host "== pytest: lilsunspot daemon =="
    python -m pytest lilsunspot/daemon/tests

    Write-Host "== secret guard =="
    python scripts/guard_no_secrets.py

    if ((Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path "lilsunspot/desktop/node_modules")) {
        Write-Host "== desktop build =="
        npm run build --prefix lilsunspot/desktop
    }
    else {
        Write-Warning "npm or lilsunspot/desktop/node_modules not found; desktop build skipped."
    }

    Write-Host "lilsunspot check passed."
}
finally {
    Pop-Location
}
