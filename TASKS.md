# TASKS.md

## Current

`LIL-HERMES-UPSTREAM-FULL-SYNC-01`：同步执行时可确认的 Hermes 官方最新 `main`，并让 lilsunspot 在 Windows 安装版中完整继承上游全部能力。已固定、抓取目标 `d9f1043c3337818b1f29224a7deb5bbb17402370` 到 `upstream/sync-d9f1043`，本地 ancestry left/right=`0 / 8485`。固定目标已展开为 519 行 parity ledger；57 toolsets、74 tools 和 4 provider transports 已完成设计映射，当前 135 design_mapped / 384 unspecified、0 validated。执行 owner、安全边界、operator/cron/platform、integration read/write、Yuanbao 归属和 browser CDP 动态 toolset 均已分开记录。77 个 config surfaces 经只读审计确认不能先批量映射：目标 `_config_version=33`，而当前产品缺少版本门禁、schema 校验、备份/回滚和降级拒绝，且 model/providers/secrets 与旧产品键存在结构漂移。尚未 merge 或更新 `UPSTREAM_COMMIT.txt`；下一步保存审计检查点，合入固定 SHA 后先实现 v33 配置迁移契约，再完成 config/plugins/skills/MCP/gateways 映射。

以下 `LIL-CAPABILITY-ORCHESTRATION-01B` 内容为此前在途背景，本轮暂停，不作为当前源码修改目标；其既有未提交记录保留，后续回到 Next 继续收口。

LIL-CAPABILITY-ORCHESTRATION-01B：迁移 Hermes 本地能力并修复重配/图片/微信链路。按 `lilsunspot/notes/model-capability-ux-plan.md` 第一阶段继续执行：能力判断和视觉调用迁移到 Hermes resolver/metadata，重配流程从首启向导拆出，微信会话里的桌面插话复用微信 route/coalescer/session，安装版必须重建验证。允许使用本机已有真实 API Key 做定向 live smoke，但不得记录 Key/token/微信凭据/私聊正文/附件原文或完整模型回复。

