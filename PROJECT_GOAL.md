<!-- codex-important-project -->

# Project Goal

## Objective

交付“小黑子”这一普通 Windows 用户可安装、可配置并长期使用的本地个人 Agent：桌面与微信共享可靠的 Hermes Agent 运行时，同时保持清楚的能力、隐私和安全边界。

## User and Problem

目标用户是不想安装 Python、Node、Git 或 Docker的普通 Windows 用户。他们需要从安装、模型配置、聊天、文件与微信入口一路获得可理解的中文反馈，而不是理解 Provider、工具或内部协议。

## Observable Stopping Condition

- 新用户通过 `setup.exe` 安装后能启动、配置模型并完成真实聊天。
- 桌面与微信共享对话、生成策略、文件交付和安全规则。
- 支持与不支持的模型能力均有真实运行证据和普通中文解释。
- 发布前自动检查、安装包构建、云端模型与本地模型端到端验证都有可追溯记录。
- API Key、runtime token、私聊正文、敏感附件和完整内部 prompt 不进入日志、测试夹具或诊断导出。

## Critical User Journeys

1. 安装应用，配置云端或本地模型，发送第一条消息。
2. 在桌面对话中调整表达风格与真实生成参数，并在下一轮看到生效结果。
3. 在微信和桌面之间继续同一类 Agent 工作，保持会话与策略隔离。
4. 上传、生成、打开和返还文件，并在高风险动作前执行既定安全流程。
5. 遇到模型或 Provider 不兼容时，看到可恢复的中文原因和实际降级结果。

## Non-goals

- 不重写 Hermes core 或复制一套独立 Agent runtime。
- 不承诺所有模型支持相同参数、视觉或工具能力。
- 不要求普通用户直接编辑 Hermes raw config。
- 不因高自主模式绕过审批、外部发送、文件范围或凭据边界。

## Constraints

- 新产品代码优先位于 `lilsunspot/`。
- daemon 只绑定 `127.0.0.1`，除 `/health` 外的本地 API 均要求 token。
- 最终用户不依赖开发工具链。
- UI 错误必须是普通中文；诊断必须脱敏。
- 安装版行为才是用户可交付事实，仓库单测或 dev server 不能替代安装版验收。

## Current Lifecycle Stage

当前处于 Windows 可安装版本的能力整合与产品硬化阶段。核心桌面、Hermes、微信、文件、Mode 和 NSIS 链路已存在，但仍需逐项建立真实能力契约和安装版验收证据。

## Approval Gates

发布、部署、购买、新增有成本或高风险的生产依赖、凭据处理变化、不可逆数据迁移、公共 API 破坏以及安全/授权模型变化必须单独确认。

## Assumptions

- Hermes 继续作为唯一 Agent 执行真相，lilsunspot 只提供产品控制层。
- `%LOCALAPPDATA%\Lilsunspot` 仍是 Windows 安装和每用户数据的主要边界。

## Unknowns

- 尚未对全部受支持 Provider/模型完成真实安装版矩阵验证。
- 真实微信多账号隔离、长周期更新与公开分发签名仍未完成产品级验收。
