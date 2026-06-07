import { useEffect, useState } from "react";
import type { AppBootstrapState, CurrentMode } from "../../types";
import { getCurrentMode, sendChatMessage } from "../../api";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { ModeQuickPanel, modeName } from "../mode/ModeQuickPanel";
import { displayProvider } from "../model/ProviderCard";
import { ChatBlockedState } from "./ChatBlockedState";
import { ChatComposer } from "./ChatComposer";
import { ChatTranscript, type ChatMessage } from "./ChatTranscript";

type ChatHomeProps = {
  bootstrap: AppBootstrapState;
  initialMessages?: ChatMessage[];
  onSetupModel: () => void;
  onRefresh: () => void;
  onOpenSettings: () => void;
};

export function ChatHome({ bootstrap, initialMessages = [], onSetupModel, onRefresh, onOpenSettings }: ChatHomeProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<CurrentMode | null>(null);
  const [modeOpen, setModeOpen] = useState(false);

  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  useEffect(() => {
    let mounted = true;
    async function loadMode() {
      try {
        const current = await getCurrentMode();
        if (mounted) {
          setMode(current);
        }
      } catch {
        if (mounted) {
          setMode(null);
        }
      }
    }
    void loadMode();
    return () => {
      mounted = false;
    };
  }, []);

  if (bootstrap.stage !== "chat_ready" || !bootstrap.runtime.configured) {
    return <ChatBlockedState bootstrap={bootstrap} onSetupModel={onSetupModel} onRetry={onRefresh} />;
  }

  async function send() {
    const message = input.trim();
    if (!message) {
      return;
    }
    const userMessage: ChatMessage = { id: `${Date.now()}-user`, role: "user", text: message };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setBusy(true);
    try {
      const result = await sendChatMessage(message);
      if (result.ok) {
        setMessages((current) => [
          ...current,
          {
            id: `${Date.now()}-assistant`,
            role: "assistant",
            text: result.reply,
            meta: `${displayProvider(result.provider)} / ${result.model}`
          }
        ]);
      } else {
        setMessages((current) => [
          ...current,
          {
            id: `${Date.now()}-assistant-error`,
            role: "assistant",
            text: `${result.message}\n${result.suggestion}`,
            error: true
          }
        ]);
      }
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: `${Date.now()}-assistant-error`,
          role: "assistant",
          text: `${error instanceof Error ? error.message : "发送失败。"}\n请重新检查 AI 服务设置。`,
          error: true
        }
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="chatHome">
      <header className="chatTopBar">
        <div>
          <h2>和小黑子聊天</h2>
          <p>
            {displayProvider(bootstrap.runtime.provider)} / {bootstrap.runtime.model}
          </p>
        </div>
        <div className="topBarActions">
          <StatusBadge tone="ok">输出：{modeName(mode?.current)}</StatusBadge>
          <button type="button" className="secondaryButton" onClick={() => setModeOpen((current) => !current)}>
            输出模式
          </button>
          <button type="button" className="secondaryButton" onClick={onOpenSettings}>
            设置
          </button>
        </div>
      </header>
      {modeOpen && <ModeQuickPanel onModeChanged={setMode} />}
      <ChatTranscript messages={messages} />
      <ChatComposer value={input} onChange={setInput} onSend={send} busy={busy} />
    </section>
  );
}
