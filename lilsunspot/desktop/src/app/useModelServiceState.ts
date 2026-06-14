import { useCallback, useEffect, useMemo, useState } from "react";
import { getProviderCapabilities, getProviders } from "../api";
import type { ModelCapabilities, OperationNotice, OperationState, Provider } from "../types";

type RuntimeKey = {
  configured: boolean;
  provider: string;
  model: string;
};

export type ModelServiceState = {
  providers: Provider[];
  providerState: OperationState;
  providerNotice: OperationNotice | null;
  modelCapabilities: ModelCapabilities | null;
  capabilityState: OperationState;
  capabilityNotice: OperationNotice | null;
  refreshProviders: () => Promise<Provider[]>;
  refreshCapabilities: () => Promise<ModelCapabilities | null>;
  setModelCapabilities: (capabilities: ModelCapabilities | null) => void;
  clearModelCapabilities: () => void;
};

function notice(message: string, source: string, blocking = false): OperationNotice {
  return {
    tone: blocking ? "danger" : "warning",
    message,
    blocking,
    source
  };
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function useModelServiceState(runtime: RuntimeKey): ModelServiceState {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerState, setProviderState] = useState<OperationState>("idle");
  const [providerNotice, setProviderNotice] = useState<OperationNotice | null>(null);
  const [modelCapabilities, setModelCapabilities] = useState<ModelCapabilities | null>(null);
  const [capabilityState, setCapabilityState] = useState<OperationState>("idle");
  const [capabilityNotice, setCapabilityNotice] = useState<OperationNotice | null>(null);

  const refreshProviders = useCallback(async () => {
    setProviderState("running");
    setProviderNotice(null);
    try {
      const nextProviders = await getProviders();
      setProviders(nextProviders);
      setProviderState("succeeded");
      return nextProviders;
    } catch (error) {
      setProviderState("failed");
      setProviderNotice(notice(errorMessage(error, "AI 服务列表加载失败。"), "providers", true));
      return [];
    }
  }, []);

  const refreshCapabilities = useCallback(async () => {
    if (!runtime.configured) {
      setModelCapabilities(null);
      setCapabilityState("idle");
      setCapabilityNotice(null);
      return null;
    }
    setCapabilityState("running");
    setCapabilityNotice(null);
    try {
      const nextCapabilities = await getProviderCapabilities();
      setModelCapabilities(nextCapabilities);
      setCapabilityState("succeeded");
      return nextCapabilities;
    } catch (error) {
      setCapabilityState("succeeded_with_warning");
      setCapabilityNotice(
        notice(errorMessage(error, "能力状态暂时不可读取，稍后会重新刷新。"), "providers.capabilities")
      );
      return null;
    }
  }, [runtime.configured, runtime.provider, runtime.model]);

  const clearModelCapabilities = useCallback(() => {
    setModelCapabilities(null);
    setCapabilityState("idle");
    setCapabilityNotice(null);
  }, []);

  useEffect(() => {
    void refreshProviders();
  }, [refreshProviders]);

  useEffect(() => {
    void refreshCapabilities();
  }, [refreshCapabilities]);

  return useMemo(
    () => ({
      providers,
      providerState,
      providerNotice,
      modelCapabilities,
      capabilityState,
      capabilityNotice,
      refreshProviders,
      refreshCapabilities,
      setModelCapabilities,
      clearModelCapabilities
    }),
    [
      providers,
      providerState,
      providerNotice,
      modelCapabilities,
      capabilityState,
      capabilityNotice,
      refreshProviders,
      refreshCapabilities,
      clearModelCapabilities
    ]
  );
}
