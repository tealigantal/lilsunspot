import { useEffect, useMemo, useState } from "react";
import { getCapabilities, patchCapability, testCapability } from "../../api";
import type { Capability, CapabilitiesResult } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { TechnicalDetails } from "../../shared/components/TechnicalDetails";

function toneFor(capability: Capability): "ok" | "warning" | "danger" | "neutral" {
  if (!capability.available || capability.status === "blocked") {
    return "warning";
  }
  if (capability.risk === "high") {
    return "danger";
  }
  if (capability.enabled) {
    return "ok";
  }
  return "neutral";
}

function riskText(risk: string) {
  if (risk === "high") {
    return "高风险";
  }
  if (risk === "medium") {
    return "中风险";
  }
  return "低风险";
}

function statusText(capability: Capability) {
  if (capability.status === "enabled") {
    return "已启用";
  }
  if (capability.status === "blocked") {
    return "被依赖阻断";
  }
  if (capability.status === "needs_config") {
    return "需配置";
  }
  if (capability.status === "unsupported") {
    return "不支持";
  }
  return "未启用";
}

function safeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

export function CapabilitySettings() {
  const [data, setData] = useState<CapabilitiesResult | null>(null);
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setMessage("");
    try {
      setData(await getCapabilities());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "能力列表读取失败。");
    }
  }

  async function toggle(capability: Capability) {
    setBusyId(capability.id);
    setMessage("");
    try {
      await patchCapability(capability.id, !capability.enabled);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "能力开关保存失败。");
    } finally {
      setBusyId("");
    }
  }

  async function runTest(capability: Capability) {
    setBusyId(capability.id);
    setMessage("");
    try {
      const result = await testCapability(capability.id);
      await load();
      setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "能力检查失败。");
    } finally {
      setBusyId("");
    }
  }

  const grouped = useMemo(() => {
    const groups = new Map<string, Capability[]>();
    for (const capability of data?.capabilities || []) {
      const key = capability.category_label || capability.category;
      groups.set(key, [...(groups.get(key) || []), capability]);
    }
    return Array.from(groups.entries());
  }, [data]);

  const enabledCount = data?.capabilities.filter((item) => item.enabled).length || 0;
  const totalCount = data?.capabilities.length || 0;

  return (
    <section className="settingsSection capabilityConsole">
      <div className="settingsHeader">
        <div>
          <h3>Hermes 能力中心</h3>
          <p>本地已有能力统一显示、配置、检查，并纳入审批和审计。</p>
        </div>
        <StatusBadge tone={enabledCount > 0 ? "ok" : "neutral"}>
          {totalCount ? `${enabledCount}/${totalCount} 已启用` : "读取中"}
        </StatusBadge>
      </div>
      <div className="capabilityToolbar">
        <button type="button" className="secondaryButton" onClick={() => void load()} disabled={Boolean(busyId)}>
          重新读取
        </button>
        <span>高风险能力启用后仍需要安全审批，缺账号或缺依赖会显示为不可用。</span>
      </div>
      {message && <p className="inlineStatus">{message}</p>}
      <div className="capabilityGroups">
        {grouped.map(([group, capabilities]) => (
          <article key={group} className="capabilityGroup">
            <header>
              <h4>{group}</h4>
              <span>{capabilities.length} 项</span>
            </header>
            <div className="capabilityList">
              {capabilities.map((capability) => {
                const dependencies = safeStringList(capability.dependencies);
                return (
                  <div key={capability.id} className="capabilityCard">
                    <div className="capabilityCardMain">
                      <div className="capabilityTitleRow">
                        <strong>{capability.name}</strong>
                        <StatusBadge tone={toneFor(capability)}>{statusText(capability)}</StatusBadge>
                      </div>
                      <p>{capability.description || capability.status_text}</p>
                      <div className="capabilityMeta">
                        <span>{riskText(capability.risk)}</span>
                        <span>{capability.source || "hermes"}</span>
                        {dependencies.slice(0, 2).map((dependency, index) => (
                          <span key={`${dependency}-${index}`}>{dependency}</span>
                        ))}
                      </div>
                    </div>
                    <div className="capabilityActions">
                      <button
                        type="button"
                        className="secondaryButton"
                        onClick={() => void runTest(capability)}
                        disabled={busyId === capability.id}
                      >
                        检查
                      </button>
                      <button
                        type="button"
                        onClick={() => void toggle(capability)}
                        disabled={!capability.configurable || busyId === capability.id}
                        title={capability.configurable ? "" : "这个能力需要在对应配置页调整"}
                      >
                        {capability.enabled ? "关闭" : "启用"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </article>
        ))}
      </div>
      {data && <TechnicalDetails title="能力注册详情" data={data} />}
    </section>
  );
}
