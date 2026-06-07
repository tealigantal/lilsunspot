import { useCallback, useEffect, useMemo, useState } from "react";
import {
  connectDaemon,
  getAppBootstrap,
  getDaemonUrl,
  getHealth,
  isDesktopRuntime,
  setRuntimeToken
} from "../api";
import type { AppBootstrapState, DaemonConnectStatus, HealthStatus } from "../types";

const STARTING_BOOTSTRAP: AppBootstrapState = {
  stage: "starting",
  title: "正在准备小黑子",
  message: "正在启动本地服务，并检查 AI 服务设置。",
  primary_action: { id: "wait", label: "请稍等" },
  secondary_actions: [],
  checks: {
    daemon: "unknown",
    model_config: "unknown",
    chat: "unknown",
    mode: "unknown",
    weixin: "unavailable",
    safety: "unknown"
  },
  runtime: {
    configured: false,
    provider: "",
    model: ""
  },
  user_visible_blockers: []
};

function failedBootstrap(message: string, suggestion = "请点击重新检查，或打开诊断。"): AppBootstrapState {
  return {
    stage: "daemon_failed",
    title: "本地服务没有成功启动",
    message,
    primary_action: { id: "retry", label: "重新检查" },
    secondary_actions: [{ id: "open_doctor", label: "一键检查" }],
    checks: {
      daemon: "failed",
      model_config: "unknown",
      chat: "blocked",
      mode: "unknown",
      weixin: "unavailable",
      safety: "unknown"
    },
    runtime: {
      configured: false,
      provider: "",
      model: ""
    },
    user_visible_blockers: [
      {
        code: "daemon_failed",
        message,
        suggestion
      }
    ]
  };
}

export function useBootstrapState() {
  const devMode = useMemo(() => !isDesktopRuntime(), []);
  const [bootstrap, setBootstrap] = useState<AppBootstrapState>(STARTING_BOOTSTRAP);
  const [connection, setConnection] = useState<DaemonConnectStatus | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    setBootstrap((current) => (current.stage === "starting" ? current : STARTING_BOOTSTRAP));
    try {
      const connected = await connectDaemon();
      if (connected) {
        setConnection(connected);
        if (!connected.ok) {
          setBootstrap(failedBootstrap(connected.message_cn || "小黑子本地服务没有成功启动。"));
          return;
        }
      }

      const healthBody = await getHealth();
      setHealth(healthBody);
      if (!healthBody.ok) {
        setBootstrap(failedBootstrap(healthBody.message_cn || "小黑子本地服务没有响应。"));
        return;
      }

      const nextBootstrap = await getAppBootstrap();
      setBootstrap(nextBootstrap);
    } catch (error) {
      const message = error instanceof Error ? error.message : "小黑子本地服务没有响应。";
      setBootstrap(
        failedBootstrap(
          devMode && message.includes("调试 Token") ? "开发者模式需要填写调试 Token。正式桌面版会自动连接。" : message,
          devMode ? "在下方开发者模式里填写调试 Token 后重新检查。" : "请点击重新检查，或打开诊断。"
        )
      );
    } finally {
      setBusy(false);
    }
  }, [devMode]);

  function applyDevToken(token: string) {
    setRuntimeToken(token);
    void refresh();
  }

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    bootstrap,
    connection,
    health,
    busy,
    devMode,
    daemonUrl: getDaemonUrl(),
    refresh,
    applyDevToken
  };
}
