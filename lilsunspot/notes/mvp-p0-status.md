# MVP P0 当前状态

## 记录信息

- Git root：`<repo-root>`
- 当前分支：`release/mvp-p0`
- 当前 commit：以 PR 分支提交为准
- 更新时间：`2026-06-06`
- 记录方式：基于 LIL-P0-01 本地自动验证；未运行或仍需真实用户环境的功能标记为未验证。

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
| Windows 安装包 | 自动构建通过 | `npm run tauri:build --prefix lilsunspot/desktop` | 生成 `Lilsunspot_0.1.0_x64-setup.exe`；干净 Windows 安装未验证。 |
| Lilsunspot.exe | 自动构建通过 | Tauri release build | 构建出 release exe；仓库外已安装启动未验证。 |
| lilsunspotd | 自动验证通过 | sidecar smoke `/health` | PyInstaller sidecar 可在临时数据目录启动。 |
| runtime token | 自动验证通过 | sidecar smoke token-protected `/providers` | 创建 token/runtime file；日志 token 泄漏检查通过；未记录 token。 |
| provider registry | 自动验证通过 | sidecar smoke `/providers` | 返回 6 个 provider。 |
| provider test | 测试通过 | `lilsunspot/daemon/tests`, `lilsunspot/tests` | 覆盖 mock 成功和错误；本次未使用真实 API Key。 |
| provider save | 测试通过 | `lilsunspot/tests/test_provider_api.py` | 覆盖写入 lilsunspot 独立 Hermes home；本次未保存真实 API Key。 |
| desktop provider wizard | 构建通过 | `npm run build --prefix lilsunspot/desktop` | TypeScript/Vite 通过；未做视觉或端到端验证。 |
| desktop chat | 测试/构建通过 | chat API tests, desktop build | daemon chat 路径和桌面 build 通过；本次未跑真实桌面 UI 聊天。 |
| mode profiles | 部分实现 | lilsunspot/resources/, lilsunspot/daemon/app.py | mode profile API 存在；三滑杆未验证。 |
| Weixin gateway | 部分实现 | lilsunspot/daemon/app.py, lilsunspot/notes/weixin-feasibility.md | 产品层命令/状态骨架存在；真实私聊未验证。 |
| safety approvals | 部分实现 | lilsunspot/daemon/app.py, lilsunspot/daemon/tests/ | 审批队列 API 存在；真实高危动作拦截未验证。 |
| doctor | 部分实现 | lilsunspot/daemon/doctor.py, lilsunspot/daemon/app.py | doctor/repair API 存在；本任务未运行。 |
| diagnostics export | 未实现 | 未验证 | 未发现明确诊断包导出入口。 |
| clean Windows install | 未验证 | 未验证 | 必须在干净 Windows 上人工验证。 |

## 当前 P0 阻断项

- 安装包是否能在干净 Windows 上运行。
- 2026-06-08 用户确认除干净 Windows 安装以外，LIL-P0-01 其余人工验收已完成；本文件未记录真实 API Key、runtime token 或私有截图。
- LIL-P0-02 已新增 `scripts/check_release.ps1` 作为发布候选强校验入口，不允许静默跳过 desktop build。

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

## 下一步建议

1. LIL-P0-02：新增发布级 `check_release.ps1`，不允许静默跳过 desktop build。
2. LIL-P0-03：干净 Windows 安装冒烟，验证仓库外 `Lilsunspot.exe` 启动 `lilsunspotd`。
