import { useEffect, useState } from "react";
import type { AppBootstrapState, CurrentMode } from "../../types";
import { getCurrentMode, getSafetyApprovals, sendChatMessage } from "../../api";
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
  onModeChanged?: (mode: CurrentMode) => void;
};

const EXAMPLE_PROMPTS = [
  { title: "帮我整理今天要做的三件事", note: "适合务实模式，输出清单" },
  { title: "我明天交方案但没开始", note: "先安抚，再给步骤" },
  { title: "微信里把模式调到 80", note: "命令同步到桌面端" }
];

export function ChatHome({ bootstrap, initialMessages = [], onSetupModel, onRefresh, onOpenSettings, onModeChanged }: ChatHomeProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<CurrentMode | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState(0);

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
          onModeChanged?.(current);
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

  useEffect(() => {
    let mounted = true;
    async function loadApprovals() {
      try {
        const approvals = await getSafetyApprovals();
        if (mounted) {
          setPendingApprovals(approvals.pending.length);
        }
      } catch {
        if (mounted) {
          setPendingApprovals(0);
        }
      }
    }
    void loadApprovals();
    return () => {
      mounted = false;
    };
  }, []);

  if (bootstrap.stage !== "chat_ready" || !bootstrap.runtime.configured) {
    return <ChatBlockedState bootstrap={bootstrap} onSetupModel={onSetupModel} onRetry={onRefresh} />;
  }

  function updateMode(nextMode: CurrentMode) {
    setMode(nextMode);
    onModeChanged?.(nextMode);
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
      <article className="chatMainPanel">
        <header className="panelHeader chatPanelHeader">
          <div>
            <h2>今日任务台</h2>
            <p>把普通聊天、桌面执行、微信命令都压进同一个控制台。</p>
          </div>
          <button type="button" className="secondaryButton compactButton" onClick={onOpenSettings}>
            模型服务
          </button>
        </header>
        <ChatTranscript messages={messages} examples={EXAMPLE_PROMPTS} onExampleSelect={setInput} />
        <ChatComposer
          value={input}
          onChange={setInput}
          onSend={send}
          busy={busy}
          placeholder="输入你想问的内容，Ctrl+Enter 发送"
        />
      </article>
      <aside className="chatSidePanel" aria-label="模式和安全摘要">
        <ModeQuickPanel variant="compact" onModeChanged={updateMode} />
        <section className="safetyMiniPanel">
          <h3>安全审批</h3>
          <strong>{pendingApprovals > 0 ? `${pendingApprovals} 个待审批` : "暂无待处理高危动作"}</strong>
          <p>Shell / 删除文件 / 微信发送 会先确认</p>
        </section>
        <p className="modeRuntimeLine">
          当前：{modeName(mode?.current)} · {displayProvider(bootstrap.runtime.provider)} / {bootstrap.runtime.model}
        </p>
      </aside>
    </section>
  );
}
