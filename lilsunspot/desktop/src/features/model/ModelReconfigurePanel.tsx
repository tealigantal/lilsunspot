import { useEffect, useMemo, useState } from "react";
import { getModelRuntimeConfig, saveProvider, testProvider } from "../../api";
import type { AppBootstrapRuntime, ModelCapabilities, Provider, ProviderTestResult } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { AdvancedModelSettings } from "./AdvancedModelSettings";

type SaveStatus = "idle" | "saving" | "saved" | "refreshing" | "failed";

type ModelReconfigurePanelProps = {
  runtime: AppBootstrapRuntime;
  providers: Provider[];
  currentProvider: Provider | null;
  onSaved: () => Promise<void> | void;
  onCapabilitiesChanged: (capabilities: ModelCapabilities | null) => void;
  onCapabilitiesRefresh: () => Promise<ModelCapabilities | null>;
};

function statusCopy(status: SaveStatus) {
  const copy: Record<SaveStatus, string> = {
    idle: "已保存配置",
    saving: "正在保存",
    saved: "已保存配置",
    refreshing: "正在刷新能力",
    failed: "需要处理"
  };
  return copy[status];
}

function providerMatchesRuntime(provider: Provider, runtime: AppBootstrapRuntime) {
  return provider.id === runtime.provider || provider.hermes_provider === runtime.provider;
}

export function ModelReconfigurePanel({
  runtime,
  providers,
  currentProvider,
  onSaved,
  onCapabilitiesChanged,
  onCapabilitiesRefresh
}: ModelReconfigurePanelProps) {
  const initialProvider = currentProvider?.id || providers.find((provider) => providerMatchesRuntime(provider, runtime))?.id || providers[0]?.id || "";
  const [providerId, setProviderId] = useState(initialProvider);
  const [model, setModel] = useState(runtime.model || currentProvider?.default_model || "");
  const [baseUrlOverride, setBaseUrlOverride] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [message, setMessage] = useState("");
  const [capabilities, setCapabilities] = useState<ModelCapabilities | null>(null);
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null);
  const selectedProvider = useMemo(() => providers.find((provider) => provider.id === providerId) || null, [providers, providerId]);

  useEffect(() => {
    setProviderId(initialProvider);
  }, [initialProvider]);

  useEffect(() => {
    if (!providerId || !selectedProvider) {
      return;
    }
    if (!model.trim()) {
      setModel(runtime.model || selectedProvider.default_model || "");
    }
  }, [providerId, selectedProvider, runtime.model, model]);

  useEffect(() => {
    let mounted = true;
    async function loadRuntime() {
      try {
        const config = await getModelRuntimeConfig();
        if (!mounted) {
          return;
        }
        if (config.main.provider === runtime.provider || config.main.provider === selectedProvider?.hermes_provider) {
          setBaseUrlOverride(config.main.base_url || "");
        }
      } catch {
        if (mounted) {
          setBaseUrlOverride("");
        }
      }
    }
    void loadRuntime();
    return () => {
      mounted = false;
    };
  }, [runtime.provider, selectedProvider?.hermes_provider]);

  function chooseProvider(nextProviderId: string) {
    const provider = providers.find((item) => item.id === nextProviderId) || null;
    setProviderId(nextProviderId);
    setModel(provider?.default_model || "");
    setBaseUrlOverride("");
    setApiKey("");
    setTestResult(null);
    setMessage("");
    setSaveStatus("idle");
  }

  async function runTest() {
    if (!selectedProvider) {
      setMessage("请先选择 AI 服务。");
      return;
    }
    const nextModel = model.trim();
    const nextApiKey = apiKey.trim();
    if (!nextModel) {
      setMessage("模型名称不能为空。");
      return;
    }
    if (selectedProvider.type !== "local" && !nextApiKey) {
      setMessage("重新测试需要粘贴新 Key；只改模型或 Base URL 可以直接保存。");
      return;
    }
    setSaveStatus("idle");
    setMessage("");
    setTestResult(null);
    const result = await testProvider(selectedProvider.id, nextModel, nextApiKey, baseUrlOverride.trim());
    setTestResult(result);
    if (result.ok) {
      setModel(result.model);
    }
  }

  async function save() {
    if (!selectedProvider) {
      setMessage("请先选择 AI 服务。");
      return;
    }
    const nextModel = model.trim();
    if (!nextModel) {
      setMessage("模型名称不能为空。");
      return;
    }
    setSaveStatus("saving");
    setMessage("");
    setTestResult(null);
    setCapabilities(null);
    try {
      const saved = await saveProvider(selectedProvider.id, nextModel, apiKey.trim(), baseUrlOverride.trim());
      setModel(saved.model);
      setApiKey("");
      setSaveStatus("saved");
    } catch (error) {
      setSaveStatus("failed");
      setMessage(error instanceof Error ? error.message : "保存失败，请稍后重试。");
      return;
    }
    setSaveStatus("refreshing");
    try {
      const nextCapabilities = await onCapabilitiesRefresh();
      setCapabilities(nextCapabilities);
      onCapabilitiesChanged(nextCapabilities);
      if (!nextCapabilities) {
        setMessage("保存成功，能力状态稍后刷新。");
      }
    } catch (error) {
      setMessage(error instanceof Error ? `保存成功，能力状态稍后刷新：${error.message}` : "保存成功，能力状态稍后刷新。");
    }
    try {
      await onSaved();
    } catch (error) {
      setMessage(error instanceof Error ? `保存成功，界面状态稍后刷新：${error.message}` : "保存成功，界面状态稍后刷新。");
    }
    setSaveStatus("saved");
  }

  const imageNode = capabilities?.capability_graph?.by_id?.["image.read"];
  const busy = saveStatus === "saving" || saveStatus === "refreshing";

  return (
    <div className="reconfigurePanel">
      <div className="settingsHeader compact">
        <div>
          <h4>更换或重新测试</h4>
          <p>留空 API Key 会复用本机已保存的 Key；切换到新服务且本机没有旧 Key 时会要求重新粘贴。</p>
        </div>
        <StatusBadge tone={saveStatus === "failed" ? "warning" : saveStatus === "saved" ? "ok" : "neutral"}>{statusCopy(saveStatus)}</StatusBadge>
      </div>
      <div className="formStack">
        <label>
          AI 服务
          <select value={providerId} onChange={(event) => chooseProvider(event.target.value)} disabled={busy}>
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          API Key
          <input
            value={apiKey}
            type="password"
            onChange={(event) => setApiKey(event.target.value)}
            disabled={busy}
            placeholder="留空复用已保存 Key"
          />
        </label>
        <AdvancedModelSettings
          provider={selectedProvider}
          model={model}
          baseUrlOverride={baseUrlOverride}
          onModelChange={setModel}
          onBaseUrlChange={setBaseUrlOverride}
          editable={!busy}
        />
        <div className="buttonRow">
          <button type="button" onClick={() => void runTest()} disabled={busy}>
            测试连接
          </button>
          <button type="button" className="primaryButton" onClick={() => void save()} disabled={busy}>
            保存设置
          </button>
        </div>
      </div>
      {testResult && (
        <p className={testResult.ok ? "inlineSuccess" : "inlineError"}>{testResult.ok ? testResult.message : testResult.message}</p>
      )}
      {imageNode && <p className="inlineHint">图片识别：{imageNode.user_message_cn}</p>}
      {message && <p className="inlineError">{message}</p>}
    </div>
  );
}
