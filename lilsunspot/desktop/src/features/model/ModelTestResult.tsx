import type { ProviderTestResult } from "../../types";
import { ErrorWithAction } from "../../shared/components/ErrorWithAction";
import { StatusBadge } from "../../shared/components/StatusBadge";

type ModelTestResultProps = {
  result: ProviderTestResult | null;
  testing: boolean;
  onRetry: () => void;
  onRepaste: () => void;
  onChangeProvider: () => void;
  onOpenKeyUrl: () => void;
};

export function ModelTestResult({
  result,
  testing,
  onRetry,
  onRepaste,
  onChangeProvider,
  onOpenKeyUrl
}: ModelTestResultProps) {
  if (testing) {
    return (
      <div className="inlineNotice">
        <StatusBadge tone="warning">检测中</StatusBadge>
        <span>正在测试 AI 服务，请稍等。</span>
      </div>
    );
  }
  if (!result) {
    return (
      <div className="inlineNotice">
        <StatusBadge>未测试</StatusBadge>
        <span>测试通过后会自动保存到本机。</span>
      </div>
    );
  }
  if (result.ok) {
    return (
      <div className="inlineNotice success">
        <StatusBadge tone="ok">已通过</StatusBadge>
        <span>{result.message}</span>
      </div>
    );
  }
  return (
    <ErrorWithAction
      title={result.title}
      message={result.message}
      suggestion={result.suggestion || "按下面的下一步处理后再试。"}
      primaryAction={{ label: result.actions[0] || "重新测试", onClick: onRetry }}
      secondaryActions={[
        { label: "重新粘贴", onClick: onRepaste },
        { label: "换一个服务", onClick: onChangeProvider },
        { label: "打开官网", onClick: onOpenKeyUrl }
      ]}
      technicalDetails={result.safe_details}
    />
  );
}
