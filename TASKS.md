# TASKS.md

## Current

### LIL-00-01: 创建 lilsunspot 完整开发骨架

Goal:
建立 lilsunspot 的完整开发骨架，包括 Codex 工作规则、daemon、desktop、resources、测试、脚本和开发说明。

Allowed files:
- AGENTS.md
- TASKS.md
- pytest.ini
- requirements.txt
- pyproject.toml
- scripts/**
- lilsunspot/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. AGENTS.md 存在，且包含 Codex 工作规则。
2. TASKS.md 存在，且有 Current / Next / Done。
3. lilsunspot/ 目录结构完整。
4. lilsunspotd 可以启动。
5. GET /health 返回 ok。
6. /providers 无 token 返回 403。
7. 正确 token 访问 /providers 返回 provider 列表。
8. token 写入 data/runtime-token.json。
9. token 不进入日志。
10. resources 下存在 provider_registry.yaml。
11. resources 下存在 default_mode_profiles.yaml。
12. resources 下存在 default_safety_policy.yaml。
13. daemon 有 provider、mode、chat、gateway、safety、doctor 的 API 骨架。
14. desktop 有 React/Tauri 兼容骨架。
15. desktop 有首页、Provider 页、Chat 页、Mode 页、Weixin 页、Safety 页、Doctor 页占位。
16. pytest 最小测试通过。
17. scripts/check.ps1 可以运行。
18. scripts/guard_no_secrets.py 可以运行。
19. 不修改 Hermes 核心。
20. 不修改 SOUL.md。
21. 没有真实 API Key 或 token 泄露。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

## Next

- LIL-00-02: 打通 lilsunspotd 启动器和桌面端自动发现。
- LIL-00-03: 实现真实 Provider 配置验证。
- LIL-00-04: 实现桌面聊天到 Hermes runtime 的真实桥接。

## Done

- 暂无。
