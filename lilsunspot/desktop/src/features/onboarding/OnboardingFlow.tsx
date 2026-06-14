import { useEffect, useMemo, useRef, useState } from "react";
import { getProviderCapabilities, openProviderKeyUrl, saveProvider, testProvider } from "../../api";
import { StepLayout } from "../../shared/components/StepLayout";
import { ErrorWithAction } from "../../shared/components/ErrorWithAction";
import { OperationNoticeBanner } from "../../shared/components/OperationNoticeBanner";
import type { ModelCapabilities, OperationNotice, Provider, ProviderTestResult } from "../../types";
import type { ChatMessage } from "../chat/ChatTranscript";
import { ChooseModelServiceStep } from "./ChooseModelServiceStep";
import { FirstChatStep } from "./FirstChatStep";
import { ApiKeyStep } from "./ApiKeyStep";
import { VisionModelPanel } from "../model/VisionModelPanel";
import { WelcomeStep } from "./WelcomeStep";

type OnboardingStep = "welcome" | "choose" | "api_key" | "first_chat";

type OnboardingFlowProps = {
  initialProvider?: string;
  initialStep?: "welcome" | "choose" | "api_key";
  completion?: "first_chat" | "return_to_chat";
  onSaved: () => Promise<void> | void;
  onFirstChatDone: (messages: ChatMessage[]) => void;
  providers: Provider[];
  providersBusy?: boolean;
  providersNotice?: OperationNotice | null;
  onProvidersRefresh: () => Promise<Provider[]>;
  modelCapabilities?: ModelCapabilities | null;
  onModelCapabilitiesChanged?: (capabilities: ModelCapabilities | null) => void;
};

const STEPS = ["欢迎", "选择模型", "模型服务", "第一句聊天"];

function stepNumber(step: OnboardingStep) {
  return ["welcome", "choose", "api_key", "first_chat"].indexOf(step) + 1;
}

function stepCopy(step: OnboardingStep) {
  const copy: Record<OnboardingStep, { title: string; message: string }> = {
    welcome: { title: "欢迎使用小黑子", message: "先给小黑子设置一个 AI 服务，就能开始聊天。" },
    choose: { title: "选择 AI 服务", message: "推荐先选一个常用服务，也可以稍后在设置里更换。" },
    api_key: { title: "保存模型设置", message: "API Key 和图片识别都在这里处理；Key 只保存在你的电脑本机。" },
    first_chat: { title: "试着说第一句话", message: "如果服务商暂时连不上，也可以稍后回到设置里重新测试。" }
  };
  return copy[step];
}

function needsVisionOnboarding(capabilities: ModelCapabilities) {
  return capabilities.configured && !capabilities.supports_image;
}

function operationNotice(
  tone: OperationNotice["tone"],
  message: string,
  source: string,
  blocking = false
): OperationNotice {
  return {
    tone,
    message,
    blocking,
    source
  };
}

