# Weixin Gateway Feasibility

## 结论

已完成 P2-01 最小真实私聊闭环。

仓库内存在 Hermes 原生 Weixin / WeChat personal account adapter 和 gateway setup 入口。lilsunspot 产品层已经在 P2-01 封装扫码登录、二维码状态、断开入口、凭据隔离保存、runtime 启动和私聊文本回复；主动发送微信消息仍必须走安全审批，不能直接发送。

## 当前项目状态补充

- lilsunspot 当前已封装 Weixin 扫码登录状态、真实二维码、断开清理和私聊文本回复。
- 2026-06-09 用户人工确认真实桌面聊天、真实微信扫码登录、微信端登录、私聊文本回复、`/help`、`/mode` 和安装版 UI 点击均已跑通，P2-01 人工校验成功。
- 后续稳定性风险：断线重连、二维码真实过期仍需补验；微信命令 UX 也需要改成更适合普通用户的自然语言、按钮/菜单或快捷卡。
- Provider/token/Hermes home 链路已推进到当前产品层；后续 Weixin 接入应复用 lilsunspot 数据目录和安全审批策略。
- 不应直接重写 Hermes Weixin adapter；只在 lilsunspot 层做配置、启动、审批和用户可见错误封装。

## 入口文件

- `gateway/platforms/weixin.py`
- `hermes_cli/gateway.py`
- `gateway/run.py`
- `gateway/config.py`

## 入口命令

- `hermes gateway setup`
- `hermes gateway status`
- 当前 PowerShell PATH 中裸 `hermes` 不可见；等价命令使用 `uv run hermes ...`。

## 命令级探测

- `hermes gateway --help`：当前 shell 返回 command not found。
- `hermes gateway status`：当前 shell 返回 command not found。
- `uv run hermes gateway --help`：成功，显示 gateway 子命令包含 `run/start/stop/restart/status/install/uninstall/list/setup/migrate-legacy`。
- `uv run python -c "from gateway.platforms.weixin import check_weixin_requirements; print(check_weixin_requirements())"`：返回 `True`。

## 是否发现二维码流程

是。

- `gateway/platforms/weixin.py` 中存在 `qr_login(...)`。
- `qr_login(...)` 调用 `ilink/bot/get_bot_qrcode` 获取二维码。
- 流程会打印二维码链接，并在安装 `qrcode` 时尝试终端二维码渲染。
- `hermes_cli/gateway.py` 中 `_setup_weixin()` 调用 `qr_login(str(get_hermes_home()))`。

## 是否需要人工扫码

需要，且 P2-01 已完成一轮人工扫码验收。

Day1 只做代码级和非交互命令探测；P2-01 已补上真实扫码、微信端登录、普通私聊文本回复、`/help`、`/mode` 和安装版 UI 点击人工验收。后续媒体/文件、断线重连、二维码过期仍不能仅凭代码存在判断可交付，必须继续人工验收。

## 是否影响后续验收

不阻断 lilsunspot 继续推进，但会影响真实验收范围。

- 如果只做 lilsunspot 对 Hermes Weixin gateway 的配置封装：可继续推进。
- P2-01 已覆盖一轮真实扫码和普通私聊文本回复；如果继续要求稳定性、媒体/文件或主动发送能力，仍必须安排断线重连、二维码过期、文件/PDF 和安全审批验证。

## 下一步建议

1. 先做 LIL-P2-03：把 `/help`、`/mode` 这类命令式路径改成普通用户能理解的自然语言引导、按钮/菜单或快捷卡。
2. 推进 LIL-P2-02：复用官方 Hermes Weixin adapter 的媒体/文件、`MessageEvent` 和 artifact 交付能力，补本地会话同步、桌面 UI、审批和脱敏。
3. 在媒体/文件和稳定性能力交付前继续做真实扫码、断线重连、二维码过期和安装版 smoke，不能把代码级存在当成验收完成。
