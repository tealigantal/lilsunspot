import { useEffect, useState } from "react";
import { deleteConversation, getConversations, searchSessions, updateConversation } from "../../api";
import type { Conversation, ConversationSearchResult } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";

type HistoryPageProps = {
  onOpenConversation: (conversationId: string) => void;
};

function isArchived(conversation: Conversation) {
  return Boolean(conversation.metadata?.archived_at);
}

function conversationLabel(conversation: Conversation) {
  if (conversation.kind === "weixin") {
    return conversation.metadata?.weixin_route_active ? "微信当前入口" : "微信对话";
  }
  if (conversation.kind === "personal") {
    return "个人默认";
  }
  return "桌面对话";
}

function resultLabel(result: ConversationSearchResult) {
  return result.type === "attachment" ? "附件" : "消息";
}

export function HistoryPage({ onOpenConversation }: HistoryPageProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [results, setResults] = useState<ConversationSearchResult[]>([]);
  const [query, setQuery] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    setMessage("");
    try {
      setConversations(await getConversations(includeArchived));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "历史记录读取失败。");
    }
  }

  useEffect(() => {
    void load();
  }, [includeArchived]);

  async function runSearch() {
    const text = query.trim();
    if (!text) {
      setResults([]);
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      setResults(await searchSessions(text, includeArchived));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "搜索失败。");
    } finally {
      setBusy(false);
    }
  }

  async function rename(conversation: Conversation) {
    const title = window.prompt("新的对话名称", conversation.title);
    if (title === null || !title.trim()) {
      return;
    }
    const updated = await updateConversation(conversation.id, { title: title.trim() });
    setConversations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function toggleArchive(conversation: Conversation) {
    const updated = await updateConversation(conversation.id, { archived: !isArchived(conversation) });
    if (!includeArchived && isArchived(updated)) {
      setConversations((current) => current.filter((item) => item.id !== updated.id));
      return;
    }
    setConversations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function remove(conversation: Conversation) {
    if (!window.confirm("确定删除这个对话吗？此操作不能撤销。")) {
      return;
    }
    await deleteConversation(conversation.id);
    setConversations((current) => current.filter((item) => item.id !== conversation.id));
  }

  return (
    <section className="productPage historyPage">
      <header className="productPageHeader">
        <div>
          <h2>历史</h2>
          <p>搜索桌面和微信聊天记录，打开结果后回到对应对话。</p>
        </div>
        <StatusBadge>{conversations.length} 个对话</StatusBadge>
      </header>

      <article className="productPanel historySearchPanel">
        <form
          className="conversationSearch"
          onSubmit={(event) => {
            event.preventDefault();
            void runSearch();
          }}
        >
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              if (!event.target.value.trim()) {
                setResults([]);
              }
            }}
            placeholder="搜索消息、附件摘要或文件名"
            aria-label="搜索历史"
          />
          <button type="submit" className="secondaryButton compactButton" disabled={busy}>
            {busy ? "搜索中" : "搜索"}
          </button>
        </form>
        <label className="archiveToggle">
          <input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />
          <span>包含归档</span>
        </label>
        {results.length > 0 && (
          <div className="historyResultGrid">
            {results.map((result) => (
              <button
                key={`${result.type}-${result.message_id}-${result.attachment_id}`}
                type="button"
                className="historyResult"
                onClick={() => onOpenConversation(result.conversation_id)}
              >
                <strong>{result.conversation_title}</strong>
                <span>{resultLabel(result)} · {result.snippet}</span>
              </button>
            ))}
          </div>
        )}
      </article>

      <div className="historyConversationGrid">
        {conversations.map((conversation) => (
          <article key={conversation.id} className="productPanel historyConversationCard">
            <header>
              <div>
                <strong>{conversation.title}</strong>
                <span>{conversationLabel(conversation)} · {conversation.updated_at}</span>
              </div>
              <StatusBadge tone={isArchived(conversation) ? "warning" : "neutral"}>{isArchived(conversation) ? "归档" : "可打开"}</StatusBadge>
            </header>
            <div className="actionRow">
              <button type="button" className="secondaryButton compactButton" onClick={() => onOpenConversation(conversation.id)}>
                打开
              </button>
              <button type="button" className="secondaryButton compactButton" onClick={() => void rename(conversation)}>
                改名
              </button>
              <button type="button" className="secondaryButton compactButton" onClick={() => void toggleArchive(conversation)}>
                {isArchived(conversation) ? "恢复" : "归档"}
              </button>
              <button type="button" className="secondaryButton compactButton dangerMiniButton" onClick={() => void remove(conversation)}>
                删除
              </button>
            </div>
          </article>
        ))}
      </div>
      {message && <p className="inlineStatus">{message}</p>}
    </section>
  );
}
