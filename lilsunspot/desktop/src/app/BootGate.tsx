import type { AppBootstrapState, ModelCapabilities, OperationNotice, Provider } from "../types";
import { ErrorWithAction } from "../shared/components/ErrorWithAction";
import { PrimaryActionPanel } from "../shared/components/PrimaryActionPanel";
import { StatusBadge } from "../shared/components/StatusBadge";
import { TechnicalDetails } from "../shared/components/TechnicalDetails";
import { ChatHome } from "../features/chat/ChatHome";
import type { ChatMessage } from "../features/chat/ChatTranscript";
import { OnboardingFlow } from "../features/onboarding/OnboardingFlow";
import type { SettingsTab } from "../features/settings/SettingsDrawer";

type BootGateProps = {
  bootstrap: AppBootstrapState;
  forceOnboarding: boolean;
  initialMessages: ChatMessage[];
  modelCapabilities: ModelCapabilities | null;
  providers: Provider[];
  providersBusy?: boolean;
  providersNotice?: OperationNotice | null;
  busy?: boolean;
  onProvidersRefresh: () => Promise<Provider[]>;
  onModelCapabilitiesChanged: (capabilities: ModelCapabilities | null) => void;
  onRefresh: () => void;
  onOpenSettings: (tab?: SettingsTab) => void;
  onSetupModel: () => void;
  onBootstrapChanged: () => Promise<void> | void;
  onFirstChatDone: (messages: ChatMessage[]) => void;
};

export function BootGate({
  bootstrap,
  forceOnboarding,
  initialMessages,
  modelCapabilities,
  providers,
  providersBusy = false,
  providersNotice = null,
  busy = false,
  onProvidersRefresh,
  onModelCapabilitiesChanged,
  onRefresh,
  onOpenSettings,
  onSetupModel,
  onBootstrapChanged,
  onFirstChatDone
}: BootGateProps) {
  const reconfiguringExistingModel = forceOnboarding && bootstrap.runtime.configured;

  if (bootstrap.stage === "starting") {
    return (
      <PrimaryActionPanel
        title="正在准备小黑子"
        message="正在启动本地服务、读取 AI 服务设置，并准备聊天界面。"
        primaryLabel="重新检查"
        onPrimary={onRefresh}
        busy={busy}
      >
        <div className="checkList">
          <span>启动本地服务</span>
          <span>读取模型设置</span>
          <span>准备聊天</span>
        </div>
        <div className="progressTrack">
          <span />
        </div>
      </PrimaryActionPanel>
    );
  }

  if (forceOnboarding || bootstrap.stage === "needs_model" || bootstrap.stage === "model_test_required") {
    return (
      <OnboardingFlow
        onSaved={onBootstrapChanged}
        onFirstChatDone={onFirstChatDone}
        providers={providers}
        providersBusy={providersBusy}
        providersNotice={providersNotice}
        onProvidersRefresh={onProvidersRefresh}
        modelCapabilities={modelCapabilities}
        onModelCapabilitiesChanged={onModelCapabilitiesChanged}
        initialProvider={bootstrap.runtime.provider}
        initialStep={reconfiguringExistingModel ? "api_key" : bootstrap.runtime.provider ? "choose" : undefined}
        completion={reconfiguringExistingModel ? "return_to_chat" : "first_chat"}
      />
    );
  }

  if (bootstrap.stage === "daemon_failed" || bootstrap.stage === "repair_required") {
    const blocker = bootstrap.user_visible_blockers[0];
    return (
      <ErrorWithAction
        title={bootstrap.title || "本地服务没有成功启动"}
        message={blocker?.message || bootstrap.message}
        suggestion={blocker?.suggestion || "请重新检查；如果模型设置不正确，请重新设置 AI 服务。"}
        primaryAction={{ label: "重新检查", onClick: onRefresh }}
        secondaryActions={[
          { label: "重新设置 AI 服务", onClick: onSetupModel }
        ]}
        technicalDetails={{ stage: bootstrap.stage, checks: bootstrap.checks, runtime: bootstrap.runtime }}
      />
    );
  }

  if (bootstrap.stage === "chat_ready") {
    return (
      <ChatHome
        bootstrap={bootstrap}
        initialMessages={initialMessages}
        modelCapabilities={modelCapabilities}
        onSetupModel={onSetupModel}
        onRefresh={onRefresh}
        onOpenSettings={onOpenSettings}
      />
    );
  }

  return (
    <section className="primaryActionPanel">
      <StatusBadge tone="warning">需要处理</StatusBadge>
      <h2>{bootstrap.title}</h2>
      <p>{bootstrap.message}</p>
      <button type="button" onClick={onRefresh}>
        重新检查
      </button>
      <TechnicalDetails data={bootstrap} />
    </section>
  );
}
