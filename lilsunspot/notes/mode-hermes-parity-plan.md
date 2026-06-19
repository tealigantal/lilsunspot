# Mode 与 Hermes 能力对齐实施计划

## 文档信息

- 计划编号：`LIL-MODE-HERMES-PARITY-01`
- 文档状态：当前实施计划
- 归档日期：2026-06-19
- 目标分支：`develop`
- 适用范围：Mode、Prompt、Agent runtime、对话、文件、记忆、工具宿主与兼容性测试
- 非目标：安装、更新、发布渠道和 setup.exe 迁移问题

## 1. 背景

Lilsunspot 已经把 Hermes `AIAgent` 接入桌面聊天、微信会话、文件交付和能力中心，并增加了独立的 Mode 功能。Mode 是产品差异化能力，应继续保留。

当前问题不是“存在 Mode”，而是 Mode 与产品层其他逻辑共同形成了第二套控制面：

- Mode 编译器负责了部分产品基线和能力描述。
- Mode 状态保存在全局文件，不按会话隔离。
- 自然语言 Mode 判断会额外直连 provider 的 `chat/completions`。
- Mode 指令可能在进入 Hermes 前被产品层截获。
- 三个滑杆主要转成粗粒度提示词，没有稳定映射到 Hermes 运行参数。
- Hermes 的 SOUL、Context Files、Clarify、流式事件等能力没有完整进入 Lilsunspot 宿主。

最终应把 Mode 定义为 Hermes 之上的“会话级输出与执行策略覆盖层”，而不是独立 Agent 或替代 Hermes Prompt 的第二套系统。

## 2. 总目标

形成以下稳定分层：

```text
Hermes AIAgent
├─ Hermes 原生身份与系统提示
├─ SOUL / Context Files
├─ Hermes Memory / SessionDB
├─ Skills / MCP / Toolsets
├─ Provider routing / fallback / compression
└─ Lilsunspot 产品覆盖层
   ├─ 产品安全基线
   ├─ 动态能力真实性快照
   ├─ 当前会话 Mode overlay
   └─ 当前回合文件交付说明
```

Mode 只决定：

- 回答表达方式。
- 回答细节程度。
- 对明确且安全任务的主动推进程度。
- 本回合合理的输出预算和 Agent 迭代预算。

Mode 永远不能决定：

- 是否绕过安全审批。
- 是否扩大工具集。
- 是否访问未授权路径。
- 是否跳过 Memory 或 SessionDB。
- 是否绕过 MCP、Skills 或文件安全约束。
- 是否改变 Provider 凭据和外部账号权限。

## 3. 当前仓库问题清单

### 3.1 Prompt 职责混杂

`lilsunspot/resources/default_mode_prompt.yaml` 同时包含产品身份、安全基线和具体能力是否实现的描述。具体能力状态会随仓库变化，不应静态写入 Mode 资源。

风险：

- 已经接入的能力仍可能被 Prompt 告知“未实现”。
- Mode 配置更新会意外改变产品安全基线。
- 能力中心与 Agent 自我认知可能不一致。

### 3.2 Mode 是全局状态

`mode-profile.json` 只有一个当前状态。桌面对话、项目对话和不同微信联系人共享同一个 Mode。

风险：

- 工作对话切换到务实模式后，生活对话也同步变化。
- 微信联系人之间互相影响。
- 用户无法为不同长期会话保存不同偏好。

### 3.3 Mode Router 绕开 Hermes

`mode_intents.py` 会额外调用 provider 的 `chat/completions` 判断短句是否为 Mode 指令。

风险：

- 普通消息可能产生隐藏 API 调用、费用和延迟。
- 不复用 Hermes Provider router、fallback 和非 Chat Completions transport。
- Mode 判断不进入 Hermes SessionDB 和工具历史。
- 不同 provider 的行为不一致。

### 3.4 Mode 控制事件污染或分裂对话历史

Mode 指令可能在产品层直接返回，不进入 Hermes；Mode 状态消息也可能写入默认个人会话，而不是实际发起指令的会话。

风险：

- 用户可见历史与 Hermes 历史不一致。
- `session_search` 找不到 Mode 变化上下文，或看到与 UI 不一致的内容。
- 微信会话的 Mode 变化可能错误显示在个人会话。

### 3.5 三滑杆实际效果过粗

当前滑杆主要按低、中、高阈值转成自然语言提示。大量数值区间没有实际差异。

风险：

- 0～100 的 UI 给出连续调节预期，但运行效果接近三档。
- `autonomy_level` 没有稳定控制 Agent 迭代和确认策略。
- `detail_level` 没有稳定控制输出预算。

