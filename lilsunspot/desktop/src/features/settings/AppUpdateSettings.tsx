import { useEffect, useState } from "react";
import { checkUpdate, dismissUpdate, downloadAndInstallUpdate } from "../../api";
import type { AppUpdateStatus } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";

type AppUpdateSettingsProps = {
  status: AppUpdateStatus | null;
  onStatusChanged: (status: AppUpdateStatus) => void;
};

function statusTone(status: AppUpdateStatus | null): "ok" | "warning" | "danger" | "neutral" {
  if (!status) {
    return "neutral";
  }
  if (status.state === "available") {
    return status.update?.critical ? "danger" : "warning";
  }
  if (status.state === "current" || status.state === "dismissed") {
    return "ok";
  }
  if (status.state === "failed") {
    return "danger";
  }
  return "neutral";
}

function statusLabel(status: AppUpdateStatus | null) {
  if (!status) {
    return "未检查";
  }
  if (status.state === "available") {
    return "有新版";
  }
  if (status.state === "current") {
    return "已是最新";
  }
  if (status.state === "dismissed") {
    return "已忽略";
  }
  if (status.state === "checking") {
    return "检查中";
  }
  if (status.state === "failed") {
    return "检查失败";
  }
  return "不可用";
}

function formatSize(size?: number | null) {
  if (!size) {
    return "大小待发布源返回";
  }
  if (size > 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.round(size / 1024))} KB`;
}

export function AppUpdateSettings({ status, onStatusChanged }: AppUpdateSettingsProps) {
  const [busy, setBusy] = useState(false);
  const [hiddenUntilNextCheck, setHiddenUntilNextCheck] = useState(false);
  const [message, setMessage] = useState("");
  const update = status?.update || null;

  async function refresh() {
    setBusy(true);
    setHiddenUntilNextCheck(false);
    setMessage("");
    onStatusChanged({ state: "checking", update: update, message: "正在检查更新。" });
    try {
      const next = await checkUpdate();
      onStatusChanged(next);
      setMessage(next.message);
    } finally {
      setBusy(false);
    }
  }

  async function install() {
    setBusy(true);
    setMessage("正在下载并安装更新。");
    try {
      const result = await downloadAndInstallUpdate();
      setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "更新下载或安装失败。");
    } finally {
      setBusy(false);
    }
  }

  async function dismiss() {
    if (!update) {
      return;
    }
    setBusy(true);
    try {
      await dismissUpdate(update.version);
      const next: AppUpdateStatus = {
        state: "dismissed",
        update,
        message: "已忽略这个版本。"
      };
      onStatusChanged(next);
      setMessage(next.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "忽略版本失败。");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!status) {
      void refresh();
    }
  }, []);

  const showUpdate = status?.state === "available" && update && !hiddenUntilNextCheck;

  return (
    <section className="settingsSection appUpdateConsole" aria-busy={busy}>
      <div className="settingsHeader">
        <div>
          <h3>应用更新</h3>
          <p>从小黑子的大陆更新源下载 Windows 安装包，安装时会保留本机数据目录。</p>
        </div>
        <StatusBadge tone={statusTone(status)}>{statusLabel(status)}</StatusBadge>
      </div>

      {showUpdate ? (
        <article className="updateCard">
          <div>
            <span>{update.critical ? "重要更新" : "新版可用"}</span>
            <h4>{update.version}</h4>
            <p>当前版本：{update.current_version || "未知"}</p>
            <p>发布时间：{update.published_at || "待发布源返回"}</p>
            <p>安装包：{formatSize(update.size)}</p>
          </div>
          {update.notes && <p className="updateNotes">{update.notes}</p>}
          <div className="actionRow">
            <button type="button" onClick={install} disabled={busy}>
              {busy ? "处理中" : "下载并安装"}
            </button>
            <button type="button" className="secondaryButton" onClick={() => setHiddenUntilNextCheck(true)} disabled={busy}>
              稍后提醒
            </button>
            <button type="button" className="secondaryButton" onClick={dismiss} disabled={busy}>
              忽略此版本
            </button>
          </div>
        </article>
      ) : (
        <article className="controlPanelCard">
          <h4>{status?.message || "还没有检查更新。"}</h4>
          <p>更新源：updates.lilsunspot.com</p>
          <button type="button" className="secondaryButton compactButton" onClick={() => void refresh()} disabled={busy}>
            {busy ? "检查中" : "重新检查"}
          </button>
        </article>
      )}

      {message && <p className="inlineStatus">{message}</p>}
    </section>
  );
}
