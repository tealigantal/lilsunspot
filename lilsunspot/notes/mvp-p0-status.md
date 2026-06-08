# MVP P0 当前状态

## 记录信息

- Git root：`<repo-root>`
- 当前分支：`release/mvp-p0`
- 当前 commit：以 PR 分支提交为准
- 更新时间：`2026-06-08`
- 记录方式：基于 LIL-P0-01 本地自动验证和 LIL-P0-03 当前开发机仓库外 installed-app smoke/临时目录真实安装 smoke/当前用户真实安装目录 smoke、真实 DeepSeek chat、多能力 API smoke、安装版窗口视觉 QA；未运行或仍需真实用户环境的功能标记为未验证。

## P0 完成定义

安装包
-> Lilsunspot.exe
-> lilsunspotd
-> token 鉴权
-> provider 列表
-> provider 测试
-> provider 保存
-> 桌面聊天
-> 关闭重开配置仍在

## 当前状态表

| 项目 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| Windows 安装包 | 本机直接安装通过 | setup.exe `/S /D=$env:LOCALAPPDATA\Lilsunspot` | 当前用户真实安装目录安装通过，卸载注册表项和快捷方式存在。 |
| Lilsunspot.exe | 本机安装环境运行通过 | `%LOCALAPPDATA%\Lilsunspot\Lilsunspot.exe` | 启动同目录 sidecar，`/health`、`/providers` 和 `/app/bootstrap` 通过。 |
| lilsunspotd | 自动验证通过 | sidecar smoke `/health` | PyInstaller sidecar 可在临时数据目录启动。 |
| runtime token | 自动验证通过 | sidecar smoke token-protected `/providers` | 创建 token/runtime file；日志 token 泄漏检查通过；未记录 token。 |
| provider registry | 自动验证通过 | sidecar smoke `/providers` | 返回 6 个 provider。 |
| provider test | 真实 DeepSeek 通过 | `/providers/test` | 使用环境变量中的 DeepSeek API Key 真实验证；未记录 Key。 |
| provider save | 真实 DeepSeek 保存通过 | `/providers/save` | 保存 `deepseek/deepseek-chat` 到本机 lilsunspot 数据目录；未记录 Key。 |
| desktop provider wizard | 构建/安装版视觉通过 | `npm run build --prefix lilsunspot/desktop`、DWM screenshots | TypeScript/Vite 通过；安装版 960x680 和 390x760 视觉复验通过。 |
| desktop chat | 真实 DeepSeek 多轮单轮 API 通过 | `/chat/send` | 连续 3 次真实 chat 成功；当前 adapter 明确不支持 conversation id，未记录回复正文。 |
| mode profiles | 安装版 API 验证通过 | `/modes/*` + `/chat/send` | default/pragmatic/balanced 与三滑杆保存后 chat 通过；完整 prompt 编译留给 LIL-P1-01。 |
| Weixin gateway | 命令骨架验证通过 | `/weixin/command` | `/help` 和 `/mode pragmatic` 通过；真实私聊未验证。 |
| safety approvals | 队列 API 验证通过 | `/safety/approvals/*` | create/reject 后 pending 归零；真实高危动作拦截未验证。 |
| doctor | 安装版 API 验证通过 | `/doctor` | 返回 10 项检查。 |
| diagnostics export | 未实现 | 未验证 | 未发现明确诊断包导出入口。 |
| clean Windows install | 不作为当前阻断 | 用户要求直接在本机安装环境运行 | 当前 LIL-P0-03 以本机真实安装目录验收为准。 |

## 当前 P0 阻断项

- 2026-06-08 用户确认除干净 Windows 安装以外，LIL-P0-01 其余人工验收已完成；本文件未记录真实 API Key、runtime token 或私有截图。
- LIL-P0-02 已新增 `scripts/check_release.ps1` 作为发布候选强校验入口，不允许静默跳过 desktop build。
- LIL-P0-03 已新增 `scripts/smoke_lilsunspot_installed_app.ps1`，并在当前开发机通过已安装 app `-SkipInstall` 路径、NSIS 临时目录真实静默安装路径、当前用户真实安装目录直接安装路径。
- LIL-P0-03 已追加多轮/多能力/视觉 QA：连续真实 DeepSeek chat、mode sliders、Weixin command skeleton、Safety approval queue、Doctor 和安装版窗口截图均已验证；当前 P0 chat 仍是 `lilsunspot_provider_adapter`，不是完整 Hermes agent loop。
- 当前 P0 安装主路径没有本机阻断项；clean VM 未执行只作为额外环境差异记录。

## LIL-P0-01 自动验证记录

2026-06-06 在 `release/mvp-p0` 本地分支运行：

