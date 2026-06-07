import type { Provider, ProviderTestResult } from "../../types";
import { AdvancedModelSettings } from "../model/AdvancedModelSettings";
import { ModelTestResult } from "../model/ModelTestResult";
import { displayProvider } from "../model/ProviderCard";

type ApiKeyStepProps = {
  provider: Provider | null;
  apiKey: string;
  model: string;
  baseUrlOverride: string;
  result: ProviderTestResult | null;
  onApiKeyChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onBaseUrlChange: (value: string) => void;
  onPaste: () => void;
  onOpenKeyUrl: () => void;
  onBack: () => void;
  onSave: () => void;
  onTest: () => void;
  onChangeProvider: () => void;
  busy?: boolean;
  saving?: boolean;
  testing?: boolean;
};

export function ApiKeyStep({
  provider,
  apiKey,
  model,
  baseUrlOverride,
  result,
  onApiKeyChange,
  onModelChange,
  onBaseUrlChange,
  onPaste,
  onOpenKeyUrl,
  onBack,
  onSave,
  onTest,
  onChangeProvider,
  busy = false,
  saving = false,
  testing = false
}: ApiKeyStepProps) {
  const localProvider = provider?.type === "local";
  return (
    <div className="formStack">
      <div className="selectedProviderLine">
        <span>当前 AI 服务</span>
        <strong>{displayProvider(provider?.id)}</strong>
        <span>{localProvider ? "本地模型通常不用 API Key，可以留空。" : "API Key 只保存在你的电脑本机。"}</span>
      </div>
      <div className="setupGuide">
        <article>
          <strong>1. 打开官网</strong>
          <span>登录服务商账号，进入 API Key 页面。</span>
        </article>
        <article>
          <strong>2. 复制 Key</strong>
          <span>只复制完整文本，不截图也不发给别人。</span>
        </article>
        <article>
          <strong>3. 保存到本机</strong>
          <span>先保存配置，网络测试失败也不会丢失 Key。</span>
        </article>
      </div>
      <label>
        推荐模型
        <input value={model} onChange={(event) => onModelChange(event.target.value)} placeholder={provider?.default_model || "模型名称"} />
      </label>
      <div className="actionRow">
        <button type="button" className="secondaryButton" onClick={onOpenKeyUrl} disabled={busy || !provider}>
          {localProvider ? "打开本地服务说明" : "打开官网获取 Key"}
        </button>
        <button type="button" className="secondaryButton" onClick={onPaste} disabled={busy}>
          从剪贴板粘贴
        </button>
      </div>
      <label>
        API Key
        <input
          type="password"
          value={apiKey}
          onChange={(event) => onApiKeyChange(event.target.value)}
          placeholder={localProvider ? "本地模型可留空" : "粘贴 API Key"}
        />
      </label>
      <AdvancedModelSettings
        provider={provider}
        model={model}
        baseUrlOverride={baseUrlOverride}
        onModelChange={onModelChange}
        onBaseUrlChange={onBaseUrlChange}
        showModelField={false}
      />
      <div className="actionRow">
        <button type="button" className="secondaryButton" onClick={onBack} disabled={busy}>
          上一步
        </button>
        <button type="button" className="secondaryButton" onClick={onTest} disabled={busy || !provider || !model.trim() || (!localProvider && !apiKey.trim())}>
          {testing ? "测试中" : "测试连接"}
        </button>
        <button type="button" onClick={onSave} disabled={busy || !provider || !model.trim() || (!localProvider && !apiKey.trim())}>
          {saving ? "保存中" : "保存并继续"}
        </button>
      </div>
      <ModelTestResult
        result={result}
        testing={testing}
        onRetry={onTest}
        onRepaste={onPaste}
        onChangeProvider={onChangeProvider}
        onOpenKeyUrl={onOpenKeyUrl}
      />
    </div>
  );
}