- 2026-06-30 截图级全界面验收记录：本轮只做 Vite + headless Chrome/CDP + mock daemon 的截图级验收，不改产品代码，不访问真实 Key/token/微信二维码/私聊正文/附件原文。覆盖首启欢迎、选择模型、保存模型、第一句聊天、日常聊天、微信、任务、历史、设置抽屉 8 个分类，以及 390px 移动宽度聊天/设置/微信/任务，共 22 张截图；指标层面未发现横向溢出，首启阶段唯一 console error 是 dev server `favicon.ico` 404。下一步计划仅记录问题：1）首启保存模型后进入“试着说第一句话”时，顶栏仍显示“未配置”，与页面内“模型服务已保存到本机”互相冲突，需刷新/传递 bootstrap runtime 状态或在该步骤隐藏旧状态；2）“保存模型设置”页在 1280x760 首屏看不到“保存并继续”主操作，关键完成动作被压到滚动区下方，需压缩说明卡或做 sticky action；3）设置抽屉的分类导航在桌面 760 高和移动宽度下占用过多纵向空间，实际设置内容从半屏以下开始，需改成横向/紧凑分段或 sticky tab；4）390px 聊天首屏优先显示导航、状态和对话列表，真正的聊天内容/输入区不在首屏，需把移动端会话列表折叠或改为可切换面板。截图和 mock 结果保存在 ignored 临时目录 `ignored/ui-acceptance/`，不提交。
- 2026-06-13 附件返还链路问题记录：用户在桌面对话里要求“小黑子把刚上传的图片再发给我”时，模型回复成“没有直接发送图片文件能力 / weixin.send_file 未配置”，暴露的是能力编排口径问题，不是图片识别失败。当前会话库已经把桌面上传附件保存到安全附件目录，`/attachments/{id}` 也能按附件 id 取回安全路径；但能力图和 prompt 快照只暴露 `runtime.desktop_image_upload`（上传/预览/识别）与 `weixin.send_file`（微信发送文件且需连接/审批），没有暴露“复用最近已上传/已生成的本地安全附件并返还给当前桌面用户”的默认能力，也没有把这类自然语言意图路由到附件卡打开/下载/复制或安全返还动作。因此模型只能按微信发送能力判断并拒绝。后续修复应把“已入库安全附件的当前聊天返还/打开/下载”作为默认可用的桌面能力处理；若目标是微信或外部平台，再走 `weixin.send_file + safety.approval`，不要让普通用户理解 weixin/tool 名称。本轮仅研究并记录，不改代码。
- 2026-06-13 定位追加：微信会话界面里从桌面端插入一段对话时，截图中的“请求失败，请稍后再试。请重新检查 AI 服务设置。”失败泡泡与前端 `ChatHome.send()` catch 分支文案一致；本机会话库脱敏检查未发现持久化 `status=error` 消息，说明该泡泡更像前端本地临时错误，而不是后端真实落库回复。可疑链路是桌面插话走 `/conversations/{id}/messages -> _accept_conversation_message() -> turn_coalescer.key_for_desktop(conversation_id)`，但微信入站走 `turn_coalescer.key_for_weixin(route, conversation_id)` 并携带微信 route/source；同一个微信会话内的桌面插话和微信入站没有统一 route/coalescer/session contract，后续修复应覆盖：微信会话内桌面发言被接受时不出现本地假失败泡泡，assistant 占位只由同一条 SSE/DB 状态更新，且桌面插话与微信入站共享一致的会话上下文和串行规则。本轮仅定位并记录，不做代码修复。
- 2026-06-13 定位追加：已有本地模型配置后再“更换或重新测试”会复用首启 `OnboardingFlow`，不是独立的重配置流程。该入口把 `forceOnboarding=true`，用 `bootstrap.runtime.provider` 进入 `api_key` 步，但 `chooseProvider()` 会重置模型、Base URL、API Key 和测试结果；`ApiKeyStep` 对云端 provider 又要求 `apiKey.trim()` 才允许测试/保存，后端 `save_provider_credentials()` 也会在非本地 provider 且空 Key 时返回 `API Key 不能为空。`。本轮用临时数据目录验证：已有 DeepSeek 配置后，空 Key 保存同 provider 新模型失败且旧配置保持不变。后续修复应把“首启设置”和“已有配置重配”拆开，已有 Key 时允许只改 model/base_url/provider 映射或明确要求重新粘贴 Key，不能显示“当前步骤没有完成 / 请求失败”这种泛化错误。另一个鲁棒性风险是 provider id 映射：设置抽屉按 `provider.id === runtime.provider` 查当前 provider，若旧配置或 Hermes 配置只暴露 `alibaba/custom` 等 Hermes provider id，而不是 `qwen/openai` 这类产品 id，向导会找不到当前 provider 并静默回退到列表第一个服务，造成用户想换配置却看到/保存成错误 provider。当前本机脱敏配置显示 `deepseek/deepseek-chat` 主模型 + `qwen-vl-max` 辅助视觉；但最近图片附件仍是 `preview_only` 且没有 `recognition_backend/stage/error_code` metadata，这与当前仓库实现不一致，说明已安装运行版本/升级链路仍可能落后于仓库实现，导致 UI 声称辅助视觉已启用但真实聊天仍只预览。后续验收必须覆盖“已有配置 -> 更换主模型/Key/Base URL -> 保留或更新辅助视觉 -> 上传图片真实识别”的完整闭环。本轮仅检验并记录，不做代码修复。
- 2026-06-13 真实本机 trouble-shoot 追加：用当前本机已保存 Key 做真实验证，结论是“当前安装版不能真正使用图片识别”。当前脱敏配置为 DeepSeek 主模型 `deepseek-chat` + Qwen 辅助视觉 `qwen-vl-max`，DeepSeek Key 存在且 `/providers/test` 返回通过，`/providers/save` 用同一个已保存 Key 直接调用也返回 200，随后 `/app/bootstrap` 为 `chat_ready`，所以用户截图里的“重新填写 DeepSeek Key 后保存报错”不是 DeepSeek Key 无效或后端保存失败。问题在前端向导：`saveAndContinue()` 把 `saveProvider()`、`getProviderCapabilities()` 和 `onSaved()/bootstrap.refresh()` 都包在同一个 catch 中，任意后置刷新/状态切换失败都会渲染成“当前步骤没有完成 / 请求失败”，把已成功保存误报成保存失败。图片链路真实测试：当前运行 daemon 的 `/providers/capabilities` 返回 `supports_image=true`、`image_backend=auxiliary_vision`，但没有 `capability_graph` / `image_capability_status`，`/capability-graph` 为 404；用生成的非私密 PNG 走 `/conversations/{id}/messages` 上传后，附件仍是 `preview_only`，原因仍是“当前 DeepSeek 文本模型不能识别图片内容”，且没有 `recognition_backend/stage/error_code` metadata。这说明当前安装版 daemon 仍是旧链路：UI/能力接口声称辅助视觉可用，但真实附件识别没有调用辅助视觉。用仓库当前代码直接读取本机已保存配置调用 `describe_image_data_url()` 时已进入 `backend=auxiliary_vision` / `stage=vision.auxiliary`，但服务端对 `qwen-vl-max` 返回 `model_not_found`；即使部署了新代码，当前保存的 Qwen 视觉模型名/服务端可用性也还不能通过真实识图。后续修复必须同时处理：安装版更新到统一能力图版本、主模型重配置使用独立流程并区分“保存成功但刷新失败”、能力口径不能把未真实验证的辅助视觉显示成可用、Qwen 视觉模型名/Provider Base URL/Key 的 live 验证错误要在设置页明确展示。本轮仅 trouble-shoot 并记录，不做代码修复。
- 2026-06-13 VL 模型资料搜索记录：当前 `qwen-vl-max` 不是凭空写错的模型名，Alibaba Cloud Model Studio 官方模型列表仍列出 `qwen-vl-max` / `qwen-vl-plus`，并说明它们属于 Qwen2.5-VL 系列；但 Alibaba 视觉理解页也把新一代 `qwen3-vl-plus` / `qwen3-vl-flash` 列为 Qwen3-VL 系列，并描述更适合高精度识别、定位、文档/网页解析、复杂问题和长视频理解。因此后续默认推荐不应只硬编码 `qwen-vl-max`，应把 Qwen 视觉 provider 设计成“从官方/接口模型清单或 live smoke 选择可用模型”，优先考虑 `qwen3-vl-plus` / `qwen3-vl-flash`，并保留 `qwen-vl-plus` / `qwen-vl-max` 作为兼容项；用户本机 `qwen-vl-max` 返回 `model_not_found` 可能是账号、部署模式、区域、Base URL 或模型下线/不可用导致，产品必须把这个错误显示为“视觉模型不可用/请换推荐模型”，不能笼统说保存失败。DeepSeek 方面，官方 DeepSeek API 文档当前列出的托管 API 模型是 `deepseek-v4-flash`、`deepseek-v4-pro`，并标注旧 `deepseek-chat` / `deepseek-reasoner` 将在 2026-07-24 15:59 UTC 废弃；官方 API 文档页未列出 `deepseek-vl` 可作为同一 DeepSeek API base URL 的视觉模型。但 DeepSeek 确实有开源视觉/文档模型：`DeepSeek-VL`、`DeepSeek-VL2`、`DeepSeek-OCR` / OCR2，适合通过本地 vLLM/Ollama/Hugging Face/第三方推理服务接入，不能直接复用 DeepSeek API Key 当作云端视觉模型。其它可纳入后续统一设计的视觉服务：OpenAI 官方当前说明最新模型支持文本+图片输入；Claude 官方说明当前 Claude 模型都支持文本和图片输入；Gemini 官方说明 Gemini 模型原生多模态，支持图片理解；Kimi 官方平台显示 Kimi K2.6 / K2.5 支持文本、图片、视频输入；OpenRouter 官方支持向 vision-capable models 发送 URL 或 base64 图片，可作为聚合兜底；Mistral 当前文档把 Mistral Medium 3.5、Small 4、Large 3、Ministral 3 14B 等列为多模态/视觉能力模型，旧 Pixtral 系列已标为 deprecated；本地 Ollama 可选 `qwen3-vl`、`qwen2.5vl`、`deepseek-ocr`、`llava`、`llama3.2-vision`、`minicpm-v`、`mistral-small3.1`、`moondream` 等，但必须先检测本机是否已安装模型和 Ollama 版本/硬件。后续统一修改计划应把“模型推荐”和“能力判断”改成 provider adapter + live model probe + capability graph verified 状态，而不是静态默认模型名。
- 2026-06-13 Hermes 本地官方依据追加：后续不要在小黑子产品层自建一套 VL provider/model 适配表，应优先直接迁移 Hermes 已有机制。官方本地代码的 source of truth 是 `agent/auxiliary_client.py`、`agent/image_routing.py`、`agent/models_dev.py`、`hermes_cli/model_switch.py`、`hermes_cli/main.py`、`hermes_cli/setup.py` 和 `hermes_cli/web_server.py`：`auxiliary_client` 明确 vision/multimodal auto 顺序为主 provider（仅当模型支持视觉）-> OpenRouter -> Nous -> Anthropic -> custom endpoint -> none，并通过 `resolve_vision_provider_client()` / `get_available_vision_backends()` 给 setup、tool gating 和 runtime 复用；`image_routing` 用 `agent.image_input_mode=auto|native|text`、`auxiliary.vision` 显式覆盖和 `models.dev` 的 `supports_vision` 元数据决定用户附件是 native image_url 还是先走 `vision_analyze` 文本摘要；`models_dev` 已维护 Hermes provider 到 models.dev provider 的映射和 `modalities.input`/`attachment` 能力解析；Hermes 的辅助模型菜单只针对已认证 provider 做 task routing，新增 provider/key 应先走正常模型配置，再把 `auxiliary.vision` 指向该 provider/model/base_url。对小黑子的迁移约束：`/providers/capabilities` 和 capability graph 应从 Hermes resolver/metadata 派生状态，不再以 `lilsunspot/resources/provider_registry.yaml` 的 `vision_default_model` 或产品自写模型清单作为能力判断；`describe_image_data_url()` 应复用 Hermes `async_call_llm(task="vision")` 或 `resolve_vision_provider_client()` 路径，不再手拼 OpenAI-compatible 请求和 provider 映射；设置页应拆成“主模型凭据配置”和“辅助任务路由配置”，保留中文 UX 包装但底层语义对齐 Hermes `/api/model/auxiliary` / `/api/model/set`；真实验证只记录 provider/model 和脱敏错误分类，不记录 key、图片原文或完整回复。本轮仅调查并记录迁移依据，不做代码修改。
- 2026-06-13 实现追加：01B 已在产品层迁移主要链路，不改 Hermes core。`describe_image_data_url()` 现在准备本机 `hermes_home` 环境后调用 Hermes `async_call_llm(task="vision")`，能力状态从 `decide_image_input_mode()`、Hermes provider 映射、`resolve_vision_provider_client()` 和 `get_available_vision_backends()` 派生；`image.read.details` 输出脱敏 `verification_status`、`last_error_code`、`resolved_provider`、`resolved_model`、`source`。主模型保存支持已有同 provider/env Key 时空 Key 重配，只改 model/base_url 不覆盖旧 Key；首启 `OnboardingFlow` 的保存和能力刷新错误已拆开，已有配置在设置页使用独立重配面板，`forceOnboarding` 不再作为重配入口。微信 conversation 中桌面插话会读取 `weixin_route`，使用同一个 `weixin:<route>` turn key、`source=weixin` 和 route 传给 agent loop。设置页图片识别面板现在会把 `invalid_key`、`model_not_found`、限流、额度、网络等脱敏错误码翻译成明确中文失败原因。sidecar 构建脚本增加 `uv` 优先、本地 PyInstaller venv 兜底，并且只有在新 sidecar 成功生成后才替换旧 bundle，避免依赖下载失败破坏旧安装资源。本机 PyPI TLS 阻断已用临时镜像环境变量绕过，`npm run tauri:build --prefix lilsunspot/desktop` 已重新生成 NSIS：`Lilsunspot_0.1.0_x64-setup.exe`，大小 55,792,692 bytes，时间 2026-06-13 19:35:18 +08:00；已静默覆盖安装到当前用户 `%LOCALAPPDATA%\Lilsunspot`，安装目录里的 `Lilsunspot.exe` 和 `binaries/lilsunspotd/lilsunspotd.exe` 均为本轮新产物。安装版 live smoke 使用本机已保存 Key 验证：`/capability-graph` 可用，`/app/bootstrap=chat_ready`，主模型 `deepseek/deepseek-chat` 可回复；图片上传走 Hermes `auxiliary_vision` -> `alibaba/qwen-vl-max`，但服务端返回脱敏 `invalid_key`，附件为 `preview_only`，能力图为 `blocked / failed / invalid_key`。本机只发现已保存 DeepSeek 与 DashScope Key 名，未记录任何 Key、token、附件原文或完整模型回复。已跑验证：focused capability/product/conversation pytest 53 passed、`test_chat_api.py` 7 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh scripts/check.ps1`（daemon 102 passed + secret guard + desktop build）、`git diff --check`。
- 2026-06-13 Qwen/大陆 provider 兼容修复追加：按阿里云 Model Studio 官方 OpenAI 兼容和区域文档修正产品层兼容性，不改 Hermes core。Qwen/DashScope 不能只保存 provider/model；大陆百炼 Key 必须和 `https://dashscope.aliyuncs.com/compatible-mode/v1` 或用户手填的同区域 Base URL 匹配。产品层 `save_auxiliary_model()` 现在会把 `qwen -> alibaba` 这类产品 provider 到 Hermes provider 的默认 Base URL 写入 `auxiliary.vision.base_url`，`read_hermes_config()` 会为旧的 `lilsunspot.auxiliary.vision.provider=qwen` 且 Hermes `auxiliary.vision.provider=alibaba`、缺 base_url 的配置自动补齐；视觉调用改为先用 Hermes `resolve_vision_provider_client(async_mode=True)` 拿到实际 client/model，再直接调用该 client，避免已解析出的 `alibaba/qwen-vl-max` 被泛用 `async_call_llm(task=vision)` 二次 fallback 到 OpenRouter/Nous。Kimi 产品 registry 同步调整为国内开放平台默认：`base_url=https://api.moonshot.cn/v1`、`default_model=kimi-k2.6`，保留用户手工 Base URL 覆盖。真实本机检测只记录脱敏状态：DeepSeek `deepseek-chat` 通过，Kimi 未配置 Key，Qwen `qwen-plus` 通过；同一 DashScope Key 和大陆 Base URL 下，`qwen-vl-max`、`qwen-vl-plus`、`qwen3-vl-flash`、`qwen3-vl-plus`、`qwen3.6-flash` 用 128x128 生成 PNG 直连均返回 200。此前 1x1 PNG 会被 Qwen 视觉返回“图片长宽不满足限制”，不能误判为额度或 Key 问题；本机免费获取的 DashScope Key 当前不是“没有免费额度”，真实视觉调用可用。安装版已重新构建并静默覆盖安装：`Lilsunspot_0.1.0_x64-setup.exe` 大小 55,786,085 bytes，时间 2026-06-13 20:28:34 +08:00；安装目录 `Lilsunspot.exe` 和 `binaries/lilsunspotd/lilsunspotd.exe` 均为本轮新产物。安装版 live smoke 使用真实已保存 Key：`/capability-graph` 可用，`/models/auxiliary` 保存 `qwen/qwen-vl-max` 后 Hermes 配置为 `alibaba/qwen-vl-max` 且 base_url 存在；发送生成 PNG 走 `auxiliary_vision / vision.auxiliary`，附件 `summary_status=recognized`，assistant `sent`，临时测试会话已删除；发送后 `image.read=ready / verified / resolved_provider=alibaba / resolved_model=qwen-vl-max`。已跑验证：`python -m pytest lilsunspot/daemon/tests/test_capabilities.py lilsunspot/daemon/tests/test_conversation_sync.py lilsunspot/daemon/tests/test_product_features.py -q` 第二次 54 passed（第一次同组有 1 个微信切换顺序相关失败，单测立即复跑通过）、`python -m pytest lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot -q` 7 passed、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`（daemon 104 passed + secret guard + desktop build）、`npm run build --prefix lilsunspot/desktop`、`git diff --check`（仅 CRLF warning）、`npm run tauri:build --prefix lilsunspot/desktop`。未记录 Key、runtime token、附件原文或完整模型回复。
- 2026-06-13 clean-start 安装版现场验收追加：清空当前安装版数据前已把旧 `%LOCALAPPDATA%\Lilsunspot\data` 备份到 `data-backups/data-before-clean-start-20260613-211643`，随后覆盖安装并从零开始。用户保存 DeepSeek Key 后 UI 卡住，定位为保存本身已成功，但首启后置 `/providers/capabilities` 和 `/capability-graph` 同步调用 Hermes `models.dev` 远程 metadata，且无显式辅助视觉配置时还触发 OpenRouter/Nous 自动视觉 backend 探测；本机 TLS/proxy 握手导致能力刷新长时间阻塞。修复为能力状态只读取显式配置覆盖、已有内存/磁盘 models.dev 缓存和已配置的辅助视觉，不在普通状态读取中触发 models.dev 网络 fetch 或未显式配置的外部视觉 backend 探测；无辅助视觉时 DeepSeek 文本模型快速返回 `image.read=needs_setup` 并引导添加图片识别模型。验证：同一安装数据目录下仓库代码 `model_capabilities` 从超时/13s 降到约 402ms；focused `test_product_features.py` + `test_capabilities.py` 17 passed；首次 NSIS 重建因 PyPI TLS 失败，使用临时镜像环境变量后 `npm run tauri:build --prefix lilsunspot/desktop` 成功并静默覆盖安装。热修安装版启动后 `/health=ready`，`/app/bootstrap=chat_ready`，`/providers/capabilities` 18ms，`/capability-graph` 12ms，DeepSeek `deepseek-chat` 配置仍在，`chat.text=ready`，`image.read=needs_setup`。未记录 Key、runtime token、聊天正文、附件原文或完整模型回复。
- 2026-06-13 clean-start 首启引导问题记录：首次设置 API Key 的引导仍不够细。当前入口如果把用户带到服务商页面，但用户还没有注册账号或尚未登录，实际落点可能只是服务商主页/控制台入口，而不是可直接创建或复制 API Key 的页面。后续应把普通用户路径写清楚：先注册/登录服务商账号，再进入 API Key/控制台页面，必要时提示可能需要实名、开通服务或选择模型；不能只假设用户已经有账号并能直接拿到 Key。本轮仅记录问题，不改代码。
- 2026-06-13 clean-start 首启流程问题记录：图片识别配置不应作为保存主模型 Key 之后的独立首启步骤打断用户。对普通用户来说，“选择 AI 服务 / 保存 API Key / 是否支持图片识别 / 是否需要辅助视觉模型”属于同一个服务配置问题，应在同一界面里解释和处理；如果主聊天模型不能看图，就应在配置 API Key 的同一流程中给出辅助视觉选择、默认推荐、可跳过说明和后续补配入口。当前单独的“图片识别设置”步骤会让用户以为又进入了另一套模型配置，和 API Key 配置割裂，不符合首次启动的用户逻辑。本轮仅记录问题，不改代码。
- 2026-06-13 clean-start UI 现场验收追加：用户反馈图片识别设置页同一句“已配置辅助视觉模型”同时以能力节点消息和 limitations 黄色提示显示两次，且保存视觉模型后聊天输入区附件提示仍停留在旧的“还没有配置辅助视觉模型”。本轮改为前端共享能力状态，而不是局部事件补丁：`AppShell` 统一持有 `ModelCapabilities`，`BootGate` / `ChatHome` / `SettingsDrawer` / `ModelSettings` 透传同一份能力对象，`VisionModelPanel` 保存/清除视觉模型后用刚刷新的 `ModelCapabilities` 更新父级状态；`ChatHome` 不再单独拉取能力接口，也不监听窗口事件。`VisionModelPanel` 继续对当前提示和 limitations 做同文案去重，避免同一后端消息在同一面板显示两次。验证：`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`git diff --check`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`（daemon 105 passed + secret guard + desktop build）、`npm run tauri:build --prefix lilsunspot/desktop` 均通过；新 NSIS `Lilsunspot_0.1.0_x64-setup.exe` 大小 55,793,173 bytes，时间 2026-06-13 21:55:38 +08:00，已静默覆盖安装并重启当前用户安装版。脱敏 live check：`/health=ready`、`/app/bootstrap=chat_ready`、`/providers/capabilities` 返回 DeepSeek `deepseek-chat`，`image.read=degraded`、`image_backend=auxiliary_vision`、`auxiliary_configured=True`。未记录 Key、runtime token、聊天正文、附件原文或完整模型回复。
- 2026-06-14 全页面状态 contract 实现追加：本轮不按单张截图止血，继续在产品层收口首启、模型设置、图片识别、聊天、能力页、控制台、安全页和输出模式页。前端新增共享 `ModelServiceState`，由 `AppShell` 统一持有 providers 与 `ModelCapabilities`；保存、清除、发送、审批等主动作与后续能力刷新拆开，刷新失败只作为非阻塞提示，不再污染成“当前步骤没有完成”或本地假失败泡泡。设置抽屉各 tab badge 从共享状态派生；能力页、控制台、安全页、模式页改为分区独立加载，单区失败不清空其他区；聊天发送失败不再插入独立 assistant 失败消息，后端同 turn 成功事件到达后会清理 composer 提示。provider 官网跳转继续只走产品 provider id 的 registry `key_url`，不允许用主模型 provider、detect_url 或 Base URL 兜底；assistant 交付状态只显示中文结果和安全附件卡，不暴露 Hermes/tool/本地路径。验证：`npm run build --prefix lilsunspot/desktop`、focused daemon tests 61 passed、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`（daemon 114 passed + secret guard + desktop build）、`git diff --check`（仅 CRLF warning）、`npm run tauri:build --prefix lilsunspot/desktop` 均通过；最终 NSIS `Lilsunspot_0.1.0_x64-setup.exe` 大小 55,802,748 bytes，时间 2026-06-14 20:21:57 +08:00。安装版临时目录 smoke 通过：基础 sidecar/runtime/providers smoke 通过，补充 state contract smoke 确认首次启动 `needs_model`、`/providers/reset-local` 后仍回到 `needs_model`、图片附件上传返回 1 个安全附件卡且响应不含本地安全路径字段。未记录 Key、runtime token、聊天正文、附件原文或完整模型回复。
- 2026-06-14 截图级全场景 QA 阻断：按用户要求用本地 Chrome CDP + Vite + mock daemon 做截图级验收，覆盖 960x680 与 390x760、开发态未填 Token、首启空 Key 禁用/官网 Key 页面、聊天附件超大错误、发送失败恢复附件、发送成功清空附件、设置抽屉模型/能力/控制台/安全/诊断分区加载与失败、微信二维码/断开二次确认、输出模式保存和移动端主要页面。通过项未发现横向溢出、内部 `MEDIA:` / `safe_path` / `weixin.send_file` 文案泄漏或本地假 assistant 失败泡泡残留。未通过项：首次配置保存主模型时，如果 `/providers/save` 已成功但后续 `/providers/capabilities` 失败，当前 UI 没有停留并显示“模型服务已保存；能力状态稍后刷新”，而是直接进入“试着说第一句话”，导致用户看不到保存成功但刷新失败的分层结果。按本轮规则，截图级测试未通过，不创建 PR；后续修复应让首启保存成功后的能力刷新失败以非阻塞提示保留在当前流程或带到下一步可见区域。
- 2026-06-14 截图级 QA 修复追加：首启向导保存结果改为共享 `OperationNotice`，和设置页 provider/capability notice 使用同一展示组件；保存成功后的能力刷新失败不再绑定在 `ApiKeyStep` 局部提示里，步骤切到第一句聊天后仍显示“模型服务已保存；能力状态稍后刷新”。复跑本地 Chrome CDP + Vite + mock daemon 全场景通过，报告目录 `ignored/visual-qa/screenshots/1781445731835-42212`，覆盖同上 7 组截图级场景且命令退出码为 0。该 QA harness 位于 ignored 临时目录，不提交截图或 mock 数据。
- 2026-06-14 验收追加：本轮状态 contract 修复后已跑 `npm run build --prefix lilsunspot/desktop`、focused pytest 65 passed、`python scripts/guard_no_secrets.py`、`git diff --check`（仅 CRLF warning）、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`（daemon 114 passed + secret guard + desktop build）和 `npm run tauri:build --prefix lilsunspot/desktop`。NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 55,806,446 bytes，时间 2026-06-14 22:07:57 +08:00。

