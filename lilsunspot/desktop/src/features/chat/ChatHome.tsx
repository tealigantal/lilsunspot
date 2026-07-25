import { useEffect, useState } from "react";
import type { AppBootstrapState, Conversation, ConversationAttachment, ConversationSearchResult, GenerationSelection, LilsunspotEvent } from "../../types";
import {
  branchConversationTurn,
  createConversation,
  deleteConversation,
  getConversations,
  getConversationMessages,
  listenDaemonEvents,
  retryConversationTurn,
  saveConversationSummary,
  searchConversations,
  sendConversationMessage,
  stopConversationTurn,
  subscribeDaemonEvents,
  undoConversationTurn,
  updateConversation
} from "../../api";
import type { CapabilityNode, ModelCapabilities } from "../../types";
import type { SettingsTab } from "../settings/SettingsDrawer";
import { ModeQuickPanel } from "../mode/ModeQuickPanel";
import { GenerationControlPanel } from "../mode/GenerationControlPanel";
import { useModeState } from "../mode/ModeState";
import { displayProvider } from "../model/ProviderCard";
import { ChatBlockedState } from "./ChatBlockedState";
import { ChatComposer } from "./ChatComposer";
import { ChatTranscript, type ChatMessage } from "./ChatTranscript";

type ChatHomeProps = {
  bootstrap: AppBootstrapState;
  initialMessages?: ChatMessage[];
  modelCapabilities: ModelCapabilities | null;
  onSetupModel: () => void;
  onRefresh: () => void;
  onOpenSettings: (tab?: SettingsTab) => void;
  requestedConversationId?: string;
  onRequestedConversationHandled?: () => void;
};

const EXAMPLE_PROMPTS = [
  { title: "帮我整理今天要做的三件事", note: "适合务实模式，输出清单" },
  { title: "我明天交方案但没开始", note: "先安抚，再给步骤" },
  { title: "切到务实一点", note: "自然语言调整回答风格" }
];

const PERSONAL_CONVERSATION_ID = "personal";
const MAX_UPLOAD_FILES = 5;
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

function mergeMessageList(current: ChatMessage[], incoming: ChatMessage) {
  const index = current.findIndex((item) => item.id === incoming.id);
  if (index >= 0) {
    const next = [...current];
    next[index] = { ...next[index], ...incoming, attachments: incoming.attachments || next[index].attachments || [] };
    return next;
  }
  return [...current, incoming];
}

function mergeAttachment(current: ChatMessage[], attachment: ConversationAttachment) {
  return current.map((message) => {
    if (message.id !== attachment.message_id) {
      return message;
    }
    const attachments = message.attachments || [];
    const index = attachments.findIndex((item) => item.id === attachment.id);
    const nextAttachments =
      index >= 0
        ? attachments.map((item) => (item.id === attachment.id ? { ...item, ...attachment } : item))
        : [...attachments, attachment];
    return { ...message, attachments: nextAttachments };
  });
}

function isArchived(conversation: Conversation) {
  const metadata = conversation.metadata || {};
  return typeof metadata.archived_at === "string" && metadata.archived_at.length > 0;
}

function isWeixinActive(conversation: Conversation) {
  return conversation.kind === "weixin" && conversation.metadata?.weixin_route_active === true;
}

function hasWeixinRoute(
  conversation: Conversation | undefined
): conversation is Conversation & { metadata: Record<string, unknown> & { weixin_route: Record<string, unknown> } } {
  return Boolean(
    conversation?.kind === "weixin" && conversation.metadata?.weixin_route && typeof conversation.metadata.weixin_route === "object"
  );
}

function conversationKindLabel(conversation: Conversation) {
  if (conversation.kind === "weixin") {
    return isWeixinActive(conversation) ? "微信消息进入这里" : "微信对话";
  }
  if (conversation.id === PERSONAL_CONVERSATION_ID) {
    return "默认";
  }
  return "桌面";
}

function weixinRecipientFromConversation(conversation: Conversation | undefined) {
  const route = hasWeixinRoute(conversation) ? conversation.metadata.weixin_route : null;
  if (!route) {
    return "";
  }
  return String(route.chat_id || route.user_id || "").trim();
}

function capabilityNode(capabilities: ModelCapabilities | null, id: string): CapabilityNode | null {
  const graph = capabilities?.capability_graph;
  return graph?.by_id?.[id] || graph?.nodes?.find((node) => node.id === id) || null;
}

