import type { AppBootstrapRuntime, Provider } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { AdvancedModelSettings } from "./AdvancedModelSettings";
import { displayProvider } from "./ProviderCard";

type ModelSettingsProps = {
  runtime: AppBootstrapRuntime;
  provider: Provider | null;
  onSetupModel: () => void;
};

export function ModelSettings({ runtime, provider, onSetupModel }: ModelSettingsProps) {
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
      <button type="button" onClick={onSetupModel}>
        {runtime.configured ? "更换或重新测试" : "现在设置"}
      </button>
      <AdvancedModelSettings provider={provider} model={runtime.model || provider?.default_model || ""} baseUrlOverride="" editable={false} />
    </section>
  );
}
