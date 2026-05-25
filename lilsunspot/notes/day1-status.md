# Day1 Status

## Hermes 基础链路

- Hermes CLI 原生链路已由用户手动验证通过：
  - uv 环境安装成功。
  - `hermes doctor` 可执行。
  - DeepSeek 已配置并连通。
  - `hermes chat -q "Hello"` 可以正常回复。
- 本轮没有读取、复制或迁移用户真实 `~/.hermes/.env`。

## 当前实现能力

- 新增 `lilsunspot/` 工程目录。
- 记录上游 commit 到 `lilsunspot/UPSTREAM_COMMIT.txt`。
- 新增 `lilsunspotd` FastAPI daemon。
- daemon 默认只绑定 `127.0.0.1:8765`。
- 初始化 `%LOCALAPPDATA%/Lilsunspot/data`、`hermes_home`、`logs`。
- 实现 `runtime-token.json` 基础随机 token。
- `/health` 无 token 返回 `{"ok": true}`。
- `/runtime/info`、`/providers`、`/providers/open-key-url`、`/providers/save`、`/doctor/run` 默认需要 `X-Lilsunspot-Token`。
- 新增 provider registry、mode profiles、safety policy 三个 YAML。
- 新增 Tauri 2 + React + TypeScript desktop 空壳。

## lilsunspotd 状态

- Day1 可通过 FastAPI TestClient 验证。
- 真实启动方式：
  - `python -m lilsunspot.daemon.app`
  - `uvicorn lilsunspot.daemon.app:app --host 127.0.0.1 --port 8765`

## desktop 状态

- Day1 只提供最小桌面空壳。
- 可显示产品名、Day1 状态、daemon 地址和四个检查按钮。
- 受保护接口需要手动粘贴 token；Day1 暂不自动读取 `runtime-token.json`。

## resources 状态

- `provider_registry.yaml` 包含 deepseek、openrouter、openai、kimi、qwen、ollama。
- `default_mode_profiles.yaml` 包含 default、pragmatic、balanced、emotional。
- `default_safety_policy.yaml` 将 shell、delete_file、send_weixin_message、read_sensitive_directory、write_sensitive_file、network_post、credential_access 标为 high_risk，默认需要审批。

## Weixin 可行性状态

- 结论：部分可用。
- 仓库内存在 Hermes 原生 Weixin personal account adapter：`gateway/platforms/weixin.py`。
- 代码依据：`gateway/platforms/weixin.py` 中存在 `qr_login(...)`，`hermes_cli/gateway.py` 中 `_setup_weixin()` 会调用该流程。
- 命令依据：`uv run hermes gateway --help` 可显示 gateway 子命令；`uv run python -c "from gateway.platforms.weixin import check_weixin_requirements; print(check_weixin_requirements())"` 返回 `True`。
- QR 登录流程存在，但真实 Weixin 私聊仍需要人工扫码和收发验收。
- Day1 不做微信 UI、不做原生资料页注入。

## 当前阻断

- 当前 PowerShell PATH 中裸 `hermes` 不可见；用 `uv run hermes ...` 可执行。
- 当前环境未发现 Rust 工具链，Tauri 打包/运行需要后续安装 Rust。
- Day1 桌面端暂不自动读取 token。

## 明日第一任务建议

先实现 Day2 provider/token/Hermes home 的闭环：

1. 桌面端自动读取或安全请求 `runtime-token.json`。
2. provider 保存后用独立 `HERMES_HOME=%LOCALAPPDATA%/Lilsunspot/data/hermes_home` 跑最小 Hermes doctor。
3. 设计 provider 测试接口，但继续避免把 API key 打进日志或 prompt。
