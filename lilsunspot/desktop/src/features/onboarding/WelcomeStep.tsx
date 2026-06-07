type WelcomeStepProps = {
  onNext: () => void;
};

export function WelcomeStep({ onNext }: WelcomeStepProps) {
  return (
    <div className="formStack">
      <div className="welcomePanel">
        <strong>欢迎使用小黑子</strong>
        <span>先设置一个 AI 服务，小黑子就能开始在桌面上帮你聊天、整理和执行日常任务。</span>
      </div>
      <button type="button" onClick={onNext}>
        开始设置
      </button>
    </div>
  );
}
