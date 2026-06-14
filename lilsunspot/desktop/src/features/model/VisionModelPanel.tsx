import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getModelRuntimeConfig, getProviderCapabilities, openProviderKeyUrl, saveAuxiliaryModel } from "../../api";
import { StatusBadge } from "../../shared/components/StatusBadge";
import type { CapabilityNode, ModelCapabilities, ModelRuntimeConfig, Provider } from "../../types";
import { displayProvider } from "./ProviderCard";

type VisionModelPanelProps = {
  providers: Provider[];
  modelCapabilities?: ModelCapabilities | null;
  title?: string;
  description?: string;
  saveLabel?: string;
  allowClear?: boolean;
  headerAction?: ReactNode;
  onSaved?: (capabilities: ModelCapabilities) => void;
  onCapabilitiesChanged?: (capabilities: ModelCapabilities | null) => void;
  onCapabilitiesLoaded?: (capabilities: ModelCapabilities) => void;
  onCapabilitiesRefresh?: () => Promise<ModelCapabilities | null>;
};

function selectedProviderFromRuntime(models: ModelRuntimeConfig | null, providers: Provider[]) {
  const vision = models?.lilsunspot_auxiliary?.vision || models?.auxiliary?.vision;
  const providerId = String(vision?.provider || "").trim();
  if (!providerId) {
    return "auto";
  }
  if (providers.some((item) => item.id === providerId)) {
    return providerId;
  }
  const byHermesProvider = providers.find((item) => item.hermes_provider === providerId);
  return byHermesProvider?.id || providerId;
}

function modelForProvider(providerId: string, providers: Provider[]) {
  const provider = providers.find((item) => item.id === providerId);
  return provider?.vision_default_model || provider?.default_model || "";
}

function visionProviderScore(provider: Provider) {
  const localPenalty = provider.type === "local" ? 100 : 0;
  const optionalPenalty = provider.auxiliary_vision === "optional" ? 20 : 0;
  return localPenalty + optionalPenalty;
}

function capabilityNode(capabilities: ModelCapabilities | null, id: string): CapabilityNode | null {
  const graph = capabilities?.capability_graph;
  return graph?.by_id?.[id] || graph?.nodes?.find((node) => node.id === id) || null;
}

const visionErrorMessages: Record<string, string> = {
  missing_api_key: "缺少图片识别服务的 API Key。",
  invalid_key: "图片识别服务返回 Key 不可用，请重新保存该服务的 Key。",
  model_not_found: "图片识别模型不可用，请换一个当前账号和 Base URL 支持的视觉模型。",
  rate_limited: "图片识别服务限流，请稍后重试。",
  quota_exhausted: "图片识别服务额度不足，请更换 Key 或服务。",
  network_error: "连接图片识别服务失败，请检查网络或 Base URL。",
  provider_error: "图片识别服务返回错误，请检查服务状态和模型配置。",
  unknown: "图片识别验证失败，请重新测试配置。"
};

function visionFailureMessage(node: CapabilityNode | null) {
  if (node?.status !== "blocked") {
    return "";
  }
  const code = String(node.details?.last_error_code || node.blocking_reason || "unknown").trim() || "unknown";
  return `失败原因：${visionErrorMessages[code] || visionErrorMessages.unknown}`;
}

function cleanMessage(value: unknown) {
  return String(value || "").trim();
}

