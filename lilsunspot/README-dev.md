# lilsunspot 开发说明

产品名：`lilsunspot`
中文名：`小黑子`

`lilsunspot/` 是 Hermes Agent fork 里的产品层代码。当前目标是把 Windows 桌面个人助手的本地启动、Provider 配置、桌面首启流程和安全边界先跑通；不要改 Hermes 核心业务代码。

## 当前状态

已具备：

- `lilsunspotd` 本地 FastAPI daemon，固定绑定 `127.0.0.1`。
- 本地 runtime token 与 daemon discovery 文件。
- Tauri 2 + React + TypeScript 桌面端。
- 桌面端自动连接 daemon；开发浏览器模式支持手动 token。
- Provider 列表、打开 Key 页面、真实 `/chat/completions` 最小连接测试、保存 Hermes 兼容配置。
- 模式配置、微信状态、安全策略、诊断页的本地 API 骨架。
- secret guard、daemon pytest、desktop TypeScript/Vite build 检查入口。

仍是占位：

- `/chat/send` 不调用真实模型，只检查 Provider 配置是否完整并返回占位回复。
- 微信扫码、联系人、消息发送尚未实现。
- 安全审批队列只有策略和占位接口。
- 诊断修复与诊断包导出仍是占位。
- Windows 安装包和最终 `Lilsunspot.exe -> lilsunspotd` 分发链路尚未完成。

## 目录

- `daemon/`: `lilsunspotd` 本地 daemon。
- `desktop/`: Tauri 桌面端和 React UI。
- `resources/`: Provider registry、默认输出风格、安全策略。
- `daemon/tests/`: daemon API、鉴权、资源和 secret guard 相关测试。
- `tests/`: 产品层补充测试。
- `notes/`: 当前阶段调研和状态记录。
- `installer/`, `plugins/`, `profile_card/`: 后续产品能力占位。

## 本地数据

默认数据目录：

```powershell
%LOCALAPPDATA%\Lilsunspot\data
```

可用临时目录覆盖，测试和本地实验优先使用：

```powershell
$env:LILSUNSPOT_DATA_DIR = "$pwd\.tmp-lilsunspot-data"
```

主要文件：

- `runtime-token.json`: 本地 API token。只能本机使用，不应进入日志、prompt、fixture、截图或诊断文本。
- `daemon-runtime.json`: daemon discovery 文件，包含 `127.0.0.1` base URL、端口、进程号、数据目录和 token 文件路径，不包含 token 明文。
- `hermes_home/.env`: Provider API Key 存储位置。
- `hermes_home/config.yaml`: Hermes 兼容模型配置，同时写入 `lilsunspot.provider` 和 `lilsunspot.model`。
- `logs/`: daemon 日志目录。

## 启动 daemon

从仓库根目录运行：

```powershell
python -m lilsunspot.daemon.launcher
```

默认地址：

```text
http://127.0.0.1:8765
```

`lilsunspotd` 只能绑定 `127.0.0.1`。`LILSUNSPOT_BIND_HOST` 如果不是 `127.0.0.1` 会启动失败；端口可通过 `LILSUNSPOT_BIND_PORT` 覆盖。

## 启动桌面端

开发浏览器模式：

```powershell
cd lilsunspot/desktop
npm install
npm run dev
```

Tauri 桌面模式：

```powershell
cd lilsunspot/desktop
npm run tauri:dev
```

桌面模式会调用 Tauri `connect_daemon`：

1. 先读取 `daemon-runtime.json` 并检查 `/health`。
2. 如果没有健康 daemon，尝试启动 `lilsunspotd.exe`、同目录 `lilsunspotd`、PATH 中的 `lilsunspotd`。
3. debug 构建下还会尝试 `python -m lilsunspot.daemon.launcher`。
4. 之后读取 `runtime-token.json`，通过 `daemon_request` 访问受保护 API。

浏览器开发模式没有 Tauri token 代理，需要在页面的开发者模式区域手动填入 `runtime-token.json` 里的 token。

## API 规则

公开 API：

- `GET /health`

除 `/health` 外，所有本地 API 都必须带：

```text
X-Lilsunspot-Token: <runtime token>
```

当前 API：

- `GET /app/state`
- `GET /runtime/info`
- `GET /providers`
- `POST /providers/open-key-url`
- `POST /providers/test`
- `POST /providers/save`
- `GET /modes`
- `GET /modes/current`
- `POST /modes/select`
- `POST /chat/send`
- `GET /gateway/weixin/status`
- `GET /gateway/weixin/commands`
- `GET /safety/policy`
- `GET /safety/approvals`
- `POST /safety/approvals/placeholder`
- `GET /doctor/run`
- `POST /doctor/repair`

用户可见错误要保持普通中文。API Key、runtime token 不能出现在响应明文、日志、测试 fixture、截图或诊断文本中。

## Provider 配置

Provider registry 在：

```text
lilsunspot/resources/provider_registry.yaml
```

当前内置：

- `deepseek`
- `kimi`
- `qwen`
- `ollama`
- `openrouter`
- `openai`

`POST /providers/test` 会：

- 从 registry 读取 `base_url`，没有时退回 `detect_url`。
- 对 OpenAI-compatible `chat/completions` 发起最小请求。
- cloud provider 必须提供 API Key。
- local provider 可以不提供 API Key。
- 成功必须证明 API Key 和模型组合被服务商接受。
- 失败会映射为 `invalid_key`、`quota_exceeded`、`rate_limited`、`network_error`、`model_not_found` 或 `unknown`。
- `safe_details.masked_key` 只允许出现脱敏后的 Key。

`POST /providers/save` 会把配置写到 `hermes_home/.env` 和 `hermes_home/config.yaml`。保存前应先完成连接测试；当前接口本身不重新探测。