## Next

1. LIL-WEIXIN-FILE-FORMAT-HARDENING：修复并复验生成文件真实格式。2026-06-20 安装版真实微信现场已验证：文本回合通过、TXT 文件生成并发回微信通过、微信图片入站识别通过、图片按请求发回微信通过；但“表格文件”请求生成的 `.xlsx` 实际只有 24 bytes，内容是 UTF-8 文本 `文件传输测试通过`，不是合法 Excel/OpenXML 文件。后续应先修复：普通“表格”默认生成 `.csv`，明确要求 Excel 时生成真实 `.xlsx`；`.xlsx/.docx/.pdf` 必须做格式签名/打开校验，不能把纯文本伪装成 Office/PDF 后交付。2026-06-22 代码侧已增加交付工具、delivery action、同路微信发送和审批发送前的真实格式校验：普通表格提示默认 `.csv`，`.xlsx`/`.docx` 由文本生成真实 Office 包，纯文本 `.pdf` 被拒绝，伪 `.xlsx/.docx/.pdf` 不会注册或发送；仍需重建安装版后做真实微信 CSV/XLSX/DOCX/PDF 现场复验。
2. LIL-HERMES-FULL-01-INSTALL-QA：继续安装版全链路人工验收。已覆盖 `Lilsunspot.exe -> lilsunspotd -> Hermes runtime -> Weixin text/file/image` 的部分主链路；待补 `/capabilities` 页面、能力中心/附件卡在 960x680 和 390x760 下无重叠或横向溢出、PDF/docx/xlsx/csv 真实格式、生成文件经审批发回微信、关窗进托盘、托盘打开、托盘退出。
3. LIL-WEIXIN-SINGLE-ACCOUNT-SCOPE：初版收缩微信多账号范围。2026-06-21 安装版最新对话脱敏检查发现，新微信账号登录后仍可能沿用过去会话/Hermes session/记忆上下文；本地数据也可能同时残留多个 Weixin account credential/sync 文件。多账号隔离要同时处理账号凭据、route、conversation、Hermes session、Mode 和记忆，风险高于当前主线。初版应暂时取消“多微信账户”能力承诺，只支持一个当前微信账号；切换账号必须要求显式断开/重置账号绑定会话与记忆，或给出清晰中文风险提示，不能静默复用旧记忆。
4. LIL-MEMORY-RESET-TRUTHFULNESS：记忆删除和本地清空必须可信。2026-06-21 最新对话与截图显示，用户要求删除指定主题记忆后，assistant 先承诺已彻底清空，又在追问本地清空时暴露 `memory`、`read_file/search_files`、`ripgrep` 等内部工具/实现名，并给出“工具不存在/无法通过文件系统验证/0 entries”等不可靠解释。后续应把“产品本地记忆、Hermes agent memory、会话历史、微信 route/session 上下文”分层展示和清理；删除前后返回可验证的中文结果；无法验证时明确说不能确认，不能伪造已删除或暴露内部工具名。实现约束：安装包/sidecar 构建时应随产品提供本地搜索依赖（例如 `ripgrep`/`rg`），并在 release/smoke 检查里确认安装版可用，避免再让模型因为缺少搜索工具而猜测；但真实删除仍必须通过结构化记忆/会话清理 API 执行，不能只靠 grep 搜索结果当作删除动作。
5. LIL-WEIXIN-MEDIA-STABILITY-QA：微信 live 稳定性复验。重点覆盖扫码误操作、二维码过期、断线重连、同一微信账号下多个联系人/route、删除当前微信对话后的下一条入站、微信端自然语言切换会话、大文件/多文件、以及安装版 runtime 断线后的恢复状态。
6. LIL-CREDENTIAL-CAPABILITY-QA：外部账号/凭据依赖能力验收。用安全测试凭据验证 MCP server、browser、x_search、image/video/tts、Home Assistant、Spotify、Discord/Yuanbao 等能力从“需配置”到“可用/失败原因”的状态闭环；不得记录任何 secret、私聊正文、附件内容或二维码。
7. LIL-UPSTREAM-SYNC-REMOTE-QA：GitHub Actions 首次远程验收。手动触发 `lilsunspot-upstream-sync.yml` 的 `workflow_dispatch`，确认 upstream 变更时能创建草稿 PR，冲突时能创建 issue，PR 检查和能力覆盖测试按预期执行。
8. LIL-RELEASE-CANDIDATE-HARDENING：发布候选收口。跑 `scripts/check_release.ps1`、安装版 smoke、真实 provider smoke、secret guard、NSIS 产物确认，并整理最终已知风险；必要时补一个“普通用户验收清单”。

## Blocked / Unknown

- 2026-06-13：定向 live smoke 已跑到“DeepSeek 文本主模型 -> Qwen 辅助视觉”真实链路，但本机 DashScope Key 被服务端归类为 `invalid_key`，所以真实 `recognized` 成功仍需一个有效视觉 Key 复验；mock pytest 已覆盖辅助视觉成功闭环和脱敏错误分类。
- 真实外部账号能力仍依赖安全测试凭据；没有凭据时只能验配置状态、脱敏和失败原因。
- 真实微信扫码、二维码过期、断线重连和同账号多联系人 route 仍需要 live 微信环境人工复验，自动测试只能覆盖 fake runtime 和产品层状态机。
- 2026-06-21：多微信账号暂不应作为初版功能。最新对话脱敏检查显示，新账号登录后仍可能沿用旧会话/Hermes session/记忆上下文；在账号级隔离完成前，多账号切换属于高风险未知项，应先收缩为单微信账号体验。
- 2026-06-21：记忆删除/本地清空目前不能作为可信能力对外承诺。最新对话显示 assistant 会把内部工具名和错误环境假设暴露给用户，并在没有完整验证边界时承诺“已清空”；后续必须先补真实清理路径和可验证结果。
- 2026-06-20 安装版真实微信现场验收确认传输链路可用，但生成 Office/PDF 真实格式尚未闭环；当前发现 `.xlsx` 可被发送到手机，但文件实际是纯文本伪装，属于产品生成/格式校验问题，不是微信传输失败。
- Browser IAB、CodeRabbit 等外部工具在本机不总是可用；截图级 UI 和外部 review 需要在工具可用时补跑，或采用本地 headless/CDP/manual 兜底。
- 视觉模型推荐、价格和可用模型会随服务商变化；后续实现只能跳转官方页面并复用 Hermes/model metadata 判断能力，不应在产品层写死 provider 名或价格承诺。

## Done

