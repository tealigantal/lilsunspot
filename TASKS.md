# TASKS.md

## Current

### LIL-00-05: 接入 mode profiles 到真实聊天行为。

Goal:
让已选择的 mode profile 影响真实聊天请求的系统提示、输出风格和默认行为，同时继续避免泄露 API Key 或 runtime token。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `/chat/send` 继续要求 `X-Lilsunspot-Token`。
2. 当前 mode profile 必须从 lilsunspot 独立数据目录读取。
3. mode profile 的 `system_hint` 必须进入真实聊天请求。
4. 未选择 mode 时使用默认 profile。
5. 用户可见错误保持普通中文。
6. API Key、runtime token 不得进入日志、响应、prompt fixture、截图或诊断文本。
7. daemon pytest 最小测试通过。
8. chat/mode 产品层补充测试通过。
9. desktop TypeScript build 通过。
10. `scripts/check.ps1` 可以运行。
11. 不修改 Hermes 核心。
12. 不修改 SOUL.md。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

## Next

- 待定。

## Done

### LIL-00-04: 实现桌面聊天到 Hermes runtime 的真实桥接。

Goal:
让 `/chat/send` 不再返回占位回复，而是使用 lilsunspot 独立 `hermes_home` 中已保存的 Provider、模型和 API Key 配置调用 Hermes runtime，桌面 Chat 页展示真实模型回复，同时继续避免泄露 API Key 或 runtime token。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `/chat/send` 除 `/health` 规则外必须继续要求 `X-Lilsunspot-Token`。
2. 未保存 provider/model 时返回普通中文设置提示，不调用 Hermes runtime。
3. cloud provider 缺少 API Key 时返回普通中文错误，不调用 Hermes runtime。
4. local provider 可以在没有 API Key 时进入聊天桥接。
5. 桥接必须使用 `LILSUNSPOT_DATA_DIR` 下的独立 `hermes_home`，不能读取或污染用户真实 `~/.hermes`。
6. 桥接必须读取 `hermes_home/config.yaml` 中的 lilsunspot provider/model 配置。
7. 桥接必须从 `hermes_home/.env` 读取对应 provider env key，但 API Key 不得进入日志、响应、prompt fixture、截图或诊断文本。
8. 成功响应必须来自真实 Hermes runtime 或最小 runtime 适配层，不能再返回 `placeholder` engine。
9. 桌面 Chat 页显示 loading、成功回复、普通中文错误和禁用状态。
10. 桌面 Chat 页不得显示 API Key、runtime token 或原始异常。
11. daemon pytest 最小测试通过。
12. chat/provider 产品层补充测试通过。
13. desktop TypeScript build 通过。
14. `scripts/check.ps1` 可以运行。
15. 不修改 Hermes 核心。
16. 不修改 SOUL.md。
17. 没有真实 API Key 或 token 泄露。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests/test_provider_api.py lilsunspot/tests/test_provider_client.py lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

- LIL-00-01: 创建 lilsunspot 完整开发骨架。
- LIL-00-02: 打通 lilsunspotd 启动器和桌面端自动发现。
- LIL-00-03: 实现真实 Provider 配置验证。