## 本机 API Key 实测

优先用临时数据目录做实测，避免污染日常配置，也方便删掉测试数据：

```powershell
$env:LILSUNSPOT_DATA_DIR = "$pwd\.tmp-lilsunspot-data"
python -m lilsunspot.daemon.launcher
```

另开一个 PowerShell，从 discovery/token 文件读取本地 token：

```powershell
$dataDir = "$pwd\.tmp-lilsunspot-data"
$token = (Get-Content "$dataDir\runtime-token.json" | ConvertFrom-Json).token
```

不要把真实 API Key 写进命令行、README、提交信息或截图。实测时从本机环境变量读取 Key，不手动粘贴、不打印 Key。

常用 provider 对应环境变量：

- `deepseek`: `DEEPSEEK_API_KEY`
- `kimi`: `KIMI_API_KEY`
- `qwen`: `DASHSCOPE_API_KEY`
- `openrouter`: `OPENROUTER_API_KEY`
- `openai`: `OPENAI_API_KEY`

如果环境变量是刚设置的，重新打开 PowerShell 后再跑下面命令。

选择 provider、模型和对应环境变量：

```powershell
$provider = "deepseek"
$model = "deepseek-chat"
$apiKeyEnv = "DEEPSEEK_API_KEY"
```

从环境变量读取 Key，并调用 `/providers/test`：

```powershell
$apiKey = [Environment]::GetEnvironmentVariable($apiKeyEnv, "Process")
if (-not $apiKey) {
    $apiKey = [Environment]::GetEnvironmentVariable($apiKeyEnv, "User")
}
if (-not $apiKey) {
    $apiKey = [Environment]::GetEnvironmentVariable($apiKeyEnv, "Machine")
}
if (-not $apiKey) {
    throw "没有读取到环境变量 $apiKeyEnv。请确认已设置，并重新打开 PowerShell。"
}

try {
    $body = @{
        provider = $provider
        model = $model
        api_key = $apiKey
    } | ConvertTo-Json

    Invoke-RestMethod `
        -Method Post `
        -Uri "http://127.0.0.1:8765/providers/test" `
        -Headers @{ "X-Lilsunspot-Token" = $token } `
        -ContentType "application/json" `
        -Body $body
}
finally {
    $apiKey = $null
    $body = $null
}
```

成功时预期返回：

```text
ok: true
title: 模型服务连接通过
message: 模型服务已响应，API Key 和模型名称验证通过。
```

失败时看 `error_code`：

- `invalid_key`: Key 缺失、错误或权限不通过。
- `quota_exceeded`: 账户余额或额度不足。
- `rate_limited`: 请求太频繁。
- `network_error`: 本机到服务商网络不通、URL 错误或服务端 5xx。
- `model_not_found`: 模型名不被服务商接受。

确认测试通过后，用同一个 Key 保存配置：

```powershell
$apiKey = [Environment]::GetEnvironmentVariable($apiKeyEnv, "Process")
if (-not $apiKey) {
    $apiKey = [Environment]::GetEnvironmentVariable($apiKeyEnv, "User")
}
if (-not $apiKey) {
    $apiKey = [Environment]::GetEnvironmentVariable($apiKeyEnv, "Machine")
}
if (-not $apiKey) {
    throw "没有读取到环境变量 $apiKeyEnv。请确认已设置，并重新打开 PowerShell。"
}

try {
    $body = @{
        provider = $provider
        model = $model
        api_key = $apiKey
    } | ConvertTo-Json

    Invoke-RestMethod `
        -Method Post `
        -Uri "http://127.0.0.1:8765/providers/save" `
        -Headers @{ "X-Lilsunspot-Token" = $token } `
        -ContentType "application/json" `
        -Body $body
}
finally {
    $apiKey = $null
    $body = $null
}
```

如果测试本地 Ollama，先确保 Ollama 的 OpenAI-compatible 服务可访问，再用空 Key：

```powershell
$body = @{ provider = "ollama"; model = "llama3.2"; api_key = "" } | ConvertTo-Json
Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8765/providers/test" `
    -Headers @{ "X-Lilsunspot-Token" = $token } `
    -ContentType "application/json" `
    -Body $body
```

实测完成后，确认 `$dataDir` 指向 `.tmp-lilsunspot-data` 后再删除临时目录：

```powershell
Resolve-Path $dataDir
Remove-Item -Recurse -Force -LiteralPath $dataDir
```

## 验证

从仓库根目录运行：

```powershell
python -m pytest lilsunspot/daemon/tests
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

`scripts/check.ps1` 当前会：

1. 跑 `python -m pytest lilsunspot/daemon/tests`。
2. 跑 `python scripts/guard_no_secrets.py`。
3. 如果存在 `npm` 且 `lilsunspot/desktop/node_modules` 已安装，跑 `npm run build --prefix lilsunspot/desktop`。

Provider client 还有产品层补充测试。Windows 下从仓库根配置读取 `pytest-timeout` 时使用 `thread` timeout：

```powershell
python -m pytest lilsunspot/tests/test_provider_client.py --timeout-method=thread
```

## 开发约束

- 只在 `lilsunspot/`、`scripts/` 和当前任务允许的文件里改产品代码。
- 不重写 Hermes core。
- `lilsunspotd` 必须绑定 `127.0.0.1`。
- `/health` 之外的本地 API 必须鉴权。
- 测试必须使用临时数据目录。
- 不加入真实 API Key 或 token 到代码、日志、fixture、截图、prompt 或诊断文本。
- 不要求最终用户安装 Python、Node、Git 或 Docker。
- 不做无关重构，不新增大依赖。
