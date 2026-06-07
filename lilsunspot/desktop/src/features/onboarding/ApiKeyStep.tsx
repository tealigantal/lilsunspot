import type { Provider } from "../../types";
import { displayProvider } from "../model/ProviderCard";

type ApiKeyStepProps = {
  provider: Provider | null;
  apiKey: string;
  onApiKeyChange: (value: string) => void;
  onPaste: () => void;
  onOpenKeyUrl: () => void;
  onBack: () => void;
  onNext: () => void;
  busy?: boolean;
};

export function ApiKeyStep({
  provider,
  apiKey,
  onApiKeyChange,
  onPaste,
  onOpenKeyUrl,
  onBack,
  onNext,
  busy = false
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
          <strong>3. 粘贴测试</strong>
          <span>测试通过后会自动保存到本机。</span>
        </article>
      </div>
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
      <div className="actionRow">
        <button type="button" className="secondaryButton" onClick={onBack} disabled={busy}>
          上一步
        </button>
        <button type="button" onClick={onNext} disabled={busy || !provider || (!localProvider && !apiKey.trim())}>
          下一步：测试连接
        </button>
      </div>
    </div>
  );
}
