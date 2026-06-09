import lilsunspotIcon from "../../assets/lilsunspot-icon.png";

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

const ASSISTANT_NAME = "小黑子";

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
            className={`chatBubble ${message.role === "user" ? "userBubble" : "assistantBubble"} ${message.error ? "errorBubble" : ""}`}
          >
            {message.role === "assistant" && (
              <img className="assistantAvatar" src={lilsunspotIcon} alt={`${ASSISTANT_NAME}头像`} />
            )}
            <div className="chatBubbleBody">
              <span>{message.role === "user" ? "你" : ASSISTANT_NAME}</span>
              <p>{message.text}</p>
              {message.meta && <em>{message.meta}</em>}
            </div>
          </article>
        ))
      )}
    </div>
  );
}
