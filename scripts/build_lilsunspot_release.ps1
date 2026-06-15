param(
    [string] $OutputDir = "",
    [string] $MirrorBaseUrl = "https://updates.lilsunspot.com/lilsunspot/windows",
    [string] $ReleaseNotesFile = "",
    [switch] $Production
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DesktopDir = Join-Path $Root "lilsunspot\desktop"
$TauriConfigPath = Join-Path $DesktopDir "src-tauri\tauri.conf.json"
$NsisDir = Join-Path $DesktopDir "src-tauri\target\release\bundle\nsis"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $Root "ignored\lilsunspot-release"
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required for the lilsunspot release build."
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

function Assert-UpdaterSigningEnv {
    $HasInlineKey = -not [string]::IsNullOrWhiteSpace($env:TAURI_SIGNING_PRIVATE_KEY)
    $HasKeyPath = -not [string]::IsNullOrWhiteSpace($env:TAURI_SIGNING_PRIVATE_KEY_PATH)
    if (-not ($HasInlineKey -or $HasKeyPath)) {
        throw "TAURI_SIGNING_PRIVATE_KEY or TAURI_SIGNING_PRIVATE_KEY_PATH is required to create updater .sig artifacts."
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

function Get-ReleaseNotes {
    if (-not [string]::IsNullOrWhiteSpace($ReleaseNotesFile)) {
        if (-not (Test-Path -LiteralPath $ReleaseNotesFile)) {
            throw "Release notes file not found: $ReleaseNotesFile"
        }
        return (Get-Content -LiteralPath $ReleaseNotesFile -Raw).Trim()
    }
    return "小黑子 Windows 更新。"
}

function Assert-AuthenticodeForProduction {
    param(
        [Parameter(Mandatory = $true)]
        [string] $InstallerPath
    )

    $Signature = Get-AuthenticodeSignature -LiteralPath $InstallerPath
    if ($Production -and $Signature.Status -ne "Valid") {
        throw "Production release requires a valid Windows Authenticode signature. Current status: $($Signature.Status)."
    }
    if (-not $Production -and $Signature.Status -ne "Valid") {
        Write-Host "Staging build is not Authenticode-signed. Production release will be blocked until signing is valid."
    }
}

function Set-UpdaterArtifactsEnabled {
    param(
        [Parameter(Mandatory = $true)]
        [bool] $Enabled
    )

    $RawConfig = Get-Content -LiteralPath $TauriConfigPath -Raw
    $Config = $RawConfig | ConvertFrom-Json
    if (-not $Config.bundle) {
        throw "Tauri bundle config is missing."
    }
    $Config.bundle.createUpdaterArtifacts = $Enabled
    ($Config | ConvertTo-Json -Depth 100) | Set-Content -LiteralPath $TauriConfigPath -Encoding utf8
    return $RawConfig
}

Push-Location $Root
$OriginalTauriConfig = $null
try {
    Assert-Command "npm"
    Assert-UpdaterSigningEnv

    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    $OriginalTauriConfig = Set-UpdaterArtifactsEnabled $true
    Invoke-Native "desktop NSIS updater build" "npm" @("run", "tauri:build", "--prefix", $DesktopDir)

    $Installer = Get-ChildItem -Path $NsisDir -Filter "Lilsunspot_*_x64-setup.exe" -File -ErrorAction Stop |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $Installer) {
        throw "NSIS installer not found in $NsisDir."
    }

    Assert-AuthenticodeForProduction $Installer.FullName

    $SignaturePath = "$($Installer.FullName).sig"
    if (-not (Test-Path -LiteralPath $SignaturePath)) {
        throw "Updater signature not found: $SignaturePath"
    }

    $InstallerOut = Join-Path $OutputDir $Installer.Name
    $SignatureOut = Join-Path $OutputDir "$($Installer.Name).sig"
    Copy-Item -LiteralPath $Installer.FullName -Destination $InstallerOut -Force
    Copy-Item -LiteralPath $SignaturePath -Destination $SignatureOut -Force

    $Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $InstallerOut).Hash.ToLowerInvariant()
    $ChecksumPath = Join-Path $OutputDir "$($Installer.Name).sha256"
    Set-Content -LiteralPath $ChecksumPath -Value "$Hash  $($Installer.Name)" -Encoding utf8

    $TauriConfig = Get-Content -LiteralPath $TauriConfigPath -Raw | ConvertFrom-Json
    $Version = [string] $TauriConfig.version
    $PublishedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $Notes = Get-ReleaseNotes
    $DownloadUrl = "$($MirrorBaseUrl.TrimEnd('/'))/$($Installer.Name)"
    $Signature = (Get-Content -LiteralPath $SignatureOut -Raw).Trim()
    $Size = (Get-Item -LiteralPath $InstallerOut).Length

    $Manifest = [ordered]@{
        version = $Version
        notes = $Notes
        pub_date = $PublishedAt
        size = $Size
        critical = $false
        platforms = [ordered]@{
            "windows-x86_64" = [ordered]@{
                url = $DownloadUrl
                signature = $Signature
                size = $Size
            }
        }
    }

    $ManifestPath = Join-Path $OutputDir "latest.json"
    ($Manifest | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $ManifestPath -Encoding utf8

    Write-Host "Lilsunspot release artifacts ready:"
    Write-Host "Installer: $InstallerOut"
    Write-Host "Updater signature: $SignatureOut"
    Write-Host "Manifest: $ManifestPath"
    Write-Host "SHA256: $ChecksumPath"
}
finally {
    if ($null -ne $OriginalTauriConfig) {
        Set-Content -LiteralPath $TauriConfigPath -Value $OriginalTauriConfig -Encoding utf8NoBOM
    }
    Pop-Location
}
