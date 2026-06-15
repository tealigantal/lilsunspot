param(
    [string] $Remote = "upstream",
    [string] $Branch = "main",
    [string] $SyncBranch = "",
    [switch] $Fetch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$UpstreamCommitFile = Join-Path $Root "lilsunspot\UPSTREAM_COMMIT.txt"
$CheckScript = Join-Path $Root "scripts\hermes_upstream_check.ps1"

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required for Hermes upstream sync."
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

function Get-GitOutput {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $Arguments
    )

    $Output = & git @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed. $Output"
    }
    return @($Output | ForEach-Object { "$_" })
}

Push-Location $Root
try {
    Assert-Command "git"
    Assert-Command "pwsh"

    $DirtyEntries = @(Get-GitOutput @("status", "--short") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($DirtyEntries.Count -gt 0) {
        throw "Working tree is dirty. Commit or stash changes before running Hermes upstream sync."
    }

    if ($Fetch) {
        Invoke-Native "fetch upstream" "git" @("fetch", $Remote, $Branch)
    }

    $RemoteRef = "$Remote/$Branch"
    $RemoteCommit = (Get-GitOutput @("rev-parse", "--verify", "$RemoteRef^{commit}"))[0].Trim()
    $RecordedCommit = ""
    if (Test-Path -LiteralPath $UpstreamCommitFile) {
        $RecordedCommit = (Get-Content -LiteralPath $UpstreamCommitFile -Raw).Trim()
    }
    if ($RecordedCommit -eq $RemoteCommit) {
        throw "Recorded Hermes upstream commit is already current: $RemoteCommit"
    }
    if ([string]::IsNullOrWhiteSpace($SyncBranch)) {
        $SyncBranch = "codex/upstream-sync-$(Get-Date -Format 'yyyyMMdd')"
    }

    $ExistingBranch = & git "rev-parse" "--verify" "--quiet" $SyncBranch 2>$null
    if ($LASTEXITCODE -eq 0) {
        throw "Sync branch already exists: $SyncBranch"
    }

    Invoke-Native "create sync branch" "git" @("switch", "-c", $SyncBranch)
    Invoke-Native "pre-merge upstream report" "pwsh" @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $CheckScript,
        "-Remote",
        $Remote,
        "-Branch",
        $Branch
    )

    Invoke-Native "merge official Hermes upstream" "git" @(
        "merge",
        "--no-ff",
        $RemoteRef,
        "-m",
        "Merge official Hermes upstream $RemoteCommit"
    )

    Set-Content -LiteralPath $UpstreamCommitFile -Value $RemoteCommit -NoNewline -Encoding utf8
    Invoke-Native "stage upstream commit marker" "git" @("add", "lilsunspot/UPSTREAM_COMMIT.txt")
    Invoke-Native "record upstream marker in merge commit" "git" @("commit", "--amend", "--no-edit")

    Invoke-Native "post-merge upstream report" "pwsh" @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $CheckScript,
        "-Remote",
        $Remote,
        "-Branch",
        $Branch
    )

    Write-Host "Hermes upstream sync branch ready: $SyncBranch"
    Write-Host "Recorded upstream commit: $RemoteCommit"
    Write-Host "Next: resolve any product adapter gaps, then run focused Hermes compatibility checks and scripts/check.ps1."
}
finally {
    Pop-Location
}
