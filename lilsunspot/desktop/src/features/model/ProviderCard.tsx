import type { Provider } from "../../types";

type ProviderCardProps = {
  provider: Provider;
  selected: boolean;
  onSelect: (provider: Provider) => void;
};

const PROVIDER_COPY: Record<string, { description: string; keyRequirement: string }> = {
  deepseek: { description: "便宜易用，适合先跑通。", keyRequirement: "需要 API Key" },
  kimi: { description: "长文本能力好，适合资料整理。", keyRequirement: "需要 API Key" },
  qwen: { description: "国内云服务，兼容 OpenAI 接口。", keyRequirement: "需要 API Key" },
  ollama: { description: "模型运行在本机，适合离线尝试。", keyRequirement: "通常不用 API Key" },
  openrouter: { description: "海外聚合服务，适合已有账号。", keyRequirement: "需要 API Key" },
  openai: { description: "OpenAI 官方服务，适合海外网络环境。", keyRequirement: "需要 API Key" }
};

export function providerCopy(provider: Provider) {
  return PROVIDER_COPY[provider.id] || { description: provider.notes || "OpenAI 兼容 AI 服务。", keyRequirement: "需要配置" };
}

export function displayProvider(providerId?: string) {
  const names: Record<string, string> = {
    deepseek: "DeepSeek",
    kimi: "Kimi",
    qwen: "通义千问",
    ollama: "本地 Ollama",
    openrouter: "OpenRouter",
    openai: "OpenAI"
  };
  return providerId ? names[providerId] || providerId : "未设置";
}

export function ProviderCard({ provider, selected, onSelect }: ProviderCardProps) {
  const copy = providerCopy(provider);
  return (
    <button type="button" className={selected ? "providerCard selected" : "providerCard"} onClick={() => onSelect(provider)}>
      <span className="providerCardTop">
        <strong>{provider.display_name}</strong>
        {selected && <em>已选</em>}
      </span>
      <span className="providerDescription">{copy.description}</span>
      <small>推荐模型</small>
      <b>{provider.default_model}</b>
      <span className="providerKeyRequirement">{copy.keyRequirement}</span>
    </button>
  );
}
