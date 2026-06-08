# Codex 提示词：Lilsunspot 小黑子 UI v3 整体整改

你在 `tealigantal/lilsunspot` 的 `develop` 分支工作。目标是把当前普通浅色 SaaS 风格的桌面 UI，整改为“Lilsunspot 小黑子梗图主题 + Windows 桌面 Agent 控制台”风格。必须保持主链路可运行，不允许为了 UI 改坏 provider、聊天、输出模式、微信、安全审批、诊断接口。

参考图已经提供，请先读取并观察这些图：

1. `00_design_tokens_typography.png`：颜色、字号、间距、组件尺寸。
2. `01_chat_home_clean.png`：聊天首页正式目标图。
3. `01_chat_home_annotated.png`：聊天首页布局标注，只用于理解尺寸，不要把标注文字、红线、青色标尺渲染进正式 UI。
4. `02_output_mode_mixer.png`：输出模式调音台目标图。
5. `03_onboarding_provider_cards.png`：首启 Provider 出场卡目标图。
6. `04_weixin_gateway.png`：微信二维码与命令页目标图。
7. `05_safety_doctor.png`：安全审批与诊断页目标图。

核心审美方向：深蓝黑背景、Aero 玻璃感、篮球橙、舞台黄、Aero 青、少量 Y2K 贴纸。界面要有“梗图记忆点”，但不能低俗、不能花屏、不能影响长期阅读。不要做普通白色企业后台。不要使用真人照片、外部表情包、长歌词、侵权素材。可以继续使用仓库已有的 `lilsunspot-icon.png` 作为吉祥物头像。

## 一、硬约束

1. 不重写 Hermes 核心。
2. 不修改后端 API 协议，除非现有 UI 必须读取已有字段。
3. 不引入大型 UI 库，不引入 Tailwind，不引入复杂主题系统。
4. 不新增产品分支，不做 Lite / Pro / Full。
5. API Key、token、日志脱敏逻辑不能被 UI 改动破坏。
6. `lilsunspotd` 仍然只监听本地；UI 只调用现有本地 API。
7. UI 主要修改放在 `lilsunspot/desktop/src/`。
8. 任务完成后必须能 `npm run build` 通过。
9. 目标窗口按 `1365 x 768` 优先验收，不能出现文字过小、按钮挤压、输入框跑出屏幕。
10. 正文最小字号 15px，说明/标签最小 12px。不要出现 10px 以下正文。

## 二、现有代码入口

重点检查并修改这些文件；可以拆新组件，但不要大规模改业务逻辑：

- `lilsunspot/desktop/src/App.css`
- `lilsunspot/desktop/src/app/AppShell.tsx`
- `lilsunspot/desktop/src/app/BootGate.tsx`
- `lilsunspot/desktop/src/features/chat/ChatHome.tsx`
- `lilsunspot/desktop/src/features/chat/ChatTranscript.tsx`
- `lilsunspot/desktop/src/features/chat/ChatComposer.tsx`
- `lilsunspot/desktop/src/features/mode/ModeQuickPanel.tsx`
- `lilsunspot/desktop/src/features/mode/ModeSlider.tsx`
- `lilsunspot/desktop/src/features/onboarding/OnboardingFlow.tsx`
- `lilsunspot/desktop/src/features/onboarding/ChooseModelServiceStep.tsx`
- `lilsunspot/desktop/src/features/onboarding/ApiKeyStep.tsx`
- `lilsunspot/desktop/src/features/model/ProviderCard.tsx`
- `lilsunspot/desktop/src/features/settings/SettingsDrawer.tsx`
- `lilsunspot/desktop/src/features/settings/WeixinSettings.tsx`
- `lilsunspot/desktop/src/features/settings/SafetySettings.tsx`
- `lilsunspot/desktop/src/features/settings/DoctorSettings.tsx`

建议新增但不强制：

- `lilsunspot/desktop/src/shared/components/AppChrome.tsx`
- `lilsunspot/desktop/src/shared/components/SideNav.tsx`
- `lilsunspot/desktop/src/shared/components/TopStatusBar.tsx`
- `lilsunspot/desktop/src/shared/components/GlassCard.tsx`

## 三、设计 Token

在 `App.css` 的 `:root` 增加或替换为下面的主题变量。可以保留旧变量作为 alias，但新 UI 应主要使用新变量。

```css
:root {
  --ikun-bg: #050b16;
  --ikun-bg-soft: #0b1424;
  --ikun-panel: #102033;
  --ikun-panel-2: #14263d;
  --ikun-text: #f8fbff;
  --ikun-muted: #a8b6c9;
  --ikun-muted-2: #7c8da3;
  --ikun-cyan: #63f6da;
  --ikun-orange: #ff8b24;
  --ikun-yellow: #ffd552;
  --ikun-pink: #ff6dc7;
  --ikun-green: #47f08a;
  --ikun-red: #ff5a6a;
  --ikun-line: rgba(99, 246, 218, 0.28);
  --ikun-line-warm: rgba(255, 213, 82, 0.35);
  --ikun-glass: rgba(16, 32, 51, 0.86);
  --ikun-glass-strong: rgba(12, 22, 38, 0.94);
  --radius-control: 12px;
  --radius-card: 18px;
  --radius-panel: 24px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
}
```

