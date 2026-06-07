import type { Provider, ProviderTestResult } from "../../types";
import { AdvancedModelSettings } from "../model/AdvancedModelSettings";
import { ModelTestResult } from "../model/ModelTestResult";
import { displayProvider } from "../model/ProviderCard";

type TestAndSaveStepProps = {
  provider: Provider | null;
  model: string;
  baseUrlOverride: string;
  result: ProviderTestResult | null;
  testing: boolean;
  onModelChange: (value: string) => void;
  onBaseUrlChange: (value: string) => void;
  onBack: () => void;
  onTestAndSave: () => void;
  onRepaste: () => void;
  onChangeProvider: () => void;
  onOpenKeyUrl: () => void;
};

export function TestAndSaveStep({
  provider,
  model,
  baseUrlOverride,
  result,
  testing,
  onModelChange,
  onBaseUrlChange,
  onBack,
  onTestAndSave,
  onRepaste,
  onChangeProvider,
  onOpenKeyUrl
}: TestAndSaveStepProps) {
  const localProvider = provider?.type === "local";
  return (
    <div className="formStack">
      <div className="selectedProviderLine">
        <span>将要测试</span>
        <strong>
          {displayProvider(provider?.id)} / {model || provider?.default_model || "推荐模型"}
        </strong>
        <span>{localProvider ? "将检测本地服务是否可用。" : "将验证 API Key、模型名称和网络连接。"}</span>
      </div>
      <label>
        推荐模型
        <input value={model} onChange={(event) => onModelChange(event.target.value)} placeholder={provider?.default_model || "模型名称"} />
      </label>
      <AdvancedModelSettings
        provider={provider}
        model={model}
        baseUrlOverride={baseUrlOverride}
        onModelChange={onModelChange}
        onBaseUrlChange={onBaseUrlChange}
      />
      <div className="actionRow">
        <button type="button" className="secondaryButton" onClick={onBack} disabled={testing}>
          上一步
        </button>
        <button type="button" onClick={onTestAndSave} disabled={testing || !provider || !model.trim()}>
          {testing ? "测试中" : localProvider ? "检测本地服务" : "测试并保存"}
        </button>
      </div>
      <ModelTestResult
        result={result}
        testing={testing}
        onRetry={onTestAndSave}
        onRepaste={onRepaste}
        onChangeProvider={onChangeProvider}
        onOpenKeyUrl={onOpenKeyUrl}
      />
    </div>
  );
}
