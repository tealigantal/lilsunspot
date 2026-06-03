# TASKS.md

## Current

### LIL-00-03: 实现真实 Provider 配置验证。

Goal:
让 `/providers/test` 对已登记的 OpenAI-compatible provider 发起真实连接验证，确认 API Key 可用并检查选择的模型名称，同时继续避免泄露 API Key 或 runtime token。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `/providers/test` 对 cloud provider 要求 API Key。
2. `/providers/test` 使用 provider registry 中的 `base_url` 或 `detect_url` 发起最小 `/chat/completions` 探测。
3. 成功响应必须证明所选 API Key 和模型组合被服务商接受。
4. local provider 可以在没有 API Key 时验证。
5. 401/403 映射为 `invalid_key`。
6. 402 或额度错误映射为 `quota_exceeded`。
7. 429 映射为 `rate_limited`。
8. 网络错误映射为 `network_error`。
9. 模型不存在映射为 `model_not_found`。
10. API Key 和 token 不进入响应明文、日志、测试 fixture、截图或诊断文本。
11. pytest 最小测试通过。
12. desktop TypeScript build 通过。
13. `scripts/check.ps1` 可以运行。
14. 不修改 Hermes 核心。
15. 不修改 SOUL.md。
16. 没有真实 API Key 或 token 泄露。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

## Next

- LIL-00-04: 实现桌面聊天到 Hermes runtime 的真实桥接。

## Done

- LIL-00-01: 创建 lilsunspot 完整开发骨架。
- LIL-00-02: 打通 lilsunspotd 启动器和桌面端自动发现。
