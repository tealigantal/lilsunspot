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

以下是当前仓库已有检查入口；本任务未运行 pytest 或 npm build。

```powershell
python scripts/guard_no_secrets.py
python -m pytest lilsunspot/daemon/tests
npm run build --prefix lilsunspot/desktop
```

## 构建 sidecar

当前 `scripts/` 下存在 sidecar 构建脚本；本任务未运行。

```powershell
pwsh scripts/build_lilsunspotd_sidecar.ps1
```

## 构建 NSIS

当前 desktop 文档记录的 NSIS 构建命令；本任务未运行。

```powershell
npm run tauri:build --prefix lilsunspot/desktop -- --bundles nsis
```

## 当前未完成项

- clean Windows install
- mode sliders
- Weixin real private chat
- real high-risk approval interception
- diagnostics export

## Secrets 规则

不要把 API Key、runtime token 写入日志、prompt、截图、测试输出或提交记录。
