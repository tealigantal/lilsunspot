import { useEffect, useMemo, useState } from "react";
import type { AppBootstrapRuntime, CurrentMode, Provider } from "../../types";
import { getProviders } from "../../api";
import { ModelSettings } from "../model/ModelSettings";
import { ModeSettings } from "../mode/ModeSettings";
import { DoctorSettings } from "./DoctorSettings";
import { SafetySettings } from "./SafetySettings";
import { WeixinSettings } from "./WeixinSettings";

export type SettingsTab = "model" | "mode" | "weixin" | "safety" | "doctor";

type SettingsDrawerProps = {
  open: boolean;
  runtime: AppBootstrapRuntime;
  onClose: () => void;
  onSetupModel: () => void;
  onModeChanged?: (mode: CurrentMode) => void;
  initialTab?: SettingsTab;
};

const TABS: { id: SettingsTab; label: string; badge?: string }[] = [
  { id: "model", label: "模型服务" },
  { id: "mode", label: "输出模式" },
  { id: "weixin", label: "微信", badge: "未连接" },
  { id: "safety", label: "安全审批", badge: "暂无待处理" },
  { id: "doctor", label: "诊断", badge: "未检查" }
];

export function SettingsDrawer({ open, runtime, onClose, onSetupModel, onModeChanged, initialTab = "model" }: SettingsDrawerProps) {
  const [active, setActive] = useState<SettingsTab>(initialTab);
  const [providers, setProviders] = useState<Provider[]>([]);

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
    let mounted = true;
    async function load() {
      try {
        const list = await getProviders();
        if (mounted) {
          setProviders(list);
        }
      } catch {
        if (mounted) {
          setProviders([]);
        }
      }
    }
    void load();
    return () => {
      mounted = false;
    };
  }, [open, initialTab]);

  const currentProvider = useMemo(
    () => providers.find((provider) => provider.id === runtime.provider) || null,
    [providers, runtime.provider]
  );

  if (!open) {
    return null;
  }

  return (
    <div className="drawerBackdrop" role="presentation">
      <aside className="settingsDrawer" aria-label="设置">
        <header>
          <div>
            <h2>设置</h2>
            <p>模型、输出风格和本地连接状态都在这里调整。</p>
          </div>
          <button type="button" className="iconButton" onClick={onClose} aria-label="关闭设置">
            ×
          </button>
        </header>
        <nav className="settingsNav" aria-label="设置分类">
          {TABS.map((tab) => (
            <button key={tab.id} type="button" className={active === tab.id ? "active" : ""} onClick={() => setActive(tab.id)}>
              <span>{tab.label}</span>
              {tab.badge && <em>{tab.badge}</em>}
            </button>
          ))}
        </nav>
        <div className="drawerBody">
          {active === "model" && <ModelSettings runtime={runtime} provider={currentProvider} onSetupModel={onSetupModel} />}
          {active === "mode" && <ModeSettings onModeChanged={onModeChanged} />}
          {active === "weixin" && <WeixinSettings />}
          {active === "safety" && <SafetySettings />}
          {active === "doctor" && <DoctorSettings />}
        </div>
      </aside>
    </div>
  );
}
