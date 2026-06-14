import type { CapabilityNode } from "../../types";

type ChatComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  attachments?: File[];
  onAddFiles?: (files: FileList) => void;
  onRemoveAttachment?: (index: number) => void;
  imageCapability?: CapabilityNode | null;
  onOpenVisionSettings?: () => void;
  busy?: boolean;
  disabled?: boolean;
  placeholder?: string;
};

function formatUploadSize(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function isImageFile(file: File) {
  const name = file.name.toLowerCase();
  return file.type.startsWith("image/") || /\.(png|jpg|jpeg|gif|webp|bmp|svg)$/.test(name);
}

function imageCapabilityText(node: CapabilityNode | null | undefined) {
  if (!node) {
    return "图片能力状态暂时不可读取。";
  }
  if (node.status === "ready") {
    return node.user_message_cn || "图片会由当前模型识别。";
  }
  if (node.status === "degraded") {
    return node.user_message_cn || "图片会先由图片识别模型读取，再交给当前聊天模型。";
  }
  return node.user_message_cn || "图片会先保存和预览，当前还不能识别内容。";
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  attachments = [],
  onAddFiles,
  onRemoveAttachment,
  imageCapability,
  onOpenVisionSettings,
  busy = false,
  disabled = false,
  placeholder
}: ChatComposerProps) {
  const canSend = Boolean(value.trim() || attachments.length > 0);
  const hasImageAttachment = attachments.some(isImageFile);
  const showVisionAction = hasImageAttachment && imageCapability?.status !== "ready";
  return (
    <div className="chatComposer">
      <div className="composerInputStack">
        {attachments.length > 0 && (
          <div className="composerAttachmentList" aria-label="待发送附件">
            {attachments.map((file, index) => (
              <span key={`${file.name}-${file.size}-${index}`} className="composerAttachmentChip">
                <strong>{file.name}</strong>
                <em>{formatUploadSize(file.size)}</em>
                <button type="button" onClick={() => onRemoveAttachment?.(index)} disabled={busy || disabled} aria-label={`移除 ${file.name}`}>
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        {hasImageAttachment && (
          <div className={`composerCapabilityHint ${imageCapability?.status || "unknown"}`}>
            <span>{imageCapabilityText(imageCapability)}</span>
            {showVisionAction && onOpenVisionSettings && (
              <button type="button" className="secondaryButton compactButton" onClick={onOpenVisionSettings} disabled={busy || disabled}>
                {imageCapability?.status === "degraded" ? "检查设置" : "添加图片识别"}
              </button>
            )}
          </div>
        )}
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
              onSend();
            }
          }}
          rows={3}
          disabled={busy || disabled}
          placeholder={placeholder || "输入你想问的内容"}
        />
      </div>
      <div className="composerActions">
        <label className={`composerFileButton ${busy || disabled ? "disabled" : ""}`}>
          <input
            type="file"
            multiple
            disabled={busy || disabled}
            accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.md,.json,.yaml,.yml,.log,audio/*,video/*"
            onChange={(event) => {
              if (event.target.files?.length) {
                onAddFiles?.(event.target.files);
              }
              event.currentTarget.value = "";
            }}
          />
          附件
        </label>
        <button type="button" onClick={onSend} disabled={busy || disabled || !canSend}>
          {busy ? "发送中" : "发送"}
        </button>
      </div>
    </div>
  );
}
