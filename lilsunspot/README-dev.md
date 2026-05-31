# lilsunspot 开发说明

产品名：`lilsunspot`
中文昵称：`小黑子`

本目录是 Hermes Agent fork 中的产品层骨架。当前任务只建立可继续开发的最短链路，不实现真实 provider 调用、真实微信扫码、真实安装包或完整业务闭环。

## 目录

- `daemon/`: `lilsunspotd` 本地 FastAPI daemon。
- `desktop/`: Tauri 2 + React + TypeScript 桌面端骨架。
- `resources/`: 默认 provider registry、mode profiles、safety policy。
- `daemon/tests/`: 当前骨架的最小验收测试。
- `installer/`, `plugins/`, `profile_card/`: 后续任务占位目录。

## 本地 daemon

默认绑定：

```powershell
http://127.0.0.1:8765
```

启动：

```powershell
python -m lilsunspot.daemon.launcher
```

`/health` 不需要 token。其他本地 API 都需要：

```text
X-Lilsunspot-Token: <runtime token>
```

token 文件写入：

```powershell
%LOCALAPPDATA%\Lilsunspot\data\runtime-token.json
```

daemon 发现文件写入：

```powershell
%LOCALAPPDATA%\Lilsunspot\data\daemon-runtime.json
```

`daemon-runtime.json` 只包含 `127.0.0.1` base URL、端口、进程号和 token 文件路径，不包含 token 明文。

开发和测试可用临时目录覆盖：

```powershell
$env:LILSUNSPOT_DATA_DIR = "$pwd\.tmp-lilsunspot-data"
```

## 当前 API 骨架

- `GET /health`
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

## 桌面端

```powershell
cd lilsunspot/desktop
npm install
npm run dev
```

桌面端现在只有占位页面：首页、Provider、Chat、Mode、Weixin、Safety、Doctor。Tauri command `discover_daemon` 会读取本地 daemon 发现文件和 runtime token；`read_runtime_token` 保留给开发模式兼容。两个命令都不打印 token。

## 验收

从仓库根目录运行：

```powershell
python -m pytest lilsunspot/daemon/tests
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

## 安全约束

- 不把 API Key 或 token 写入日志。
- 不把 API Key 或 token 放进 prompt、测试 fixture、截图或诊断结果。
- 测试必须使用临时 `LILSUNSPOT_DATA_DIR`。
- 当前 provider test 和 chat send 都是占位实现，不会发起真实模型请求。

## 暂未实现

- 真实 provider 联网测试。
- 真实 Hermes runtime 聊天桥接。
- 真实微信扫码、联系人或消息发送。
- 安全审批队列的真实批准/拒绝流程。
- 自动修复动作。
- Windows 安装包。
