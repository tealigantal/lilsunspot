# TASKS.md

## Current

### LIL-00-04: 实现桌面聊天到 Hermes runtime 的真实桥接。

Goal:
让桌面 Chat 页通过 `lilsunspotd` 的 `/chat/send` 使用已保存的 Hermes 兼容 provider 配置发起真实 OpenAI-compatible `chat/completions` 请求，不再返回占位回复，同时继续避免泄露 API Key 或 runtime token。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `/chat/send` 继续要求 `X-Lilsunspot-Token`。
2. `/chat/send` 从 `hermes_home/config.yaml` 读取当前 provider 和 model。
3. `/chat/send` 从 `hermes_home/.env` 读取对应 provider 的 API Key，cloud provider 缺 Key 时返回中文错误。
4. `/chat/send` 使用 provider registry 中的 `base_url` 或 `detect_url` 发起非流式 `chat/completions` 请求。
5. local provider 可以在没有 API Key 时聊天。
6. 成功响应返回模型真实回复，`engine` 标记为 `hermes_runtime`。
7. 401/403 映射为 `invalid_key`。
8. 402 或额度错误映射为 `quota_exceeded`。
9. 429 映射为 `rate_limited`。
10. 网络错误映射为 `network_error`。
11. 模型不存在映射为 `model_not_found`。
12. 桌面 Chat 页不再显示“不会调用真实模型服务”的占位文案。
13. API Key 和 token 不进入响应明文、日志、测试 fixture、截图或诊断文本。
14. pytest 最小测试通过。
15. desktop TypeScript build 通过。
16. `scripts/check.ps1` 可以运行。
17. 不修改 Hermes 核心。
18. 不修改 SOUL.md。
19. 没有真实 API Key 或 token 泄露。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

## Next

- 待定

## Done

- LIL-00-01: 创建 lilsunspot 完整开发骨架。
- LIL-00-02: 打通 lilsunspotd 启动器和桌面端自动发现。
- LIL-00-03: 实现真实 Provider 配置验证。
