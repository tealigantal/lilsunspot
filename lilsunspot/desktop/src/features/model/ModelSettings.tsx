import { useState } from "react";
import { resetLocalProviderConfig } from "../../api";
import type { AppBootstrapRuntime, ModelCapabilities, OperationNotice, OperationState, Provider } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { OperationNoticeBanner } from "../../shared/components/OperationNoticeBanner";
import { AdvancedModelSettings } from "./AdvancedModelSettings";
import { displayProvider } from "./ProviderCard";
import { VisionModelPanel } from "./VisionModelPanel";
import { ModelReconfigurePanel } from "./ModelReconfigurePanel";

type ModelSettingsProps = {
  runtime: AppBootstrapRuntime;
  provider: Provider | null;
  providers: Provider[];
  providerState: OperationState;
  providerNotice: OperationNotice | null;
  onProvidersRefresh: () => Promise<Provider[]>;
  modelCapabilities: ModelCapabilities | null;
  capabilityNotice: OperationNotice | null;
  onModelCapabilitiesChanged: (capabilities: ModelCapabilities | null) => void;
  onModelCapabilitiesRefresh: () => Promise<ModelCapabilities | null>;
  onSetupModel: () => void;
  onModelSaved: () => Promise<void> | void;
  onLocalProviderReset: () => Promise<void> | void;
};

export function ModelSettings({
  runtime,
  provider,
  providers,
  providerState,
  providerNotice,
  onProvidersRefresh,
  modelCapabilities,
  capabilityNotice,
  onModelCapabilitiesChanged,
  onModelCapabilitiesRefresh,
  onSetupModel,
  onModelSaved,
  onLocalProviderReset
}: ModelSettingsProps) {
  const [showReconfigure, setShowReconfigure] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState("");

  async function handleResetLocalProviderConfig() {
    setResetError("");
    const confirmed = window.confirm(
      "确定清除本机保存的 AI Key 和模型设置吗？\n\n清除后会直接回到首次启动配置。聊天记录、附件和微信连接不会被删除。"
    );
    if (!confirmed) {
      return;
    }
    setResetting(true);
    try {
      await resetLocalProviderConfig();
      onModelCapabilitiesChanged(null);
      await onLocalProviderReset();
    } catch (error) {
      setResetError(error instanceof Error ? error.message : "清除失败，请稍后再试。");
    } finally {
      setResetting(false);
    }
  }

  return (
    <section className="settingsSection">
      <div className="settingsHeader">
        <div>
          <h3>模型服务设置</h3>
          <p>这里决定小黑子聊天时使用哪个 AI 服务。</p>
        </div>
        <StatusBadge tone={runtime.configured ? "ok" : "warning"}>{runtime.configured ? "已设置" : "未设置"}</StatusBadge>
      </div>
      <div className="settingsSummary">
        <span>当前 AI 服务</span>
        <strong>{displayProvider(runtime.provider)}</strong>
        <span>当前模型</span>
        <strong>{runtime.model || "未设置"}</strong>
      </div>
      <div className="buttonRow">
        <button type="button" onClick={() => (runtime.configured ? setShowReconfigure((value) => !value) : onSetupModel())}>
          {runtime.configured ? "更换或重新测试" : "现在设置"}
        </button>
        {providerNotice && (
          <button type="button" className="secondaryButton" onClick={() => void onProvidersRefresh()} disabled={providerState === "running"}>
            重新读取服务列表
          </button>
        )}
        {runtime.configured && (
          <button type="button" className="dangerButton" onClick={handleResetLocalProviderConfig} disabled={resetting}>
            {resetting ? "正在清除..." : "清除本机 AI Key"}
          </button>
        )}
      </div>
      {providerNotice && <OperationNoticeBanner notice={providerNotice} />}
      {capabilityNotice && <OperationNoticeBanner notice={capabilityNotice} />}
      {resetError && <p className="inlineError">{resetError}</p>}
      {runtime.configured && showReconfigure ? (
        <ModelReconfigurePanel
          runtime={runtime}
          providers={providers}
          currentProvider={provider}
          onSaved={onModelSaved}
          onCapabilitiesChanged={onModelCapabilitiesChanged}
          onCapabilitiesRefresh={onModelCapabilitiesRefresh}
        />
      ) : (
        <AdvancedModelSettings provider={provider} model={runtime.model || provider?.default_model || ""} baseUrlOverride="" editable={false} />
      )}
      <VisionModelPanel
        providers={providers}
        modelCapabilities={modelCapabilities}
        onCapabilitiesChanged={onModelCapabilitiesChanged}
        onCapabilitiesLoaded={onModelCapabilitiesChanged}
        onCapabilitiesRefresh={onModelCapabilitiesRefresh}
      />
    </section>
  );
}
