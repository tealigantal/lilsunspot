import { useEffect, useMemo, useState } from "react";
import type { AppBootstrapRuntime, AppUpdateStatus, ModelCapabilities, OperationNotice, OperationState, Provider } from "../../types";
import { ModelSettings } from "../model/ModelSettings";
import { AppUpdateSettings } from "./AppUpdateSettings";
import { CapabilitySettings } from "./CapabilitySettings";
import { ControlCenterSettings } from "./ControlCenterSettings";
import { DoctorSettings } from "./DoctorSettings";
import { SafetySettings } from "./SafetySettings";
import { WeixinSettings } from "./WeixinSettings";

export type SettingsTab = "model" | "capabilities" | "weixin" | "safety" | "doctor" | "control" | "update";

type SettingsDrawerProps = {
  open: boolean;
  runtime: AppBootstrapRuntime;
  providers: Provider[];
  providerState: OperationState;
  providerNotice: OperationNotice | null;
  onProvidersRefresh: () => Promise<Provider[]>;
  modelCapabilities: ModelCapabilities | null;
  capabilityState: OperationState;
  capabilityNotice: OperationNotice | null;
  onModelCapabilitiesChanged: (capabilities: ModelCapabilities | null) => void;
  onModelCapabilitiesRefresh: () => Promise<ModelCapabilities | null>;
  onClose: () => void;
  onSetupModel: () => void;
  onModelSaved: () => Promise<void> | void;
  onLocalProviderReset: () => Promise<void> | void;
  updateStatus: AppUpdateStatus | null;
  onUpdateStatusChanged: (status: AppUpdateStatus) => void;
  initialTab?: SettingsTab;
};

const TABS: { id: SettingsTab; label: string }[] = [
  { id: "model", label: "模型服务" },
  { id: "capabilities", label: "能力" },
  { id: "weixin", label: "微信" },
  { id: "safety", label: "安全审批" },
  { id: "doctor", label: "诊断" },
  { id: "control", label: "控制台" },
  { id: "update", label: "应用更新" }
];

function imageStatus(modelCapabilities: ModelCapabilities | null) {
  const node = modelCapabilities?.capability_graph?.by_id?.["image.read"];
  if (!node) {
    return "待刷新";
  }
  if (node.status === "ready") {
    return "图片可用";
  }
  if (node.status === "degraded") {
    return "待验证";
  }
  if (node.status === "blocked") {
    return "需检查";
  }
  return "可预览";
}

export function SettingsDrawer({
  open,
  runtime,
  providers,
  providerState,
  providerNotice,
  onProvidersRefresh,
  modelCapabilities,
  capabilityState,
  capabilityNotice,
  onModelCapabilitiesChanged,
  onModelCapabilitiesRefresh,
  onClose,
  onSetupModel,
  onModelSaved,
  onLocalProviderReset,
  updateStatus,
  onUpdateStatusChanged,
  initialTab = "model"
}: SettingsDrawerProps) {
  const [active, setActive] = useState<SettingsTab>(initialTab);

  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setActive(initialTab);
    if (providers.length === 0 && providerState !== "running") {
      void onProvidersRefresh();
    }
  }, [open, initialTab, providers.length, providerState, onProvidersRefresh]);

  const currentProvider = useMemo(
    () => providers.find((provider) => provider.id === runtime.provider || provider.hermes_provider === runtime.provider) || null,
    [providers, runtime.provider]
  );

  const tabBadges: Partial<Record<SettingsTab, string>> = {
    model: runtime.configured ? "已设置" : "未设置",
    capabilities: capabilityState === "running" ? "刷新中" : imageStatus(modelCapabilities),
    weixin: modelCapabilities?.supports_weixin ? "可配置" : "未连接",
    safety: "审批",
    doctor: "诊断",
    control: "总览",
    update:
      updateStatus?.state === "available"
        ? "有新版"
        : updateStatus?.state === "failed"
          ? "检查失败"
          : updateStatus?.state === "current"
            ? "最新"
            : "检查"
  };

  if (!open) {
    return null;
  }

  return (
    <div className="drawerBackdrop" role="presentation">
      <aside className="settingsDrawer" aria-label="设置">
        <header>
          <div>
            <h2>设置</h2>
            <p>模型服务、微信连接和本地控制台都在这里调整。</p>
          </div>
          <button type="button" className="iconButton" onClick={onClose} aria-label="关闭设置">
            ×
          </button>
        </header>
        <nav className="settingsNav" aria-label="设置分类">
          {TABS.map((tab) => (
            <button key={tab.id} type="button" className={active === tab.id ? "active" : ""} onClick={() => setActive(tab.id)}>
              <span>{tab.label}</span>
              {tabBadges[tab.id] && <em>{tabBadges[tab.id]}</em>}
            </button>
          ))}
        </nav>
        <div className="drawerBody">
          {active === "model" && (
            <ModelSettings
              runtime={runtime}
              provider={currentProvider}
              providers={providers}
              providerState={providerState}
              providerNotice={providerNotice}
              onProvidersRefresh={onProvidersRefresh}
              modelCapabilities={modelCapabilities}
              capabilityNotice={capabilityNotice}
              onModelCapabilitiesChanged={onModelCapabilitiesChanged}
              onModelCapabilitiesRefresh={onModelCapabilitiesRefresh}
              onSetupModel={onSetupModel}
              onModelSaved={onModelSaved}
              onLocalProviderReset={onLocalProviderReset}
            />
          )}
          {active === "capabilities" && (
            <CapabilitySettings
              modelCapabilities={modelCapabilities}
              capabilityNotice={capabilityNotice}
              onModelCapabilitiesRefresh={onModelCapabilitiesRefresh}
              onModelCapabilitiesChanged={onModelCapabilitiesChanged}
            />
          )}
          {active === "weixin" && <WeixinSettings />}
          {active === "safety" && <SafetySettings />}
          {active === "doctor" && <DoctorSettings />}
          {active === "update" && <AppUpdateSettings status={updateStatus} onStatusChanged={onUpdateStatusChanged} />}
          {active === "control" && (
            <ControlCenterSettings
              modelCapabilities={modelCapabilities}
              capabilityNotice={capabilityNotice}
              onModelCapabilitiesRefresh={onModelCapabilitiesRefresh}
              onModelCapabilitiesChanged={onModelCapabilitiesChanged}
            />
          )}
        </div>
      </aside>
    </div>
  );
}
