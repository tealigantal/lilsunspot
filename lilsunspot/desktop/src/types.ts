export type DaemonDiscovery = {
  base_url: string;
  data_dir: string;
  runtime_file: string;
};

export type DaemonConnectStatus = {
  ok: boolean;
  base_url: string;
  data_dir: string;
  runtime_file: string;
  launch_attempted: boolean;
  message_cn: string;
};

export type DaemonHttpResponse = {
  status: number;
  body: string;
};

export type HealthStatus = {
  ok: boolean;
  status: "ready" | string;
  message_cn: string;
  setup_required: boolean;
  version: string;
};

export type AppBootState =
  | "starting_daemon"
  | "daemon_ready"
  | "daemon_failed"
  | "provider_missing"
  | "provider_testing"
  | "provider_ready"
  | "chat_ready";

export type AppState = {
  boot: AppBootState;
  title: string;
  message: string;
  next_action: string;
};

export type AppBootstrapStage =
  | "starting"
  | "daemon_failed"
  | "needs_model"
  | "model_test_required"
  | "chat_ready"
  | "repair_required";

export type AppBootstrapAction = {
  id: "wait" | "repair" | "setup_model" | "test_model" | "open_chat" | "open_doctor" | "open_settings" | "retry";
  label: string;
};

export type AppBootstrapChecks = {
  daemon: "ok" | "failed" | "unknown";
  model_config: "missing" | "present" | "invalid" | "unknown";
  chat: "ready" | "blocked" | "unknown";
  mode: "ready" | "defaulted" | "unknown";
  weixin: "not_configured" | "connected" | "unavailable";
  safety: "ready" | "placeholder" | "unknown";
};

export type AppBootstrapRuntime = {
  configured: boolean;
  provider: string;
  model: string;
};

export type UserVisibleBlocker = {
  code: string;
  message: string;
  suggestion: string;
};

export type AppBootstrapState = {
  stage: AppBootstrapStage;
  title: string;
  message: string;
  primary_action: AppBootstrapAction;
  secondary_actions: AppBootstrapAction[];
  checks: AppBootstrapChecks;
  runtime: AppBootstrapRuntime;
  user_visible_blockers: UserVisibleBlocker[];
};

export type Provider = {
  id: string;
  display_name: string;
  type: "cloud" | "local" | string;
  key_url?: string;
  detect_url?: string;
  default_model: string;
  env_key?: string;
  hermes_provider?: string;
  base_url?: string;
  notes?: string;
};

export type ProviderTestResult =
  | {
      ok: true;
      provider: string;
      model: string;
      title?: string;
      message: string;
    }
  | {
      ok: false;
      provider: string;
      model: string;
      error_code: string;
      title: string;
      message: string;
      actions: string[];
      suggestion?: string;
      safe_details: {
        provider: string;
        masked_key: string;
        http_status: number | null;
      };
    };

export type SaveProviderResult = {
  ok: boolean;
  provider: string;
  model: string;
  hermes_home: string;
};

export type RuntimeInfo = {
  data_dir: string;
  hermes_home: string;
  logs_dir: string;
  platform: string;
  daemon_version: string;
  bind_host: string;
  bind_port: number;
  base_url: string;
  pid: number;
  runtime_file: string;
  configured: boolean;
  provider: string;
  model: string;
};

export type ChatSendResult =
  | {
      ok: true;
      reply: string;
      engine: "lilsunspot_provider_adapter" | string;
      provider: string;
      model: string;
      conversation_id: string | null;
      conversation_id_supported: boolean;
      conversation_id_requested: boolean;
    }
  | {
      ok: false;
      error_code: string;
      message: string;
      suggestion: string;
    };

export type ModeProfile = {
  id: string;
  description: string;
  style_axis: number;
  detail_level: number;
  autonomy_level: number;
  system_hint: string;
};

export type CurrentMode = {
  current: string;
  profile: ModeProfile;
};

export type WeixinStatus = {
  gateway: "weixin";
  available: boolean;
  connected: boolean;
  message: string;
};

export type WeixinCommand = {
  name: string;
  enabled: boolean;
  description: string;
};

export type SafetyPolicy = Record<string, unknown>;

export type SafetyApprovals = {
  pending: unknown[];
  message: string;
};

export type DoctorCheck = {
  name: string;
  ok: boolean;
  detail: string;
};

export type DoctorResult = {
  ok: boolean;
  daemon_version: string;
  checks: DoctorCheck[];
};

export type RepairResult = {
  ok: boolean;
  check: string;
  message: string;
  suggestion: string;
};
