import { useEffect, useMemo, useState } from "react";
import type { AppBootstrapRuntime, Provider } from "../../types";
import { getProviders } from "../../api";
import { ModelSettings } from "../model/ModelSettings";
import { ControlCenterSettings } from "./ControlCenterSettings";
import { WeixinSettings } from "./WeixinSettings";

export type SettingsTab = "model" | "weixin" | "control";

type SettingsDrawerProps = {
  open: boolean;
  runtime: AppBootstrapRuntime;
  onClose: () => void;
  onSetupModel: () => void;
  initialTab?: SettingsTab;
};

const TABS: { id: SettingsTab; label: string; badge?: string }[] = [
  { id: "model", label: "模型服务" },
  { id: "weixin", label: "微信", badge: "未连接" },
  { id: "control", label: "控制台" }
];

export function SettingsDrawer({ open, runtime, onClose, onSetupModel, initialTab = "model" }: SettingsDrawerProps) {
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
              {tab.badge && <em>{tab.badge}</em>}
            </button>
          ))}
        </nav>
        <div className="drawerBody">
          {active === "model" && <ModelSettings runtime={runtime} provider={currentProvider} onSetupModel={onSetupModel} />}
          {active === "weixin" && <WeixinSettings />}
          {active === "control" && <ControlCenterSettings />}
        </div>
      </aside>
    </div>
  );
}
