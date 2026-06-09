import { useEffect, useRef, useState } from "react";
import { disconnectWeixin, getWeixinLoginStatus, getWeixinStatus, startWeixinLogin } from "../../api";
import lilsunspotIcon from "../../assets/lilsunspot-icon.png";
import type { WeixinStatus } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";

function badgeTone(status: WeixinStatus | null) {
  if (status?.connected) {
    return "ok";
  }
  if (status?.status === "error" || status?.status === "credential_expired") {
    return "danger";
  }
  return "warning";
}

function badgeLabel(status: WeixinStatus | null) {
  if (status?.connected) {
    return "已连接";
  }
  if (status?.status === "qr_pending") {
    return "等待扫码";
  }
  if (status?.status === "scanned") {
    return "等待确认";
  }
  if (status?.status === "qr_expired") {
    return "已过期";
  }
  if (status?.status === "error") {
    return "出错";
  }
  return "未连接";
}

function shouldAutoStartLogin(status: WeixinStatus) {
  if (status.connected || status.login) {
    return false;
  }
  return ["not_configured", "qr_expired", "credential_expired"].includes(status.status);
}

function qrEmptyTitle(status: WeixinStatus | null) {
  if (status?.connected) {
    return "微信已连接";
  }
  if (status?.status === "error") {
    return "二维码生成失败";
  }
  if (status?.status === "qr_expired") {
    return "二维码已过期";
  }
  return "准备连接";
}

function userStatusTitle(status: WeixinStatus | null) {
  if (status?.connected) {
    return "微信已连接";
  }
  if (status?.status === "qr_pending") {
    return "等待扫码";
  }
  if (status?.status === "scanned") {
    return "等待手机确认";
  }
  if (status?.status === "qr_expired") {
    return "二维码已过期";
  }
  if (status?.status === "credential_expired") {
    return "需要重新连接";
  }
  if (status?.status === "error") {
    return "连接失败";
  }
  return "准备连接";
}

function userStatusDetail(status: WeixinStatus | null) {
  if (status?.connected) {
    return "";
  }
  if (status?.status === "qr_pending") {
    return "用手机微信扫描二维码，然后在手机上确认登录。";
  }
  if (status?.status === "scanned") {
    return "手机已经扫到二维码，请回到微信完成确认。";
  }
  if (status?.status === "qr_expired") {
    return "点刷新生成新的二维码。";
  }
  if (status?.status === "credential_expired") {
    return "当前连接已经失效，点刷新重新连接。";
  }
  if (status?.status === "error") {
    return status.message || "微信连接暂时不可用，请刷新重试。";
  }
  return "点刷新生成二维码。";
}

function qrPanelHint(status: WeixinStatus | null, hasQrImage: boolean) {
  if (hasQrImage) {
    return status?.login?.message || "请用手机微信扫码。";
  }
  if (status?.connected) {
    return "";
  }
  if (status?.status === "error") {
    return status.message || "连接失败，请刷新重试。";
  }
  if (status?.status === "qr_expired") {
    return "二维码已过期，点刷新重新生成。";
  }
  if (status?.status === "credential_expired") {
    return "连接已失效，点刷新重新连接。";
  }
  if (status?.message) {
    return status.message;
  }
  return "点刷新生成二维码。";
}

