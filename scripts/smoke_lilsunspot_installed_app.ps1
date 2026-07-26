param(
    [string] $InstallerPath = "",
    [string] $InstallDir = "",
    [string] $DataDir = "",
    [switch] $SkipInstall,
    [switch] $KeepInstalled,
    [switch] $SeedLegacyConfig,
    [switch] $RealProviderE2E,
    [switch] $RealWeixinLoginProbe,
    [switch] $PurgeDataAfter,
    [int] $TimeoutSeconds = 25
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$NsisDir = Join-Path $Root "lilsunspot\desktop\src-tauri\target\release\bundle\nsis"
$DefaultSmokeInstallRoot = Join-Path ([System.IO.Path]::GetTempPath()) "lilsunspot-installed-app-smoke"
$DefaultSmokeDataRoot = Join-Path $Root "ignored\installed-app-smoke"

function Resolve-FullPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    return [System.IO.Path]::GetFullPath($Path)
}

function Add-TrailingSeparator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $separator = [System.IO.Path]::DirectorySeparatorChar
    if ($Path.EndsWith([string] $separator)) {
        return $Path
    }
    return "$Path$separator"
}

function Test-IsUnderPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Parent
    )

    $fullPath = Add-TrailingSeparator (Resolve-FullPath $Path)
    $fullParent = Add-TrailingSeparator (Resolve-FullPath $Parent)
    return $fullPath.StartsWith($fullParent, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-SafeCleanupPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Description
    )

    $ignoredRoot = Resolve-FullPath (Join-Path $Root "ignored")
    $tempRoot = Resolve-FullPath ([System.IO.Path]::GetTempPath())
    if ((Test-IsUnderPath $Path $ignoredRoot) -or (Test-IsUnderPath $Path $tempRoot)) {
        return
    }

    throw "$Description 不在 ignored 或系统临时目录下，拒绝递归清理：$Path"
}

function Remove-SmokeDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Assert-SafeCleanupPath $Path $Description
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function Assert-Path {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Description 不存在：$Path"
    }
}

function Invoke-Process {
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
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        throw "$Label 失败，退出码：$($process.ExitCode)"
    }
}

function Stop-LilsunspotProcesses {
    $names = @("Lilsunspot", "lilsunspotd", "lilsunspot_desktop")
    $processes = Get-Process -ErrorAction SilentlyContinue | Where-Object { $names -contains $_.ProcessName }
    foreach ($process in $processes) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    if ($processes) {
        Start-Sleep -Milliseconds 800
    }
}

function Get-ProcessByExecutablePath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProcessName,

        [Parameter(Mandatory = $true)]
        [string] $ExecutablePath
    )

    $expectedPath = Resolve-FullPath $ExecutablePath
    Get-CimInstance Win32_Process -Filter "Name = '$ProcessName'" |
        Where-Object {
            $_.ExecutablePath -and
            [string]::Equals((Resolve-FullPath $_.ExecutablePath), $expectedPath, [System.StringComparison]::OrdinalIgnoreCase)
        }
}

function Get-InstalledSidecarPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $InstallDir
    )

    $candidates = @(
        (Join-Path $InstallDir "resources\binaries\lilsunspotd\lilsunspotd.exe"),
        (Join-Path $InstallDir "binaries\lilsunspotd\lilsunspotd.exe"),
        (Join-Path $InstallDir "resources\lilsunspotd\lilsunspotd.exe"),
        (Join-Path $InstallDir "lilsunspotd.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-FullPath $candidate)
        }
    }
    throw "仓库外 lilsunspotd.exe 不存在。"
}

function Wait-ForCondition {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Description,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Condition,

        [Parameter(Mandatory = $true)]
        [int] $TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) {
            return
        }
        Start-Sleep -Milliseconds 250
    }

    throw "等待超时：$Description"
}

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = Join-Path $DefaultSmokeInstallRoot "app"
}
$InstallDir = Resolve-FullPath $InstallDir

if ([string]::IsNullOrWhiteSpace($DataDir)) {
    $DataDir = Join-Path $DefaultSmokeDataRoot "data"
}
$DataDir = Resolve-FullPath $DataDir

if (-not $SkipInstall) {
    if ([string]::IsNullOrWhiteSpace($InstallerPath)) {
        $installer = Get-ChildItem -Path $NsisDir -Filter "Lilsunspot_*_x64-setup.exe" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if (-not $installer) {
            throw "未找到 NSIS 安装包：$NsisDir"
        }
        $InstallerPath = $installer.FullName
    }
    $InstallerPath = Resolve-FullPath $InstallerPath
    Assert-Path $InstallerPath "NSIS 安装包"
}

