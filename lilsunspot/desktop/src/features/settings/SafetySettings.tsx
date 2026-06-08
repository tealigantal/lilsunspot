import { useEffect, useState } from "react";
import { decideSafetyApproval, getSafetyApprovals, getSafetyPolicy } from "../../api";
import type { SafetyApproval, SafetyApprovals, SafetyPolicy } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { TechnicalDetails } from "../../shared/components/TechnicalDetails";

function riskTone(approval: SafetyApproval) {
  const text = `${approval.operation} ${approval.summary}`.toLowerCase();
  if (text.includes("delete") || text.includes("shell") || text.includes("credential") || text.includes("file")) {
    return "danger";
  }
  if (text.includes("weixin") || text.includes("message") || text.includes("send")) {
    return "warning";
  }
  return "ok";
}

function riskCopy(approval: SafetyApproval) {
  const tone = riskTone(approval);
  if (tone === "danger") {
    return "风险：可能改写本机文件或读取敏感信息。";
  }
  if (tone === "warning") {
    return "风险：可能向外部联系人发送内容。";
  }
  return "风险：普通操作，仍建议确认来源。";
}

function operationTitle(operation: string) {
  const names: Record<string, string> = {
    send_weixin_message: "微信发送消息",
    shell: "Shell 执行",
    credential_access: "凭据访问"
  };
  return names[operation] || operation.replace(/_/g, " ");
}

export function SafetySettings() {
  const [policy, setPolicy] = useState<SafetyPolicy | null>(null);
  const [approvals, setApprovals] = useState<SafetyApprovals | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void load();
  }, []);

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

  async function decide(approvalId: string, decision: "approved" | "rejected") {
    setBusy(true);
    setMessage("");
    try {
      const result = await decideSafetyApproval(approvalId, decision);
      setMessage(result.message);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "审批处理失败。");
    } finally {
      setBusy(false);
    }
  }

  const pendingCount = approvals?.pending?.length || 0;

  return (
    <section className="settingsSection safetyConsole">
      <div className="settingsHeader">
        <div>
          <h3>裁判席：待审批操作</h3>
          <p>不要展示原始 tool JSON，只展示人话风险和可选动作。</p>
        </div>
        <StatusBadge tone={pendingCount > 0 ? "warning" : "ok"}>{pendingCount > 0 ? `${pendingCount} 个待审批` : "暂无待处理"}</StatusBadge>
      </div>
      <div className="approvalList">
        {pendingCount === 0 ? (
          <article className="emptyApprovalCard">
            <strong>暂无待审批操作</strong>
            <p>Shell、删除文件、微信发送这类动作会先进入这里。</p>
          </article>
        ) : (
          approvals?.pending.map((approval) => (
            <article key={approval.id} className={`approvalCard ${riskTone(approval)}`}>
              <div>
                <StatusBadge tone={riskTone(approval) === "danger" ? "danger" : "warning"}>待审批</StatusBadge>
                <h4>{operationTitle(approval.operation)}</h4>
                <p>{approval.summary || "准备执行一个需要确认的本地操作。"}</p>
                <strong>{riskCopy(approval)}</strong>
              </div>
              <div className="approvalActions">
                <button type="button" className="dangerButton" onClick={() => void decide(approval.id, "rejected")} disabled={busy}>
                  拒绝
                </button>
                <button type="button" onClick={() => void decide(approval.id, "approved")} disabled={busy}>
                  允许一次
                </button>
                <button type="button" className="secondaryButton" disabled title="后端策略接口尚未接入">
                  总是允许
                </button>
              </div>
            </article>
          ))
        )}
      </div>
      <button type="button" className="secondaryButton" onClick={load} disabled={busy}>
        {busy ? "读取中" : "重新读取审批状态"}
      </button>
      {message && <p className="inlineStatus">{message}</p>}
      {(policy || approvals) && <TechnicalDetails data={{ policy, approvals }} />}
    </section>
  );
}
