import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  getCurrentMode,
  getModes,
  listenDaemonEvents,
  selectMode,
  subscribeDaemonEvents
} from "../../api";
import type { CurrentMode, LilsunspotEvent, ModeProfile } from "../../types";

type ModeSaveInput = Pick<ModeProfile, "style_axis" | "detail_level" | "autonomy_level">;

type ModeStateValue = {
  modes: ModeProfile[];
  current: CurrentMode | null;
  busy: boolean;
  status: string;
  reload: () => Promise<void>;
  saveMode: (mode: string, sliders: ModeSaveInput) => Promise<CurrentMode>;
  setStatus: (message: string) => void;
};

const ModeStateContext = createContext<ModeStateValue | null>(null);

export function ModeProvider({ children }: { children: ReactNode }) {
  const [modes, setModes] = useState<ModeProfile[]>([]);
  const [current, setCurrent] = useState<CurrentMode | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  const reload = useCallback(async () => {
    setBusy(true);
    setStatus("");
    const failures: string[] = [];
    const [modeListResult, modeResult] = await Promise.allSettled([getModes(), getCurrentMode()]);
    if (modeListResult.status === "fulfilled") {
      setModes(modeListResult.value);
    } else {
      failures.push(modeListResult.reason instanceof Error ? modeListResult.reason.message : "输出模式列表读取失败。");
    }
    if (modeResult.status === "fulfilled") {
      setCurrent(modeResult.value);
    } else {
      failures.push(modeResult.reason instanceof Error ? modeResult.reason.message : "当前输出模式读取失败。");
    }
    if (failures.length > 0) {
      setStatus(failures.join(" "));
    }
    setBusy(false);
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    let cleanup: (() => void) | undefined;
    let cancelled = false;

    function applyModeEvent(event: LilsunspotEvent) {
      if (event.event !== "mode.changed" || !event.data?.mode) {
        return;
      }
      setCurrent(event.data.mode as CurrentMode);
      setStatus("");
    }

    async function subscribe() {
      try {
        cleanup = await listenDaemonEvents(applyModeEvent);
        if (!cancelled) {
          await subscribeDaemonEvents();
        }
      } catch {
        cleanup = undefined;
      }
    }

    void subscribe();
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, []);

  const saveMode = useCallback(async (mode: string, sliders: ModeSaveInput) => {
    setBusy(true);
    setStatus("");
    try {
      const result = await selectMode(mode, sliders);
      setCurrent(result);
      setStatus(`已保存输出模式。`);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : "输出模式保存失败。";
      setStatus(message);
      throw error;
    } finally {
      setBusy(false);
    }
  }, []);

  const value = useMemo(
    () => ({ modes, current, busy, status, reload, saveMode, setStatus }),
    [modes, current, busy, status, reload, saveMode]
  );

  return <ModeStateContext.Provider value={value}>{children}</ModeStateContext.Provider>;
}

export function useModeState() {
  const value = useContext(ModeStateContext);
  if (!value) {
    throw new Error("useModeState must be used inside ModeProvider");
  }
  return value;
}
