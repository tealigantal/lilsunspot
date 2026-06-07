import type { Provider } from "../../types";
import { TechnicalDetails } from "../../shared/components/TechnicalDetails";

type AdvancedModelSettingsProps = {
  provider: Provider | null;
  model: string;
  baseUrlOverride: string;
  onModelChange?: (value: string) => void;
  onBaseUrlChange?: (value: string) => void;
  editable?: boolean;
};

export function AdvancedModelSettings({
  provider,
  model,
  baseUrlOverride,
  onModelChange,
  onBaseUrlChange,
  editable = true
}: AdvancedModelSettingsProps) {
  return (
    <details className="advancedSettings">
      <summary>高级设置</summary>
      <div className="formStack">
        <label>
          模型名称
          <input
            value={model}
            onChange={(event) => onModelChange?.(event.target.value)}
            disabled={!editable}
            placeholder={provider?.default_model || "推荐模型"}
          />
        </label>
        <label>
          Base URL
          <input
            value={baseUrlOverride}
            onChange={(event) => onBaseUrlChange?.(event.target.value)}
            disabled={!editable}
            placeholder={provider?.base_url || "使用服务商默认地址"}
          />
        </label>
      </div>
      <TechnicalDetails
        title="技术字段"
        data={{
          provider_id: provider?.id || "",
          model,
          base_url: baseUrlOverride || provider?.base_url || "",
          hermes_provider: provider?.hermes_provider || "",
          env_key: provider?.env_key || ""
        }}
      />
    </details>
  );
}
