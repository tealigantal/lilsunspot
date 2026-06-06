# Lilsunspot 小黑子

## 一句话说明

Lilsunspot 小黑子是基于 Hermes Agent 的 Windows 桌面个人 Agent 产品层。

## 当前目标

P0 主路径：

安装包
-> Lilsunspot.exe
-> lilsunspotd
-> provider 配置
-> 桌面聊天

后续目标：

- 输出模式
- 微信私聊
- 安全审批
- 诊断包

## 当前真实状态

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| Windows 安装包 | 部分实现 | 文档和脚本显示已有 NSIS 构建链路，干净 Windows 未验证。 |
| Lilsunspot.exe 启动 | 部分实现 | 桌面文档显示 Tauri 启动和 sidecar 接入，仓库外安装启动未验证。 |
| lilsunspotd | 部分实现 | `lilsunspot/daemon/` 存在本地 daemon 和测试，当前任务未运行。 |
| runtime token | 部分实现 | `runtime-token.json` 相关代码和文档存在，当前任务未运行。 |
| provider 列表 | 部分实现 | `lilsunspot/resources/provider_registry.yaml` 和 `/providers` 入口存在，当前任务未运行。 |
| provider 测试 | 部分实现 | `/providers/test` 入口和历史记录存在，当前任务未运行真实 provider。 |
| provider 保存 | 部分实现 | `/providers/save` 入口和 Hermes home 写入说明存在，当前任务未运行。 |
| 桌面聊天 | 部分实现 | `/chat/send` 和桌面 Chat 入口存在；是否等同完整 Hermes agent loop 未验证。 |
| 输出模式 | 部分实现 | mode profile 已有资源和 API，三滑杆完整效果未验证。 |
| 微信 | 部分实现 | Weixin 命令和状态骨架存在，真实扫码私聊未验证。 |
| 安全审批 | 部分实现 | 审批队列相关 API 存在，真实高危动作拦截未验证。 |
| 诊断导出 | 未实现 | doctor/repair 骨架存在，诊断包导出未确认。 |

## 本周目标

先打穿安装、首启、provider、桌面聊天主路径，不先打磨 UI。

## 不做的事

- 不做 macOS
- 不做 Linux
- 不做插件市场
- 不做云后台
- 不做移动端 App
- 不做复杂主题
- 不做微信原生资料页注入
- 不大面积修改 Hermes 核心

## 快速入口

- 开发文档：`lilsunspot/README-dev.md`
- 当前状态：`lilsunspot/notes/mvp-p0-status.md`
- 架构说明：`lilsunspot/notes/architecture.md`
- QA 清单：`lilsunspot/notes/qa-checklist.md`
- 文档索引：`lilsunspot/notes/doc-index.md`

## 下一步

执行 LIL-P0-01，收敛可安装、可首启、可配置 provider、可桌面聊天的 MVP 候选分支。
