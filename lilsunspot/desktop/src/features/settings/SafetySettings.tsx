import { useState } from "react";
import { getSafetyApprovals, getSafetyPolicy } from "../../api";
import type { SafetyApprovals, SafetyPolicy } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { TechnicalDetails } from "../../shared/components/TechnicalDetails";

export function SafetySettings() {
  const [policy, setPolicy] = useState<SafetyPolicy | null>(null);
  const [approvals, setApprovals] = useState<SafetyApprovals | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    setBusy(true);
    setMessage("");
    try {
      const [nextPolicy, nextApprovals] = await Promise.all([getSafetyPolicy(), getSafetyApprovals()]);
      setPolicy(nextPolicy);
      setApprovals(nextApprovals);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "安全审批状态读取失败。");
    } finally {
      setBusy(false);
    }
  }

  const pendingCount = approvals?.pending?.length || 0;

  return (
    <section className="settingsSection">
      <div className="settingsHeader">
        <div>
          <h3>安全审批</h3>
          <p>安全审批基础接口存在，真实高危动作拦截仍需验证。</p>
        </div>
        <StatusBadge tone="warning">需要后续验证</StatusBadge>
      </div>
      <div className="settingsSummary">
        <span>待审批</span>
        <strong>{pendingCount > 0 ? `${pendingCount} 个` : "暂无待审批"}</strong>
      </div>
      <button type="button" className="secondaryButton" onClick={load} disabled={busy}>
        {busy ? "读取中" : "加载审批状态"}
      </button>
      {message && <p className="inlineStatus">{message}</p>}
      {(policy || approvals) && <TechnicalDetails data={{ policy, approvals }} />}
    </section>
  );
}