export function WeixinSettings() {
  const [status, setStatus] = useState<WeixinStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const autoStartedRef = useRef(false);

  useEffect(() => {
    void load({ autoStart: true });
  }, []);

  useEffect(() => {
    if (!status || !["qr_pending", "scanned"].includes(status.status)) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshLoginStatus();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [status?.status]);

  async function load(options: { autoStart?: boolean; forceAutoStart?: boolean } = {}) {
    setBusy(true);
    setMessage("");
    try {
      const nextStatus = await getWeixinStatus();
      if (
        options.autoStart &&
        (options.forceAutoStart || !autoStartedRef.current) &&
        shouldAutoStartLogin(nextStatus)
      ) {
        autoStartedRef.current = true;
        setStatus(nextStatus);
        const loginStatus = await startWeixinLogin();
        setStatus(loginStatus);
        return;
      }
      setStatus(nextStatus);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "微信状态读取失败。");
    } finally {
      setBusy(false);
    }
  }

  async function refreshLoginStatus() {
    try {
      const nextStatus = await getWeixinLoginStatus();
      setStatus(nextStatus);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "微信扫码状态读取失败。");
    }
  }

  async function refreshWeixin() {
    if (status && ["qr_pending", "scanned"].includes(status.status)) {
      setBusy(true);
      setMessage("");
      try {
        const nextStatus = await getWeixinLoginStatus();
        setStatus(nextStatus);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "微信扫码状态读取失败。");
      } finally {
        setBusy(false);
      }
      return;
    }

    await load({ autoStart: true, forceAutoStart: true });
  }

  async function forceDisconnect() {
    setBusy(true);
    setMessage("");
    try {
      const nextStatus = await disconnectWeixin();
      setStatus(nextStatus);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "微信连接清理失败。");
    } finally {
      setBusy(false);
    }
  }

  const qrImage = status?.login?.qr_image_data_url || "";
  const botProfile = status?.bot_profile || {
    nickname: "小黑子",
    avatar_asset: "lilsunspot-icon.png",
    avatar_alt: "小黑子头像"
  };
  const isPolling = status ? ["qr_pending", "scanned"].includes(status.status) : false;
  const hasQrImage = Boolean(qrImage);
  const currentStatusDetail = userStatusDetail(status);
  const currentQrHint = qrPanelHint(status, hasQrImage);

  return (
    <section className="settingsSection weixinConsole">
      <div className="settingsHeader">
        <div>
          <h3>扫码连接微信私聊</h3>
          <p>不走公众号、小程序或开放平台认证；当前使用微信扫码授权的私聊通道。</p>
        </div>
        <StatusBadge tone={badgeTone(status)}>{badgeLabel(status)}</StatusBadge>
      </div>
      <div className="weixinGrid">
        <article className="qrPanel">
          <div className={`qrPlaceholder ${hasQrImage ? "ready" : "empty"}`} aria-label="微信二维码区域">
            {hasQrImage ? (
              <img className="qrImage" src={qrImage} alt="微信登录二维码" />
            ) : (
              <div className="qrEmptyState" aria-hidden="true">
                <strong>{qrEmptyTitle(status)}</strong>
              </div>
            )}
          </div>
          {currentQrHint && (
            <div className="qrMetaPanel">
              <p>{currentQrHint}</p>
            </div>
          )}
          <div className="weixinButtonRow">
            <button type="button" onClick={refreshWeixin} disabled={busy}>
              刷新
            </button>
          </div>
          <div className="weixinDisconnectRow">
            <button type="button" onClick={forceDisconnect} disabled={busy}>
              断开
            </button>
          </div>
        </article>
        <article className="weixinStatusPanel">
          <div className="weixinBotIdentity">
            <img src={lilsunspotIcon} alt={botProfile.avatar_alt || "小黑子头像"} />
            <div>
              <small>默认昵称</small>
              <strong>{botProfile.nickname || "小黑子"}</strong>
              <span>使用本项目头像：{botProfile.avatar_asset || "lilsunspot-icon.png"}</span>
            </div>
          </div>
          <div className="weixinUserStatus">
            <span className={status?.connected ? "weixinSignal ok" : isPolling ? "weixinSignal pending" : "weixinSignal"} />
            <div>
              <small>当前状态</small>
              <h3>{userStatusTitle(status)}</h3>
              {currentStatusDetail && <p>{currentStatusDetail}</p>}
            </div>
          </div>
          <div className="weixinUseList">
            <h3>扫码后可以发送</h3>
            <div className="weixinUseCards">
              <div>
                <strong>普通消息</strong>
                <span>直接发问题或资料文本。</span>
              </div>
              <div>
                <strong>/help</strong>
                <span>查看微信私聊命令。</span>
              </div>
              <div>
                <strong>/mode pragmatic</strong>
                <span>切换到务实输出风格。</span>
              </div>
            </div>
          </div>
          {(status?.runtime?.last_inbound_at || status?.runtime?.last_reply_at) && (
            <p className="runtimeStatusLine">
              最近收到 {status.runtime.last_inbound_at || "无"} · 最近回复 {status.runtime.last_reply_at || "无"}
            </p>
          )}
        </article>
      </div>
      {message && <p className="inlineStatus">{message}</p>}
    </section>
  );
}
