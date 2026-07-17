# QA Checklist

## LIL-MACOS-DMG-01 自动验证边界

- [x] 独立 Mac Tauri 配置只覆盖前端 build、DMG、macOS 15、`icon.icns` 与 ad-hoc 签名。
- [x] Mac sidecar 脚本与 Windows 脚本的 hidden imports、collect-submodules 和产品资源集合保持一致。
- [x] arm64/x86_64 原生 Artifact workflow、安装后烟测和 PR Windows regression job 已实现。
- [x] `macos-15` 实际生成 `Lilsunspot_0.1.0_macos-arm64.dmg` 并通过安装后烟测。
- [x] `macos-15-intel` 实际生成 `Lilsunspot_0.1.0_macos-x86_64.dmg` 并通过安装后烟测。
- [x] 本分支重新生成 Windows `Lilsunspot_0.1.0_x64-setup.exe` 并通过临时安装 smoke。
- [ ] 真实 Mac 微信扫码/收发、真实模型服务、Finder 附件交互和托盘点击人工验收。

GitHub Actions run `29576626648` 已通过并完成本地 Artifact SHA-256 复核；真实 Mac 人工项目仍不得标记为通过。DMG Artifact 来自公开仓库，14 天保留不等于保密存储。

## LIL-P0-01 自动验证记录

- [x] daemon tests：23 passed。
- [x] product tests：20 passed。
- [x] secret guard：未发现 lilsunspot task scope 内 secret-like values。
- [x] desktop TypeScript/Vite build 通过。
- [x] `scripts/check.ps1` 通过。
- [x] sidecar build 生成 `lilsunspotd-x86_64-pc-windows-msvc.exe`。
- [x] NSIS build 生成 `Lilsunspot_0.1.0_x64-setup.exe`。
- [x] sidecar smoke：`/health` ok，`/providers` 返回 6 个 provider，绑定 `127.0.0.1`，runtime file 创建成功，token 未写入 daemon 日志。

以下清单仍按人工/发布验收口径维护；没有在干净安装环境中验证的项目不勾选。

## P0 MVP

- [ ] 干净 Windows 可安装
- [ ] 不要求管理员权限
- [ ] 不要求用户安装 Python
- [ ] 不要求用户安装 Node
- [ ] 不要求用户安装 Git
- [ ] Lilsunspot.exe 可启动
- [ ] lilsunspotd 自动启动或被发现
- [ ] 首启向导可完成
- [ ] provider 可选择
- [ ] API Key 可测试
- [ ] provider 保存后可聊天
- [ ] 关闭重开配置仍在

## Provider

- [ ] /providers 可列出服务商
- [ ] key_url 可打开
- [ ] invalid key 有人话错误
- [ ] network error 有人话错误
- [ ] model not found 有人话错误
- [ ] 日志不含完整 API Key

## Desktop

- [ ] 正式桌面版不要求用户粘贴 runtime token
- [ ] Tauri 代理可访问受保护 API
- [ ] 聊天页可发送消息
- [ ] 聊天页可显示回复
- [ ] 错误提示不是原始堆栈

## Mode

- [ ] 三滑杆可保存
- [ ] style_axis=20 生效
- [ ] style_axis=80 生效
- [ ] detail_level 生效
- [ ] autonomy_level 生效
- [ ] 不修改 SOUL.md

## Weixin

- [x] 桌面显示二维码
- [x] 手机扫码后 connected
- [x] 微信私聊普通消息可回复
- [x] `/help` 可返回帮助
- [x] `/mode` 可切换或确认模式
- [x] 安装版 UI 人工点击验收通过
- [ ] 断线重连
- [ ] 二维码真实过期处理

## Safety

- [ ] 高危操作进入审批
- [ ] 桌面端可允许
- [ ] 桌面端可拒绝
- [ ] 审批结果进入 audit.db
- [ ] 默认 shell 或发送微信消息不直接执行

## Installer

- [ ] 生成 LilsunspotSetup-x64.exe
- [ ] 安装到用户目录
- [ ] 不写系统 PATH
- [ ] 安装失败有日志
- [ ] 卸载可保留 data
- [ ] 重装后配置仍可读取

## Diagnostics

- [ ] doctor 可运行
- [ ] repair 可运行
- [ ] 诊断包可导出
- [ ] 诊断包不含完整 API Key
- [ ] 诊断包不含 runtime token

## Release 输出物

- [ ] LilsunspotSetup-x64.exe
- [ ] SHA256
- [ ] release-notes.md
- [ ] known-issues.md
- [ ] qa-checklist.md
- [ ] diagnostics-sample-redacted.zip
