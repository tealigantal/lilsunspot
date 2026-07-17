# Lilsunspot 小黑子

## 一句话说明

Lilsunspot 小黑子是基于 Hermes Agent 的桌面个人 Agent 产品层。Windows 安装包仍是正式基线；macOS 只通过独立云端链路提供 arm64 与 x86_64 私用 DMG。

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
| Windows 安装包 | 自动构建通过 | LIL-P0-01 已构建 NSIS 安装包；干净 Windows 未验证。 |
| macOS 私用安装包 | workflow 已实现、待云端执行 | macOS 15+ arm64/x86_64 分别原生构建 DMG Artifact；不做正式签名、公证、Release 或自动更新。 |
| Lilsunspot.exe 启动 | 自动构建通过 | Tauri release exe 已构建；仓库外安装启动未验证。 |
| lilsunspotd | 自动验证通过 | PyInstaller sidecar 可在临时数据目录启动并通过 `/health`。 |
| runtime token | 自动验证通过 | sidecar smoke 创建 runtime token 和 discovery file，token 未写入 daemon 日志；未记录 token。 |
| provider 列表 | 自动验证通过 | sidecar smoke 通过 token-protected `/providers` 返回 6 个 provider。 |
| provider 测试 | 测试通过 | mock provider 测试通过；本次未运行真实 API Key。 |
| provider 保存 | 测试通过 | 写入 lilsunspot 独立 Hermes home 的测试通过；本次未保存真实 API Key。 |
| 桌面聊天 | 测试/构建通过 | chat API 测试和桌面 build 通过；真实桌面 UI 聊天未验证。 |
| 输出模式 | 部分实现 | mode profile 已有资源和 API，三滑杆完整效果未验证。 |
| 微信 | 部分实现 | Weixin 命令和状态骨架存在，真实扫码私聊未验证。 |
| 安全审批 | 部分实现 | 审批队列相关 API 存在，真实高危动作拦截未验证。 |
| 诊断导出 | 未实现 | doctor/repair 骨架存在，诊断包导出未确认。 |

## 本周目标

先打穿安装、首启、provider、桌面聊天主路径，不先打磨 UI。

## 不做的事

- 不做 macOS 正式发布、Developer ID 签名、公证或自动更新
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

执行 LIL-P0-02 和 LIL-P0-03：新增发布级强检查，并在干净 Windows 上验证仓库外安装首启。