```powershell
git diff --check
python scripts/guard_no_secrets.py
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
npm run build --prefix lilsunspot/desktop
pwsh scripts/check.ps1
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop
```

结果：

- daemon tests：23 passed。
- product tests：20 passed。
- secret guard：未发现 lilsunspot task scope 内 secret-like values。
- desktop build：TypeScript/Vite build passed。
- `scripts/check.ps1`：passed。
- sidecar build：生成 `lilsunspotd-x86_64-pc-windows-msvc.exe`。
- NSIS build：生成 `Lilsunspot_0.1.0_x64-setup.exe`。
- sidecar smoke：`/health` ok，`/providers` 返回 6 个 provider，`runtime_bind_host=127.0.0.1`，runtime file 创建成功，token 未写入 daemon 日志。
- 发布候选清理：删除已追踪的 `.tmp-lilsunspot-data/*` 临时 runtime artifacts，并加入 `.gitignore`。

## LIL-P0-03 当前验证记录

2026-06-08 在当前开发机运行：

```powershell
python -m pytest lilsunspot/tests/test_installed_app_smoke_script.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
pwsh -NoProfile -File scripts/smoke_lilsunspot_installed_app.ps1 -SkipInstall -InstallDir "$env:LOCALAPPDATA\Lilsunspot"
pwsh -NoProfile -File scripts/smoke_lilsunspot_installed_app.ps1
.\lilsunspot\desktop\src-tauri\target\release\bundle\nsis\Lilsunspot_0.1.0_x64-setup.exe /S /D=$env:LOCALAPPDATA\Lilsunspot
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
pwsh -NoProfile -File scripts/check.ps1
npm run build --prefix lilsunspot/desktop
npm run tauri:build --prefix lilsunspot/desktop
git diff --check
```

结果：

- 新增脚本静态测试：4 passed；产品测试：32 passed。
- `scripts/check.ps1`：daemon tests 25 passed、secret guard passed、desktop build passed。
- installed-app smoke：当前用户已安装的仓库外 `Lilsunspot.exe` 启动同目录 `lilsunspotd.exe`，隔离数据目录生成 runtime/token，`/health` ok，带 token 的 `/providers` 返回 6 个 provider，daemon 日志不含 runtime token。
- real installer smoke：用户允许后运行非 `-SkipInstall` 路径，NSIS 静默安装到 `%TEMP%\lilsunspot-installed-app-smoke\app`，仓库外安装版启动 sidecar 并通过 `/health` 和 `/providers`，脚本随后静默卸载；本机当前用户安装已重装回 `%LOCALAPPDATA%\Lilsunspot`，注册表卸载项和桌面/开始菜单快捷方式存在。
- direct local install：按用户要求直接静默安装到 `%LOCALAPPDATA%\Lilsunspot`，启动真实安装版 `Lilsunspot.exe`，确认同目录 `lilsunspotd.exe` 进程、`http://127.0.0.1:8765`、真实数据目录 `%LOCALAPPDATA%\Lilsunspot\data`、`/health` ok、带 token 的 `/providers` 返回 6 个 provider、`/app/bootstrap` stage=`chat_ready`；未记录 runtime token。
- real DeepSeek provider/chat：按用户要求从环境变量读取 DeepSeek API Key 到内存，`/providers/test` 通过，`/providers/save` 保存 `deepseek/deepseek-chat`，`/chat/send` 真实返回 4 字回复，`/app/bootstrap` stage=`chat_ready`；未记录 API Key、runtime token 或回复正文。
- multi-round/multi-capability smoke：连续 3 次真实 DeepSeek chat 通过；`conversation_id_supported=false`，跨轮记忆未按已实现能力计入；mode default/pragmatic/balanced 和三滑杆保存后 chat 通过并恢复原 mode；Weixin `/help`、`/mode pragmatic` 通过；Safety approval create/reject 后 pending 归零；Doctor 返回 10 项检查。
- visual QA：真实安装版 DWM 截图覆盖 960x680 与 390x760；初检发现 ChatHome 输入框在窄屏首屏不可见，已调整 `App.css` 的 AppShell/ChatHome/transcript/composer 高度约束，重建并重装后复验输入框可见且未见重叠/横向溢出。
- clean Windows VM：未执行，但不作为当前 LIL-P0-03 阻断项；当前验收以用户要求的本机直接安装环境为准。

## 下一步建议

1. LIL-P1-01：输出模式三滑杆、三层合并和 prompt 编译。
2. LIL-P2-01：Weixin gateway 二维码、状态和真实私聊。
3. LIL-P3-01：真实高危动作审批拦截和 audit.db。
4. LIL-P4-01：诊断包导出和脱敏。
