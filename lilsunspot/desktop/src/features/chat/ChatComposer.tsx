type ChatComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  busy?: boolean;
  disabled?: boolean;
  placeholder?: string;
};

export function ChatComposer({ value, onChange, onSend, busy = false, disabled = false, placeholder }: ChatComposerProps) {
  return (
    <div className="chatComposer">
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
      <button type="button" onClick={onSend} disabled={busy || disabled || !value.trim()}>
        {busy ? "发送中" : "发送"}
      </button>
    </div>
  );
}