- 2026-07-25：完成 `LIL-HERMES-TERMINAL-01`。小黑子默认启用 Hermes 原生 `terminal` toolset，实际工具为官方 `terminal/process`，危险命令仍由 Hermes `tools.approval` 和既有 gateway approval bridge 处理；没有新增产品层 shell 或审批绕过。定向 capability/approval 17 passed，全量 daemon 151 passed，secret guard、桌面构建和 NSIS 重建通过。新安装版能力接口显示终端已启用且来源为 `hermes_toolset`；DeepSeek V4 Flash 经 `hermes_agent_loop` 执行只读终端命令成功、退出码 0、工具迭代 5 次，未产生待审批残留。最终 setup.exe 为 56,742,464 bytes，时间 2026-07-25 21:44:37 +08:00，已覆盖安装。
- 2026-07-25：完成 `LIL-GENERATION-CONTROL-01`。五种生成模式通过独立 resolver 真实控制 sampling、输出、推理和 Agent 迭代预算；全局、会话、单轮按字段覆盖，桌面与微信复用同一规则；不支持/锁定字段省略，Provider 明确拒参时只安全降级重试一次；旧“务实 / 均衡 / 感性”仅保留表达风格。桌面提供基础/高级设置和回复生成详情，并按用户要求把新增说明文字改为亮白/青色高对比度，不使用灰色说明字。验证：daemon 150 passed、secret guard、TypeScript/Vite build、最终 NSIS build、云端 DeepSeek 与本地 Ollama `llama3.2:1b` 安装版真实聊天均通过；最终安装包 56,766,639 bytes，已覆盖安装到当前用户目录并恢复原 Provider 配置。详细证据见 `docs/VALIDATION.md` 和执行计划。
- 2026-07-25 收尾：按用户授权删除本轮下载的 Ollama `llama3.2:1b`、`qwen2.5:0.5b`，未删除原有 `deepseek-r1:1.5b`；安装版从已失效的 `deepseek-chat` 切换为 `deepseek-v4-flash`，真实 `/chat/send` 经 `hermes_agent_loop` 回复成功，避免用户后续默认配置不可用。
- 2026-07-25 安装包修复：此前只修改当前用户运行配置，没有改掉 `provider_registry.yaml` 中的 `deepseek-chat` 默认值，导致重置/新安装仍不可用。本轮将产品默认改为 `deepseek-v4-flash`，补资源回归测试，完成 daemon 150 passed、`scripts/check.ps1`、NSIS 重建和当前用户覆盖安装。新安装版 `/providers` 已返回 V4 Flash 默认值；从本轮本机备份安全恢复 Key 后，连接测试、保存、`chat_ready` 与真实 Hermes Agent 回复全部通过。最终 setup.exe 为 56,768,504 bytes，时间 2026-07-25 21:17:10 +08:00。

以下为历史任务记录，是否完全代表当前主线状态需以当前 Current / Next / Blocked / Unknown 为准。

### Completed 2026-07-17

- LIL-MACOS-DMG-01：在保持 Windows NSIS、PowerShell 构建、installer hooks、release workflow 和 Hermes core 不变的前提下，完成 macOS 15+ arm64/x86_64 私用 DMG。GitHub Actions run `29576626648` 的两个 Mac 安装后 smoke 与 Windows regression 全部通过；DMG Artifact 已下载到 `ignored/macos-artifacts/run-29576626648/` 并完成 SHA-256 复核。真实 Mac 微信扫码/收发、真实模型服务、Finder 交互和托盘点击仍属于后续人工验收。

### Moved From Current 2026-06-12

- LIL-VISION-ONBOARDING-01：模型选择/更换后的视觉能力引导。
  - 2026-06-12：保存主聊天模型后复用 `/providers/capabilities` 与 Hermes `image_routing` 判断图片能力；主模型不能直接看图且未配置 `auxiliary.vision` 时，在进入聊天前提示“当前模型不能直接识别图片”，提供“继续使用文字聊天”和“添加图片识别模型”两条路径。图片识别模型配置共用 Hermes `auxiliary.vision`，配置和 API 响应均脱敏，不按 DeepSeek/Kimi 等 provider 名硬编码判断。
  - 2026-06-12：按用户误触补验：重复点击继续文字聊天不会重复推进；未选择图片识别服务直接保存会显示中文错误且不写空配置；选择云端视觉服务但缺 API Key 会显示中文错误且不泄漏 secret；移动端 390x760 首屏能看到错误反馈，无横向溢出。
  - 验证已跑：focused capabilities/product pytest 12 passed、daemon pytest 98 passed、product pytest 38 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`、`git diff --check`、本地 Chrome/CDP 视觉验收覆盖 960x680 和 390x760、`npm run tauri:build --prefix lilsunspot/desktop`；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 55,772,121 bytes，时间 2026-06-12 23:57:55 +08:00。
  - 未覆盖：未用真实视觉 provider API Key 发起实际识图调用，未把最新 NSIS 覆盖安装到 `%LOCALAPPDATA%\Lilsunspot` 做实机点击验收；视觉截图和 mock daemon 数据只保存在 ignored 临时目录，未提交。

- LIL-HERMES-FULL-01：Hermes 本地全能力一体化接入。
  - 2026-06-12：新增小黑子能力中心后端 registry，按本地 Hermes `TOOLSETS`、`CONFIGURABLE_TOOLSETS`、`DEFAULT_CONFIG`、provider/runtime 状态生成能力清单；能力可发现、可测试，官方可配置 toolset 能写入 `platform_toolsets.lilsunspot`，非普通配置 toolset 也在能力中心显示状态/风险/依赖。默认 agent loop 显式读取 lilsunspot toolsets 和 fallback chain，避免未配置时暴露过宽工具面。
  - 2026-06-12：新增模型配置桥 `/models/runtime`、`/models/fallbacks`、`/models/routing`、`/models/auxiliary`，新增 `/tools/platform/lilsunspot`、`/mcp/servers` CRUD，配置写入 Hermes `config.yaml`，响应脱敏。
  - 2026-06-12：新增 `audit.db`、`/safety/audit` 和诊断包导出 `/doctor/diagnostics/export`；安全审批核心路径写审计，诊断包包含能力状态、Doctor、Hermes compat、模型运行态、审计摘要和配置形状，不包含 API Key、runtime token、微信凭据、私聊正文或附件原文。
  - 2026-06-12：审计、审批详情、公开 MCP/模型配置视图统一脱敏敏感字段和命令行参数形态（如 `--token value`、`Authorization: Bearer ...`、URL token 参数）；真实配置仍可写入 Hermes config，但 API/诊断/审计不回显 secret。
  - 2026-06-12：桌面设置新增“能力”页，诊断页接入脱敏诊断包导出，安全页展示最近审计；新增 GitHub Action `lilsunspot-upstream-sync.yml`，定时/手动检测官方 upstream，创建草稿 PR，不自动合并，并在 PR 模板加入 lilsunspot 产品边界检查。
  - 2026-06-12 截图级前端复验：Browser IAB 覆盖 960x680 和 390x760 的能力中心、能力检查、诊断导出、安全审计；修复能力 payload 缺少 `dependencies/source` 时的崩溃和重复 key 警告，开发调试面板不再遮挡正常验收视图，移动能力卡操作按钮改为下排布局。
  - 验证已跑：focused capabilities/safety pytest 9 passed、daemon pytest 67 passed、product pytest 35 passed、Browser IAB 当前轮 console 0 error/warn 且 960x680/390x760 无横向溢出、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check`、`pwsh -NoProfile -File scripts/build_lilsunspotd_sidecar.ps1`、`npm run tauri:build --prefix lilsunspot/desktop`；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 62,262,130 bytes，时间 2026-06-12 15:06:21 +08:00。

