import { useState } from "react";
import { exportDiagnostics, runDoctor, runRepair } from "../../api";
import type { DoctorCheck, DoctorResult } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { TechnicalDetails } from "../../shared/components/TechnicalDetails";

const CHECK_NAMES: Record<string, string> = {
  daemon_responding: "本地服务 lilsunspotd",
  provider_registry_readable: "Provider / API Key",
  "resource:mode_profiles.yaml": "输出模式文件",
  "resource:provider_registry.yaml": "Provider 注册表",
  "resource:safety_policy.yaml": "安全策略文件",
  daemon_bind_host: "本地服务绑定",
  runtime_token_exists: "运行令牌文件",
  data_dir_exists: "数据目录",
  hermes_home_exists: "Hermes 工作目录",
  logs_dir_exists: "日志目录",
  weixin_gateway: "微信网关",
  diagnostics_redaction: "诊断包脱敏"
};

function checkName(check: DoctorCheck) {
  return CHECK_NAMES[check.name] || check.name;
}

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

  async function exportBundle() {
    setBusy(true);
    setMessage("");
    try {
      const result = await exportDiagnostics();
      setMessage(`${result.message} 文件：${result.file_name}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "诊断包导出失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settingsSection doctorConsole">
      <div className="settingsHeader">
        <div>
          <h3>一键诊断</h3>
          <p>检查项必须人话展示，技术详情默认折叠。</p>
        </div>
        <StatusBadge tone={doctor?.ok ? "ok" : "neutral"}>{doctor ? (doctor.ok ? "检查通过" : "存在问题") : "未检查"}</StatusBadge>
      </div>
      <div className="doctorList">
        {(doctor?.checks || [
          { name: "daemon_responding", ok: false, detail: "尚未检查" },
          { name: "provider_registry_readable", ok: false, detail: "尚未检查" },
          { name: "resource:mode_profiles.yaml", ok: false, detail: "尚未检查" },
          { name: "weixin_gateway", ok: false, detail: "当前只检查状态骨架" },
          { name: "diagnostics_redaction", ok: false, detail: "导出时必须脱敏" }
        ]).map((check) => (
          <article key={check.name} className="doctorCheckCard">
            <span className={check.ok ? "checkDot ok" : "checkDot warning"} />
            <strong>{checkName(check)}</strong>
            <em>{check.ok ? "通过" : "待检查"}</em>
          </article>
        ))}
      </div>
      <div className="actionRow">
        <button type="button" onClick={check} disabled={busy}>
          {busy ? "检查中" : "重新检查"}
        </button>
        <button type="button" className="secondaryButton" onClick={repair} disabled={busy}>
          一键修复
        </button>
        <button type="button" className="secondaryButton" onClick={exportBundle} disabled={busy}>
          导出脱敏诊断包
        </button>
      </div>
      <p className="inlineNotice">
        <StatusBadge>脱敏</StatusBadge>
        <span>诊断包导出必须隐藏 API Key、runtime token 和私聊正文。</span>
      </p>
      {message && <p className="inlineStatus">{message}</p>}
      {doctor && <TechnicalDetails data={doctor} />}
    </section>
  );
}
