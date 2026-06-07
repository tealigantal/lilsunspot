import type { AppBootstrapState } from "../../types";
import { ErrorWithAction } from "../../shared/components/ErrorWithAction";

type ChatBlockedStateProps = {
  bootstrap: AppBootstrapState;
  onSetupModel: () => void;
  onRetry: () => void;
};

export function ChatBlockedState({ bootstrap, onSetupModel, onRetry }: ChatBlockedStateProps) {
  const blocker = bootstrap.user_visible_blockers[0];
  const needsModel = blocker?.code === "missing_model" || bootstrap.stage === "needs_model";
  return (
    <ErrorWithAction
      title="还不能聊天"
      message={blocker?.message || bootstrap.message || "聊天暂时不可用。"}
      suggestion={blocker?.suggestion || "请按下一步处理后再试。"}
      primaryAction={{ label: needsModel ? "现在设置" : "重新检查", onClick: needsModel ? onSetupModel : onRetry }}
      secondaryActions={[{ label: needsModel ? "重新检查" : "现在设置", onClick: needsModel ? onRetry : onSetupModel }]}
      technicalDetails={{
        stage: bootstrap.stage,
        checks: bootstrap.checks,
        runtime: bootstrap.runtime
      }}
    />
  );
}