- LIL-P2-02 + LIL-P2-03：微信私聊同步、文件附件、自然语言模式 UX 合并交付。
  - 2026-06-09：新增 lilsunspot SQLite 会话库、事件表、附件表和审批动作表；`/conversations`、`/conversations/{id}/messages`、`/events/stream`、`/attachments/{id}` 全部继续要求 `X-Lilsunspot-Token`，`/chat/send` 兼容路径改为写入稳定 `personal` 会话。
  - 2026-06-09：微信 `MessageEvent(media_urls/media_types)` 入站后登记附件、复制到 `data_dir/attachments/YYYYMM`、生成图片/PDF/txt/md/csv/docx/xlsx 摘要或中文不可读原因，并把附件摘要拼入 AI 回复 prompt；附件来源只允许 `data_dir/attachments` 和 Hermes 媒体缓存目录，不允许 Weixin credential 目录。
  - 2026-06-09：桌面端聊天改为会话数据源，启动加载最近消息并通过 Tauri `subscribe_events` 接收 daemon SSE；Tauri 用 header token 连接 `/events/stream`，token 不进入 URL/前端 state，并新增受控 `open_attachment`。Tauri core 增加托盘：关窗隐藏到后台，“打开小黑子”恢复窗口，“退出”真实退出。
  - 2026-06-09：微信模式入口支持普通自然语言：务实/平衡/温柔、详细/简短、主动/谨慎和当前风格查询；未知 slash command 返回中文提示，`/help`、`/mode` 保留为隐藏高级兼容路径。mode 变化落库为 system message 并广播 `mode.changed`。
  - 2026-06-09：主动微信发送仍走安全审批；审批通过后才调用 Weixin adapter 的 `send`、`send_document` 或 `send_image_file`，拒绝不会发送。
  - 2026-06-09 收尾复核：修复 CSV 被通用 `text/*` 提前解析的问题；SSE 等待改为跨线程 condition，避免非当前 asyncio loop 落库事件只能等 keepalive；Tauri SSE 重连会重新发现 endpoint 并在 401/403 后重读 token。
  - 验证已跑：focused conversation/media/mode/approval pytest 5 passed、daemon pytest 38 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check`、`npm run tauri:build --prefix lilsunspot/desktop`、临时目录安装版 smoke 通过；NSIS 产物为 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-09：中断续跑收尾复核并补小修复：Weixin runtime 文本入站统一走事件入口，保留真实 `message_id`；审批通过发送微信文件前先验证所有附件存在且位于安全附件目录，避免文本已发送但附件失败的半完成状态。新增对应回归测试，更新 runtime fake event 测试入口。验证：focused conversation/safety pytest 11 passed、daemon pytest 40 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`pwsh -NoProfile -File scripts/build_lilsunspotd_sidecar.ps1`、`npm run tauri:build --prefix lilsunspot/desktop`、临时目录安装版 smoke 通过；NSIS 产物已确认存在。
  - 2026-06-09：按“小白用户误点”视角修复微信扫码页卡顿体感：刷新请求进行中再次点击会排队一次并在二维码说明区给反馈；断开按钮不再被慢刷新禁用，二次确认后可抢占旧刷新；后端扫码登录增加 generation，断开或新刷新后旧的 `/login/start` / `/login/status` 慢响应不能重新写回扫码会话。顺手修复会话消息列表按随机 id 排序导致同一时间戳消息偶发倒序的问题，改为 SQLite 写入顺序。验证：focused Weixin pytest 8 passed、daemon pytest 41 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop`；最新 setup.exe 已覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`，随后 `scripts/smoke_lilsunspot_installed_app.ps1 -SkipInstall -InstallDir %LOCALAPPDATA%\Lilsunspot` 通过。
  - 2026-06-09：继续修复 Mode 同步、图片识别状态和微信附件基础链路。桌面新增统一 ModeProvider/useModeState，顶部状态、聊天右栏、模式页和设置抽屉共用同一份 mode state 并监听 `mode.changed`；图片附件区分 `preview_only` 和 `recognized`，支持 `image_url` 的 OpenAI/Qwen-VL 类模型可写入视觉摘要，DeepSeek 文本模型明确显示只能预览不能识别；微信私聊消息 metadata 记录脱敏 `chat_id/user_id` 路由；显式 `/gateway/weixin/send` 可携带安全 attachment ids 创建 `send_weixin_message` 审批，不直接发送；聊天右侧安全摘要增加进入审批的按钮。
  - 验证新增已跑：focused conversation/media/mode/approval pytest 10 passed、daemon pytest 46 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check`、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。Browser IAB 打开 Vite dev UI 后，默认桌面截图和 390x844 移动截图显示基础壳正常渲染。
  - 未覆盖：Browser IAB 精确 960x680/390x760 批量截图调用超时，后续 viewport reset 调用也超时；CodeRabbit CLI 未安装，按插件技能通过 `bash -lc "curl -fsSL https://cli.coderabbit.ai/install.sh | sh"` 安装时 124 秒超时，未取得 CodeRabbit review 结果；真实微信发图片/PDF/docx/xlsx/csv 后桌面实时显示、审批后发回微信文件、关窗托盘/托盘打开/托盘退出仍需人工安装版验收。`cargo fmt --check` 未运行，因为本机 Rust toolchain 缺少 `rustfmt` 组件。
  - 2026-06-10：新增 Hermes 官方接口兼容审计边界：`hermes_compat` 记录 provider、Weixin、attachment、mode、safety、doctor/runtime 的官方接口来源和产品层包装理由；Doctor 和 `/runtime/info` 暴露 Hermes 版本、upstream commit 与关键接口探测。显式微信发送仍创建 `send_weixin_message` 审批，审批通过后调用官方 `WeixinAdapter` / `BasePlatformAdapter` 的 `send()`、`send_image_file()`、`send_document()`；不安全附件路径和未连接微信都不会发送。验证：focused Hermes compat pytest 5 passed、focused approval/send pytest 5 passed、daemon pytest 56 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-10：按用户截图修复模式/对话真实状态错位。自然语言切换到目标 mode 时不再继承上一模式 sliders，而是写入目标 profile 默认值，避免后端 `current=balanced` 但 UI 仍显示感性滑杆；桌面 `/chat/send` 语义模式响应带回最新 mode，前端在收到 `mode_intent` 后主动重载共享 mode state，降低 SSE/Tauri 事件漏收时右侧展示条不同步的风险。Mode 面板三条滑杆标签从错误的“唱/RAP/篮球”修正为“风格/表达、长度/细节、确认/自主”。用户指出文件/附件判断不应混入产品层文本拦截后，已删除桌面和微信普通聊天路径上的附件能力/发送文件关键词拦截；mode 层只做 LLM 语义判断是否调整参数，未命中 mode 的消息回到正常聊天。验证：focused conversation/hermes compat pytest 6 passed、daemon pytest 57 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、旧拦截符号扫描、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-10：按“预设 + 自定义”重做 mode 边界。`default_mode_profiles.yaml` 仅保留 `pragmatic/balanced/emotional/custom` 四个模式，`balanced` 是默认；固定预设不再保存任意 sliders，API 或旧状态里出现“固定预设 + 非预设滑杆”会读取/保存为 `custom`，自然语言 slider 调整也落到 `custom`。桌面端删除左侧 `MD 模式` 页面、设置抽屉输出模式 tab 和 `ModeSettings.tsx`，聊天右侧改为四个模式按钮、滑杆、实时预览卡，移除原安全审批 mini panel 和 runtime line。验证：focused mode/conversation pytest 29 passed、daemon pytest 58 passed、product pytest 35 passed、`npm run build --prefix lilsunspot/desktop`、headless Chrome/CDP mock Tauri 截图检查四模式/无 MD/无安全 mini panel/无横向溢出、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-10：落实“微信连接 != 当前桌面对话”的多对话边界。普通桌面“新建”只创建桌面对话，不抢微信入站 route；微信私聊按 active Weixin conversation 落库，只有“新开此微信对话”或“设为当前”会切换同一微信 route 的入站落点；Weixin route key 增加 `account_id` 维度，兼容旧的无账号 route，真实 runtime handler 会把当前 adapter account id 注入事件 metadata。验证：focused conversation pytest 22 passed、daemon pytest 63 passed、product pytest 35 passed、`npm run build --prefix lilsunspot/desktop`、`py -3 scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 62,214,241 bytes，时间 2026-06-10 14:34:45 +08:00。
  - 2026-06-10：修复安装版会话管理代理并收敛小白 UI。Tauri `daemon_request` 放行 `PATCH`/`DELETE` 并新增本地 TCP 单测确认请求行、JSON body 和 `X-Lilsunspot-Token` header；FastAPI CORS 同步放行 `PATCH`/`DELETE`。普通用户主导航和设置抽屉只保留“聊天/微信”和“模型服务/微信”，首启/阻塞态、微信页、模式预览不再展示审批或诊断承诺；`/gateway/weixin/commands` 和 `/help` 不再展示 `/approve`/`/reject`，但 `/safety/*`、`/doctor/*` 和隐藏审批处理路径保留为后台安全边界。验证：focused conversation/safety/api pytest 6 passed、daemon pytest 63 passed、product pytest 35 passed、Tauri `http_request_allows_*` 2 passed、`cargo test --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`npm run build --prefix lilsunspot/desktop`、`py -3 scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、Browser 打开 Vite 页确认主导航/设置抽屉无“审批/诊断”且无 console error、`npm run tauri:build --prefix lilsunspot/desktop`、临时安装目录 smoke 通过；NSIS 产物为 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 62,212,374 bytes，时间 2026-06-10 18:52:01 +08:00。未覆盖：Browser 安全策略拒绝 `data:` mock 页面，未完成 chat_ready 会话按钮的渲染级 mock；真实微信扫码、真实外部模型调用和当前用户安装目录覆盖安装仍需人工验收。
  - 2026-06-10：经用户同意后把最新 NSIS 覆盖安装到当前用户目录 `%LOCALAPPDATA%\Lilsunspot`。安装后 `Lilsunspot.exe` 时间为 2026-06-10 18:51:12 +08:00，`lilsunspotd.exe` 时间为 2026-06-10 18:50:16 +08:00；随后使用隔离数据目录复测当前用户安装版：`scripts/smoke_lilsunspot_installed_app.ps1 -SkipInstall -InstallDir %LOCALAPPDATA%\Lilsunspot` 通过；额外安装版 CRUD smoke 通过 `POST /conversations`、`PATCH` 改名/归档/恢复、`DELETE` 删除，确认 `/gateway/weixin/commands` 不展示 `/approve`/`/reject`，且 `/safety/policy` 无 token 返回 403。复测未输出 runtime token 或 API Key。
  - 2026-06-10：按用户要求直接用当前安装版和默认数据目录继续人工协作测试，不再用隔离 mock 数据。安装版 `127.0.0.1:8765`、`/health`、受保护 `/providers` 通过；真实默认数据目录里临时会话 CRUD 通过并删除测试会话；临时 Weixin route 的“设为当前”后端路径通过；真实微信扫码最终连接成功，文字私聊入站和回复成功，自然语言“务实切换/更理性一点的模式”成功切到 `pragmatic` 并写入 `mode_intent`；真实图片入站为 `preview_only` 且本地预览/原因存在；真实 PDF 和 DOCX 入站为 `ready` 且摘要存在；桌面 `personal` 会话真实 provider 路径通过，`hermes_agent_loop` 调用 `deepseek/deepseek-chat` 并落库；安装版日志检查未发现 runtime token。用户要求文件测试跳过后，未继续测 xlsx/csv。待统一分析问题：扫码后 UI 曾短暂显示“出错”，API 一度为 `status=error/login_status=error` 且提示“微信扫码状态读取失败，请稍后再试”，随后轮询恢复 `connected`；扫码期间和后续观察到同安装目录下两个 `lilsunspotd.exe` 进程，端口监听由后启动进程持有，可能导致状态不稳定。本轮按用户要求仅记录问题，不做代码修复。
  - 2026-06-10：继续用当前安装版测试微信端新对话和会话管理。基于真实 active 微信 route 创建“Codex 新微信对话测试”会话后，新会话成为当前、旧会话失活；用户从微信发送“新对话路由测试”后，消息落到新会话，旧会话未新增该消息。随后对测试会话执行归档、默认列表隐藏、显示归档可见、恢复、旧会话设为当前、删除测试会话，最终恢复为原“微信私聊”会话 active。新增待统一分析问题：新会话收到微信入站消息后 8 秒内未看到 assistant 回复，`last_reply_at` 当时仍停在上一轮；清理期间 `last_reply_at` 后续更新，可能存在新会话回复延迟或删除竞态。本轮继续只记录问题，不做代码修复。
  - 2026-06-10：微信端切换本地对话方案记录。Hermes Weixin 和 OpenClaw Weixin 公开能力边界更适合“微信聊天内容里的交互”，不能假设可改微信客户端原生 UI 或增加真正多线程选择器。后续推荐保留本地 active route 机制，在微信端增加自然语言和编号菜单：如“切回上一个对话 / 新开一个对话 / 切到项目总结那个对话”，或回复最近 5 个微信会话编号选择；切换后明确回复“已切到：xxx，之后微信消息会进入这个对话”。桌面端同步把“设为当前”改成“让微信消息进入这个对话”，并在微信页/聊天页显式显示“微信消息现在进入：xxx”。实现前应先修复新会话入站后回复延迟/删除竞态和双 daemon 进程问题。
  - 2026-06-10：补测小黑子主动发文件回微信。使用当前安装版默认数据目录中已入站且位于安全附件目录的 DOCX 附件，通过 `/gateway/weixin/send` 创建 `send_weixin_message` 审批；审批未绕过，返回 `approval_required=true`。随后批准该审批，安装版 runtime 返回 `delivery.ok=true`、`sent_text=true`、`sent_files=1`、pending 审批数为 0；用户在微信端确认已收到测试文本和 DOCX 文件。日志复查未发现 runtime token。该链路通过。
  - 2026-06-10：落实微信稳定性与产品入口修复方案。daemon 启动器增加 data dir 文件锁，Tauri `connect_daemon` 增加同进程防重入；扫码 poll 短暂异常不再写 `error`，已连接状态优先清理陈旧扫码会话；微信入站先落 assistant `generating` 占位并通过 `message.updated` 更新，删除会话后不复活、不发送延迟回复；微信端新增“新开一个对话 / 切回上一个对话 / 切换对话 + 编号”本地 route 切换；桌面对话文案改为“微信消息进入这里”，附件卡新增“发到微信”确认入口，仍走 `/gateway/weixin/send` + `/safety/approvals/{id}/decide` 审批链路。验证已跑：focused runtime/weixin/conversation pytest 42 passed、daemon pytest 70 passed、product pytest 35 passed、`npm run build --prefix lilsunspot/desktop`、`cargo test --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` 退出码 0（末尾有 ignored venv pytest 噪声）、`git diff --check` 仅 LF/CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop`；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 62,244,279 bytes，时间 2026-06-10 21:29:53 +08:00。未覆盖：真实扫码、真实微信自然语言切换、删除竞态、附件发回微信和安装版双进程仍需人工复验。
  - 2026-06-10：落实短消息合并与桌面假报错修复。新增产品层 `turn_coalescer`，普通桌面/微信文本按 conversation + source/route_key 以 3 秒静默窗口、8 条、4000 字上限合并；同一 key 串行运行 Hermes turn，运行中新增文本进入下一批；桌面 `/conversations/{id}/messages` 改为快速返回 `accepted=true`、`turn_id`、user message 和 assistant `generating` 占位，最终通过 `message.updated` 更新；微信普通文本同 route 只由 owner 等待并发送一次回复，切换对话、mode、审批和附件继续即时处理不进合并器；删除会话后后台完成静默取消，不复活会话。前端识别 `accepted`，不再把等待模型完成渲染成最终失败气泡；mode router 候选收窄，避免“调试/详细解释/写文案”等普通聊天先被 8 秒 router 阻塞。验证已跑：focused conversation pytest 29 passed、daemon pytest 74 passed、product pytest 35 passed、`npm run build --prefix lilsunspot/desktop`、`cargo test --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`、`git diff --check` 仅 LF/CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop`。本轮按用户要求只更新仓库内 NSIS 产物，未运行安装器、未覆盖 `%LOCALAPPDATA%\Lilsunspot`、未启动真实微信扫码；新 setup.exe：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 62,252,884 bytes，时间 2026-06-10 22:58:06 +08:00。
  - 2026-06-11：修复桌面显示“微信消息进入这里”后真实微信仍可能进入旧对话的问题。原因不是微信客户端机制，而是产品层 route 兼容：旧安装数据可能保存无 `account_id` 的 `weixin_route_key`，真实 runtime 入站会带账号维度，导致桌面激活和入站查找使用不同 key。现在激活旧微信对话时会在可唯一确定账号的情况下升级为带账号 route，并同时停用同联系人旧/新 key 下的其他 active 对话；若坏状态已存在，下一条真实入站也会迁移到刚激活的对话。新增旧 route 激活和入站自修复回归测试。同步参考 Hermes 现有 `web/` Dashboard 与 `ui-tui/`/`tui_gateway/`：可借鉴会话搜索、日志/状态摘要、模型能力提示和审批/澄清交互；不建议直接搬入普通用户版的 Config/Env/Cron/Skills/Profiles/PTY Chat 全量控制台。验证已跑：focused route pytest 5 passed、conversation sync pytest 31 passed、daemon pytest 76 passed、product pytest 35 passed、`npm run build --prefix lilsunspot/desktop`、`py -3 scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`、`git diff --check` 仅 LF/CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop`；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 62,256,372 bytes，时间 2026-06-11 12:56:47 +08:00。未覆盖：未覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`，未用真实微信复测桌面点击后的下一条入站。
  - 2026-06-11：追加用户误用/脏数据自测。新增回归覆盖：对普通桌面对话误 PATCH `weixin_route_active=true` 会返回中文 404 且不写入微信 metadata；同一联系人存在多个微信账号 route 时，桌面激活旧无账号对话不会随便挑账号，等真实入站后只迁移到该入站账号且保留另一个账号的 active 对话；微信端“切换对话”后输入不存在编号会返回中文错误且不切换；用户删除当前微信 active 对话后，下一条入站会创建新微信对话，不复活已删会话。验证：focused misuse pytest 7 passed、conversation sync pytest 35 passed、daemon pytest 80 passed、product pytest 35 passed、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`、`git diff --check` 仅 LF/CRLF warnings。未发现需要追加产品代码修复的问题；本轮只扩展自动测试和记忆记录。
  - 2026-06-11：执行 Hermes 能力合并计划 Phase 0。新增 `lilsunspot/notes/hermes-feature-inventory.md` 和 `lilsunspot/notes/hermes-merge-plan.md`，把当前仓库已有 Hermes Dashboard/TUI/gateway/tools/cron/memory/provider 能力按“直接复用 / 包装后复用 / 暂不开放”分类，并明确小黑子只通过产品层 adapter/API wrapper 合并，不直接把上游控制台搬给普通用户。新增只读 `scripts/hermes_upstream_check.ps1` 作为未来官方更新同步入口，默认不联网、不建分支、不 merge，只读取 `lilsunspot/UPSTREAM_COMMIT.txt` 和本地 `upstream/main` 生成分类报告；本地运行生成 `lilsunspot/notes/upstream-sync-reports/2026-06-11-203215.md`，显示当前缓存的 `upstream/main` 相对记录 base 有 650 commits、1757 changed files，工作树非干净所以后续 sync 不应执行。验证：PowerShell parser ok、`python -m pytest lilsunspot/tests/test_hermes_upstream_check_script.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot-upstream-script` 3 passed、只读 upstream check 生成报告、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` 通过（daemon 80 passed、secret guard、desktop build）。
  - 2026-06-11：按合并计划把 Phase 1-7 一并落到最小产品版。新增产品层 `product_features` SQLite 表和受 token 保护 API：`/diagnostics/summary`、`/providers/capabilities`、`/conversations/search`、`/reminders`、`/memory`、`/capabilities`、`/upstream/status`；桌面设置抽屉新增“控制台”，集中展示诊断摘要、模型能力、提醒、记忆、能力开关和 upstream 检查报告；聊天左栏新增会话/附件搜索。微信 route 选择继续修复旧无账号 route 与带账号 route 并存时的落点。提醒、记忆和能力开关本轮是可见/可管理的本地最小版本，尚未做完整调度执行、prompt 记忆注入或跨工具强制拦截；复核时修正 upstream 报告 changed files 统计为解析分类表求和。验证：focused product features pytest 5 passed、conversation sync pytest 35 passed、daemon pytest 85 passed、product pytest 38 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`、`git diff --check` 仅 LF/CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop`；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 62,276,286 bytes，时间 2026-06-11 20:57:08 +08:00。未覆盖：当前已安装 daemon 占用 `127.0.0.1:8765` 且避免截图真实 token/数据，本轮未做 Browser 真实渲染级控制台验收，也未覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`。
  - 2026-06-11：复测当前 UI 接入和 mode 影响。结论：Hermes 上游仓库内确实存在 dashboard、TUI、tools、cron、memory 等能力，但并非都适合或已经完成普通用户产品化；小黑子当前 UI 已能接入本轮落地的本地产品层 API，仍不等同于接入所有 Hermes 官方未合并/未产品化能力。验证：`python -m pytest lilsunspot/daemon/tests/test_product_features.py lilsunspot/daemon/tests/test_conversation_sync.py lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-ui-mode-check` 47 passed；`python -m pytest lilsunspot/tests/test_chat_api.py lilsunspot/daemon/tests/test_api_skeleton.py lilsunspot/daemon/tests/test_conversation_sync.py -k "mode or modes or mode_intent or semantic or slider" --timeout-method=thread --basetemp .tmp-pytest-mode-check` 11 passed；`npm run build --prefix lilsunspot/desktop` 通过。Mode 未发现受控制台/搜索/提醒/记忆改动影响。未覆盖：普通浏览器 dev 模式需要调试 token，正式 Tauri 版才自动代理 token；本轮未把真实安装版 token 输入 Browser 做截图级 UI 点击验收。
  - 2026-06-11：按用户要求用最新 NSIS 直接覆盖当前用户本地安装 `%LOCALAPPDATA%\Lilsunspot` 并打开真实本地 App。覆盖前结束旧 `Lilsunspot/lilsunspotd` 进程，安装后确认 `Lilsunspot.exe` 时间 2026-06-11 20:56:40 +08:00、`lilsunspotd.exe` 时间 2026-06-11 20:56:08 +08:00；随后可见启动安装版，窗口进程 `Responding=True`，本地服务 `/health` 通过，受保护 `/app/bootstrap` 返回 `chat_ready`，`/modes/current` 返回 `pragmatic`，`/diagnostics/summary` 和 `/providers/capabilities` 可用，`/conversations/search` 空查询 smoke 正常返回 0 条。观察到安装版仍显示 2 个 `lilsunspotd.exe` 进程，但它们是父子关系，runtime discovery 和端口监听均指向子进程 pid，当前未发现双服务抢占端口；未输出 runtime token 或 API Key。
  - 2026-06-11：确认并改进安装版 `lilsunspotd.exe` 双进程观感。结论：2 个 sidecar 不是两个 daemon 争抢端口，而是 PyInstaller onefile 父进程 + 实际服务子进程；只有 runtime pid 监听 `127.0.0.1:8765`。新增 runtime process metadata：runtime descriptor、`/runtime/info`、`/diagnostics/summary` 和桌面控制台诊断摘要会显示 `process_model=pyinstaller_onefile_parent_child`、pid、parent pid 和中文说明，避免后续把打包父子进程误判为双服务。验证：focused runtime/product pytest 10 passed、`npm run build --prefix lilsunspot/desktop`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`（daemon 85 passed、secret guard、desktop build）、`npm run tauri:build --prefix lilsunspot/desktop`；NSIS 产物 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe` 大小 62,279,286 bytes，时间 2026-06-11 21:32:13 +08:00。已覆盖安装到 `%LOCALAPPDATA%\Lilsunspot` 并打开：`/health` 通过，runtime pid 与 8765 listening pid 一致，`/app/bootstrap=chat_ready`、`/modes/current=pragmatic`、诊断 process note 存在；未输出 runtime token 或 API Key。
  - 2026-06-11：按用户“不需要两个”继续改进 sidecar 交付。将 `scripts/build_lilsunspotd_sidecar.ps1` 从 PyInstaller `--onefile` 改为 `--onedir`，Tauri 不再用 `externalBin` 单 exe，而是通过 bundle resources 安装 `binaries/lilsunspotd/` 目录；启动候选优先使用 onedir sidecar，NSIS postinstall 删除旧版根目录 `lilsunspotd.exe` / `lilsunspotd-x86_64-pc-windows-msvc.exe` 残留；安装 smoke 脚本同步按 onedir/legacy 路径查找 sidecar。runtime process metadata 现在区分 `pyinstaller_onedir_single_process` 和旧 onefile 父子模型；secret guard 精确排除 PyInstaller 生成的 `_internal` 第三方运行时目录，避免 botocore 示例假阳性。验证：focused runtime/product/smoke pytest 14 passed、Rust Tauri 单测 2 passed、focused guard/smoke pytest 6 passed、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` 通过（daemon 85 passed、secret guard、desktop build）、`npm run tauri:build --prefix lilsunspot/desktop` 通过。新 NSIS：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 55,719,787 bytes，时间 2026-06-11 22:19:51 +08:00。已覆盖安装并打开当前用户本地 App：安装目录仅 1 个 `binaries/lilsunspotd/lilsunspotd.exe`，运行中仅 1 个 `lilsunspotd.exe`，runtime pid=8765 listening pid，`process_model=pyinstaller_onedir_single_process`，`/app/bootstrap=chat_ready`，`/modes/current=pragmatic`；未输出 runtime token 或 API Key。
  - 2026-06-11：新增微信伪登录与用户误操作检测。确认态返回缺少账号标识、登录凭据、服务地址或用户标识时不再保存凭据；`/gateway/weixin/login/status` 在 confirmed 后必须启动 Weixin runtime 且 `running=true` 才算已连接，否则清理本次凭据并返回 `login_verification.state=failed`。扫码后回到等待会标记 `user_scan_cancelled_or_wrong_qr` 并持续提示可能误点取消、扫错或扫旧二维码；扫码后长时间未确认会标记 `user_confirmation_delayed`，不误报系统失败。新增桌面类型字段 `login_verification` / `risk_flags`，未新增依赖，未修改 Hermes core。验证：focused Weixin pytest 16 passed、daemon pytest 89 passed、product pytest 38 passed、`npm run build --prefix lilsunspot/desktop`、Rust Tauri 单测 2 passed、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`、`git diff --check` 仅 LF/CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe` 大小 55,729,539 bytes，时间 2026-06-11 22:41:50 +08:00。未覆盖：真实微信扫码误操作场景和 runtime 断线后的人工安装版复验。

### Moved From Current 2026-06-09

- LIL-P0-FLOW-UI-01：产品流程重构 + UI 重排 + P0 主路径修复。
  - 2026-06-07：桌面主导航从开发者模块 tab 改为 BootGate 状态驱动流程；未配置模型进入首启向导，已配置模型进入聊天主界面，本地服务失败进入修复/诊断入口。
  - 新增 `/app/bootstrap` 作为前端启动状态契约；`/app/state` 保留兼容；当前聊天引擎如实命名为 `lilsunspot_provider_adapter`，不再假称完整 Hermes runtime。
  - 模型设置支持可编辑 model 和安全校验后的 `base_url_override`；本地 Ollama 允许空 API Key；输出模式支持三滑杆并写入下一条 chat system hint。
  - Weixin/Safety/Doctor 移入设置抽屉，并明确标记“暂未开放 / 待验证 / 骨架”，不再作为首屏主流程误导用户。
  - 2026-06-07：安装包首启 API Key 设置结构调整；保存 API Key / 模型配置成为主路径，连接测试改为可选验证，避免网络、额度或服务商临时错误阻断本机保存；同时增强 Tauri 运行环境识别。
  - 2026-06-07：真实 setup.exe 当前用户安装验证复现安装版 `/health` 仍走 WebView fetch 的阻断；已改为安装版所有 daemon 请求都走 Tauri 命令代理。重建并静默安装后，仓库外 `Lilsunspot.exe` 能启动安装目录 sidecar，首启进入向导，保存占位 API Key 后进入聊天页，关闭重开后直达聊天页；验证结束后已卸载。
  - 2026-06-07：继续修复从设置入口更换 API Key 的保存流程；已配置模型时重新设置会直接进入保存表单，保存后退出强制向导并回到聊天主界面；首启保存后进入第一句聊天，同时提供“稍后再聊”避免真实 provider 暂时不可用时卡住。Figma MCP 仍受 Starter 计划调用上限阻断，本次沿用仓库内 P0 规格。
  - 2026-06-07：完成本机验收；重建 sidecar 和 NSIS 安装包，headless Edge 用 mock daemon 跑通首启保存、跳过第一句聊天进入 ChatHome、设置抽屉再次保存 API Key 后回 ChatHome，并检查 960x680 / 390x760 无水平溢出；新构建 sidecar 在临时数据目录验证 `/app/bootstrap` 从 `needs_model` 到两次保存后的 `chat_ready`，日志不含占位 Key 或 runtime token。
  - 2026-06-07：完成视觉验收和小范围 UI 调整；Figma 新建设计文件 `https://www.figma.com/design/75o6t0GKbEVYkzHcnwVFHz` 成功，但 `generate_figma_design` / `use_figma` 写入继续受 Starter 计划 MCP 调用上限阻断。headless Edge + 临时 daemon 复验桌面 960x680 和移动 390x760：移动端步骤栏改为横向进度，聊天顶栏按钮更紧凑，设置抽屉加宽到 440px 并锁定背景滚动，所有复验状态无水平溢出。
  - 2026-06-08：按 `lilsunspot/lilsunspot_ui_v3_reference` 完成桌面 UI v3 整体整改；主外壳改为深蓝黑控制台、72px 侧栏、顶部状态栏，ChatHome 增加任务示例卡和右侧模式/安全摘要，输出模式改为调音台页面，首启 Provider 改为出场卡，Weixin/Safety/Doctor 改为同一套深色玻璃面板。前端仅补已有 `/safety/approvals/{id}/decide` 的 API 包装；未新增后端协议，二维码和诊断包导出仍按未接入能力展示。验证：`npm run build --prefix lilsunspot/desktop`、`git diff --check`、`python scripts/guard_no_secrets.py`、`pwsh scripts/check.ps1` 通过；headless Chrome CDP 截图覆盖 1365x768 的 Chat/Mode/Onboarding/Weixin/Safety/Doctor 和 390x760 Chat，均无水平溢出，移动聊天输入框首屏可见。
  - 验证已跑：`git diff --check`、`python scripts/guard_no_secrets.py`、daemon pytest 25 passed、product pytest 25 passed、desktop build、`pwsh scripts/check.ps1`、sidecar build、Tauri NSIS build、headless Edge frontend acceptance、headless Edge visual acceptance、临时 sidecar API acceptance、当前用户 setup.exe 安装/启动/保存/重开/卸载。
  - 仍未覆盖：干净 Windows VM 安装、真实 API Key provider 测试/聊天、完整 Hermes agent loop、真实安装版 UI 人工点击验收；Figma 文件已创建但可编辑 UI 调整稿仍被 MCP Starter 调用上限阻断。

- LIL-P0-01：收敛 `release/mvp-p0` 分支，验证安装、首启、provider、桌面聊天。
  - 2026-06-06：本地自动验证已覆盖 daemon/product tests、secret guard、desktop build、`scripts/check.ps1`、sidecar build、NSIS build、sidecar `/health` 和 token-protected `/providers` smoke。
  - 2026-06-07：按 `lilsunspot/feed_back/feed_back07-06-2026` 插入并完成 LIL-P0-02A 首启体验修复；覆盖黑窗构建配置、首启模型向导、API Key 保存提示、聊天输入清空、Mode 横向选择和安装包图标。
  - 2026-06-07：继续修正 setup.exe 产物；安装包现在安装 `Lilsunspot.exe`，升级时关闭并清理旧 `lilsunspot_desktop.exe`，静默安装后快捷方式和注册表均指向 `Lilsunspot.exe`。
  - 2026-06-07：当前用户 setup.exe 安装版已验证仓库外 `Lilsunspot.exe` 首启、保存占位 API Key、关闭重开直达聊天页，并在验证后卸载。
  - 2026-06-08：用户确认除干净 Windows 安装以外，LIL-P0-01 其余人工验收已完成；clean Windows 安装保留给 LIL-P0-03。
  - 仍未覆盖：干净 Windows VM 安装。

- LIL-P0-03：干净 Windows 安装冒烟，验证仓库外 Lilsunspot.exe 启动 lilsunspotd。
  - 2026-06-08：新增 `scripts/smoke_lilsunspot_installed_app.ps1`，固定安装版 smoke 路径：可静默安装 NSIS、使用隔离 `LILSUNSPOT_DATA_DIR`、启动仓库外 `Lilsunspot.exe`、验证同目录 `lilsunspotd.exe` 进程、`127.0.0.1` runtime discovery、`/health`、带 token 的 `/providers`，并检查 daemon 日志不含 runtime token。
  - 2026-06-08：本机已用当前用户已安装的仓库外 `%LOCALAPPDATA%\Lilsunspot\Lilsunspot.exe` 跑通 `-SkipInstall` smoke；临时数据目录为 `ignored\installed-app-smoke\data`，`/providers` 返回 6 个 provider，未打印 runtime token。
  - 2026-06-08：经用户允许后跑通真实安装路径：`scripts/smoke_lilsunspot_installed_app.ps1` 静默安装到 `%TEMP%\lilsunspot-installed-app-smoke\app`，仓库外安装版启动同目录 sidecar，`/health` 和带 token 的 `/providers` 通过，随后自动静默卸载；为恢复本机当前用户安装状态，已用同一安装包重装回 `%LOCALAPPDATA%\Lilsunspot`，卸载注册表项和桌面/开始菜单快捷方式存在。
  - 2026-06-08：按用户要求直接在本机安装环境验证：静默安装到 `%LOCALAPPDATA%\Lilsunspot`，启动真实安装版 `Lilsunspot.exe`，确认同目录 `lilsunspotd.exe` 进程、`http://127.0.0.1:8765`、真实数据目录 `%LOCALAPPDATA%\Lilsunspot\data`、`/health`、带 token 的 `/providers` 6 个 provider、`/app/bootstrap` stage=`chat_ready`；未打印 runtime token。
  - 2026-06-08：按用户要求使用系统环境中的 DeepSeek API Key 验证真实 provider 主路径；从环境变量读取 Key 到内存，`/providers/test` 通过，`/providers/save` 保存 `deepseek/deepseek-chat`，`/chat/send` 真实返回 4 字回复，`/app/bootstrap` 仍为 `chat_ready`；未打印或记录 API Key、runtime token、回复正文。
  - 2026-06-08：追加多轮/多能力/视觉验证：真实安装版连续 3 次 DeepSeek chat 成功，当前 `/chat/send` 明确 `conversation_id_supported=false`，跨轮记忆未作为已实现能力验收；mode default/pragmatic/balanced 与三滑杆保存后 chat 均通过并恢复原 mode；Weixin `/help`、`/mode pragmatic` 骨架命令通过；Safety approval create/reject 后 pending 归零；Doctor 返回 10 项检查；DWM 截图发现窄屏聊天输入框首屏不可见后，已调整 ChatHome/AppShell CSS、重建并重装，最终 960x680 和 390x760 安装版截图中输入框可见且未见重叠/横向溢出。
  - 本轮结论：LIL-P0-03 本机直接安装验收完成；clean Windows VM 不再作为当前阻断项。

- LIL-P1-01：输出模式三滑杆、三层合并和 prompt 编译。
  - 2026-06-08：完成后端 prompt compiler，固定按“产品基线 + 模式预设 + 三滑杆覆盖”三层合并；新增 `default_mode_prompt.yaml`，`/modes/current` 和 `/modes/select` 返回 `prompt.system_hint`、三层 `prompt.layers[]` 和 `prompt.slider_summary`，并保留 `profile.system_hint` 作为编译后 prompt 兼容字段。
  - `/chat/send` 现在只读取编译后的 `prompt.system_hint` 作为 OpenAI-compatible system message；缺失滑杆时使用所选 mode profile 默认值，保存滑杆继续 clamp 到 `0..100`。
  - 桌面输出模式页读取新 `prompt` 结构，展示三层合并摘要和当前滑杆效果；未新增生产依赖，未修改 Hermes core。
  - 验证已跑：daemon pytest 25 passed、product pytest 33 passed、`test_chat_api.py` 6 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 通过。Browser IAB 当前返回 unavailable；2026-06-08 重试改用 headless Chrome/CDP 截图复验 Chat compact panel 和 Mode page 的 960x680 / 390x760，均无页面级横向溢出，三层 prompt 摘要和滑杆效果可见。截图位于 `%TEMP%\lilsunspot-p1-ui-recheck-20260608-225323`，未包含 API Key 或 runtime token。

- LIL-P2-01：Weixin gateway 二维码、状态和真实私聊。
  - 2026-06-09：新增 lilsunspot 产品层 Weixin 扫码登录状态机和 API：`/gateway/weixin/status` 返回 `not_configured/qr_pending/scanned/qr_expired/connected/credential_expired/error`、能力 flags 和无需微信官方付费/材料标记；新增 `/gateway/weixin/login/start`、`/gateway/weixin/login/status`、`/gateway/weixin/disconnect`，所有接口继续要求 `X-Lilsunspot-Token`。
  - 扫码确认后复用 Hermes Weixin iLink helper 保存凭据到 lilsunspot 独立 `hermes_home/weixin/accounts`，产品状态写入 `weixin-state.json`；响应不返回 token 或 account_id，主动 `/gateway/weixin/send` 仍只创建安全审批，不直接发送微信。
  - `/gateway/weixin/commands/handle` 现在把普通私聊文本复用当前 `lilsunspot_provider_adapter` 生成回复，`/help`、`/mode`、`/approve`、`/reject` 命令继续走产品层处理。
  - 2026-06-09：补齐真实运行态：新增 lilsunspot Weixin runtime manager，读取已保存凭据后构造 Hermes `WeixinAdapter`，通过 `set_message_handler()` 接入私聊文字；扫码确认后自动启动，daemon 启动时仅在已有凭据且模型已配置时自动恢复监听。`/gateway/weixin/status` 增加脱敏 runtime 状态、入站/回复时间和错误摘要。
  - 二维码响应增加后端生成的 SVG `qr_image_data_url`；桌面 Weixin 页直接显示二维码、轮询扫码状态、显示 runtime 状态并支持断开清理。sidecar 构建加入 Weixin 运行依赖和 hidden imports，并修复 windowed PyInstaller stdio，避免无控制台启动时 uvicorn/logging 早退。
  - 桌面 Weixin 页接入开始扫码、状态轮询、断开清理、扫码链接/载荷操作和新状态时间线；未新增前端依赖，仍不接公众号、小程序或开放平台材料流程。
  - 2026-06-09：联网核对 Hermes 官方 Weixin adapter 后确认 `qrcode_img_content` 是完整可扫码 liteapp URL，`qrcode` 只用于轮询状态；后端已禁止在缺少 `qrcode_img_content` 时退回用 `qrcode` 生成二维码，前端进入微信页后自动请求真实二维码，并且真实二维码未返回前不再展示可误扫的假 QR 占位。
  - 2026-06-09：按 setup.exe 主链路重建并重装到 `%LOCALAPPDATA%\Lilsunspot`，安装版 `/gateway/weixin/login/start` 返回 `qr_pending`、`qr_payload_kind=url`、host=`liteapp.weixin.qq.com`、`qr_image_data_url` 存在且响应不含 `token/account_id`；真实二维码只在安装版窗口里给用户现场查看，不写入截图或聊天。
  - 2026-06-09：按用户反馈修复真实二维码状态下的 UI 重叠：二维码容器只承载二维码图像，扫码说明和“打开扫码链接/复制扫码载荷”移动到独立说明面板；低高度窗口同步收紧说明区，避免说明文字、按钮和二维码互相覆盖。
  - 2026-06-09：按用户反馈移除右侧开发者式 `qr_pending/scanned/credential_expired/runtime` 状态时间线和“命令贴纸”，改为普通用户可理解的当前状态、下一步说明，以及扫码后可发送的三类内容。
  - 验证已跑：微信/API 相关 pytest 10 passed、daemon pytest 32 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check`、`pwsh -NoProfile -File scripts/build_lilsunspotd_sidecar.ps1`、packaged windowed sidecar `/health` + token-protected `/gateway/weixin/status` smoke 通过；status smoke 未泄漏 runtime token 或 Weixin credential 字段。Browser IAB 未用于本轮截图级 UI 验收。
  - 2026-06-09 追加验证：`python -m pytest lilsunspot/daemon/tests/test_weixin_gateway_login.py` 7 passed、`npm run build --prefix lilsunspot/desktop` 通过、`npm run tauri:build --prefix lilsunspot/desktop` 通过、setup.exe 静默重装通过、安装版基础 smoke 通过、`python scripts/guard_no_secrets.py` 通过、`git diff --check` 仅 CRLF warnings、`pwsh -NoProfile -File scripts/check.ps1` 通过且 daemon pytest 33 passed。UI 重叠和右侧无意义面板修复后再次完成 focused Weixin pytest、desktop build、NSIS rebuild 和 setup.exe 覆盖安装，安装版微信页已打开供人工复验。
  - 2026-06-09：用户确认微信文字对话人工测试通过后，补齐 lilsunspot 默认 bot 资料：后端 `/gateway/weixin/status` 和扫码启动响应返回 `bot_profile.nickname=小黑子`、`avatar_asset=lilsunspot-icon.png`；桌面聊天助手气泡和微信设置页统一使用项目头像。腾讯 `@tencent-weixin/openclaw-weixin@2.4.4` 源码仅暴露 `get_bot_qrcode?bot_type=...`，本次未猜测 iLink 服务端头像/昵称参数。验证：focused Weixin pytest 7 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`git diff --check` 仅 CRLF warnings、`pwsh -NoProfile -File scripts/check.ps1` 通过；Browser 渲染未跑，因为当前安装版占用 `127.0.0.1:8765` 且避免截图/记录真实微信二维码或 runtime token。
  - 2026-06-09：补做 setup.exe 构建并加强 agent 约束：`AGENTS.md` 新增安装版影响触发规则，凡桌面 UI、Tauri、sidecar/runtime、安装脚本、bundle 图标/资产、Weixin runtime delivery 或只能通过安装版交付的变更，收尾必须跑 `npm run tauri:build --prefix lilsunspot/desktop` 并确认 NSIS `setup.exe` 产物。已补跑 `pwsh -NoProfile -File scripts/check.ps1`、`python scripts/guard_no_secrets.py`、`npm run tauri:build --prefix lilsunspot/desktop`，生成 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-09：按用户确认用最新 `setup.exe` 覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`，确认安装目录下 `Lilsunspot.exe` 和 `lilsunspotd.exe` 来自本次构建；随后运行 `scripts/smoke_lilsunspot_installed_app.ps1 -SkipInstall -InstallDir %LOCALAPPDATA%\Lilsunspot`，安装版 smoke 通过，验证安装目录 sidecar、`127.0.0.1` runtime discovery、`/health`、带 `X-Lilsunspot-Token` 的 `/providers`，且未输出 runtime token 或 API Key。
  - 2026-06-09：复核微信端无法显示“小黑子”头像/昵称的问题：当前 iLink/ClawBot 协议和腾讯 `openclaw-weixin` 插件只公开 QR 登录、消息收发、上传、配置和 typing 等接口；`get_bot_qrcode` 只接收 `bot_type`，登录确认只返回 `ilink_bot_id/bot_token/baseurl/ilink_user_id`，消息 API 类型里没有 bot 昵称或头像字段。结论：本地只能设置 lilsunspot 桌面端展示资料，微信客户端里的 ClawBot/iLink bot identity 展示资料由微信服务端控制；除非腾讯后续开放 profile API 或管理台配置，否则不应在本地伪造参数。
  - 2026-06-09：按用户截图反馈精简微信扫码面板：底部三个操作收敛为唯一“刷新”按钮，刷新按状态执行读取状态/拉取扫码状态/重新生成二维码；移除“读取中”“正在生成二维码”“这里不会显示可扫描的假二维码”“复制扫码载荷”等用户无意义文案或控件。验证：`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`npm run tauri:build --prefix lilsunspot/desktop`、setup.exe 覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`、安装版 smoke 通过。Browser IAB 本轮返回不可用，未做截图级自动验收。
  - 2026-06-09：按用户补充要求恢复独立强制断开入口：微信扫码面板保留“刷新”主操作，另增单独“断开”按钮，直接调用 `/gateway/weixin/disconnect` 清理连接或扫码状态，不再把断开语义混入刷新。验证：`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`npm run tauri:build --prefix lilsunspot/desktop`、setup.exe 覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`、安装版 smoke 通过；Browser IAB 仍返回不可用，未做截图级自动验收。
  - 2026-06-09：用户人工确认真实桌面端聊天、微信扫码登录、微信端成功登录、微信私聊文本回复、`/help` 和 `/mode` 均已跑通。先不实现但需记录的产品风险：`/help`、`/mode` 这类 slash command/命令式调整路径不适合本产品目标用户，绝大多数用户是代码小白，后续应改成自然语言、按钮/菜单、快捷卡或低门槛引导，不应要求用户理解类似代码的命令格式。
  - 2026-06-09：用户补充确认 P2-01 安装版 UI 人工校验成功；P2-01 以真实桌面聊天、扫码登录、微信端登录、私聊文本回复、`/help`、`/mode` 和安装版 UI 点击验收通过收尾。
  - 后续稳定性风险：断线重连、二维码真实过期仍需在后续 Weixin 能力迭代中补验，不再作为 P2-01 当前阻断项。

### LIL-P0-02: 发布级 check_release.ps1。

Goal:
新增发布候选强校验入口，避免发布前因为缺少 npm 或 desktop 依赖而静默跳过桌面构建。

Result:
新增 `scripts/check_release.ps1`，固定执行 git diff check、daemon pytest、product pytest、secret guard、desktop build、sidecar build、NSIS build，并检查 sidecar exe 和 NSIS setup.exe 产物存在；缺少 `git`、`python`、`npm`、`uv` 或 `lilsunspot/desktop/node_modules` 时直接失败。新增脚本约束测试，防止 release check 回退到跳过 desktop build。

Check:
```powershell
python -m pytest lilsunspot/tests/test_release_check_script.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
pwsh scripts/check_release.ps1
pwsh scripts/check.ps1
```

### LIL-P0-02A: 安装后首启体验修复。

Goal:
根据 `feed_back07-06-2026` 修复安装包测试阶段暴露的首启体验问题，先于发布级 check 和干净 Windows 冒烟处理真实用户阻断。

Result:
Windows release 桌面进程改为无控制台子系统，sidecar PyInstaller 改为 `--noconsole`；setup.exe 安装的主程序改为 `Lilsunspot.exe`，并在升级时处理旧 `lilsunspot_desktop.exe`；桌面端首启未配置 provider 时直接进入模型设置；Provider 向导补充 API Key 获取/保存说明；测试保存成功后清空前端 Key；聊天页改为消息流并在发送后清空输入；Mode 页自动加载并使用横向选择卡；安装包/快捷方式图标改用反馈图片。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
python scripts/guard_no_secrets.py
npm run build --prefix lilsunspot/desktop
pwsh scripts/check.ps1
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop
.\lilsunspot\desktop\src-tauri\target\release\bundle\nsis\Lilsunspot_0.1.0_x64-setup.exe /S
```

### LIL-DOC-01: 按仓库现有 MD 架构整理 lilsunspot 项目文档。

Goal:
把 lilsunspot 当前状态、开发入口、文档索引和历史任务关系收敛到产品层 Markdown，不修改 Hermes upstream 文档作为任务记忆。

Result:
建立 `README.lilsunspot.md`、`lilsunspot/notes/doc-index.md`、`lilsunspot/notes/doc-inventory.md`、`lilsunspot/notes/mvp-p0-status.md` 等当前状态入口；后续任务以 `mvp-p0-status.md` 为准。

### LIL-00-07: Windows 安装包与 daemon sidecar 最小闭环。

Goal:
让普通 Windows 用户安装后打开 `Lilsunspot.exe`，不需要 Python、Node、Git 或 Docker，也能自动启动并连接 `lilsunspotd`。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. Windows daemon sidecar 构建脚本能生成 `lilsunspotd-x86_64-pc-windows-msvc.exe`。
2. sidecar 入口等价于 `python -m lilsunspot.daemon.launcher`。
3. sidecar 打包必须包含 `lilsunspot/resources/*.yaml`，不能依赖仓库源码路径。
4. Tauri bundle 使用 `externalBin` 接入 daemon sidecar。
5. Windows bundle target 固定为 `nsis`，避免 `targets: all` 触发 MSI/WiX 下载失败。
6. 桌面端启动 daemon 时优先查找打包 sidecar；debug 构建下仍保留 Python fallback。
7. 安装包构建命令能生成可安装 `.exe`。
8. sidecar 首次启动能创建 lilsunspot 独立数据目录、runtime token、discovery file 和 logs。
9. 桌面端能通过 Tauri token 代理访问 `/app/state` 和 `/providers`。
10. API Key、runtime token 不得进入日志、响应、prompt fixture、截图或诊断文本。
11. `scripts/check.ps1` 可以运行。
12. 不修改 Hermes 核心。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop -- --bundles nsis
```

### LIL-00-06: 微信命令意图与安全审批队列最小闭环。

Goal:
在不触碰 Hermes 微信 adapter 的前提下，先完成 lilsunspot 产品层的微信命令解析/处理入口和本地安全审批队列，让高风险微信发送动作只能进入审批流程，不能直接发送。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `/gateway/weixin/*` 和 `/safety/*` 除 `/health` 外继续要求 `X-Lilsunspot-Token`。
2. 微信状态必须明确说明当前不会扫码登录或真实发送消息。
3. `/gateway/weixin/commands` 暴露 `/help`、`/mode`、`/approve`、`/reject` 的产品层命令。
4. 微信命令处理接口能解析 `/help`、`/mode <id>`、`/approve <id>`、`/reject <id>`，用户可见错误保持普通中文。
5. `send_weixin_message` 必须按安全策略创建 pending approval，不得直接发送。
6. 审批队列必须保存在 lilsunspot 独立数据目录，不写入 Hermes home。
7. 审批支持 approve/reject 后从 pending 列表移除，并保留状态记录。
8. API Key、runtime token 不得进入日志、响应、prompt fixture、截图或诊断文本。
9. daemon pytest 最小测试通过。
10. `scripts/check.ps1` 可以运行。
11. 不修改 Hermes 核心。
12. 不修改 SOUL.md。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

### LIL-00-05: 接入 mode profiles 到真实聊天行为。

Goal:
让已选择的 mode profile 影响真实聊天请求的系统提示、输出风格和默认行为，同时继续避免泄露 API Key 或 runtime token。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `/chat/send` 继续要求 `X-Lilsunspot-Token`。
2. 当前 mode profile 必须从 lilsunspot 独立数据目录读取。
3. mode profile 的 `system_hint` 必须进入真实聊天请求。
4. 未选择 mode 时使用默认 profile。
5. 用户可见错误保持普通中文。
6. API Key、runtime token 不得进入日志、响应、prompt fixture、截图或诊断文本。
7. daemon pytest 最小测试通过。
8. chat/mode 产品层补充测试通过。
9. desktop TypeScript build 通过。
10. `scripts/check.ps1` 可以运行。
11. 不修改 Hermes 核心。
12. 不修改 SOUL.md。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

- LIL-00-04: 实现桌面聊天到 Hermes runtime 的真实桥接。本机 `DEEPSEEK_API_KEY` 已通过 `/providers/test` 和 `/chat/send` 真实通讯验证；未记录 API Key、runtime token 或回复正文。
- LIL-00-01: 创建 lilsunspot 完整开发骨架。
- LIL-00-02: 打通 lilsunspotd 启动器和桌面端自动发现。
- LIL-00-03: 实现真实 Provider 配置验证。
