# Day2 Status

Date: 2026-05-25

## 今日完成能力

- `lilsunspotd` 成为 provider 配置中心。
- `/health` 保持无鉴权，其余业务 API 统一校验 `X-Lilsunspot-Token`。
- runtime token 自动生成到 lilsunspot 数据目录。
- Provider registry API 支持列表、详情、key URL、格式初检、连接测试、保存和 current 状态。
- `/providers/save` 写入 `%LOCALAPPDATA%/Lilsunspot/data/hermes_home/.env` 和 `config.yaml`。
- Doctor 返回结构化 checks。
- desktop 更新为 Day2 provider 配置开发骨架。

## 当前 API 列表

- `GET /health`
- `GET /runtime/info`
- `GET /providers`
- `GET /providers/{provider_id}`
- `POST /providers/open-key-url`
- `POST /providers/validate-key-format`
- `POST /providers/test`
- `POST /providers/save`
- `GET /providers/current`
- `GET /doctor/run`
- `POST /doctor/run`

除 `/health` 外，以上业务 API 都需要 `X-Lilsunspot-Token`。

## provider 测试状态

- DeepSeek、OpenAI、OpenRouter、Kimi、Qwen 走统一 OpenAI-compatible adapter。
- Ollama 使用本地 `/models` 检测。
- 自动化测试使用 fake httpx client，不依赖真实 provider key。
- 错误分类覆盖 invalid key、model not found、rate limited、quota/balance、network、provider error 和 unknown。

## save 写入状态

- `.env` 按 registry 的 `env_key` 写入或更新。
- 其他 env 行会保留。
- `config.yaml` 写入 Hermes-compatible `model` 配置和 `lilsunspot` 元数据。
- 不读取、不写入用户 `~/.hermes/.env`。

## 脱敏状态

- `mask_secret(secret)` 用于显示短格式 masked key。
- `redact_text(text)` 覆盖 common key token 和 provider env assignment。
- API 响应、错误信息和日志不返回完整 key。

## 阻断

- 无功能阻断。
- 在当前 Windows shell，系统 Python 缺少 `pytest-timeout` 时会导致根 pytest 配置无法识别 `--timeout`；本地已安装 dev test 插件后通过。

## Day3 第一任务建议

把 desktop 的 provider 保存骨架接上更明确的状态流：加载 current provider、校验格式、可选 provider test、保存成功后刷新 current，并补一个最小端到端手动验收脚本。