### 3.6 Hermes 宿主能力没有完整桥接

当前直接创建 `AIAgent`，但没有完整传入 Clarify、流式 token、工具状态、停止和 steer 等宿主回调。

风险：

- `clarify` 工具在工具集中存在，但没有可交互回调。
- 用户看不到工具执行过程。
- Mode 的“多确认”无法转化为真正的结构化询问。

### 3.7 Mode 改动可能造成 Hermes 能力退化

当前没有专门的 Mode/Hermes parity 契约测试，无法保证切换 Mode 后以下能力保持不变：

- 文件与附件交付。
- Memory 和 Session Search。
- Skills 和 MCP。
- Provider fallback。
- 工具审批。
- SOUL 和项目 Context Files。

## 4. 设计原则

1. Hermes 是 Agent runtime 的唯一执行真相。
2. Lilsunspot conversation 是产品展示与渠道同步层，不另造一套 Agent 语义。
3. Mode 是会话策略，不是 Provider adapter，不直接请求模型。
4. 能力是否可用由 capability graph 和真实 runtime 决定，不由 Mode 静态文本决定。
5. 安全规则是硬约束，优先级始终高于 Mode。
6. 文件、记忆、Skills、MCP 和审批在所有 Mode 下保持同一能力面。
7. Mode 控制事件与普通语义消息分开存储和展示。
8. 所有功能改动优先放在 `lilsunspot/` 产品层，不大面积修改 Hermes core。

## 5. 分阶段实施

## 阶段 A：Prompt 分层与 Hermes 身份恢复

### 目标

把 Mode 从完整 system prompt 编译器收敛为单一 `mode_overlay`，恢复 Hermes 原生身份、SOUL 和项目上下文的合理加载。

### 修改建议

新增 `lilsunspot/daemon/prompt_layers.py`：

```python
@dataclass(frozen=True)
class ProductPromptLayers:
    product_baseline: str
    capability_snapshot: str
    mode_overlay: str
    delivery_overlay: str

    def compile(self) -> str:
        ...
```

调整职责：

- `default_mode_prompt.yaml` 只保留稳定的产品身份、中文交互、隐私与风险原则。
- 删除“某能力尚未实现”之类会过期的静态内容。
- `capability_prompt_snapshot()` 继续提供动态能力真实性信息。
- `prompt_compiler.py` 只编译 Mode overlay，不再拥有整份产品 system prompt。
- `agent_runner.py` 统一合并 Prompt layers。

Hermes Context 设置：

- 普通个人对话：`skip_context_files=True`，`load_soul_identity=True`。
- 明确绑定工作目录的项目对话：允许 `skip_context_files=False`。
- `skip_memory=False` 保持不变。

### 验收

- 任意 Mode 下 Agent 工具列表相同。
- SOUL 在个人对话生效。
- 项目对话能够加载 AGENTS.md 或项目上下文。
- capability snapshot 与 Mode 文案不互相覆盖。
- 安全审批规则不因 Mode 改变。

## 阶段 B：会话级 Mode 状态

### 目标

建立“全局默认 → 会话覆盖 → 单次消息临时覆盖”三级 Mode 作用域。

### 数据模型

```python
@dataclass(frozen=True)
class ModeSelection:
    mode_id: str
    style_axis: int
    detail_level: int
    autonomy_level: int
    scope: Literal["global", "conversation", "turn"]
```

建议：

- 全局默认继续保存于产品配置。
- 会话覆盖保存到 `conversations.metadata["mode"]`，或建立独立 `conversation_modes` 表。
- 单次消息覆盖仅存在于当前 turn context，不落为长期默认。

### API 契约

```http
GET /modes/current?conversation_id=conv_xxx

POST /modes/select
{
  "conversation_id": "conv_xxx",
  "mode": "pragmatic",
  "scope": "conversation",
  "style_axis": 20,
  "detail_level": 40,
  "autonomy_level": 70
}
```

### 对话展示

Mode 变化记录为控制事件：

```json
{
  "event": "mode.changed",
  "conversation_id": "conv_xxx",
  "mode": "pragmatic"
}
```

前端可显示状态条，但不得把它伪装为普通 assistant 回复，也不应污染 Agent 语义历史。

### 验收

- 对话 A 和对话 B 的 Mode 相互独立。
- 不同微信联系人 Mode 相互独立。
- 新对话继承全局默认。
- 重启后会话 Mode 保留。
- 删除会话时对应 Mode 状态同步清理。

## 阶段 C：取消隐藏 Mode Router，改为确定性命令与 Hermes 工具

