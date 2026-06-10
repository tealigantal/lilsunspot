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
      mode_intent?: {
        kind?: string;
        mode?: string | null;
        slider?: string | null;
        delta?: number;
        [key: string]: unknown;
      };
      mode?: CurrentMode;
    }
  | {
      ok: false;
      error_code: string;
      message: string;
      suggestion: string;
    };

export type Conversation = {
  id: string;
  title: string;
  kind: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
};

export type AttachmentSummaryStatus =
  | "pending"
  | "ready"
  | "recognized"
  | "preview_only"
  | "unsupported"
  | "unreadable"
  | "too_large"
  | string;

export type ConversationAttachment = {
  id: string;
  message_id: string;
  conversation_id: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  summary_status: AttachmentSummaryStatus;
  summary_text: string;
  preview_data_url: string;
  reason_cn: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
};

export type ConversationMessage = {
  id: string;
  conversation_id: string;
  source: "desktop" | "weixin" | "assistant" | "system" | string;
  role: "user" | "assistant" | "system" | string;
  text: string;
  attachments: ConversationAttachment[];
  created_at: string;
  status: "sent" | "received" | "error" | string;
  metadata?: Record<string, unknown>;
};

export type ConversationSendResult = {
  ok: boolean;
  user_message: ConversationMessage;
  assistant_message: ConversationMessage;
  chat: ChatSendResult;
};

export type LilsunspotEvent = {
  id: number;
  event: string;
  data: {
    conversation_id?: string;
    message_id?: string;
    message?: ConversationMessage;
    attachment?: ConversationAttachment;
    mode?: CurrentMode;
    approval?: SafetyApproval;
    [key: string]: unknown;
  };
};

export type ModeProfile = {
  id: string;
  description: string;
  style_axis: number;
  detail_level: number;
  autonomy_level: number;
  system_hint: string;
};

export type ModePromptLayerId = "product_baseline" | "mode_profile" | "slider_overrides";

export type ModePromptLayer = {
  id: ModePromptLayerId;
  label: string;
  summary: string;
};

export type ModePrompt = {
  system_hint: string;
  layers: ModePromptLayer[];
  slider_summary: string;
};

export type CurrentMode = {
  current: string;
  profile: ModeProfile;
  prompt: ModePrompt;
};

export type WeixinStatus = {
  gateway: "weixin";
  available: boolean;
  connected: boolean;
  status:
    | "not_configured"
    | "qr_pending"
    | "scanned"
    | "qr_expired"
    | "connected"
    | "credential_expired"
    | "error"
    | string;
  commands_available: boolean;
  bot_profile?: WeixinBotProfile;
  login?: WeixinLoginState | null;
  runtime?: WeixinRuntimeState;
  capabilities?: {
    qr_login: boolean;
    private_chat: boolean;
    commands: boolean;
    active_send_requires_approval: boolean;
    official_payment_or_materials_required: boolean;
  };
  message: string;
};

export type WeixinBotProfile = {
  nickname: string;
  avatar_asset: string;
  avatar_alt: string;
};

export type WeixinLoginState = {
  status: string;
  qr_payload: string;
  qr_payload_kind: "url" | "text" | string;
  qr_image_data_url?: string;
  expires_at: number;
  message: string;
};

export type WeixinRuntimeState = {
  state: "stopped" | "starting" | "running" | "error" | string;
  running: boolean;
  last_inbound_at: string;
  last_reply_at: string;
  last_error: string;
};

export type WeixinCommand = {
  name: string;
  enabled: boolean;
  description: string;
};

export type SafetyPolicy = Record<string, unknown>;

export type SafetyApproval = {
  id: string;
  operation: string;
  status: "pending" | "approved" | "rejected" | string;
  summary: string;
  source: string;
  details: Record<string, unknown>;
  created_at: string;
  decided_at: string | null;
};

export type SafetyApprovals = {
  pending: SafetyApproval[];
  history?: SafetyApproval[];
  message: string;
};

export type SafetyApprovalDecision = {
  ok: boolean;
  approval: SafetyApproval;
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
