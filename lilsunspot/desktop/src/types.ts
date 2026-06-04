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
      engine: string;
      provider: string;
      model: string;
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
