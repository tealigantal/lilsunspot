# lilsunspot 开发说明

## 项目名称

Lilsunspot 小黑子

## 当前推荐入口

- `README.lilsunspot.md`
- `lilsunspot/notes/doc-index.md`
- `lilsunspot/notes/mvp-p0-status.md`
- `TASKS.md`

## 启动 daemon

从仓库根目录运行，当前仓库文档和代码中存在以下入口：

```powershell
python -m lilsunspot.daemon.launcher
```

历史 Day1 文档还记录过以下入口，本任务未验证：

```powershell
python -m lilsunspot.daemon.app
```

默认地址按当前文档和代码记录为：

```text
http://127.0.0.1:8765
```

`lilsunspotd` 必须绑定 `127.0.0.1`。

## 获取 runtime token

```powershell
Get-Content "$env:LOCALAPPDATA\Lilsunspot\data\runtime-token.json"
```

不要打印、截图、提交或记录真实 runtime token。

## 调用 /health

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8765/health"
```

`/health` 不需要 `X-Lilsunspot-Token`。

## 调用 /providers

```powershell
$token = (Get-Content "$env:LOCALAPPDATA\Lilsunspot\data\runtime-token.json" | ConvertFrom-Json).token
Invoke-RestMethod `
    -Method Get `
    -Uri "http://127.0.0.1:8765/providers" `
    -Headers @{ "X-Lilsunspot-Token" = $token }
```

## 启动 desktop

从当前仓库已有 desktop 文档确认的开发浏览器模式：

```powershell
cd lilsunspot/desktop
npm install
npm run dev
```

Tauri 桌面模式在历史开发文档中记录为：

```powershell
cd lilsunspot/desktop
npm run tauri:dev
```

本任务未运行上述命令。

## 运行检查

以下是当前仓库已有检查入口：

```powershell
python scripts/guard_no_secrets.py
python -m pytest lilsunspot/daemon/tests
npm run build --prefix lilsunspot/desktop
```

LIL-P0-01 于 2026-06-06 额外运行并通过：

```powershell
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
pwsh scripts/check.ps1
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop
```

同次验证还用 ignored 临时数据目录启动 release sidecar，确认 `/health`、token-protected `/providers`、`127.0.0.1` 绑定、runtime file 创建和 daemon 日志 token 泄漏检查通过；未记录 runtime token。

发布候选使用强校验入口；该脚本要求 desktop 依赖已安装，并且不会静默跳过 desktop build：

```powershell
pwsh scripts/check_release.ps1
```

## 构建 sidecar

当前 `scripts/` 下存在 sidecar 构建脚本；LIL-P0-01 已验证可生成 `lilsunspotd-x86_64-pc-windows-msvc.exe`。

```powershell
pwsh scripts/build_lilsunspotd_sidecar.ps1
```

## 构建 NSIS

当前 desktop 文档记录的 NSIS 构建命令；LIL-P0-01 已验证可生成 `Lilsunspot_0.1.0_x64-setup.exe`。

```powershell
npm run tauri:build --prefix lilsunspot/desktop
```

## 安装版仓库外 smoke

LIL-P0-03 新增安装版 smoke 脚本，用隔离数据目录验证仓库外 `Lilsunspot.exe` 能启动同目录 `lilsunspotd.exe`，并检查 `/health`、带 `X-Lilsunspot-Token` 的 `/providers`、`127.0.0.1` 绑定和 daemon 日志 token 泄漏。

在当前开发机复用已安装 app 时：

```powershell
pwsh scripts/smoke_lilsunspot_installed_app.ps1 -SkipInstall -InstallDir "$env:LOCALAPPDATA\Lilsunspot"
```

在干净 Windows VM 上验证安装包时，先把仓库和构建好的 NSIS 安装包放入 VM，然后运行：

```powershell
pwsh scripts/smoke_lilsunspot_installed_app.ps1
```

直接安装到当前用户真实安装目录并人工/脚本验证时：

```powershell
.\lilsunspot\desktop\src-tauri\target\release\bundle\nsis\Lilsunspot_0.1.0_x64-setup.exe /S /D=$env:LOCALAPPDATA\Lilsunspot
```

脚本默认把安装目录放在系统临时目录下的 `lilsunspot-installed-app-smoke\app`，并使用 `ignored\installed-app-smoke\data` 作为临时数据目录，不会打印 runtime token。不要把该目录中的 token 文件内容复制到日志、截图或提交记录。

2026-06-08 追加本机真实安装环境验证：从环境变量读取 DeepSeek API Key 到内存，跑通 `/providers/test`、`/providers/save`、连续 `/chat/send`、mode profile/sliders、Weixin command skeleton、Safety approval queue 和 `/doctor`。当前 `/chat/send` adapter 返回 `conversation_id_supported=false`，因此跨轮记忆不按已实现能力验收。安装版窗口视觉 QA 用 DWM 截图覆盖 960x680 和 390x760；如需复查，不要把 API Key、runtime token 或回复正文带入截图或日志。

## 当前未完成项

- clean Windows install
- full mode prompt compilation
- Weixin real private chat
- real high-risk approval interception
- diagnostics export

## Secrets 规则

不要把 API Key、runtime token 写入日志、prompt、截图、测试输出或提交记录。
