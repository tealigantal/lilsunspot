# Weixin Gateway Feasibility

## 结论

部分可用。

仓库内已经存在 Hermes 原生 Weixin / WeChat personal account adapter 和 gateway setup 入口。它不是 Day1 需要新写的功能，但后续接入仍需要人工扫码、真实私聊验收和 lilsunspot 层的配置/审批封装。

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

需要。

Day1 只做代码级和非交互命令探测，不要求也不执行真实扫码。真实 Weixin 私聊收发仍必须由用户扫码登录后验收，不能仅凭代码存在判断可交付。

## 是否影响 D5

不阻断 D5，但会影响 D5 的真实验收范围。

- 如果只做 lilsunspot 对 Hermes Weixin gateway 的配置封装：可继续推进。
- 如果要求稳定私聊收发：必须安排真实扫码、真实私聊、断线重连和安全审批验证。

## 下一步建议

1. Day2 先把 lilsunspot 的 Hermes home、provider、token 流程闭环。
2. Day3/Day4 再做 Weixin 配置页或 API 封装，避免直接修改 Hermes adapter。
3. D5 前做一次人工扫码验证，记录账号状态文件、home channel、允许私聊策略和退出/清理方式。
