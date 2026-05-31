# TASKS.md

## Current

### LIL-00-02: 打通 lilsunspotd 启动器和桌面端自动发现

Goal:
让 `lilsunspotd` 有稳定启动器入口，并让桌面端自动发现本机 daemon 地址和 runtime token，减少首启时手动粘贴 token 的步骤。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `python -m lilsunspot.daemon.launcher` 可以作为 `lilsunspotd` 启动器入口。
2. `lilsunspotd` 仍然只绑定 `127.0.0.1`。
3. daemon 启动时写入 `data/daemon-runtime.json`。
4. `daemon-runtime.json` 包含 `base_url`、host、port、pid、token 文件路径。
5. `daemon-runtime.json` 不包含 token 明文。
6. `/runtime/info` 返回 daemon base_url、端口、pid 和 runtime 文件路径。
7. 桌面端 Tauri command 能读取 daemon 发现文件和 runtime token。
8. 桌面端启动后优先自动发现 daemon；失败时仍可手动填写 token。
9. token 不进入日志、测试 fixture、截图或诊断文本。
10. pytest 最小测试通过。
11. desktop TypeScript build 通过。
12. `scripts/check.ps1` 可以运行。
13. 不修改 Hermes 核心。
14. 不修改 SOUL.md。
15. 没有真实 API Key 或 token 泄露。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

## Next

- LIL-00-03: 实现真实 Provider 配置验证。
- LIL-00-04: 实现桌面聊天到 Hermes runtime 的真实桥接。

## Done

- LIL-00-01: 创建 lilsunspot 完整开发骨架。