### 目标

正常聊天只经过一次正式 Hermes Agent 流程。

### 明确命令

本地确定性解析以下高置信表达，不调用模型：

```text
/mode pragmatic
切换到务实模式
回答详细一点
以后主动一点
当前是什么模式
```

### 模糊表达

注册两个 Lilsunspot 产品工具：

```text
lilsunspot_get_mode
lilsunspot_set_mode
```

`lilsunspot_set_mode` 接受：

- `mode`
- `style_axis`
- `detail_level`
- `autonomy_level`
- `scope`

工具通过当前 turn context 获取 `conversation_id`，不允许模型指定其他会话。

### 处理顺序

```text
明确 Mode 命令 → 本地确定性处理
普通消息 → 直接进入 Hermes
模糊风格请求 → Hermes 在正常对话中调用 Mode 工具
```

### 验收

- 普通聊天不再产生隐藏 Mode Router 请求。
- OpenAI Responses、Anthropic Messages、OpenRouter 和本地模型路径一致。
- Mode 工具调用进入当前 Hermes 工具历史。
- 模糊表达不会被产品层误吞。
- Mode 工具不能改变工具集和安全策略。

## 阶段 D：三滑杆映射为真实运行策略

### 目标

让 0～100 的调节产生稳定、可观察、可测试的行为差异。

新增：

```python
@dataclass(frozen=True)
class ModeRuntimePolicy:
    style_axis: int
    detail_level: int
    autonomy_level: int
    target_answer_tokens: int
    max_iterations: int
    clarification_policy: str
    proactive_tool_policy: str
    reasoning_effort: str | None
```

### `style_axis`

只影响表达，不影响事实、权限和工具：

- 0～20：极度务实直接。
- 21～40：偏务实。
- 41～60：中性平衡。
- 61～80：温和、有陪伴感。
- 81～100：高情绪响应。

### `detail_level`

同时影响 Prompt 和软输出预算：

- 0～20：结论优先，目标 150～300 tokens。
- 21～40：简短，目标 300～600 tokens。
- 41～60：标准，目标 600～1000 tokens。
- 61～80：详细，目标 1000～1800 tokens。
- 81～100：深入，目标 1800～3000 tokens。

可映射到 `AIAgent.max_tokens`，但不得在生成后机械截断完整答案。

### `autonomy_level`

影响安全范围内的推进策略：

- 0～20：非明确任务优先询问。
- 21～40：多步骤任务先给方案。
- 41～60：自动完成明确、可逆步骤。
- 61～80：主动使用安全工具并验证结果。
- 81～100：完成完整任务，仅在真正阻断时询问。

可映射到：

- `max_iterations`
- Clarify 阈值
- 是否主动验证结果
- 是否主动继续可逆步骤

硬约束：

- 不绕过审批。
- 不自动扩大工具集。
- 不突破文件安全范围。
- 不自动发送外部消息。
- 不修改凭据权限。

### 验收

- 滑杆每变化约 10～20 点能观察到稳定差异。
- 高自主模式主动完成安全步骤。
- 低自主模式通过真正的 Clarify UI 询问。
- 不同 Mode 的工具 schema 完全一致。

## 阶段 E：Hermes 宿主回调与功能完整性

### 目标

让 Mode 的交互语义能够依赖 Hermes 原生机制，而不是仅靠 Prompt 猜测。

接入至少以下回调或等价产品事件：

- `clarify_callback`
- `tool_start_callback`
- `tool_progress_callback`
- `tool_complete_callback`
- `stream_delta_callback`
- `status_callback`
- 中断/停止控制
- steer 或当前任务补充指令

### 验收

- `clarify` 工具可在桌面和微信会话中完成一问一答。
- 用户能看到当前模型调用或工具阶段。
- 停止任务会传播到 Agent 和子代理。
- Mode 的“多确认”表现为结构化询问，不是普通文本假确认。

## 阶段 F：文件、对话和记忆一致性收口

### 文件

- Mode 不改变文件工具和交付工具是否可用。
- 上传文件、返还附件和生成文件在全部 Mode 下行为一致。
- Mode overlay 不覆盖 delivery overlay。
- 修正 `file` 工具配置与实际强制启用之间的不一致。

### 对话

- Mode 控制事件不作为普通语义消息进入模型历史。
- 正常消息始终进入 Hermes SessionDB。
- Lilsunspot 可见消息与 Hermes 消息建立稳定映射关系。
- 合并消息、附件摘要和最终可见回复的转换关系写入 metadata，便于诊断。

### 记忆

