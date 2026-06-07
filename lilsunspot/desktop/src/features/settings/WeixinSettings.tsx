import { useState } from "react";
import { getWeixinCommands, getWeixinStatus } from "../../api";
import type { WeixinCommand, WeixinStatus } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { TechnicalDetails } from "../../shared/components/TechnicalDetails";

export function WeixinSettings() {
  const [status, setStatus] = useState<WeixinStatus | null>(null);
  const [commands, setCommands] = useState<WeixinCommand[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    setBusy(true);
    setMessage("");
    try {
      const [nextStatus, nextCommands] = await Promise.all([getWeixinStatus(), getWeixinCommands()]);
      setStatus(nextStatus);
      setCommands(nextCommands);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "微信状态读取失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settingsSection">
      <div className="settingsHeader">
        <div>
          <h3>微信</h3>
          <p>微信连接暂未开放，当前版本不会扫码登录或发送消息。</p>
        </div>
        <StatusBadge tone="warning">暂未开放</StatusBadge>
      </div>
      <ul className="plainList">
        <li>后续目标：扫码连接</li>
        <li>后续目标：微信里使用 /模式</li>
        <li>后续目标：资料卡命令</li>
      </ul>
      <button type="button" className="secondaryButton" onClick={load} disabled={busy}>
        {busy ? "读取中" : "查看骨架状态"}
      </button>
      {message && <p className="inlineStatus">{message}</p>}
      {(status || commands.length > 0) && <TechnicalDetails data={{ status, commands }} />}
    </section>
  );
}
