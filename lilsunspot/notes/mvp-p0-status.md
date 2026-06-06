# MVP P0 当前状态

## 记录信息

- Git root：`<repo-root>`
- 当前分支：`develop`
- 当前 commit：`52839794e`
- 更新时间：`2026-06-06`
- 记录方式：基于本地仓库 Markdown、git 状态和文件扫描；未运行的功能标记为未验证。

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
| Windows 安装包 | 部分实现 | scripts/build_lilsunspotd_sidecar.ps1, lilsunspot/desktop/ | NSIS 构建链路存在；干净 Windows 未验证。 |
| Lilsunspot.exe | 部分实现 | lilsunspot/desktop/ | Tauri 桌面和 sidecar 文档存在；仓库外启动未验证。 |
| lilsunspotd | 部分实现 | lilsunspot/daemon/app.py, lilsunspot/daemon/launcher.py | daemon 入口存在；本任务未启动。 |
| runtime token | 部分实现 | lilsunspot/daemon/auth.py, lilsunspot/daemon/config_paths.py | token 文件逻辑存在；本任务未读取真实 token。 |
| provider registry | 部分实现 | lilsunspot/resources/provider_registry.yaml, lilsunspot/daemon/providers.py | registry 和读取代码存在。 |
| provider test | 部分实现 | lilsunspot/daemon/app.py, lilsunspot/daemon/tests/ | `/providers/test` 入口和测试存在；本任务未运行真实 provider。 |
| provider save | 部分实现 | lilsunspot/daemon/hermes_runtime.py, lilsunspot/daemon/app.py | 写入 Hermes home 的代码路径存在；本任务未运行。 |
| desktop provider wizard | 部分实现 | lilsunspot/desktop/ | 桌面 Provider 页面/API 调用存在；未做视觉或端到端验证。 |
| desktop chat | 部分实现 | lilsunspot/desktop/, lilsunspot/daemon/chat_client.py | 桌面和 daemon chat 路径存在；是否稳定未验证。 |
| mode profiles | 部分实现 | lilsunspot/resources/, lilsunspot/daemon/app.py | mode profile API 存在；三滑杆未验证。 |
| Weixin gateway | 部分实现 | lilsunspot/daemon/app.py, lilsunspot/notes/weixin-feasibility.md | 产品层命令/状态骨架存在；真实私聊未验证。 |
| safety approvals | 部分实现 | lilsunspot/daemon/app.py, lilsunspot/daemon/tests/ | 审批队列 API 存在；真实高危动作拦截未验证。 |
| doctor | 部分实现 | lilsunspot/daemon/doctor.py, lilsunspot/daemon/app.py | doctor/repair API 存在；本任务未运行。 |
| diagnostics export | 未实现 | 未验证 | 未发现明确诊断包导出入口。 |
| clean Windows install | 未验证 | 未验证 | 必须在干净 Windows 上人工验证。 |

## 当前 P0 阻断项

- 安装包是否能在干净 Windows 上运行
- 桌面是否自动连接 daemon
- provider 测试保存是否稳定
- 桌面聊天是否稳定
- secret 是否脱敏

## 最近应运行的检查

以下命令是建议检查项；本次 LIL-DOC-01 未运行 pytest、npm build 或 Tauri build。

```powershell
git diff --check
python scripts/guard_no_secrets.py
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
npm run build --prefix lilsunspot/desktop
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop -- --bundles nsis
```

## 下一步建议

LIL-P0-01：收敛 release/mvp-p0 分支并验证安装、首启、provider、桌面聊天。
