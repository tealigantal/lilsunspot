import type { Provider } from "../../types";
import { ProviderCard } from "../model/ProviderCard";

type ChooseModelServiceStepProps = {
  providers: Provider[];
  selectedProvider: string;
  showMore: boolean;
  onShowMoreChange: (value: boolean) => void;
  onSelect: (provider: Provider) => void;
  onBack: () => void;
  onNext: () => void;
  busy?: boolean;
};

const RECOMMENDED_PROVIDER_IDS = ["deepseek", "kimi", "qwen", "ollama"];

export function ChooseModelServiceStep({
  providers,
  selectedProvider,
  showMore,
  onShowMoreChange,
  onSelect,
  onBack,
  onNext,
  busy = false
}: ChooseModelServiceStepProps) {
  const recommended = providers.filter((provider) => RECOMMENDED_PROVIDER_IDS.includes(provider.id));
  const more = providers.filter((provider) => !RECOMMENDED_PROVIDER_IDS.includes(provider.id));
  return (
    <div className="formStack">
      <div className="providerGrid">
        {recommended.map((provider) => (
          <ProviderCard key={provider.id} provider={provider} selected={selectedProvider === provider.id} onSelect={onSelect} />
        ))}
      </div>
      {more.length > 0 && (
        <details className="moreProviders" open={showMore} onToggle={(event) => onShowMoreChange(event.currentTarget.open)}>
          <summary>更多服务：OpenAI、OpenRouter、自定义 OpenAI Compatible</summary>
          <div className="chipRow">
            {more.map((provider) => (
              <button
                key={provider.id}
                type="button"
                className={selectedProvider === provider.id ? "chipButton selected" : "chipButton"}
                onClick={() => onSelect(provider)}
              >
                {provider.display_name}
              </button>
            ))}
          </div>
        </details>
      )}
      <div className="actionRow">
        <button type="button" className="secondaryButton" onClick={onBack} disabled={busy}>
          上一步
        </button>
        <button type="button" onClick={onNext} disabled={busy || !selectedProvider}>
          下一步：保存 Key
        </button>
      </div>
    </div>
  );
}
