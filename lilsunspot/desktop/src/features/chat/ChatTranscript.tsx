export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  meta?: string;
  error?: boolean;
};

type ChatTranscriptProps = {
  messages: ChatMessage[];
  examples?: { title: string; note: string }[];
  onExampleSelect?: (value: string) => void;
};

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
            <span>小黑子</span>
            <p>你可以直接问，也可以让我拆任务。当前输出模式会先给结论，再给必要步骤。</p>
          </article>
        </div>
      ) : (
        messages.map((message) => (
          <article
            key={message.id}
            className={`chatBubble ${message.role === "user" ? "userBubble" : "assistantBubble"} ${message.error ? "errorBubble" : ""}`}
          >
            <span>{message.role === "user" ? "你" : "小黑子"}</span>
            <p>{message.text}</p>
            {message.meta && <em>{message.meta}</em>}
          </article>
        ))
      )}
    </div>
  );
}