- Mode 不能创建新的记忆系统。
- Hermes Memory、Session Search 和 Memory Provider 在所有 Mode 下保持相同状态。
- `product_memories` 在未接入 Hermes 前必须明确标记为“本地记录”，不能宣称 Agent 已记住。
- Mode 偏好只保存在 Mode 状态，不写入用户长期事实记忆。

## 6. 建议代码边界

```text
lilsunspot/daemon/modes.py
  Mode 状态读取、保存和作用域解析

lilsunspot/daemon/mode_policy.py
  三滑杆到 Prompt/运行参数的编译

lilsunspot/daemon/mode_tools.py
  get/set Mode 产品工具

lilsunspot/daemon/prompt_layers.py
  产品基线、能力快照、Mode、交付层合并

lilsunspot/daemon/agent_runner.py
  创建 AIAgent 并注入 runtime policy、callbacks 和 toolsets

lilsunspot/daemon/conversations.py
  会话 Mode metadata、控制事件与消息映射

lilsunspot/daemon/mode_intents.py
  仅保留高置信本地命令解析，不再请求模型
```

## 7. 契约测试

新增 `test_mode_hermes_parity.py` 或等价测试组。

### 工具不变量

对每个 Mode 创建 Agent，断言除 Mode 产品工具外，以下工具面一致：

- file
- memory
- session_search
- skills
- vision
- MCP 动态工具
- delivery 工具
- approval 工具

### 文件不变量

所有 Mode 下验证：

- TXT 上传。
- PDF 上传。
- 图片上传与视觉状态。
- 已有附件返还。
- Markdown/CSV 文件生成。
- 二进制文件交付。
- 不泄露本地路径。
- 文件安全根目录一致。

### 对话不变量

验证：

- conversation_id 与 hermes_session_id 映射稳定。
- 普通消息不会被 Mode 路由吞掉。
- Mode 控制事件不会污染语义历史。
- session_search 不因 Mode 切换丢失正常消息。

### 记忆不变量

所有 Mode 下验证：

- Hermes Memory 开关一致。
- USER.md/MEMORY.md 加载一致。
- Session Search 结果一致。
- Memory 写审批一致。

### Provider 不变量

覆盖：

- Chat Completions。
- Responses API。
- Anthropic Messages。
- OpenRouter fallback。
- 本地 Ollama。

Mode 模块不得自行构造正式 provider HTTP 请求。

## 8. 资深用户验收场景

1. 工作对话切换务实模式后，Agent 仍可读取项目上下文、使用工具和交付文件。
2. 生活对话切换感性模式，不影响工作对话。
3. 微信联系人说“以后回复短一点”，只影响当前微信会话。
4. 切换 Mode 前后，Memory、Skills、MCP、Session Search 和审批保持可用。
5. `detail_level=30` 与 `detail_level=80` 有稳定且明显的输出差异。
6. `autonomy_level=80` 会主动完成安全步骤，但删除、外部发送和凭据操作仍请求审批。
7. 普通消息只产生一次正式 Agent 请求。
8. Mode 变化显示为状态事件，不污染项目问题搜索结果。
9. 任意 Mode 下上传、生成和返还文件均可工作。
10. Mode 配置损坏时回退到 balanced，Hermes 仍能正常启动和聊天。

## 9. 完成定义

满足以下条件后，本计划可标记完成：

- Mode 是会话级策略覆盖层，不是第二套 Agent。
- 正常聊天全部通过 Hermes `AIAgent`。
- Mode 不直接调用 provider。
- Prompt 分层职责清晰且能力描述动态生成。
- 三滑杆同时影响可测试的 Prompt 与运行参数。
- Clarify、工具状态和停止控制至少具备产品闭环。
- 文件、对话、记忆、Skills、MCP 在所有 Mode 下通过 parity 测试。
- 用户可见历史与 Hermes 语义历史的映射可解释、可诊断。
- 不需要为了 Mode 大面积修改 Hermes core。

## 10. 文档归档关系

- 产品总入口：`README.lilsunspot.md`
- 当前任务入口：`TASKS.md`
- 能力编排总计划：`lilsunspot/notes/model-capability-ux-plan.md`
- Mode/Hermes 专项计划：本文件
- 架构边界：`lilsunspot/notes/architecture.md`
- Hermes 能力盘点：`lilsunspot/notes/hermes-feature-inventory.md`
- QA：`lilsunspot/notes/qa-checklist.md`

本文件是 Mode 与 Hermes 能力对齐的专项 source of truth。后续实现记录应引用本文件，不要继续把完整设计追加到 `TASKS.md` 的单行状态记录中。