字体：

```css
font-family: Inter, "Segoe UI", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif;
```

字号硬约束：

- 页面主标题：28px / 34px，bold。
- 二级标题：22px / 28px，bold。
- 卡片标题：18px / 24px，bold。
- 正文：15px / 22px。
- 标签说明：12px / 16px。
- 按钮：15px，bold，最小高度 42px。
- 输入框：正文 15px，聊天输入区域高度 84px 左右。

## 四、全局布局整改

目标参考：`01_chat_home_clean.png` 和 `01_chat_home_annotated.png`。

把全局 UI 改成桌面控制台布局：

1. 左侧固定窄导航，宽度 72px，距离窗口边缘 18px。
2. 顶部栏高度 60px，左侧显示页面标题和当前 provider/model，右侧显示“输出：xxx”、“已连接/未配置”、“设置”。
3. 主内容区从 x=108 左右开始，顶部 y=96 左右开始。
4. 聊天页主区两列：左侧聊天区、右侧模式混音器。右侧宽度约 427px，左右栏间距 18px。
5. 背景使用深蓝黑渐变 + 少量细线/光晕，不要用纯白背景。
6. 主卡片使用玻璃深色面板，圆角 24px，边框 1px，边框可用青色或舞台黄弱化显示。
7. 左侧导航项：聊天、模式、微信、审批、诊断。当前激活项使用篮球橙底色，非激活项深色。
8. 小窗口可以降级为单列，但 1365x768 必须先做漂亮。

注意：如果当前应用没有路由，不要强行引入路由库。可以通过现有设置抽屉、状态页、按钮打开不同面板；但视觉上必须像一个完整控制台。

## 五、聊天首页整改

目标参考：`01_chat_home_clean.png`。

修改 `ChatHome.tsx`，保留现有 `sendChatMessage`、`getCurrentMode`、`send()`、`messages`、`busy` 逻辑，不要改业务行为。

UI 要求：

1. 页面标题为“和小黑子聊天”或“今日任务台”。
2. 空态不要再是大白框。改为 3 个示例任务卡：
   - “帮我整理今天要做的三件事”
   - “我明天交方案但没开始”
   - “微信里把模式调到 80”
3. 点击示例卡可以填入输入框；不能调用接口也可以先只填入。
4. 聊天记录区使用深色气泡。助手气泡深色，用户气泡篮球橙。
5. 输入框固定在聊天卡片底部，高度约 84px，发送按钮在右侧，高度 56px 左右。
6. 右侧常驻模式摘要卡，不要让“输出模式”只藏在设置里。
7. 右侧模式摘要显示三项：
   - 唱 / 表达 = `style_axis`
   - RAP / 细节 = `detail_level`
   - 篮球 / 自主 = `autonomy_level`
8. “跳”只能作为装饰性小贴纸或文案，不要新增第四个持久化字段。
9. 右侧底部显示安全审批摘要：暂无待处理 / n 个待审批。

## 六、输出模式整改

目标参考：`02_output_mode_mixer.png`。

修改 `ModeQuickPanel.tsx` 和 `ModeSlider.tsx`。保留现有模式 API：`getModes()`、`getCurrentMode()`、`selectMode()`。不要新增 mode profile 字段。

UI 要求：

1. 视觉上叫“输出模式调音台”，不要叫普通“设置”。
2. 保留三个预设：务实、均衡、感性。
3. 三个滑杆对应关系固定：
   - `style_axis`：唱 / 表达风格，左“务实”，右“感性”。
   - `detail_level`：RAP / 细节程度，左“简短”，右“详细”。
   - `autonomy_level`：篮球 / 自主程度，左“确认”，右“推进”。
4. 滑杆数值显示在右侧，颜色分别使用青色、黄色、橙色。
5. 增加“实时预览”区域，固定问题：`我想做一个个人 agent，第一步怎么做？`
6. 预览不需要请求模型，可以根据当前模式本地生成三段模板文案。务实更短，感性更柔和，均衡居中。
7. 保存按钮文案为“保存输出模式”。
8. 保存后仍调用 `selectMode()`，并通过 `onModeChanged` 更新顶部状态。

## 七、首启向导整改

目标参考：`03_onboarding_provider_cards.png`。

修改 `StepLayout.tsx`、`OnboardingFlow.tsx`、`ChooseModelServiceStep.tsx`、`ProviderCard.tsx`、`ApiKeyStep.tsx`。

UI 要求：