export function VisionModelPanel({
  providers,
  modelCapabilities = null,
  title = "图片识别模型",
  description = "主聊天模型不能看图时，小黑子会用这里的视觉模型先读图，再把说明交给当前聊天模型。",
  saveLabel = "保存图片识别模型",
  allowClear = true,
  headerAction,
  onSaved,
  onCapabilitiesChanged,
  onCapabilitiesLoaded,
  onCapabilitiesRefresh
}: VisionModelPanelProps) {
  const [models, setModels] = useState<ModelRuntimeConfig | null>(null);
  const [capabilities, setCapabilities] = useState<ModelCapabilities | null>(modelCapabilities);
  const [visionProvider, setVisionProvider] = useState("auto");
  const [visionModel, setVisionModel] = useState("");
  const [visionBaseUrl, setVisionBaseUrl] = useState("");
  const [visionApiKey, setVisionApiKey] = useState("");
  const [loadingVision, setLoadingVision] = useState(false);
  const [savingVision, setSavingVision] = useState(false);
  const [visionMessage, setVisionMessage] = useState("");

  const visionProviders = useMemo(
    () =>
      providers
        .filter((provider) => provider.auxiliary_vision)
        .sort((a, b) => visionProviderScore(a) - visionProviderScore(b) || a.display_name.localeCompare(b.display_name, "zh-CN")),
    [providers]
  );
  const selectedVisionProvider = providers.find((item) => item.id === visionProvider) || null;
  const currentVision = models?.lilsunspot_auxiliary?.vision || models?.auxiliary?.vision;
  const visionConfigured = Boolean(currentVision && String(currentVision.provider || "").trim() && String(currentVision.provider || "").trim() !== "auto");
  const imageNode = capabilityNode(capabilities, "image.read");
  const imageReady = imageNode?.status === "ready";
  const imageDegraded = imageNode?.status === "degraded";
  const verificationStatus = String(imageNode?.details?.verification_status || "");
  const imageFailureMessage = visionFailureMessage(imageNode);
  const visibleVisionMessage = cleanMessage(visionMessage);
  const visibleImageNodeMessage = cleanMessage(imageNode?.user_message_cn);
  const shownMessages = new Set([visibleVisionMessage, visibleImageNodeMessage, imageFailureMessage].filter(Boolean));
  const visibleLimitations = (capabilities?.limitations || []).filter((item) => {
    const message = cleanMessage(item);
    if (!message || shownMessages.has(message)) {
      return false;
    }
    shownMessages.add(message);
    return true;
  });
  const visionStatusText = imageReady
    ? verificationStatus === "verified"
      ? "真实验证通过"
      : "推断可用"
    : imageDegraded
      ? "已配置，待验证"
      : imageNode?.status === "blocked"
        ? "失败原因"
        : visionConfigured
           ? "已保存配置"
      : "图片目前只能预览";

  useEffect(() => {
    setCapabilities(modelCapabilities);
  }, [modelCapabilities]);

  useEffect(() => {
    let mounted = true;
    async function loadVisionState() {
      setLoadingVision(true);
      let loadedRuntime = false;
      try {
        const nextModels = await getModelRuntimeConfig();
        if (!mounted) {
          return;
        }
        loadedRuntime = true;
        setModels(nextModels);
        const nextVision = nextModels.lilsunspot_auxiliary?.vision || nextModels.auxiliary?.vision;
        const nextProvider = selectedProviderFromRuntime(nextModels, providers);
        setVisionProvider(nextProvider);
        setVisionModel(String(nextVision?.model || ""));
        setVisionBaseUrl(String(nextVision?.base_url || ""));
      } catch (error) {
        if (mounted) {
          setVisionMessage(error instanceof Error ? error.message : "图片识别设置读取失败。");
        }
      }
      try {
        const nextCapabilities = modelCapabilities || (await getProviderCapabilities());
        if (!mounted || !nextCapabilities) {
          return;
        }
        setCapabilities(nextCapabilities);
        onCapabilitiesChanged?.(nextCapabilities);
        onCapabilitiesLoaded?.(nextCapabilities);
      } catch (error) {
        if (mounted && loadedRuntime) {
          setVisionMessage(
            error instanceof Error
              ? `图片识别设置已读取；能力状态稍后刷新：${error.message}`
              : "图片识别设置已读取；能力状态稍后刷新。"
          );
        }
      } finally {
        if (mounted) {
          setLoadingVision(false);
        }
      }
    }
    void loadVisionState();
    return () => {
      mounted = false;
    };
  }, [providers, onCapabilitiesChanged, onCapabilitiesLoaded]);

  function chooseVisionProvider(providerId: string) {
    setVisionProvider(providerId);
    setVisionMessage("");
    setVisionApiKey("");
    if (providerId === "auto") {
      setVisionModel("");
      setVisionBaseUrl("");
      return;
    }
    const nextProvider = providers.find((item) => item.id === providerId) || null;
    setVisionModel(modelForProvider(providerId, providers));
    setVisionBaseUrl(nextProvider?.hermes_provider === "custom" ? nextProvider.base_url || "" : "");
  }

  async function saveVision() {
    const nextProvider = visionProvider.trim();
    const nextModel = visionModel.trim();
    if (nextProvider === "auto") {
      setVisionMessage("请先选择一个图片识别服务。");
      return;
    }
    if (!nextModel) {
      setVisionMessage("请填写图片识别模型名称。");
      return;
    }
    setSavingVision(true);
    setVisionMessage("");
    try {
      const nextModels = await saveAuxiliaryModel({
        task: "vision",
        provider: nextProvider,
        model: nextModel,
        base_url: visionBaseUrl.trim(),
        api_key: visionApiKey.trim()
      });
      setModels(nextModels);
      setVisionApiKey("");
    } catch (error) {
      setVisionMessage(error instanceof Error ? error.message : "图片识别模型保存失败。");
      setSavingVision(false);
      return;
    }
    try {
      const nextCapabilities = onCapabilitiesRefresh ? await onCapabilitiesRefresh() : await getProviderCapabilities();
      if (nextCapabilities) {
        setCapabilities(nextCapabilities);
        onCapabilitiesChanged?.(nextCapabilities);
        const nextImageNode = capabilityNode(nextCapabilities, "image.read");
        setVisionMessage(
          nextImageNode?.status === "ready"
            ? "图片识别模型已保存，当前可用。"
            : nextImageNode?.status === "degraded"
              ? "图片识别模型已保存，下次上传图片时会做真实识别验证。"
              : "已保存，但当前还没有确认图片识别可用。"
        );
        onSaved?.(nextCapabilities);
      } else {
        setVisionMessage("图片识别模型已保存；能力状态稍后刷新。");
      }
    } catch (error) {
      setVisionMessage(
        error instanceof Error
          ? `图片识别模型已保存；能力状态稍后刷新：${error.message}`
          : "图片识别模型已保存；能力状态稍后刷新。"
      );
    } finally {
      setSavingVision(false);
    }
  }

  async function openVisionProviderKeyUrl() {
    if (!selectedVisionProvider || visionProvider === "auto") {
      setVisionMessage("请先选择图片识别服务。");
      return;
    }
    setVisionMessage("");
    try {
      await openProviderKeyUrl(selectedVisionProvider.id);
      setVisionMessage(
        selectedVisionProvider.type === "local"
          ? `已打开 ${displayProvider(selectedVisionProvider.id)} 的本地服务说明。`
          : `已打开 ${displayProvider(selectedVisionProvider.id)} 的 API Key 页面。`
      );
    } catch (error) {
      setVisionMessage(error instanceof Error ? error.message : "打开图片识别服务官网失败。");
    }
  }

  async function clearVision() {
    setSavingVision(true);
    setVisionMessage("");
    try {
      const nextModels = await saveAuxiliaryModel({
        task: "vision",
        provider: "auto",
        model: "",
        base_url: "",
        api_key: ""
      });
      setModels(nextModels);
      setVisionProvider("auto");
      setVisionModel("");
      setVisionBaseUrl("");
      setVisionApiKey("");
    } catch (error) {
      setVisionMessage(error instanceof Error ? error.message : "图片识别模型清除失败。");
      setSavingVision(false);
      return;
    }
    try {
      const nextCapabilities = onCapabilitiesRefresh ? await onCapabilitiesRefresh() : await getProviderCapabilities();
      if (nextCapabilities) {
        setCapabilities(nextCapabilities);
        setVisionMessage("已改为不单独配置图片识别模型。");
        onCapabilitiesChanged?.(nextCapabilities);
        onCapabilitiesLoaded?.(nextCapabilities);
      } else {
        setVisionMessage("已改为不单独配置图片识别模型；能力状态稍后刷新。");
      }
    } catch (error) {
      setVisionMessage(
        error instanceof Error
          ? `已改为不单独配置图片识别模型；能力状态稍后刷新：${error.message}`
          : "已改为不单独配置图片识别模型；能力状态稍后刷新。"
      );
    } finally {
      setSavingVision(false);
    }
  }

  return (
    <div className="visionModelPanel">
      <div className="settingsHeader compact">
        <div>
          <h4>{title}</h4>
          <p>{description}</p>
        </div>
        <div className="visionPanelHeaderActions">
          {headerAction}
          <StatusBadge tone={imageReady ? "ok" : imageNode?.status === "blocked" ? "danger" : "warning"}>{visionStatusText}</StatusBadge>
        </div>
      </div>
      {visibleVisionMessage && <p className="settingsInlineMessage">{visibleVisionMessage}</p>}
      {visibleImageNodeMessage && visibleImageNodeMessage !== visibleVisionMessage && (
        <p className="settingsInlineMessage">{visibleImageNodeMessage}</p>
      )}
      {imageFailureMessage && <p className="settingsInlineMessage danger">{imageFailureMessage}</p>}
      {visibleLimitations.length ? (
        <div className="visionLimitations">
          {visibleLimitations.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      ) : null}
      <div className="visionModelGrid">
        <label>
          图片识别服务
          <select value={visionProvider} onChange={(event) => chooseVisionProvider(event.target.value)} disabled={loadingVision || savingVision}>
            <option value="auto">请选择</option>
            {visionProvider !== "auto" && !visionProviders.some((item) => item.id === visionProvider) && (
              <option value={visionProvider}>{visionProvider}</option>
            )}
            {visionProviders.map((item) => (
              <option key={item.id} value={item.id}>
                {displayProvider(item.id)}
                {item.type === "local" ? "（本地可选）" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          视觉模型
          <input
            value={visionModel}
            onChange={(event) => setVisionModel(event.target.value)}
            disabled={visionProvider === "auto" || loadingVision || savingVision}
            placeholder={visionProvider === "auto" ? "选择服务后自动填写推荐值" : modelForProvider(visionProvider, providers)}
          />
        </label>
        <label>
          API Key
          <input
            value={visionApiKey}
            onChange={(event) => setVisionApiKey(event.target.value)}
            disabled={visionProvider === "auto" || loadingVision || savingVision}
            type="password"
            placeholder={selectedVisionProvider?.type === "local" ? "本地模型可留空" : "已保存过可留空"}
          />
        </label>
        <div className="visionProviderGuide">
          <button
            type="button"
            className="secondaryButton"
            onClick={() => void openVisionProviderKeyUrl()}
            disabled={visionProvider === "auto" || !selectedVisionProvider || loadingVision || savingVision}
          >
            {selectedVisionProvider?.type === "local" ? "打开本地服务说明" : "打开当前图片识别服务官网"}
          </button>
          <span>只会打开上面选中的图片识别服务，不会跳到主聊天模型服务。</span>
        </div>
        <label>
          Base URL
          <input
            value={visionBaseUrl}
            onChange={(event) => setVisionBaseUrl(event.target.value)}
            disabled={visionProvider === "auto" || loadingVision || savingVision}
            placeholder={selectedVisionProvider?.base_url || "服务默认地址"}
          />
        </label>
      </div>
      {visionProviders.length === 0 && <p className="settingsInlineMessage">当前服务列表里没有可直接配置的图片识别模型。</p>}
      <div className="visionModelActions">
        {allowClear && (
          <button type="button" className="secondaryButton" onClick={() => void clearVision()} disabled={savingVision || loadingVision || !visionConfigured}>
            清除图片识别模型
          </button>
        )}
        <button type="button" onClick={() => void saveVision()} disabled={savingVision || loadingVision || visionProviders.length === 0}>
          {savingVision ? "保存中" : saveLabel}
        </button>
      </div>
    </div>
  );
}
