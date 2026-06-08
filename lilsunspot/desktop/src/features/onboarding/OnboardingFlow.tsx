import { useEffect, useMemo, useState } from "react";
import { getProviders, openProviderKeyUrl, saveProvider, testProvider } from "../../api";
import { StepLayout } from "../../shared/components/StepLayout";
import { ErrorWithAction } from "../../shared/components/ErrorWithAction";
import type { Provider, ProviderTestResult } from "../../types";
import type { ChatMessage } from "../chat/ChatTranscript";
import { ChooseModelServiceStep } from "./ChooseModelServiceStep";
import { FirstChatStep } from "./FirstChatStep";
import { ApiKeyStep } from "./ApiKeyStep";
import { WelcomeStep } from "./WelcomeStep";

type OnboardingStep = "welcome" | "choose" | "api_key" | "first_chat";

type OnboardingFlowProps = {
  initialProvider?: string;
  initialStep?: "welcome" | "choose" | "api_key";
  completion?: "first_chat" | "return_to_chat";
  onSaved: () => Promise<void> | void;
  onFirstChatDone: (messages: ChatMessage[]) => void;
  onOpenDoctor: () => void;
};

const STEPS = ["欢迎", "选择模型", "保存 Key", "第一句聊天"];

function stepNumber(step: OnboardingStep) {
  return ["welcome", "choose", "api_key", "first_chat"].indexOf(step) + 1;
}

function stepCopy(step: OnboardingStep) {
  const copy: Record<OnboardingStep, { title: string; message: string }> = {
    welcome: { title: "欢迎使用小黑子", message: "先给小黑子设置一个 AI 服务，就能开始聊天。" },
    choose: { title: "选择 AI 服务", message: "推荐先选一个常用服务，也可以稍后在设置里更换。" },
    api_key: { title: "保存模型设置", message: "API Key 只保存在你的电脑本机；测试连接是保存后的可选验证。" },
    first_chat: { title: "试着说第一句话", message: "如果服务商暂时连不上，也可以稍后回到设置里重新测试。" }
  };
  return copy[step];
}

export function OnboardingFlow({
  initialProvider,
  initialStep,
  completion = "first_chat",
  onSaved,
  onFirstChatDone,
  onOpenDoctor
}: OnboardingFlowProps) {
  const [step, setStep] = useState<OnboardingStep>(initialStep || (initialProvider ? "choose" : "welcome"));
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState(initialProvider || "");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrlOverride, setBaseUrlOverride] = useState("");
  const [providerTest, setProviderTest] = useState<ProviderTestResult | null>(null);
  const [showMore, setShowMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState<"idle" | "saving" | "testing">("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    async function load() {
      setBusy(true);
      setError("");
      try {
        const list = await getProviders();
        if (!mounted) {
          return;
        }
        setProviders(list);
        const selected = list.find((provider) => provider.id === (initialProvider || selectedProvider)) || list[0];
        if (selected) {
          chooseProvider(selected);
        }
      } catch (loadError) {
        if (mounted) {
          setError(loadError instanceof Error ? loadError.message : "AI 服务列表加载失败。");
        }
      } finally {
        if (mounted) {
          setBusy(false);
        }
      }
    }
    void load();
    return () => {
      mounted = false;
    };
  }, [initialProvider]);

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
  }

  async function pasteApiKey() {
    try {
      const text = await navigator.clipboard.readText();
      setApiKey(text.trim());
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
    try {
      await openProviderKeyUrl(selectedProviderConfig.id);
    } catch (openError) {
      setError(openError instanceof Error ? openError.message : "打开官网失败。");
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
    let leavingFlow = false;
    try {
      const saved = await saveProvider(selectedProviderConfig.id, nextModel, nextApiKey, nextBaseUrlOverride);
      setApiKey("");
      setModel(saved.model);
      setProviderTest(null);
      if (completion === "return_to_chat") {
        leavingFlow = true;
        setOperation("idle");
        await onSaved();
        return;
      }
      setStep("first_chat");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存失败，请稍后重试。");
    } finally {
      if (!leavingFlow) {
        setOperation("idle");
      }
    }
  }

  const copy = stepCopy(step);

  return (
    <StepLayout current={stepNumber(step)} steps={STEPS} title={copy.title} message={copy.message}>
      {error && (
        <ErrorWithAction
          title="当前步骤没有完成"
          message={error}
          suggestion="请按提示处理后再继续。"
          primaryAction={{ label: "重新加载", onClick: () => window.location.reload() }}
          secondaryActions={[{ label: "一键检查", onClick: onOpenDoctor }]}
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
          busy={busy || operation !== "idle"}
          saving={operation === "saving"}
          testing={operation === "testing"}
        />
      )}
      {step === "first_chat" && <FirstChatStep onDone={onFirstChatDone} onSkip={onFirstChatDone} />}
    </StepLayout>
  );
}
