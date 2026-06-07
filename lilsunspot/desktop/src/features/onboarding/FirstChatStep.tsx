import { useState } from "react";
import { sendChatMessage } from "../../api";
import { ChatComposer } from "../chat/ChatComposer";
import { ChatTranscript, type ChatMessage } from "../chat/ChatTranscript";
import { displayProvider } from "../model/ProviderCard";

type FirstChatStepProps = {
  onDone: (messages: ChatMessage[]) => void;
  onSkip: (messages: ChatMessage[]) => void;
};

export function FirstChatStep({ onDone, onSkip }: FirstChatStepProps) {
  const [input, setInput] = useState("你好，帮我介绍一下你能做什么");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text) {
      return;
    }
    const userMessage: ChatMessage = { id: `${Date.now()}-user`, role: "user", text };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    try {
      const result = await sendChatMessage(text);
      if (result.ok) {
        const finalMessages = [
          ...nextMessages,
          {
            id: `${Date.now()}-assistant`,
            role: "assistant" as const,
            text: result.reply,
            meta: `${displayProvider(result.provider)} / ${result.model}`
          }
        ];
        setMessages(finalMessages);
        onDone(finalMessages);
      } else {
        setMessages([
          ...nextMessages,
          {
            id: `${Date.now()}-assistant-error`,
            role: "assistant",
            text: `${result.message}\n${result.suggestion}`,
            error: true
          }
        ]);
      }
    } catch (error) {
      setMessages([
        ...nextMessages,
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
    <div className="firstChatStep">
      <ChatTranscript messages={messages} />
      <ChatComposer value={input} onChange={setInput} onSend={send} busy={busy} />
      <div className="actionRow">
        <button type="button" className="secondaryButton" onClick={() => onSkip(messages)} disabled={busy}>
          稍后再聊，进入主界面
        </button>
      </div>
    </div>
  );
}
