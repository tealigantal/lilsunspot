param(
    [string] $Remote = "upstream",
    [string] $Branch = "main",
    [switch] $Fetch,
    [string] $ReportDir = "",
    [string] $BaseFile = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($ReportDir)) {
    $ReportDir = Join-Path $Root "lilsunspot\notes\upstream-sync-reports"
}

if ([string]::IsNullOrWhiteSpace($BaseFile)) {
    $BaseFile = Join-Path $Root "lilsunspot\UPSTREAM_COMMIT.txt"
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required for Hermes upstream checks."
    }
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $Arguments,

        [switch] $AllowFailure
    )

    $Output = & git @Arguments 2>&1
    $ExitCode = $LASTEXITCODE
    if (($ExitCode -ne 0) -and (-not $AllowFailure)) {
        throw "git $($Arguments -join ' ') failed. Exit code: $ExitCode. $Output"
    }

    return @($Output | ForEach-Object { "$_" })
}

function Test-GitCommit {
    param(
        [AllowNull()]
        [string] $Revision
    )

    if ([string]::IsNullOrWhiteSpace($Revision)) {
        return $false
    }

    & git "cat-file" "-e" "$Revision^{commit}" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Get-FirstNonEmptyLine {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }

    $Lines = @(Get-Content -LiteralPath $Path | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($Lines.Count -eq 0) {
        return ""
    }

    return $Lines[0].Trim()
}

function Get-ChangeCategory {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $Normalized = $Path.Replace("\", "/")

    if ($Normalized -eq "pyproject.toml" -or
        $Normalized -like "package*.json" -or
        $Normalized -like "*/package*.json" -or
        $Normalized -like "*/Cargo.toml" -or
        $Normalized -like "*/Cargo.lock") {
        return "Packaging/deps"
    }

    if ($Normalized -like "lilsunspot/*") {
        return "lilsunspot product"
    }

    if ($Normalized -like "gateway/*") {
        return "Messaging gateway"
    }

    if ($Normalized -like "tools/*") {
        return "Tools"
    }

    if ($Normalized -like "providers/*" -or
        $Normalized -like "hermes_cli/models*" -or
        $Normalized -like "hermes_cli/model_*" -or
        $Normalized -eq "agent/model_metadata.py") {
        return "Provider/model"
    }

    if ($Normalized -like "web/*" -or
        $Normalized -like "ui-tui/*" -or
        $Normalized -like "tui_gateway/*") {
        return "Dashboard/TUI"
    }

    if ($Normalized -like "cron/*" -or
        $Normalized -like "plugins/*" -or
        $Normalized -like "skills/*" -or
        $Normalized -like "optional-skills/*" -or
        $Normalized -like "agent/memory*") {
        return "Cron/memory/skills/plugins"
    }

    if ($Normalized -like "agent/*") {
        return "Hermes core runtime"
    }

    if ($Normalized -like "hermes_cli/*") {
        return "Hermes CLI"
    }

    return "Other upstream"
}

function Add-ReportLine {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Lines,

        [AllowNull()]
        [string] $Value
    )

    if ($null -eq $Value) {
        $Lines.Add("") | Out-Null
    }
    else {
        $Lines.Add($Value) | Out-Null
    }
}

function Format-StringList {
    param(
        [AllowNull()]
        [object] $Value
    )

    if ($null -eq $Value) {
        return "None"
    }
    $Items = @(@($Value) |
        ForEach-Object { "$_".Trim() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($Items.Count -eq 0) {
        return "None"
    }
    return (($Items | ForEach-Object { '`' + $_ + '`' }) -join ", ")
}

Push-Location $Root
try {
    Assert-Command "git"

    if ($Fetch) {
        Invoke-Git @("fetch", $Remote, $Branch) | Out-Null
    }

    $RemoteRef = "$Remote/$Branch"
    $RemoteCommitLines = @(Invoke-Git @("rev-parse", "--verify", "$RemoteRef^{commit}"))
    $RemoteCommit = $RemoteCommitLines[0]

    $HeadLines = @(Invoke-Git @("rev-parse", "HEAD"))
    $HeadCommit = $HeadLines[0]
    $HeadShortLines = @(Invoke-Git @("rev-parse", "--short", "HEAD"))
    $HeadShort = $HeadShortLines[0]
    $CurrentBranchLines = @(Invoke-Git @("branch", "--show-current"))
    $CurrentBranch = ""
    if ($CurrentBranchLines.Count -gt 0) {
        $CurrentBranch = $CurrentBranchLines[0]
    }

    $StatusLines = @(Invoke-Git @("status", "--short"))
    $Dirty = ($StatusLines.Count -gt 0)

    $RecordedBase = Get-FirstNonEmptyLine $BaseFile
    $RecordedBaseValid = Test-GitCommit $RecordedBase
    $ComparisonBase = $RecordedBase
    $ComparisonBaseSource = "recorded upstream base"

    if (-not $RecordedBaseValid) {
        $MergeBaseLines = @(Invoke-Git @("merge-base", "HEAD", $RemoteCommit) -AllowFailure)
        if ($LASTEXITCODE -eq 0 -and $MergeBaseLines.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($MergeBaseLines[0])) {
            $ComparisonBase = $MergeBaseLines[0]
            $ComparisonBaseSource = "git merge-base HEAD $RemoteRef"
        }
        else {
            $ComparisonBase = $HeadCommit
            $ComparisonBaseSource = "HEAD fallback"
        }
    }

    $CommitCountLines = @(Invoke-Git @("rev-list", "--count", "$ComparisonBase..$RemoteCommit"))
    $CommitCount = $CommitCountLines[0]
    $RecentCommits = @(Invoke-Git @("log", "--oneline", "--max-count=20", "$ComparisonBase..$RemoteCommit"))
    $ChangedFiles = @(Invoke-Git @("diff", "--name-only", "$ComparisonBase..$RemoteCommit") |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

    $CategoryCounts = [ordered]@{}
    foreach ($Path in $ChangedFiles) {
        $Category = Get-ChangeCategory $Path
        if (-not $CategoryCounts.Contains($Category)) {
            $CategoryCounts[$Category] = 0
        }
        $CategoryCounts[$Category] = [int] $CategoryCounts[$Category] + 1
    }

    $CapabilityAudit = $null
    $CapabilityAuditError = ""
    try {
        $AuditJson = @(& python "-m" "lilsunspot.daemon.upstream_audit" "--repo-root" $Root "--upstream-ref" $RemoteRef 2>&1)
        $AuditExitCode = $LASTEXITCODE
        if ($AuditExitCode -eq 0 -and $AuditJson.Count -gt 0) {
            $CapabilityAudit = ($AuditJson -join [Environment]::NewLine) | ConvertFrom-Json
        }
        else {
            $CapabilityAuditError = "python upstream audit failed. Exit code: $AuditExitCode. $($AuditJson -join ' ')"
        }
    }
    catch {
        $CapabilityAuditError = "$_"
    }

    New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
    $Timestamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
    $ReportPath = Join-Path $ReportDir "$Timestamp.md"
    $GeneratedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"

    $Lines = New-Object "System.Collections.Generic.List[string]"
    Add-ReportLine $Lines "# Hermes upstream check report"
    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "Generated: $GeneratedAt"
    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "Scope:"
    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "- This report is read-only."
    Add-ReportLine $Lines "- Fetch requested: $([bool] $Fetch)"
    Add-ReportLine $Lines "- No branch creation, source-control mutation, dependency install, or build was performed."
    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "## Repository"
    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "- Branch: $CurrentBranch"
    Add-ReportLine $Lines "- HEAD: $HeadShort"
    Add-ReportLine $Lines "- Working tree dirty: $Dirty"
    Add-ReportLine $Lines "- Dirty entry count: $($StatusLines.Count)"
    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "## Upstream reference"
    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "- Remote: $Remote"
    Add-ReportLine $Lines "- Branch: $Branch"
    Add-ReportLine $Lines "- Remote ref: $RemoteRef"
    Add-ReportLine $Lines "- Remote commit: $RemoteCommit"
    Add-ReportLine $Lines "- Base file: $BaseFile"
    Add-ReportLine $Lines "- Recorded base: $RecordedBase"
    Add-ReportLine $Lines "- Recorded base valid: $RecordedBaseValid"
    Add-ReportLine $Lines "- Comparison base: $ComparisonBase"
    Add-ReportLine $Lines "- Comparison base source: $ComparisonBaseSource"
    Add-ReportLine $Lines "- Upstream commits since comparison base: $CommitCount"
    Add-ReportLine $Lines ""

    Add-ReportLine $Lines "## Capability surface gaps"
    Add-ReportLine $Lines ""
    if ($null -eq $CapabilityAudit) {
        Add-ReportLine $Lines "- Capability audit unavailable: $CapabilityAuditError"
    }
    else {
        Add-ReportLine $Lines "- Latest upstream commit: $($CapabilityAudit.latest_commit)"
        Add-ReportLine $Lines "- Recorded base: $($CapabilityAudit.recorded_base)"
        Add-ReportLine $Lines "- Sync eligible: $($CapabilityAudit.sync_eligible)"
        Add-ReportLine $Lines "- Missing TOOLSETS in current worktree: $(Format-StringList $CapabilityAudit.missing_toolsets)"
        Add-ReportLine $Lines "- Missing CONFIGURABLE_TOOLSETS in current worktree: $(Format-StringList $CapabilityAudit.missing_configurable_toolsets)"
        Add-ReportLine $Lines "- Missing /capabilities mappings: $(Format-StringList $CapabilityAudit.missing_capability_mappings)"
        Add-ReportLine $Lines "- Missing DEFAULT_CONFIG keys in current worktree: $(Format-StringList $CapabilityAudit.missing_default_config_keys)"
        Add-ReportLine $Lines "- Missing DEFAULT_CONFIG capability mappings: $(Format-StringList $CapabilityAudit.missing_config_mappings)"
    }
    Add-ReportLine $Lines ""

    Add-ReportLine $Lines "## Change categories"
    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "| Category | Changed files |"
    Add-ReportLine $Lines "| --- | ---: |"

    if ($CategoryCounts.Count -eq 0) {
        Add-ReportLine $Lines "| No changes | 0 |"
    }
    else {
        foreach ($Category in $CategoryCounts.Keys) {
            Add-ReportLine $Lines "| $Category | $($CategoryCounts[$Category]) |"
        }
    }

    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "## Recent upstream commits"
    Add-ReportLine $Lines ""
    if ($RecentCommits.Count -eq 0) {
        Add-ReportLine $Lines "- None"
    }
    else {
        foreach ($Commit in $RecentCommits) {
            Add-ReportLine $Lines ('- `' + $Commit + '`')
        }
    }

    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "## Changed files sample"
    Add-ReportLine $Lines ""
    if ($ChangedFiles.Count -eq 0) {
        Add-ReportLine $Lines "- None"
    }
    else {
        foreach ($Path in ($ChangedFiles | Select-Object -First 120)) {
            Add-ReportLine $Lines ('- `' + $Path + '`')
        }
        if ($ChangedFiles.Count -gt 120) {
            Add-ReportLine $Lines "- ... $($ChangedFiles.Count - 120) more"
        }
    }

    Add-ReportLine $Lines ""
    Add-ReportLine $Lines "## Next action"
    Add-ReportLine $Lines ""
    if ($Dirty) {
        Add-ReportLine $Lines "- Do not run a sync step until unrelated working-tree changes are committed, stashed, or explicitly excluded."
    }
    else {
        Add-ReportLine $Lines "- Working tree is clean enough for a future controlled sync branch."
    }
    Add-ReportLine $Lines '- Before any sync, review changes touching `lilsunspot/`, `gateway/`, `tools/`, packaging files, and desktop/Tauri paths.'
    Add-ReportLine $Lines '- Required validation after a real sync: daemon tests, product tests, secret guard, desktop build, `scripts/check.ps1`, and NSIS build if installer-impacting paths changed.'

    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($ReportPath, ($Lines -join [Environment]::NewLine) + [Environment]::NewLine, $Utf8NoBom)

    Write-Host "Hermes upstream check report: $ReportPath"
    Write-Host "Remote ref: $RemoteRef"
    Write-Host "Remote commit: $RemoteCommit"
    Write-Host "Comparison base: $ComparisonBase"
    Write-Host "Commits since comparison base: $CommitCount"
    Write-Host "Changed files: $($ChangedFiles.Count)"
    if ($Dirty) {
        Write-Host "Working tree is dirty; future sync should wait for a clean or explicitly scoped tree."
    }
}
finally {
    Pop-Location
}
