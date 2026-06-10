import lilsunspotIcon from "../../assets/lilsunspot-icon.png";
import { openAttachment } from "../../api";
import type { ConversationAttachment, ConversationMessage } from "../../types";

export type ChatMessage = Partial<ConversationMessage> & {
  id: string;
  role: "user" | "assistant" | "system" | string;
  text: string;
  attachments?: ConversationAttachment[];
  error?: boolean;
};

type ChatTranscriptProps = {
  messages: ChatMessage[];
  examples?: { title: string; note: string }[];
  onExampleSelect?: (value: string) => void;
};

const ASSISTANT_NAME = "小黑子";

function sourceLabel(message: ChatMessage) {
  if (message.source === "weixin") {
    return "微信";
  }
  if (message.source === "desktop") {
    return "桌面";
  }
  if (message.source === "system" || message.role === "system") {
    return "系统";
  }
  return message.source || "本地";
}

function roleLabel(message: ChatMessage) {
  if (message.role === "user") {
    return message.source === "weixin" ? "微信私聊" : "你";
  }
  if (message.role === "system") {
    return "状态";
  }
  return ASSISTANT_NAME;
}

function formatBytes(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function attachmentStatusText(attachment: ConversationAttachment) {
  if (attachment.summary_status === "recognized") {
    return "已识别";
  }
  if (attachment.summary_status === "preview_only") {
    return "仅预览";
  }
  if (attachment.summary_status === "ready") {
    return "可读";
  }
  if (attachment.summary_status === "pending") {
    return "读取中";
  }
  if (attachment.summary_status === "too_large") {
    return "文件较大";
  }
  return "仅文件";
}

function attachmentSummaryLabel(attachment: ConversationAttachment) {
  if (attachment.summary_status === "recognized") {
    return "查看识别结果";
  }
  if (attachment.summary_text) {
    return "查看摘要";
  }
  return "查看说明";
}

function AttachmentCard({ attachment }: { attachment: ConversationAttachment }) {
  async function copySummary() {
    const text = attachment.summary_text || attachment.reason_cn || `${attachment.file_name} 已收到。`;
    await navigator.clipboard?.writeText(text);
  }

  async function openStoredAttachment() {
    await openAttachment(attachment.id);
  }

  const isImage = attachment.preview_data_url && attachment.mime_type.startsWith("image/");
  return (
    <article className="attachmentCard">
      {isImage && (
        <img className="attachmentPreview" src={attachment.preview_data_url} alt={attachment.file_name} />
      )}
      <div className="attachmentHeader">
        <div>
          <strong>{attachment.file_name}</strong>
          <span>
            {attachment.mime_type || "未知类型"} · {formatBytes(attachment.size_bytes)}
          </span>
        </div>
        <em>{attachmentStatusText(attachment)}</em>
      </div>
      {(attachment.summary_text || attachment.reason_cn) && (
        <details className="attachmentSummary">
          <summary>{attachmentSummaryLabel(attachment)}</summary>
          <p>{attachment.summary_text || attachment.reason_cn}</p>
        </details>
      )}
      <div className="attachmentActions">
        <button type="button" className="secondaryButton compactButton" onClick={() => void openStoredAttachment()}>
          打开
        </button>
        <button type="button" className="secondaryButton compactButton" onClick={() => void copySummary()}>
          复制摘要
        </button>
      </div>
    </article>
  );
}

export function ChatTranscript({ messages, examples = [], onExampleSelect }: ChatTranscriptProps) {
  return (
    <div className="chatTranscript" aria-live="polite">
      {messages.length === 0 ? (
        <div className="emptyChat">
          <div className="exampleTaskGrid">
            {examples.map((example) => (
              <button key={example.title} type="button" className="exampleTaskCard" onClick={() => onExampleSelect?.(example.title)}>
                <strong>{example.title}</strong>
                <span>{example.note}</span>
                <em>示例</em>
              </button>
            ))}
          </div>
          <article className="assistantBubble chatBubble seedBubble">
            <img className="assistantAvatar" src={lilsunspotIcon} alt={`${ASSISTANT_NAME}头像`} />
            <div className="chatBubbleBody">
              <span>{ASSISTANT_NAME}</span>
              <p>你可以直接问，也可以让我拆任务。当前输出模式会先给结论，再给必要步骤。</p>
            </div>
          </article>
        </div>
      ) : (
        messages.map((message) => (
          <article
            key={message.id}
            className={`chatBubble ${message.role === "user" ? "userBubble" : message.role === "system" ? "systemBubble" : "assistantBubble"} ${message.status === "error" || message.error ? "errorBubble" : ""}`}
          >
            {message.role === "assistant" && (
              <img className="assistantAvatar" src={lilsunspotIcon} alt={`${ASSISTANT_NAME}头像`} />
            )}
            <div className="chatBubbleBody">
              <span>
                {roleLabel(message)} · {sourceLabel(message)}
                {message.status === "error" ? " · 失败" : ""}
              </span>
              <p>{message.text}</p>
              {(message.attachments || []).length > 0 && (
                <div className="attachmentList">
                  {(message.attachments || []).map((attachment) => (
                    <AttachmentCard key={attachment.id} attachment={attachment} />
                  ))}
                </div>
              )}
              {typeof message.metadata?.engine === "string" && <em>{message.metadata.engine}</em>}
            </div>
          </article>
        ))
      )}
    </div>
  );
}
