# ADR 0001: Generation Control Resolution and Provider Compatibility

## Status

Accepted for implementation.

## Context

旧输出 Mode 将措辞、长度、思考和主动性混合在 Prompt 与少量 AIAgent 参数中。单轮覆盖未随消息进入真实请求，sampling 参数没有能力判断、降级和用户可见 trace。

## Considered Options

1. 继续扩展旧 Mode 和 Prompt：无法满足真实参数与风格分离。
2. 修改 Hermes core 为每个 Provider 增加产品配置：破坏上游边界。
3. 在 lilsunspot 建立生成控制 resolver，通过 Hermes 已有构造参数和 `request_overrides` 薄接入。

## Decision

采用选项 3。优先级为全局默认、会话覆盖、当前消息覆盖、Provider/模型兼容收紧、安全边界。未知、锁定或已拒字段省略；明确参数拒绝最多安全重试一次。表达风格只保留 Prompt overlay。

## Rationale

该方案保留 Hermes 为唯一 Agent runtime，同时让桌面与微信共用一套产品契约，并能记录实际参数与降级原因。

## Consequences

- lilsunspot 新增持久化生成控制状态和模型级拒参记录。
- fallback 参数必须按所有可达模型能力保守求交集。
- 回复 metadata 增加脱敏 generation trace。
- UI 必须区分表达风格与生成控制。

## Migration

旧 `mode-profile.json` 继续作为表达风格；新生成控制默认 `balanced`，不从旧三滑杆隐式迁移运行参数，避免把 Prompt 偏好冒充用户明确参数设置。

## Rollback

停止读取新生成控制状态并省略所有新增 request overrides；旧表达风格与 Hermes 默认运行仍可继续。不得删除用户的生成控制文件，以便恢复。

## Date

2026-07-25.
