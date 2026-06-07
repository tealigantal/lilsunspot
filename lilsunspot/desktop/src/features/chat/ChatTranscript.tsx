export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  meta?: string;
  error?: boolean;
};

type ChatTranscriptProps = {
  messages: ChatMessage[];
};

export function ChatTranscript({ messages }: ChatTranscriptProps) {
  return (
    <div className="chatTranscript" aria-live="polite">
      {messages.length === 0 ? (
        <div className="emptyChat">
          <strong>试着问一句</strong>
          <span>例如：帮我整理今天要做的三件事。</span>
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
