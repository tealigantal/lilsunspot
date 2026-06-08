import { useEffect, useState } from "react";
import { getWeixinCommands, getWeixinStatus } from "../../api";
import type { WeixinCommand, WeixinStatus } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";

const STATUS_STEPS = [
  { id: "not_configured", label: "not_configured", text: "尚未初始化微信网关" },
  { id: "qr_pending", label: "qr_pending", text: "等待手机扫码" },
  { id: "qr_expired", label: "qr_expired", text: "二维码已过期" },
  { id: "connected", label: "connected", text: "扫码成功后进入" },
  { id: "credential_expired", label: "credential_expired", text: "凭据过期，需要重连" },
  { id: "error", label: "error", text: "失败时给人话修复建议" }
];

const COMMAND_STICKERS = ["/模式 20", "/模式 80", "/务实", "/感性", "/资料", "/详细"];

function activeStatus(status: WeixinStatus | null) {
  if (!status?.available) {
    return "not_configured";
  }
  if (status.connected) {
    return "connected";
  }
  return "qr_pending";
}

export function WeixinSettings() {
  const [status, setStatus] = useState<WeixinStatus | null>(null);
  const [commands, setCommands] = useState<WeixinCommand[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void load();
  }, []);

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

  const active = activeStatus(status);

  return (
    <section className="settingsSection weixinConsole">
      <div className="settingsHeader">
        <div>
          <h3>扫码连接微信私聊</h3>
          <p>不做微信原生资料页注入，只做私聊命令和资料文本。</p>
        </div>
        <StatusBadge tone={status?.connected ? "ok" : "warning"}>{status?.connected ? "已连接" : "等待扫码"}</StatusBadge>
      </div>
      <div className="weixinGrid">
        <article className="qrPanel">
          <div className="qrPlaceholder" aria-label="微信二维码占位">
            <span>QR</span>
            <p>二维码接口尚未接入，当前只展示网关状态和命令骨架。</p>
          </div>
          <button type="button" onClick={load} disabled={busy}>
            {busy ? "读取中" : "重新读取状态"}
          </button>
        </article>
        <article className="weixinStatusPanel">
          <h3>连接状态</h3>
          <ol className="statusTimeline">
            {STATUS_STEPS.map((step) => (
              <li key={step.id} className={active === step.id ? "active" : ""}>
                <strong>{step.label}</strong>
                <span>{step.text}</span>
              </li>
            ))}
          </ol>
          <h3>微信命令贴纸</h3>
          <div className="commandStickerGrid">
            {COMMAND_STICKERS.map((command) => (
              <span key={command}>{command}</span>
            ))}
          </div>
        </article>
      </div>
      {message && <p className="inlineStatus">{message}</p>}
      {commands.length > 0 && <p className="inlineStatus">已读取 {commands.length} 个微信命令骨架，当前不会扫码登录或直接发送消息。</p>}
    </section>
  );
}
