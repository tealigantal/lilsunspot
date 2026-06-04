# Lilsunspot Desktop

Tauri 2 + React + TypeScript desktop app for `lilsunspot` / `小黑子`.

## 当前范围

当前任务是 `LIL-00-05`：把 mode profiles 接入真实聊天行为。

已具备：

- 自动连接本机 `lilsunspotd`。
- 通过 Tauri 命令代理读取 runtime token，并访问受保护 daemon API。
- Provider 首启向导：读取 registry、打开 Key 页面、调用真实 `/providers/test`、保存 Hermes 兼容配置。
- Chat 页面可调用 `/chat/send`，展示 loading、成功回复、普通中文错误和未配置模型时的禁用状态。
- Mode、Weixin、Safety、Doctor 页面展示当前本地 API 骨架状态。

仍是占位：

- mode profiles 尚未影响真实聊天 prompt；这是当前开发任务。
- Weixin 扫码、联系人和发送消息尚未接入。
- Safety 审批队列和 Doctor 修复/导出仍是本地骨架。
- Windows 安装包和最终 `Lilsunspot.exe -> lilsunspotd` 分发链路尚未完成。

## 启动

从仓库根目录启动 daemon：

```powershell
python -m lilsunspot.daemon.launcher
```

从 `lilsunspot/desktop` 启动开发浏览器模式：

```powershell
npm install
npm run dev
```

Tauri 桌面模式：

```powershell
npm run tauri:dev
```

## Daemon 发现

桌面模式会调用 `connect_daemon`：

1. 读取 lilsunspot 数据目录里的 `daemon-runtime.json`。
2. 检查 `http://127.0.0.1:<port>/health`。
3. 如果没有健康 daemon，尝试启动 `lilsunspotd.exe`、同目录 `lilsunspotd`、PATH 中的 `lilsunspotd`。
4. debug 构建下还会尝试 `python -m lilsunspot.daemon.launcher`。
5. 读取 `runtime-token.json`，后续请求通过 `daemon_request` 自动携带 `X-Lilsunspot-Token`。

浏览器开发模式没有 Tauri token 代理，需要在页面开发者区域手动填入 token。

## 页面

- 首页：显示启动状态、daemon 状态和下一步操作。
- Provider：真实测试 OpenAI-compatible provider 并保存配置。
- Chat：调用真实聊天桥接，未配置模型时禁用输入，发送中显示 loading，成功后展示模型回复。
- Mode：展示和切换本地模式配置。
- Weixin：展示微信 gateway 占位状态和计划命令。
- Safety：展示默认安全策略和占位审批队列。
- Doctor：运行本地诊断骨架。

## 受保护 API

`/health` 是公开 API。daemon 其他 API 都要求 `X-Lilsunspot-Token`。

API Key 和 runtime token 不应出现在日志、截图、fixture、诊断文本或提交内容中。

## 构建

```powershell
npm run build
```

Tauri 打包仍是后续任务：

```powershell
npm run tauri:build
```