export function ChatHome({
  bootstrap,
  initialMessages = [],
  modelCapabilities,
  onSetupModel,
  onRefresh,
  onOpenSettings,
  requestedConversationId = "",
  onRequestedConversationHandled
}: ChatHomeProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState(PERSONAL_CONVERSATION_ID);
  const [showArchived, setShowArchived] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ConversationSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [input, setInput] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<File[]>([]);
  const [sendError, setSendError] = useState("");
  const [actionBusy, setActionBusy] = useState("");
  const [busy, setBusy] = useState(false);
  const [generationOverride, setGenerationOverride] = useState<GenerationSelection | null>(null);
  const modeState = useModeState();
  const activeConversation = conversations.find((item) => item.id === activeConversationId);
  const activeWeixinRecipient = weixinRecipientFromConversation(activeConversation);
  const weixinSendTarget = activeWeixinRecipient
    ? { recipient: activeWeixinRecipient, label: activeConversation?.title || "当前微信对话" }
    : null;
  const headerHint =
    activeConversation && hasWeixinRoute(activeConversation)
      ? isWeixinActive(activeConversation)
        ? `微信消息正在进入：${activeConversation.title}`
        : "这个微信对话不会接收新消息，除非你让微信消息进入这里。"
      : "桌面聊天和微信私聊按对话分开记录。";
  const hasGeneratingMessage = messages.some((message) => message.status === "generating");

  useEffect(() => {
    setMessages(initialMessages);
    setSendError("");
  }, [initialMessages]);

  useEffect(() => {
    setGenerationOverride(null);
  }, [activeConversationId]);

  useEffect(() => {
    if (bootstrap.stage !== "chat_ready" || !bootstrap.runtime.configured) {
      return;
    }
    let mounted = true;

    async function loadConversationList() {
      try {
        let list = await getConversations(showArchived);
        if (list.length === 0) {
          const created = await createConversation({ title: "新对话" });
          list = [created];
        }
        if (!mounted) {
          return;
        }
        setConversations(list);
        if (!list.some((item) => item.id === activeConversationId)) {
          setActiveConversationId(list[0]?.id || PERSONAL_CONVERSATION_ID);
        }
      } catch {
        if (mounted) {
          setConversations([]);
        }
      }
    }

    void loadConversationList();
    return () => {
      mounted = false;
    };
  }, [bootstrap.stage, bootstrap.runtime.configured, showArchived]);

  useEffect(() => {
    if (!requestedConversationId || requestedConversationId === activeConversationId) {
      return;
    }
    setActiveConversationId(requestedConversationId);
    onRequestedConversationHandled?.();
  }, [requestedConversationId, activeConversationId, onRequestedConversationHandled]);

  useEffect(() => {
    if (bootstrap.stage !== "chat_ready" || !bootstrap.runtime.configured || !activeConversationId) {
      return;
    }
    let mounted = true;

    async function loadConversationMessages() {
      try {
        const recent = await getConversationMessages(activeConversationId);
        if (mounted) {
          setMessages(recent);
        }
      } catch {
        if (mounted) {
          setMessages([]);
        }
      }
    }

    void loadConversationMessages();
    return () => {
      mounted = false;
    };
  }, [bootstrap.stage, bootstrap.runtime.configured, activeConversationId]);

  useEffect(() => {
    if (bootstrap.stage !== "chat_ready" || !bootstrap.runtime.configured || !activeConversationId) {
      return;
    }
    modeState.setActiveConversationId(activeConversationId);
    void modeState.reload(activeConversationId);
  }, [bootstrap.stage, bootstrap.runtime.configured, activeConversationId, modeState.setActiveConversationId, modeState.reload]);

  useEffect(() => {
    if (bootstrap.stage !== "chat_ready" || !bootstrap.runtime.configured) {
      return;
    }
    let mounted = true;
    let cleanup: (() => void) | undefined;

    async function refreshList() {
      try {
        const list = await getConversations(showArchived);
        if (mounted) {
          setConversations(list);
        }
      } catch {
        // The message stream remains usable; list refresh will retry on the next event.
      }
    }

    function applyEvent(event: LilsunspotEvent) {
      const payload = event.data || {};
      const eventConversationId = typeof payload.conversation_id === "string" ? payload.conversation_id : "";
      if (payload.message) {
        if (eventConversationId === activeConversationId) {
          setSendError("");
          setMessages((current) => mergeMessageList(current, payload.message as ChatMessage));
        }
        void refreshList();
      }
      if (payload.attachment) {
        if (eventConversationId === activeConversationId) {
          setMessages((current) => mergeAttachment(current, payload.attachment as ConversationAttachment));
        }
        void refreshList();
      }
      if (event.event.startsWith("conversation.")) {
        void refreshList();
      }
      if (event.event === "mode.changed" && payload.mode) {
        return;
      }
    }

    async function subscribe() {
      try {
        cleanup = await listenDaemonEvents(applyEvent);
        await subscribeDaemonEvents();
      } catch {
        cleanup = undefined;
      }
    }

    void subscribe();
    return () => {
      mounted = false;
      cleanup?.();
    };
  }, [bootstrap.stage, bootstrap.runtime.configured, activeConversationId, showArchived]);

  if (bootstrap.stage !== "chat_ready" || !bootstrap.runtime.configured) {
    return <ChatBlockedState bootstrap={bootstrap} onSetupModel={onSetupModel} onRetry={onRefresh} />;
  }

  async function refreshConversations(preferredId = activeConversationId) {
    const list = await getConversations(showArchived);
    setConversations(list);
    if (preferredId && list.some((item) => item.id === preferredId)) {
      setActiveConversationId(preferredId);
      return list;
    }
    if (list[0]) {
      setActiveConversationId(list[0].id);
    }
    return list;
  }

  async function createDesktopConversation() {
    const conversation = await createConversation({ title: "新对话" });
    setConversations((current) => [conversation, ...current.filter((item) => item.id !== conversation.id)]);
    setActiveConversationId(conversation.id);
    setMessages([]);
  }

  async function runSearch() {
    const query = searchQuery.trim();
    if (!query) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    try {
      const results = await searchConversations(query, showArchived);
      setSearchResults(results);
    } finally {
      setSearching(false);
    }
  }

  async function openSearchResult(result: ConversationSearchResult) {
    if (!conversations.some((item) => item.id === result.conversation_id)) {
      await refreshConversations(result.conversation_id);
    }
    setActiveConversationId(result.conversation_id);
  }

  async function createWeixinThread() {
    if (!hasWeixinRoute(activeConversation)) {
      return;
    }
    const route = activeConversation.metadata?.weixin_route as Record<string, unknown>;
    const conversation = await createConversation({
      title: `${activeConversation?.title || "微信私聊"} 新对话`,
      kind: "weixin",
      metadata: { weixin_route: route }
    });
    await refreshConversations(conversation.id);
    setMessages([]);
  }

  async function activateWeixinConversation(conversation: Conversation) {
    if (!hasWeixinRoute(conversation) || isWeixinActive(conversation)) {
      return;
    }
    const updated = await updateConversation(conversation.id, { weixin_route_active: true });
    await refreshConversations(updated.id);
  }

  async function renameActiveConversation(conversation: Conversation) {
    const title = window.prompt("新的对话名称", conversation.title);
    if (title === null || !title.trim()) {
      return;
    }
    const updated = await updateConversation(conversation.id, { title: title.trim() });
    setConversations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function archiveConversation(conversation: Conversation) {
    const updated = await updateConversation(conversation.id, { archived: !isArchived(conversation) });
    await refreshConversations(activeConversationId === conversation.id && isArchived(updated) ? "" : activeConversationId);
  }

  async function removeConversation(conversation: Conversation) {
    if (!window.confirm("确定删除这个对话吗？此操作不能撤销。")) {
      return;
    }
    await deleteConversation(conversation.id);
    const remaining = await getConversations(false);
    if (remaining.length > 0) {
      setConversations(showArchived ? await getConversations(true) : remaining);
      setActiveConversationId(remaining[0].id);
      return;
    }
    const created = await createConversation({ title: "新对话" });
    setConversations([created]);
    setActiveConversationId(created.id);
    setMessages([]);
  }

  async function refreshActiveMessages() {
    const recent = await getConversationMessages(activeConversationId);
    setMessages(recent);
    void refreshConversations(activeConversationId);
  }

  async function stopTurn() {
    setActionBusy("stop");
    setSendError("");
    try {
      const result = await stopConversationTurn(activeConversationId, "用户在桌面停止了当前任务。");
      setSendError(result.message || "已请求停止当前任务。");
      await refreshActiveMessages();
    } catch (error) {
      setSendError(error instanceof Error ? error.message : "停止失败。");
    } finally {
      setActionBusy("");
    }
  }

  async function retryTurn() {
    setActionBusy("retry");
    setSendError("");
    try {
      const result = await retryConversationTurn(activeConversationId);
      if (result.user_message && result.assistant_message) {
        setMessages((current) => mergeMessageList(mergeMessageList(current, result.user_message!), result.assistant_message!));
      }
      setSendError("已按上一条用户消息重新发起。");
      void refreshConversations(activeConversationId);
    } catch (error) {
      setSendError(error instanceof Error ? error.message : "重试失败。");
    } finally {
      setActionBusy("");
    }
  }

  async function undoTurn() {
    setActionBusy("undo");
    setSendError("");
    try {
      const result = await undoConversationTurn(activeConversationId);
      setSendError(result.message || "已撤销上一轮。");
      await refreshActiveMessages();
    } catch (error) {
      setSendError(error instanceof Error ? error.message : "撤销失败。");
    } finally {
      setActionBusy("");
    }
  }

  async function branchTurn() {
    const title = window.prompt("新分支名称", `${activeConversation?.title || "对话"} 分支`);
    if (title === null) {
      return;
    }
    setActionBusy("branch");
    setSendError("");
    try {
      const result = await branchConversationTurn(activeConversationId, title.trim());
      if (result.conversation) {
        await refreshConversations(result.conversation.id);
        setSendError(`已创建分支，复制 ${result.copied_messages ?? 0} 条文本消息。`);
      }
    } catch (error) {
      setSendError(error instanceof Error ? error.message : "创建分支失败。");
    } finally {
      setActionBusy("");
    }
  }

  async function saveSummary() {
    setActionBusy("summary");
    setSendError("");
    try {
      const result = await saveConversationSummary(activeConversationId);
      setSendError(result.message || "已保存为本地记录。");
    } catch (error) {
      setSendError(error instanceof Error ? error.message : "保存摘要失败。");
    } finally {
      setActionBusy("");
    }
  }

  async function send() {
    const message = input.trim();
    const attachments = pendingAttachments;
    if (!message && attachments.length === 0) {
      return;
    }
    const oversized = attachments.find((file) => file.size > MAX_UPLOAD_BYTES);
    if (oversized) {
      setSendError(`附件 ${oversized.name} 超过 25 MB，请换一个更小的文件。`);
      return;
    }
    setSendError("");
    const userMessage: ChatMessage = {
      id: `pending-${Date.now()}-user`,
      conversation_id: activeConversationId,
      source: "desktop",
      role: "user",
      text: message || `上传了 ${attachments.length} 个附件。`,
      attachments: [],
      created_at: new Date().toISOString(),
      status: "sent"
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setPendingAttachments([]);
    setBusy(true);
    const turnGenerationOverride = generationOverride;
    if (turnGenerationOverride) {
      setGenerationOverride(null);
    }
    try {
      const result = await sendConversationMessage(activeConversationId, message, attachments, turnGenerationOverride);
      setMessages((current) => current.filter((item) => item.id !== userMessage.id));
      setSendError("");
      void refreshConversations(activeConversationId);
      if (result.ok) {
        const assistantMessage = result.accepted
          ? result.assistant_message
          : {
              ...result.assistant_message,
              metadata: {
                ...(result.assistant_message.metadata || {}),
                engine: `${displayProvider(result.chat.ok ? result.chat.provider : "")} / ${result.chat.ok ? result.chat.model : ""}`
              }
            };
        setMessages((current) =>
          mergeMessageList(mergeMessageList(current, result.user_message), assistantMessage)
        );
        if (result.chat.ok && result.chat.mode_intent) {
          void modeState.reload();
        }
      } else {
        setMessages((current) => mergeMessageList(mergeMessageList(current, result.user_message), result.assistant_message));
      }
    } catch (error) {
      setPendingAttachments(attachments);
      setMessages((current) => current.filter((item) => item.id !== userMessage.id));
      setSendError(`${error instanceof Error ? error.message : "发送失败。"}\n这次发送结果还没有被本地界面确认；如果稍后出现回复，此提示会自动消失。`);
    } finally {
      setBusy(false);
    }
  }

  function addPendingFiles(files: FileList) {
    const incoming = Array.from(files);
    setPendingAttachments((current) => {
      const next = [...current];
      for (const file of incoming) {
        if (next.length >= MAX_UPLOAD_FILES) {
          break;
        }
        const duplicate = next.some((item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified);
        if (!duplicate) {
          next.push(file);
        }
      }
      return next;
    });
  }

  function removePendingAttachment(index: number) {
    setPendingAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  return (
    <section className="chatHome">
      <aside className="conversationRail" aria-label="对话列表">
        <div className="conversationRailHeader">
          <strong>对话</strong>
          <button type="button" className="compactButton" onClick={() => void createDesktopConversation()}>
            新建桌面对话
          </button>
        </div>
        <label className="archiveToggle">
          <input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} />
          <span>显示归档</span>
        </label>
        <form
          className="conversationSearch"
          onSubmit={(event) => {
            event.preventDefault();
            void runSearch();
          }}
        >
          <input
            value={searchQuery}
            onChange={(event) => {
              setSearchQuery(event.target.value);
              if (!event.target.value.trim()) {
                setSearchResults([]);
              }
            }}
            placeholder="搜索聊天记录"
            aria-label="搜索聊天记录"
          />
          <button type="submit" className="secondaryButton compactButton" disabled={searching}>
            {searching ? "搜索中" : "搜索"}
          </button>
        </form>
        {searchResults.length > 0 && (
          <div className="conversationSearchResults" aria-label="搜索结果">
            {searchResults.map((result) => (
              <button key={`${result.type}-${result.message_id}-${result.attachment_id}`} type="button" onClick={() => void openSearchResult(result)}>
                <strong>{result.conversation_title}</strong>
                <span>{result.type === "attachment" ? "附件" : "消息"} · {result.snippet}</span>
              </button>
            ))}
          </div>
        )}
        <div className="conversationList">
          {conversations.map((conversation) => (
            <article
              key={conversation.id}
              className={`conversationItem ${conversation.id === activeConversationId ? "active" : ""} ${isArchived(conversation) ? "archived" : ""}`}
            >
              <button type="button" className="conversationSelect" onClick={() => setActiveConversationId(conversation.id)}>
                <strong>{conversation.title}</strong>
                <span>{conversationKindLabel(conversation)}</span>
              </button>
              <div className="conversationActions">
                <button type="button" className="secondaryButton compactButton" onClick={() => void renameActiveConversation(conversation)}>
                  改名
                </button>
                <button type="button" className="secondaryButton compactButton" onClick={() => void archiveConversation(conversation)}>
                  {isArchived(conversation) ? "恢复" : "归档"}
                </button>
                {conversation.kind === "weixin" && !isWeixinActive(conversation) && (
                  <button type="button" className="secondaryButton compactButton" onClick={() => void activateWeixinConversation(conversation)}>
                    让微信消息进入这里
                  </button>
                )}
                <button type="button" className="secondaryButton compactButton dangerMiniButton" onClick={() => void removeConversation(conversation)}>
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      </aside>
      <article className="chatMainPanel">
        <header className="panelHeader chatPanelHeader">
          <div>
            <h2>{activeConversation?.title || "今日任务台"}</h2>
            <p>{headerHint}</p>
          </div>
          <div className="chatHeaderActions">
            <button
              type="button"
              className="secondaryButton compactButton"
              onClick={() => void stopTurn()}
              disabled={!hasGeneratingMessage || actionBusy === "stop"}
            >
              停止
            </button>
            <button type="button" className="secondaryButton compactButton" onClick={() => void retryTurn()} disabled={Boolean(actionBusy)}>
              重试
            </button>
            <button type="button" className="secondaryButton compactButton" onClick={() => void undoTurn()} disabled={Boolean(actionBusy)}>
              撤销
            </button>
            <button type="button" className="secondaryButton compactButton" onClick={() => void branchTurn()} disabled={Boolean(actionBusy)}>
              分支
            </button>
            <button type="button" className="secondaryButton compactButton" onClick={() => void saveSummary()} disabled={Boolean(actionBusy)}>
              保存摘要
            </button>
            {hasWeixinRoute(activeConversation) && (
              <button type="button" className="secondaryButton compactButton" onClick={() => void createWeixinThread()}>
                为这个微信联系人开新对话
              </button>
            )}
            <button type="button" className="secondaryButton compactButton" onClick={() => onOpenSettings("model")}>
              模型服务
            </button>
          </div>
        </header>
        <ChatTranscript messages={messages} examples={EXAMPLE_PROMPTS} onExampleSelect={setInput} weixinSendTarget={weixinSendTarget} />
        {sendError && (
          <div className="composerError" role="alert">
            {sendError}
          </div>
        )}
        <ChatComposer
          value={input}
          onChange={setInput}
          onSend={send}
          attachments={pendingAttachments}
          onAddFiles={addPendingFiles}
          onRemoveAttachment={removePendingAttachment}
          imageCapability={capabilityNode(modelCapabilities, "image.read")}
          onOpenVisionSettings={() => onOpenSettings("model")}
          busy={busy}
          placeholder="输入你想问的内容"
        />
      </article>
      <aside className="chatSidePanel" aria-label="生成控制与表达风格">
        <GenerationControlPanel
          conversationId={activeConversationId}
          turnOverride={generationOverride}
          onTurnOverrideChange={setGenerationOverride}
        />
        <ModeQuickPanel conversationId={activeConversationId} />
      </aside>
    </section>
  );
}
