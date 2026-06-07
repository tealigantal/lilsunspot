import { useState } from "react";
import { runDoctor, runRepair } from "../../api";
import type { DoctorResult } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { TechnicalDetails } from "../../shared/components/TechnicalDetails";

export function DoctorSettings() {
  const [doctor, setDoctor] = useState<DoctorResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function check() {
    setBusy(true);
    setMessage("");
    try {
      setDoctor(await runDoctor());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "诊断失败。");
    } finally {
      setBusy(false);
    }
  }

  async function repair() {
    setBusy(true);
    setMessage("");
    try {
      const result = await runRepair();
      setMessage(`${result.message} ${result.suggestion}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "修复失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settingsSection">
      <div className="settingsHeader">
        <div>
          <h3>诊断和修复</h3>
          <p>遇到问题时先运行一键检查。技术详情默认折叠。</p>
        </div>
        <StatusBadge tone={doctor?.ok ? "ok" : "neutral"}>{doctor ? (doctor.ok ? "检查通过" : "存在问题") : "未检查"}</StatusBadge>
      </div>
      <div className="actionRow">
        <button type="button" onClick={check} disabled={busy}>
          {busy ? "检查中" : "一键检查"}
        </button>
        <button type="button" className="secondaryButton" onClick={repair} disabled={busy}>
          一键修复
        </button>
      </div>
      <p className="inlineNotice">
        <StatusBadge>待接入</StatusBadge>
        <span>诊断包导出待接入。</span>
      </p>
      {message && <p className="inlineStatus">{message}</p>}
      {doctor && <TechnicalDetails data={doctor} />}
    </section>
  );
}
