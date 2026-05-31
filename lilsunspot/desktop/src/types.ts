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
      message: string;
    }
  | {
      ok: false;
      provider: string;
      model: string;
      error_code: string;
      message: string;
      suggestion: string;
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
  configured: boolean;
  provider: string;
  model: string;
};

export type ChatSendResult =
  | {
      ok: true;
      reply: string;
      engine: "placeholder" | string;
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