1. 左侧步骤 rail 改成顶部横向步骤条，减少横向空间浪费。
2. Provider 选择页使用“出场卡”视觉，而不是普通按钮网格。
3. 推荐 provider 仍然是 DeepSeek、Kimi、Qwen、Ollama。
4. 每张卡必须显示：服务名、适合场景、推荐模型、是否需要 API Key。
5. 选中态必须明显：橙色边框 + “已选”贴纸。
6. 下一步按钮文案改成“下一步：保存 Key”。
7. 更多服务折叠显示，不占主视觉。
8. API Key 页面也要使用深色玻璃卡，不要回到白色表单。
9. 失败错误必须是人话，不展示原始异常堆栈。

## 八、微信页整改

目标参考：`04_weixin_gateway.png`。

修改 `WeixinSettings.tsx`。不要实现新微信机器人，只展示和调用已有 gateway API。

UI 要求：

1. 标题可用“微信连接”或“WEIXIN GATEWAY.EXE”。
2. 左侧显示二维码区域，二维码来自 `/gateway/weixin/qr`。没有二维码时显示清楚的占位和“生成二维码”按钮。
3. 右侧显示状态机 timeline：
   - `not_configured`
   - `qr_pending`
   - `qr_expired`
   - `connected`
   - `credential_expired`
   - `error`
4. 状态文案必须人话解释。
5. 命令贴纸区域显示：`/模式 20`、`/模式 80`、`/务实`、`/感性`、`/资料`、`/详细`。
6. 不做微信原生资料页注入，只做私聊命令和资料文本。
7. 失败时给“重新生成二维码 / 重置连接 / 打开诊断”的操作。

## 九、安全审批与诊断整改

目标参考：`05_safety_doctor.png`。

修改 `SafetySettings.tsx` 和 `DoctorSettings.tsx`，必要时可以让 `SettingsDrawer.tsx` 的布局承载这些页面。

安全审批要求：

1. 标题可用“裁判席：待审批操作”。
2. 待审批操作用卡片显示。
3. 不向用户展示原始 tool JSON。
4. 每张卡片显示：动作名、人话说明、风险说明、操作按钮。
5. 操作按钮固定为：拒绝、允许一次、总是允许。
6. 高风险使用红色，中风险使用橙色，普通状态使用青色或绿色。

诊断要求：

1. 诊断项用列表卡显示，不默认展示 JSON。
2. 检查项至少包括：本地服务、Provider/API Key、输出模式文件、微信网关、诊断包脱敏。
3. 技术详情默认折叠。
4. 按钮为“重新检查”、“导出脱敏诊断包”。
5. 导出/日志相关文案必须强调脱敏。

## 十、设置抽屉整改

当前 `SettingsDrawer.tsx` 不要保持白色抽屉。要与主 UI 主题一致。

要求：

1. 背景使用 smoke 半透明黑，不要纯灰遮罩。
2. 抽屉使用深色玻璃面板。
3. tab 按钮和状态 badge 使用同一套 token。
4. “暂未开放 / 待验证 / 骨架”这类开发者文案不要作为主文案；可以改成人话：
   - 微信：未连接
   - 安全审批：暂无待处理
   - 诊断：未检查
5. 未完成状态可以显示，但不要让用户感觉产品残缺。

## 十一、CSS 细节

1. `body` 背景必须是深蓝黑渐变，不能有大面积白底。
2. 所有卡片圆角 18-24px。
3. 按钮圆角 12px，最小高度 42px。
4. focus-visible 必须可见，可以使用舞台黄 outline。
5. hover 可以轻微抬升或增强边框，不要复杂动画。
6. 使用 `@media (prefers-reduced-motion: reduce)` 关闭非必要动画。
7. 1365x768 下不能出现纵向滚动条覆盖主输入框。
8. 文字必须清晰，禁止低对比度灰字。
9. 不要出现白色大卡片导致刺眼；只有输入框可以是浅色。

## 十二、验收截图要求

完成后运行：

```bash
cd lilsunspot/desktop
npm run build
npm run tauri:dev
```

请用 1365x768 或接近该比例截图检查：

1. 聊天首页接近 `01_chat_home_clean.png`。
2. 输出模式页接近 `02_output_mode_mixer.png`。
3. 首启 Provider 页接近 `03_onboarding_provider_cards.png`。
4. 微信页接近 `04_weixin_gateway.png`。
5. 安全审批/诊断页接近 `05_safety_doctor.png`。

不要追求像素级复刻，但必须满足：布局分区一致、字号不小、主色一致、不是普通白色后台、输出模式入口明显。

## 十三、完成后输出

完成任务后回复：

1. 修改了哪些文件。
2. 新增了哪些组件。
3. 哪些业务逻辑保持不变。
4. `npm run build` 是否通过。
5. 已知风险。
6. 附上 1365x768 截图，供我比较参考图。
