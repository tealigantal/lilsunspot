import { useState } from "react";
import lilsunspotIcon from "../../assets/lilsunspot-icon.png";
import { openAttachment, sendWeixinMessage } from "../../api";
import type { ConversationAttachment, ConversationMessage, GenerationExecution } from "../../types";

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
  weixinSendTarget?: WeixinSendTarget | null;
};

export type WeixinSendTarget = {
  recipient: string;
  label: string;
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

function deliveryStatusText(metadata: Record<string, unknown> | undefined) {
  const delivery = metadata?.delivery;
  if (!delivery || typeof delivery !== "object") {
    return "";
  }
  const value = delivery as Record<string, unknown>;
  const status = String(value.status || "none");
  const deliveredCount = Number(value.delivered_count || 0);
  const rejectedCount = Number(value.rejected_count || 0);
  if (status === "partial") {
    return `已返还 ${deliveredCount} 个附件，${rejectedCount} 个附件未能返还。`;
  }
  if (status === "rejected") {
    const reasonText = String(value.reason_text || "");
    return reasonText || "附件没有返还成功。";
  }
  return "";
}

function generationExecution(metadata: Record<string, unknown> | undefined): GenerationExecution | null {
  const value = metadata?.generation_execution;
  if (!value || typeof value !== "object") {
    return null;
  }
  return value as GenerationExecution;
}

function GenerationDetails({ execution }: { execution: GenerationExecution }) {
  return (
    <details className="generationReplyDetails">
      <summary>本次生成详情</summary>
      <dl>
        <div><dt>模型</dt><dd>{execution.provider} / {execution.model}</dd></div>
        <div><dt>模式</dt><dd>{execution.mode_label || execution.mode}</dd></div>
        <div><dt>推理强度</dt><dd>{execution.reasoning_effort || "模型默认"}</dd></div>
        <div><dt>工具迭代</dt><dd>{execution.tool_iterations} / {execution.max_iterations}</dd></div>
        <div><dt>兼容降级</dt><dd>{execution.automatic_downgrade ? `是${execution.retry_count ? `，安全重试 ${execution.retry_count} 次` : ""}` : "否"}</dd></div>
      </dl>
      <div className="generationParameterTags">
        {Object.entries(execution.effective_parameters || {}).map(([key, value]) => (
          <span key={key}>{key}: {String(value)}</span>
        ))}
        {Object.keys(execution.effective_parameters || {}).length === 0 && <span>使用模型默认生成参数</span>}
      </div>
      {execution.omitted_parameters?.length > 0 && (
        <ul>
          {execution.omitted_parameters.map((item) => (
            <li key={item.parameter}><b>{item.parameter}</b>：{item.reason || "当前模型未使用此参数。"}</li>
          ))}
        </ul>
      )}
    </details>
  );
}

function GenerationDetailsForMetadata({ metadata }: { metadata: Record<string, unknown> | undefined }) {
  const execution = generationExecution(metadata);
  return execution ? <GenerationDetails execution={execution} /> : null;
}

function AttachmentCard({
  attachment,
  weixinSendTarget
}: {
  attachment: ConversationAttachment;
  weixinSendTarget?: WeixinSendTarget | null;
}) {
  const [confirming, setConfirming] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");
  const [sendStatus, setSendStatus] = useState("");
  const [sending, setSending] = useState(false);

  async function copySummary() {
    const text = attachment.summary_text || attachment.reason_cn || `${attachment.file_name} 已收到。`;
    await navigator.clipboard?.writeText(text);
  }

  async function openStoredAttachment() {
    await openAttachment(attachment.id);
  }

  function openWeixinConfirm() {
    setDraftMessage(`发你一个文件：${attachment.file_name}`);
    setSendStatus("");
    setConfirming(true);
  }

  async function confirmSendToWeixin() {
    if (!weixinSendTarget?.recipient) {
      setSendStatus("这个附件只能在微信对话里发回微信。");
      return;
    }
    const message = draftMessage.trim() || `发你一个文件：${attachment.file_name}`;
    setSending(true);
    setSendStatus("正在发送到微信。");
    try {
      const result = await sendWeixinMessage(weixinSendTarget.recipient, message, [attachment.id]);
      if (!result.ok) {
        setSendStatus(result.delivery?.message || result.message || "微信发送失败。");
        return;
      }
      setConfirming(false);
      setSendStatus(result.delivery?.message || result.message || "已发到微信。");
    } catch (error) {
      setSendStatus(error instanceof Error ? error.message : "微信发送失败。");
    } finally {
      setSending(false);
    }
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
        {weixinSendTarget?.recipient && (
          <button type="button" className="secondaryButton compactButton" onClick={openWeixinConfirm}>
            发到微信
          </button>
        )}
      </div>
      {confirming && weixinSendTarget?.recipient && (
        <div className="weixinSendConfirm">
          <span>发给：{weixinSendTarget.label}</span>
          <textarea
            value={draftMessage}
            onChange={(event) => setDraftMessage(event.target.value)}
            rows={3}
            aria-label="微信发送说明"
          />
          <div>
            <button type="button" className="secondaryButton compactButton" onClick={() => setConfirming(false)} disabled={sending}>
              取消
            </button>
            <button type="button" className="compactButton" onClick={() => void confirmSendToWeixin()} disabled={sending}>
              {sending ? "发送中" : "确认发送"}
            </button>
          </div>
        </div>
      )}
      {sendStatus && (
        <p className="attachmentSendStatus" aria-live="polite">
          {sendStatus}
        </p>
      )}
    </article>
  );
}

export function ChatTranscript({ messages, examples = [], onExampleSelect, weixinSendTarget = null }: ChatTranscriptProps) {
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
            className={`chatBubble ${message.role === "user" ? "userBubble" : message.role === "system" ? "systemBubble" : "assistantBubble"} ${message.status === "error" || message.error ? "errorBubble" : ""} ${message.status === "generating" ? "generatingBubble" : ""}`}
          >
            {message.role === "assistant" && (
              <img className="assistantAvatar" src={lilsunspotIcon} alt={`${ASSISTANT_NAME}头像`} />
            )}
            <div className="chatBubbleBody">
              <span>
                {roleLabel(message)} · {sourceLabel(message)}
                {message.status === "error" ? " · 失败" : ""}
                {message.status === "generating" ? " · 正在回复" : ""}
              </span>
              <p>{message.text}</p>
              {(message.attachments || []).length > 0 && (
                <div className="attachmentList">
                  {(message.attachments || []).map((attachment) => (
                    <AttachmentCard key={attachment.id} attachment={attachment} weixinSendTarget={weixinSendTarget} />
                  ))}
                </div>
              )}
              {deliveryStatusText(message.metadata) && <em>{deliveryStatusText(message.metadata)}</em>}
              {message.role === "assistant" && <GenerationDetailsForMetadata metadata={message.metadata} />}
            </div>
          </article>
        ))
      )}
    </div>
  );
}
