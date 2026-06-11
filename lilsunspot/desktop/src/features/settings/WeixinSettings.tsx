import { useEffect, useRef, useState } from "react";
import { disconnectWeixin, getWeixinLoginStatus, getWeixinStatus, startWeixinLogin } from "../../api";
import lilsunspotIcon from "../../assets/lilsunspot-icon.png";
import type { WeixinStatus } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";

type BusyAction = "" | "initial" | "refresh" | "disconnect";
const DISCONNECT_CONFIRM_MESSAGE = "再次点击确认断开，正在进行的刷新结果会被忽略。";

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

function isLoginWaiting(status: WeixinStatus | null) {
  return Boolean(status && ["qr_pending", "scanned"].includes(status.status));
}

function qrEmptyTitle(status: WeixinStatus | null, busyAction: BusyAction) {
  if (busyAction === "disconnect") {
    return "正在断开";
  }
  if (busyAction === "initial" || busyAction === "refresh") {
    return "正在连接";
  }
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
  if (status?.login?.poll_warning) {
    return status.login.poll_warning;
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
  if (status?.login?.poll_warning) {
    return status.login.poll_warning;
  }
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

function busyPanelHint(action: BusyAction, queuedRefresh: boolean) {
  if (action === "disconnect") {
    return "正在断开微信连接，请稍等。";
  }
  if (queuedRefresh) {
    return "正在刷新，已经收到再次刷新请求，完成后会自动再试一次。";
  }
  if (action === "initial") {
    return "正在准备微信二维码，请稍等。";
  }
  if (action === "refresh") {
    return "正在刷新微信状态，请稍等。";
  }
  return "";
}

export function WeixinSettings() {
  const [status, setStatus] = useState<WeixinStatus | null>(null);
  const [busyAction, setBusyAction] = useState<BusyAction>("");
  const [disconnectArmed, setDisconnectArmed] = useState(false);
  const [queuedRefresh, setQueuedRefresh] = useState(false);
  const [message, setMessage] = useState("");
  const autoStartedRef = useRef(false);
  const mountedRef = useRef(false);
  const actionInFlightRef = useRef(false);
  const pollInFlightRef = useRef(false);
  const activeActionRef = useRef<BusyAction>("");
  const queuedRefreshRef = useRef(false);
  const requestVersionRef = useRef(0);
  const disconnectTimerRef = useRef<number | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    void load({ autoStart: true });
    return () => {
      mountedRef.current = false;
      if (disconnectTimerRef.current !== null) {
        window.clearTimeout(disconnectTimerRef.current);
      }
      queuedRefreshRef.current = false;
      pollInFlightRef.current = false;
    };
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

  function setQueuedRefreshValue(value: boolean) {
    queuedRefreshRef.current = value;
    if (mountedRef.current) {
      setQueuedRefresh(value);
    }
  }

  function startAction(action: Exclude<BusyAction, "">, options: { message?: string; supersede?: boolean } = {}) {
    if (actionInFlightRef.current && !options.supersede) {
      return null;
    }
    actionInFlightRef.current = true;
    activeActionRef.current = action;
    requestVersionRef.current += 1;
    const version = requestVersionRef.current;
    setBusyAction(action);
    setMessage(options.message ?? "");
    return version;
  }

  function finishAction(version: number) {
    if (version !== requestVersionRef.current) {
      return;
    }
    const finishedAction = activeActionRef.current;
    actionInFlightRef.current = false;
    activeActionRef.current = "";
    if (mountedRef.current) {
      setBusyAction("");
    }
    if (finishedAction !== "disconnect") {
      runQueuedRefresh();
    }
  }

  function runQueuedRefresh() {
    if (!queuedRefreshRef.current || !mountedRef.current || actionInFlightRef.current || pollInFlightRef.current) {
      return;
    }
    setQueuedRefreshValue(false);
    window.setTimeout(() => {
      if (mountedRef.current && !actionInFlightRef.current && !pollInFlightRef.current) {
        void refreshWeixin();
      }
    }, 0);
  }

  function applyFreshStatus(nextStatus: WeixinStatus, version: number) {
    if (!mountedRef.current || version !== requestVersionRef.current) {
      return;
    }
    setStatus(nextStatus);
  }

  async function startFreshLogin(version: number) {
    if (version !== requestVersionRef.current) {
      return;
    }
    const loginStatus = await startWeixinLogin();
    applyFreshStatus(loginStatus, version);
  }

  async function load(options: { autoStart?: boolean; forceAutoStart?: boolean } = {}) {
    const version = startAction(options.forceAutoStart ? "refresh" : "initial", {
      message: options.autoStart ? "正在准备微信二维码。" : "正在读取微信状态。"
    });
    if (version === null) {
      return;
    }
    try {
      const nextStatus = await getWeixinStatus();
      if (
        options.autoStart &&
        (options.forceAutoStart || !autoStartedRef.current) &&
        shouldAutoStartLogin(nextStatus)
      ) {
        autoStartedRef.current = true;
        applyFreshStatus(nextStatus, version);
        await startFreshLogin(version);
        return;
      }
      applyFreshStatus(nextStatus, version);
    } catch (error) {
      if (mountedRef.current && version === requestVersionRef.current) {
        setMessage(error instanceof Error ? error.message : "微信状态读取失败。");
      }
    } finally {
      finishAction(version);
    }
  }

  async function refreshLoginStatus() {
    if (actionInFlightRef.current || pollInFlightRef.current) {
      return;
    }
    pollInFlightRef.current = true;
    const version = requestVersionRef.current;
    try {
      const nextStatus = await getWeixinLoginStatus();
      applyFreshStatus(nextStatus, version);
    } catch (error) {
      if (mountedRef.current && version === requestVersionRef.current) {
        setMessage(error instanceof Error ? error.message : "微信扫码状态读取失败。");
      }
    } finally {
      pollInFlightRef.current = false;
      runQueuedRefresh();
    }
  }

  async function refreshWeixin() {
    if (actionInFlightRef.current || pollInFlightRef.current) {
      if (activeActionRef.current === "disconnect") {
        setMessage("正在断开微信，完成后可以再刷新。");
        return;
      }
      setQueuedRefreshValue(true);
      setDisconnectArmed(false);
      setMessage("正在刷新，完成后会自动再试一次。");
      return;
    }
    const version = startAction("refresh", { message: "正在刷新微信状态。" });
    if (version === null) {
      return;
    }
    setQueuedRefreshValue(false);
    setDisconnectArmed(false);
    if (status && ["qr_pending", "scanned"].includes(status.status)) {
      try {
        const nextStatus = await getWeixinLoginStatus();
        applyFreshStatus(nextStatus, version);
        if (shouldAutoStartLogin(nextStatus)) {
          await startFreshLogin(version);
        }
      } catch (error) {
        if (mountedRef.current && version === requestVersionRef.current) {
          setMessage(error instanceof Error ? error.message : "微信扫码状态读取失败。");
        }
      } finally {
        finishAction(version);
      }
      return;
    }

    try {
      const nextStatus = await getWeixinStatus();
      applyFreshStatus(nextStatus, version);
      if (shouldAutoStartLogin(nextStatus) || !nextStatus.connected) {
        await startFreshLogin(version);
      }
    } catch (error) {
      if (mountedRef.current && version === requestVersionRef.current) {
        setMessage(error instanceof Error ? error.message : "微信状态刷新失败。");
      }
    } finally {
      finishAction(version);
    }
  }

  async function forceDisconnect() {
    const shouldArmDisconnect =
      status?.connected ||
      isLoginWaiting(status) ||
      pollInFlightRef.current ||
      activeActionRef.current === "initial" ||
      activeActionRef.current === "refresh";
    if (
      !disconnectArmed &&
      shouldArmDisconnect
    ) {
      setQueuedRefreshValue(false);
      setDisconnectArmed(true);
      setMessage(DISCONNECT_CONFIRM_MESSAGE);
      if (disconnectTimerRef.current !== null) {
        window.clearTimeout(disconnectTimerRef.current);
      }
      disconnectTimerRef.current = window.setTimeout(() => {
        if (mountedRef.current) {
          setDisconnectArmed(false);
          setMessage((current) => (current === DISCONNECT_CONFIRM_MESSAGE ? "" : current));
        }
      }, 4000);
      return;
    }

    setQueuedRefreshValue(false);
    const version = startAction("disconnect", { message: "正在断开微信连接。", supersede: true });
    if (version === null) {
      return;
    }
    setDisconnectArmed(false);
    try {
      const nextStatus = await disconnectWeixin();
      autoStartedRef.current = false;
      applyFreshStatus(nextStatus, version);
    } catch (error) {
      if (mountedRef.current && version === requestVersionRef.current) {
        setMessage(error instanceof Error ? error.message : "微信连接清理失败。");
      }
    } finally {
      finishAction(version);
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
  const busy = busyAction !== "";
  const currentQrHint = busy ? busyPanelHint(busyAction, queuedRefresh) : message || qrPanelHint(status, hasQrImage);
  const refreshLabel = busyAction === "refresh" || busyAction === "initial" ? "刷新中" : "刷新";
  const disconnectLabel = disconnectArmed ? "确认断开" : busyAction === "disconnect" ? "断开中" : "断开";
  const refreshDisabled = busyAction === "disconnect";
  const disconnectDisabled = busyAction === "disconnect";
  const inlineMessage = message && message !== currentQrHint ? message : "";

  return (
    <section className="settingsSection weixinConsole" aria-busy={busy}>
      <div className="settingsHeader">
        <div>
          <h3>扫码连接微信私聊</h3>
          <p>微信文本和文件会同步到桌面；可以直接用自然语言调整回答风格。</p>
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
                <strong>{qrEmptyTitle(status, busyAction)}</strong>
              </div>
            )}
          </div>
          {currentQrHint && (
            <div className="qrMetaPanel">
              <p aria-live="polite">{currentQrHint}</p>
            </div>
          )}
          <div className="weixinButtonRow">
            <button type="button" className={queuedRefresh ? "queued" : ""} onClick={refreshWeixin} disabled={refreshDisabled}>
              {refreshLabel}
            </button>
          </div>
          <div className="weixinDisconnectRow">
            <button type="button" onClick={forceDisconnect} disabled={disconnectDisabled}>
              {disconnectLabel}
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
                <span>直接发问题、图片、PDF、Word、Excel 或 CSV。</span>
              </div>
              <div>
                <strong>调整风格</strong>
                <span>直接说“切到务实一点”或“回答详细一点”。</span>
              </div>
              <div>
                <strong>查看当前风格</strong>
                <span>直接问“现在是什么风格”。</span>
              </div>
            </div>
          </div>
          <p className="runtimeStatusLine">
            {status?.runtime?.running ? "正在同步" : "未在同步"} · 最近收到 {status?.runtime?.last_inbound_at || "无"} · 最近回复{" "}
            {status?.runtime?.last_reply_at || "无"}
          </p>
        </article>
      </div>
      {inlineMessage && (
        <p className="inlineStatus" aria-live="polite">
          {inlineMessage}
        </p>
      )}
    </section>
  );
}