$appPath = Join-Path $InstallDir "Lilsunspot.exe"
$sidecarPath = ""
$runtimeFile = Join-Path $DataDir "daemon-runtime.json"
$tokenFile = Join-Path $DataDir "runtime-token.json"
$previousDataDir = [System.Environment]::GetEnvironmentVariable("LILSUNSPOT_DATA_DIR", "Process")
$installedByScript = $false
$providerCount = 0
$extensionCounts = $null
$legacyConfigPath = Join-Path $DataDir "hermes_home\config.yaml"
$providerE2EPassed = $false
$weixinLoginProbePassed = $false

try {
    Stop-LilsunspotProcesses

    if (-not $SkipInstall) {
        Remove-SmokeDirectory $InstallDir "安装冒烟目录"
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $InstallDir) | Out-Null
        Invoke-Process "silent install" $InstallerPath @("/S", "/D=$InstallDir")
        $installedByScript = $true
    }

    Assert-Path $appPath "仓库外 Lilsunspot.exe"
    $sidecarPath = Get-InstalledSidecarPath $InstallDir
    Assert-Path $sidecarPath "仓库外 lilsunspotd.exe"

    Remove-SmokeDirectory $DataDir "安装冒烟数据目录"
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    if ($SeedLegacyConfig) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $legacyConfigPath) | Out-Null
        [System.IO.File]::WriteAllText($legacyConfigPath, "_config_version: 32`ndelegation:`n  max_async_children: 9`nlilsunspot:`n  provider: deepseek`n", [System.Text.UTF8Encoding]::new($false))
    }

    [System.Environment]::SetEnvironmentVariable("LILSUNSPOT_DATA_DIR", $DataDir, "Process")
    Write-Host "== launch installed app =="
    Start-Process -FilePath $appPath -WindowStyle Hidden | Out-Null

    Wait-ForCondition "Lilsunspot.exe 进程启动" {
        @(Get-ProcessByExecutablePath "Lilsunspot.exe" $appPath).Count -gt 0
    } $TimeoutSeconds

    Wait-ForCondition "lilsunspotd.exe 进程启动" {
        @(Get-ProcessByExecutablePath "lilsunspotd.exe" $sidecarPath).Count -gt 0
    } $TimeoutSeconds

    $runtimePayload = $null
    Wait-ForCondition "runtime discovery 写入" {
        if (-not (Test-Path -LiteralPath $runtimeFile)) {
            return $false
        }
        try {
            $script:runtimePayload = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
            return $true
        }
        catch {
            return $false
        }
    } $TimeoutSeconds

    if ($runtimePayload.type -ne "lilsunspot-daemon-runtime") {
        throw "runtime discovery 类型不正确。"
    }
    if ($runtimePayload.host -ne "127.0.0.1") {
        throw "lilsunspotd 没有绑定到 127.0.0.1。"
    }

    $baseUrl = [string] $runtimePayload.base_url
    $health = Invoke-RestMethod -Method Get -Uri "$baseUrl/health" -TimeoutSec 5
    if ($health.ok -ne $true) {
        throw "/health 没有返回 ok=true。"
    }

    Assert-Path $tokenFile "runtime token 文件"
    $tokenPayload = Get-Content -LiteralPath $tokenFile -Raw | ConvertFrom-Json
    $token = [string] $tokenPayload.token
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "runtime token 为空。"
    }

    $providersPayload = Invoke-RestMethod -Method Get -Uri "$baseUrl/providers" -Headers @{ "X-Lilsunspot-Token" = $token } -TimeoutSec 5
    $providerCount = @($providersPayload.providers).Count
    if ($providerCount -lt 1) {
        throw "/providers 没有返回 provider 列表。"
    }
    if ($SeedLegacyConfig) {
        $migratedConfig = Get-Content -LiteralPath $legacyConfigPath -Raw
        if ($migratedConfig -notmatch "(?m)^_config_version:\s*33\s*$") {
            throw "安装版没有将旧 Hermes 配置升级到 v33。"
        }
        $backups = @(Get-ChildItem -Path (Join-Path $DataDir "migration-backups") -Directory -Filter "hermes-config-v32-to-v33-*" -ErrorAction SilentlyContinue)
        if ($backups.Count -ne 1 -or -not (Test-Path -LiteralPath (Join-Path $backups[0].FullName "config.yaml"))) {
            throw "安装版 v33 配置升级没有留下可恢复备份。"
        }
    }

    $extensionsPayload = Invoke-RestMethod -Method Get -Uri "$baseUrl/extensions/catalog" -Headers @{ "X-Lilsunspot-Token" = $token } -TimeoutSec 5
    if ($extensionsPayload.ok -ne $true) {
        throw "/extensions/catalog 没有返回 ok=true。"
    }
    foreach ($asset in @("plugins", "skills", "optional-skills", "optional-mcps")) {
        if (-not $extensionsPayload.assets.$asset) {
            throw "/extensions/catalog 缺少已打包资产：$asset"
        }
    }
    $extensionCounts = $extensionsPayload.counts
    if ([int] $extensionCounts.plugin -lt 1 -or [int] $extensionCounts.skill -lt 1 -or [int] $extensionCounts.optional_mcp -lt 1 -or [int] $extensionCounts.gateway_adapter -lt 1) {
        throw "/extensions/catalog 没有发现完整的已映射扩展能力。"
    }
    if ($RealProviderE2E) {
        $providerKey = [System.Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Process")
        if ([string]::IsNullOrWhiteSpace($providerKey)) {
            $providerKey = [System.Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User")
        }
        if ([string]::IsNullOrWhiteSpace($providerKey)) {
            throw "没有可用于真实 Provider 验收的 DeepSeek API Key。"
        }
        $providerPayload = @{ provider = "deepseek"; model = "deepseek-chat"; api_key = $providerKey } | ConvertTo-Json -Compress
        $providerTest = Invoke-RestMethod -Method Post -Uri "$baseUrl/providers/test" -Headers @{ "X-Lilsunspot-Token" = $token } -ContentType "application/json" -Body $providerPayload -TimeoutSec 45
        if ($providerTest.ok -ne $true) {
            throw "真实 Provider 连通性测试失败。"
        }
        $providerSave = Invoke-RestMethod -Method Post -Uri "$baseUrl/providers/save" -Headers @{ "X-Lilsunspot-Token" = $token } -ContentType "application/json" -Body $providerPayload -TimeoutSec 20
        if ($providerSave.ok -ne $true) {
            throw "真实 Provider 保存失败。"
        }
        $chatPayload = @{ message = "请只回复：真实 Provider 已连接。" } | ConvertTo-Json -Compress
        $chat = Invoke-RestMethod -Method Post -Uri "$baseUrl/chat/send" -Headers @{ "X-Lilsunspot-Token" = $token } -ContentType "application/json" -Body $chatPayload -TimeoutSec 90
        if ($chat.ok -ne $true -or $chat.engine -ne "hermes_agent_loop") {
            throw "安装版真实 Provider 聊天失败。"
        }
        $providerE2EPassed = $true
    }
    if ($RealWeixinLoginProbe) {
        $weixinStart = Invoke-RestMethod -Method Post -Uri "$baseUrl/gateway/weixin/login/start" -Headers @{ "X-Lilsunspot-Token" = $token } -TimeoutSec 30
        $weixinLogin = $weixinStart.login
        if ($weixinStart.ok -ne $true -or [string] $weixinStart.status -ne "qr_pending" -or $null -eq $weixinLogin -or [string]::IsNullOrWhiteSpace([string] $weixinLogin.qr_image_data_url)) {
            throw "真实微信二维码获取失败。"
        }
        $weixinStatus = Invoke-RestMethod -Method Get -Uri "$baseUrl/gateway/weixin/login/status" -Headers @{ "X-Lilsunspot-Token" = $token } -TimeoutSec 30
        if ([string]::IsNullOrWhiteSpace([string] $weixinStatus.message)) {
            throw "真实微信登录状态没有返回中文说明。"
        }
        $weixinLoginProbePassed = $true
    }

    $logsDir = Join-Path $DataDir "logs"
    if (Test-Path -LiteralPath $logsDir) {
        $logText = (Get-ChildItem -Path $logsDir -Filter "*.log" -File -ErrorAction SilentlyContinue |
            ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }) -join "`n"
        if (-not [string]::IsNullOrEmpty($logText) -and $logText.Contains($token)) {
            throw "daemon 日志包含 runtime token。"
        }
    }

    Write-Host "Installed app smoke passed."
    Write-Host "App: $appPath"
    Write-Host "Sidecar: $sidecarPath"
    Write-Host "Data dir: $DataDir"
    Write-Host "Providers discovered: $providerCount"
    Write-Host "Extensions discovered: plugins=$($extensionCounts.plugin), skills=$($extensionCounts.skill), optional_mcps=$($extensionCounts.optional_mcp), gateways=$($extensionCounts.gateway_adapter)"
    if ($SeedLegacyConfig) {
        Write-Host "Legacy configuration upgraded to v33 with backup."
    }
    if ($providerE2EPassed) {
        Write-Host "Installed real Provider and Hermes chat passed."
    }
    if ($weixinLoginProbePassed) {
        Write-Host "Installed real Weixin QR login probe passed."
    }
}
finally {
    [System.Environment]::SetEnvironmentVariable("LILSUNSPOT_DATA_DIR", $previousDataDir, "Process")
    Stop-LilsunspotProcesses

    if ($installedByScript -and -not $KeepInstalled) {
        $uninstallerPath = Join-Path $InstallDir "uninstall.exe"
        if (Test-Path -LiteralPath $uninstallerPath) {
            Invoke-Process "silent uninstall" $uninstallerPath @("/S")
        }
        if (Test-Path -LiteralPath $InstallDir) {
            Remove-SmokeDirectory $InstallDir "安装冒烟目录"
        }
    }
    if ($PurgeDataAfter) {
        Remove-SmokeDirectory $DataDir "安装冒烟数据目录"
    }
}