export function OnboardingFlow({
  initialProvider,
  initialStep,
  completion = "first_chat",
  onSaved,
  onFirstChatDone,
  providers,
  providersBusy = false,
  providersNotice = null,
  onProvidersRefresh,
  modelCapabilities: sharedModelCapabilities = null,
  onModelCapabilitiesChanged
}: OnboardingFlowProps) {
  const [step, setStep] = useState<OnboardingStep>(initialStep || (initialProvider ? "choose" : "welcome"));
  const [selectedProvider, setSelectedProvider] = useState(initialProvider || "");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrlOverride, setBaseUrlOverride] = useState("");
  const [providerTest, setProviderTest] = useState<ProviderTestResult | null>(null);
  const [modelCapabilities, setModelCapabilities] = useState<ModelCapabilities | null>(sharedModelCapabilities);
  const [showMore, setShowMore] = useState(false);
  const [visionProceeding, setVisionProceeding] = useState(false);
  const [operation, setOperation] = useState<"idle" | "saving" | "testing">("idle");
  const [error, setError] = useState("");
  const [inlineNotice, setInlineNotice] = useState("");
  const [currentOperationNotice, setCurrentOperationNotice] = useState<OperationNotice | null>(null);
  const initializedProviderRef = useRef(false);

  useEffect(() => {
    setModelCapabilities(sharedModelCapabilities);
  }, [sharedModelCapabilities]);

  useEffect(() => {
    if (providers.length === 0) {
      if (!providersBusy) {
        void onProvidersRefresh();
      }
      return;
    }
    if (initializedProviderRef.current) {
      return;
    }
    const selected = providers.find((provider) => provider.id === (initialProvider || selectedProvider)) || providers[0];
    if (selected) {
      chooseProvider(selected);
      initializedProviderRef.current = true;
    }
  }, [providers, providersBusy, initialProvider, selectedProvider, onProvidersRefresh]);

  const selectedProviderConfig = useMemo(
    () => providers.find((provider) => provider.id === selectedProvider) || null,
    [providers, selectedProvider]
  );

  function chooseProvider(provider: Provider) {
    setSelectedProvider(provider.id);
    setModel(provider.default_model);
    setBaseUrlOverride("");
    setApiKey("");
    setProviderTest(null);
    setError("");
    setInlineNotice("");
    setCurrentOperationNotice(null);
  }

  async function pasteApiKey() {
    try {
      const text = await navigator.clipboard.readText();
      setApiKey(text.trim());
      setInlineNotice("");
      if (!text.trim()) {
        setError("剪贴板里没有可用内容。");
      }
    } catch {
      setError("无法读取剪贴板，请手动粘贴 API Key。");
    }
  }

  async function openKeyUrl() {
    if (!selectedProviderConfig) {
      setError("请先选择 AI 服务。");
      return;
    }
    setError("");
    setInlineNotice("");
    try {
      const keyUrl = await openProviderKeyUrl(selectedProviderConfig.id);
      setInlineNotice(`已打开 ${selectedProviderConfig.display_name} 的 Key 页面：${keyUrl}`);
    } catch (openError) {
      setInlineNotice(openError instanceof Error ? openError.message : "打开官网失败，请手动进入服务商控制台。");
    }
  }

  async function testConnection() {
    if (!selectedProviderConfig) {
      setError("请先选择 AI 服务。");
      return;
    }
    const nextModel = model.trim();
    const nextApiKey = apiKey.trim();
    const localProvider = selectedProviderConfig.type === "local";
    if (!nextModel) {
      setError("模型名称不能为空。");
      return;
    }
    if (!localProvider && !nextApiKey) {
      setError("API Key 不能为空。");
      return;
    }
    setOperation("testing");
    setError("");
    setInlineNotice("");
    setCurrentOperationNotice(null);
    setProviderTest(null);
    try {
      const testResult = await testProvider(selectedProviderConfig.id, nextModel, nextApiKey, baseUrlOverride.trim());
      setProviderTest(testResult);
      if (testResult.ok) {
        setModel(testResult.model);
      }
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : "测试连接失败，请稍后重试。");
    } finally {
      setOperation("idle");
    }
  }

  async function saveAndContinue() {
    if (!selectedProviderConfig) {
      setError("请先选择 AI 服务。");
      return;
    }
    const nextModel = model.trim();
    const nextApiKey = apiKey.trim();
    const nextBaseUrlOverride = baseUrlOverride.trim();
    const localProvider = selectedProviderConfig.type === "local";
    if (!nextModel) {
      setError("模型名称不能为空。");
      return;
    }
    if (!localProvider && !nextApiKey) {
      setError("API Key 不能为空。");
      return;
    }
    setOperation("saving");
    setError("");
    setInlineNotice("");
    setCurrentOperationNotice(null);
    try {
      const saved = await saveProvider(selectedProviderConfig.id, nextModel, nextApiKey, nextBaseUrlOverride);
      setApiKey("");
      setModel(saved.model);
      setProviderTest(null);
      setCurrentOperationNotice(operationNotice("success", "模型服务已保存到本机。", "providers.save"));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存失败，请稍后重试。");
      setOperation("idle");
      return;
    }

    let nextCapabilities: ModelCapabilities | null = null;
    try {
      nextCapabilities = await getProviderCapabilities();
      setModelCapabilities(nextCapabilities);
      onModelCapabilitiesChanged?.(nextCapabilities);
    } catch (refreshError) {
      setModelCapabilities(null);
      onModelCapabilitiesChanged?.(null);
      setCurrentOperationNotice(
        operationNotice(
          "warning",
          refreshError instanceof Error
            ? `模型服务已保存；能力状态稍后刷新。刷新失败原因：${refreshError.message}`
            : "模型服务已保存；能力状态稍后刷新。",
          "providers.capabilities"
        )
      );
    } finally {
      setOperation("idle");
    }

    if (nextCapabilities && needsVisionOnboarding(nextCapabilities)) {
      setOperation("idle");
      return;
    }
    if (completion === "return_to_chat") {
      try {
        await onSaved();
      } catch (savedRefreshError) {
        setCurrentOperationNotice(
          operationNotice(
            "warning",
            savedRefreshError instanceof Error
              ? `模型服务已保存；界面状态稍后刷新。刷新失败原因：${savedRefreshError.message}`
              : "模型服务已保存；界面状态稍后刷新。",
            "app.bootstrap"
          )
        );
      }
      return;
    }
    setStep("first_chat");
  }

  async function continueAfterVisionChoice() {
    if (visionProceeding) {
      return;
    }
    setVisionProceeding(true);
    if (completion !== "return_to_chat") {
      setStep("first_chat");
      setVisionProceeding(false);
      return;
    }
    setOperation("saving");
    try {
      await onSaved();
    } catch (savedRefreshError) {
      setCurrentOperationNotice(
        operationNotice(
          "warning",
          savedRefreshError instanceof Error
            ? `模型服务已保存；界面状态稍后刷新。刷新失败原因：${savedRefreshError.message}`
            : "模型服务已保存；界面状态稍后刷新。",
          "app.bootstrap"
        )
      );
    } finally {
      setOperation("idle");
      setVisionProceeding(false);
    }
  }

  const copy = stepCopy(step);
  const visibleSteps = completion === "return_to_chat" ? STEPS.slice(0, 3) : STEPS;
  const showVisionPanel = step === "api_key" && modelCapabilities?.configured && needsVisionOnboarding(modelCapabilities);
  const busy = providersBusy;

  return (
    <StepLayout current={stepNumber(step)} steps={visibleSteps} title={copy.title} message={copy.message}>
      {providersNotice && providers.length === 0 && (
        <ErrorWithAction
          title="AI 服务列表没有加载成功"
          message={providersNotice.message}
          suggestion="请重新读取服务列表；这不会改动已经保存的 Key。"
          primaryAction={{ label: "重新读取", onClick: () => void onProvidersRefresh() }}
        />
      )}
      {currentOperationNotice && <OperationNoticeBanner notice={currentOperationNotice} />}
      {error && (
        <ErrorWithAction
          title="当前步骤没有完成"
          message={error}
          suggestion="请按提示处理后再继续。"
          primaryAction={{ label: "重新加载", onClick: () => window.location.reload() }}
        />
      )}
      {step === "welcome" && <WelcomeStep onNext={() => setStep("choose")} />}
      {step === "choose" && (
        <ChooseModelServiceStep
          providers={providers}
          selectedProvider={selectedProvider}
          showMore={showMore}
          onShowMoreChange={setShowMore}
          onSelect={chooseProvider}
          onBack={() => setStep("welcome")}
          onNext={() => setStep("api_key")}
          busy={busy}
        />
      )}
      {step === "api_key" && (
        <>
          <ApiKeyStep
            provider={selectedProviderConfig}
            apiKey={apiKey}
            onApiKeyChange={setApiKey}
            onPaste={pasteApiKey}
            onOpenKeyUrl={openKeyUrl}
            onBack={() => setStep("choose")}
            model={model}
            baseUrlOverride={baseUrlOverride}
            result={providerTest}
            onModelChange={setModel}
            onBaseUrlChange={setBaseUrlOverride}
            onSave={saveAndContinue}
            onTest={testConnection}
            onChangeProvider={() => setStep("choose")}
            notice={inlineNotice}
            busy={busy || operation !== "idle" || visionProceeding}
            saving={operation === "saving"}
            testing={operation === "testing"}
          />
          {showVisionPanel && (
            <VisionModelPanel
              providers={providers}
              modelCapabilities={modelCapabilities}
              title="同一页添加图片识别"
              description="当前主聊天模型不能直接看图；你可以现在补一个图片识别模型，也可以先只用文字聊天。"
              saveLabel="保存并继续"
              onCapabilitiesChanged={(capabilities) => {
                setModelCapabilities(capabilities);
                onModelCapabilitiesChanged?.(capabilities);
              }}
              onCapabilitiesLoaded={(capabilities) => {
                setModelCapabilities(capabilities);
                onModelCapabilitiesChanged?.(capabilities);
              }}
              onSaved={() => void continueAfterVisionChoice()}
              headerAction={
                <button type="button" className="secondaryButton compactButton" onClick={() => void continueAfterVisionChoice()}>
                  跳过图片识别，先聊天
                </button>
              }
            />
          )}
        </>
      )}
      {step === "first_chat" && <FirstChatStep onDone={onFirstChatDone} onSkip={onFirstChatDone} />}
    </StepLayout>
  );
}
