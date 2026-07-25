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

export type AppUpdateState =
  | "idle"
  | "checking"
  | "available"
  | "current"
  | "unavailable"
  | "failed"
  | "dismissed";

export type AppUpdateInfo = {
  version: string;
  current_version: string;
  published_at: string;
  notes: string;
  size?: number | null;
  critical: boolean;
};

export type AppUpdateStatus = {
  state: AppUpdateState;
  update: AppUpdateInfo | null;
  message: string;
};

export type AppUpdateInstallResult = {
  ok: boolean;
  version: string;
  message: string;
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
  id: "wait" | "repair" | "setup_model" | "test_model" | "open_chat" | "open_settings" | "retry";
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
  vision_default_model?: string;
  auxiliary_vision?: "recommended" | "optional" | string;
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

export type LocalProviderResetResult = {
  ok: boolean;
  message: string;
  removed_env_keys: number;
  bootstrap: AppBootstrapState;
};

export type CapabilityNodeStatus = "ready" | "needs_setup" | "degraded" | "blocked" | "unknown" | string;

export type CapabilityNextAction = {
  id: "open_model_settings" | "open_vision_settings" | "open_provider_key_url" | "continue_text_chat" | "retry" | string;
  label: string;
};

export type CapabilityNode = {
  id: string;
  label: string;
  status: CapabilityNodeStatus;
  source: "main_model" | "auxiliary_vision" | "none" | string;
  blocking_reason: string;
  user_message_cn: string;
  next_actions: CapabilityNextAction[];
  last_verified_at: string;
  details: Record<string, unknown>;
};

export type CapabilityGraph = {
  version: number;
  generated_at: string;
  nodes: CapabilityNode[];
  by_id?: Record<string, CapabilityNode>;
};

export type AuxiliaryModelConfig = {
  provider?: string;
  model?: string;
  base_url?: string;
  updated_at?: string;
};

export type ModelRuntimeConfig = {
  main: {
    provider: string;
    model: string;
    base_url: string;
  };
  fallback_providers: Array<Record<string, unknown>>;
  provider_routing: Record<string, unknown>;
  auxiliary: Record<string, AuxiliaryModelConfig>;
  lilsunspot_auxiliary: Record<string, AuxiliaryModelConfig>;
  compression: Record<string, unknown>;
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
  process: RuntimeProcessInfo;
  runtime_file: string;
  configured: boolean;
  provider: string;
  model: string;
};

export type RuntimeProcessInfo = {
  pid?: number;
  parent_pid?: number;
  executable?: string;
  packaged?: boolean;
  packager?: string;
  process_model?: string;
  note_cn?: string;
};

export type ModelCapabilities = {
  configured: boolean;
  provider: string;
  provider_name: string;
  model: string;
  supports_image: boolean;
  main_supports_image: boolean;
  auxiliary_configured: boolean;
  image_backend: "main_model" | "auxiliary_vision" | "none" | string;
  image_input_mode: "native" | "text" | string;
  image_capability_status?: CapabilityNodeStatus;
  capability_graph?: CapabilityGraph;
  supports_files: boolean;
  supports_weixin: boolean;
  supports_reminders: boolean;
  source: string;
  limitations: string[];
};

export type OperationState = "idle" | "running" | "succeeded" | "succeeded_with_warning" | "failed";

export type OperationNotice = {
  tone: "neutral" | "success" | "warning" | "danger";
  message: string;
  blocking: boolean;
  source: string;
};

export type DiagnosticsSummary = {
  ok: boolean;
  generated_at: string;
  model: ModelCapabilities;
  weixin: {
    connected: boolean;
    status: string;
    message: string;
    active_conversation_count: number;
  };
  local_service: {
    doctor_ok: boolean;
    runtime_process: RuntimeProcessInfo;
    process_note: string;
    failed_checks: Array<{ name: string; ok: boolean; detail: string }>;
  };
  counts: {
    reminders: number;
    active_reminders: number;
    memories: number;
    active_memories: number;
    capabilities: number;
    enabled_capabilities: number;
  };
  upstream: UpstreamStatus;
};

export type UsageSummary = {
  generated_at: string;
  conversations: {
    total: number;
    desktop: number;
    weixin: number;
  };
  messages: {
    total: number;
    user: number;
    assistant: number;
    errors: number;
    running: number;
  };
  attachments: {
    total: number;
  };
  tasks: {
    total: number;
    active: number;
    paused: number;
    completed: number;
  };
  memories: {
    total: number;
    active: number;
  };
  capabilities: {
    total: number;
    enabled: number;
  };
  costs: {
    available: boolean;
    message: string;
  };
};

export type UiOverview = {
  generated_at: string;
  status: "ok" | "needs_attention" | string;
  diagnostics: DiagnosticsSummary;
  usage: UsageSummary;
  tasks: {
    total: number;
    active: number;
    next: ProductTask | null;
  };
  model: ModelCapabilities;
  weixin: DiagnosticsSummary["weixin"];
};

export type UpstreamStatus = {
  available: boolean;
  latest_report: string;
  generated_at: string;
  summary: string;
  commits_since_base: number | null;
  changed_files: number | null;
  working_tree_dirty: boolean | null;
};

export type ConversationSearchResult = {
  type: "message" | "attachment" | string;
  conversation_id: string;
  conversation_title: string;
  conversation_kind: string;
  message_id: string;
  attachment_id: string;
  source: string;
  role: string;
  snippet: string;
  created_at: string;
};

export type ProductReminder = {
  id: string;
  title: string;
  prompt: string;
  due_at: string;
  enabled: boolean;
  completed_at: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
};

export type ProductTaskRun = {
  ran_at: string;
  trigger?: string;
  state: string;
  message: string;
  conversation_id?: string;
  message_id?: string;
};

export type ProductTask = {
  id: string;
  title: string;
  prompt: string;
  kind: string;
  schedule: "once" | "daily" | string;
  status: "active" | "paused" | "completed" | string;
  enabled: boolean;
  completed_at: string;
  next_run_at: string;
  due_at: string;
  last_run_at: string;
  last_result: string;
  last_error: string;
  run_history: ProductTaskRun[];
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
};

export type ProductMemory = {
  id: string;
  text: string;
  source: string;
  enabled: boolean;
  memory_scope?: string;
  scope_label?: string;
  agent_memory_synced?: boolean;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
};

export type ProductProfile = {
  id: string;
  name: string;
  instructions: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
};

export type ProductCapability = {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
  requires_approval: boolean;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
};

export type AdvancedExtensions = {
  generated_at: string;
  mode: "readonly" | "guarded" | string;
  message: string;
  skills: {
    available: boolean;
    count: number;
    items: string[];
  };
  plugins: {
    available: boolean;
    count: number;
    items: string[];
  };
  toolsets: Array<{
    id: string;
    label: string;
    enabled: boolean;
    requires_approval: boolean;
  }>;
  upstream: UpstreamStatus;
  safe_actions?: {
    config_export?: boolean;
    product_config_import?: boolean;
    toolset_toggle?: boolean;
    plugin_install?: boolean;
    raw_env_edit?: boolean;
    terminal_tools?: boolean;
  };
  dangerous_actions_enabled: boolean;
};

export type AdvancedConfigExport = {
  version: number;
  generated_at: string;
  redacted: boolean;
  message: string;
  sections: Record<string, unknown>;
  not_included: string[];
};

export type AdvancedConfigImportResult = {
  ok: boolean;
  message: string;
  applied: {
    capabilities: number;
    tasks: number;
    profiles: number;
  };
  skipped: string[];
};

export type ChatSendResult =
  | {
      ok: true;
      accepted?: boolean;
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
      generation_execution?: GenerationExecution;
    }
  | {
      ok: false;
      error_code: string;
      message: string;
      suggestion: string;
      generation_execution?: GenerationExecution;
    };

export type GenerationModeId = "strict" | "balanced" | "creative" | "fast" | "deep" | "custom" | string;

export type GenerationParameterValue = number | string | null;

export type GenerationSelection = {
  mode?: GenerationModeId;
  parameters?: Record<string, GenerationParameterValue>;
};

export type GenerationMode = {
  id: GenerationModeId;
  label: string;
  description: string;
  effects: Record<string, string>;
};

export type GenerationParameterDetail = {
  requested: GenerationParameterValue;
  effective: GenerationParameterValue;
  source: string;
  source_label: string;
  status: "supported" | "unsupported" | "locked" | "omitted" | "default" | string;
  reason?: string;
  range?: { min: number; max: number };
  values?: string[];
  default?: GenerationParameterValue;
  degraded?: boolean;
};

export type GenerationControl = {
  mode: GenerationModeId;
  mode_scope: "global" | "conversation" | "turn" | string;
  label: string;
  description: string;
  effects: Record<string, string>;
  provider: string;
  model: string;
  fully_supported: boolean;
  compatibility_summary: string;
  requested_parameters: Record<string, GenerationParameterValue>;
  effective_parameters: Record<string, GenerationParameterValue>;
  parameters: Record<string, GenerationParameterDetail>;
  automatic_downgrade: boolean;
  retry_count: number;
};

export type GenerationExecution = {
  provider: string;
  model: string;
  mode: GenerationModeId;
  mode_label: string;
  effective_parameters: Record<string, GenerationParameterValue>;
  omitted_parameters: Array<{ parameter: string; status: string; reason?: string }>;
  reasoning_effort: string | null;
  tool_iterations: number;
  max_iterations: number;
  automatic_downgrade: boolean;
  retry_count: number;
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
  status: "sent" | "received" | "generating" | "error" | string;
  metadata?: Record<string, unknown>;
};

export type ConversationSendResult = {
  ok: boolean;
  accepted?: boolean;
  turn_id?: string;
  user_message: ConversationMessage;
  assistant_message: ConversationMessage;
  chat: ChatSendResult;
};

export type ConversationTurnActionResult = {
  ok?: boolean;
  message?: string;
  action?: string;
  removed_message_ids?: string[];
  retried_message_id?: string;
  conversation?: Conversation;
  copied_messages?: number;
  memory?: ProductMemory;
  user_message?: ConversationMessage;
  assistant_message?: ConversationMessage;
  chat?: ChatSendResult;
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
    approval?: Record<string, unknown>;
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

export type ModePromptLayerId = "mode_profile" | "slider_overrides";

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
  scope?: "global" | "conversation" | "turn" | string;
  conversation_id?: string;
};

export type WeixinStatus = {
  gateway: "weixin";
  available: boolean;
  connected: boolean;
  display_status?: string;
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
  login_verification?: WeixinLoginVerification;
  runtime?: WeixinRuntimeState;
  capabilities?: {
    qr_login: boolean;
    private_chat: boolean;
    commands: boolean;
    attachments?: boolean;
    attachment_send_requires_approval?: boolean;
    active_send_requires_approval: boolean;
    official_payment_or_materials_required: boolean;
    official_adapter_media_methods?: string[];
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
  display_status?: string;
  qr_payload: string;
  qr_payload_kind: "url" | "text" | string;
  qr_image_data_url?: string;
  expires_at: number;
  message: string;
  poll_warning?: string;
  risk_flags?: string[];
};

export type WeixinLoginVerification = {
  state: "not_started" | "pending" | "attention" | "verified" | "failed" | string;
  risk_flags: string[];
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

export type CapabilityRisk = "low" | "medium" | "high" | string;

export type Capability = {
  id: string;
  category: string;
  category_label: string;
  name: string;
  description: string;
  enabled: boolean;
  available: boolean;
  status: "enabled" | "blocked" | "unsupported" | "needs_config" | "disabled" | string;
  status_text: string;
  risk: CapabilityRisk;
  dependencies: string[];
  config_keys: string[];
  tools: string[];
  source: string;
  source_of_truth: string;
  configurable: boolean;
  registered: boolean;
  configured: boolean;
  executable: boolean;
  verified: boolean;
  last_verified_at: string;
};

export type CapabilitiesResult = {
  capabilities: Capability[];
  platform: string;
  enabled_toolsets: string[];
  default_toolsets: string[];
  config_keys: string[];
  upstream_audit?: Record<string, unknown>;
};

export type CapabilityTestLayer = {
  id: string;
  label: string;
  ok: boolean;
  state: string;
  message: string;
};

export type CapabilityTestResult = {
  ok: boolean;
  capability: Capability;
  message: string;
  layers?: CapabilityTestLayer[];
  actions?: string[];
};

export type AuditEvent = {
  event_id: string;
  event_type: string;
  source: string;
  status: string;
  summary: string;
  details: Record<string, unknown>;
  created_at: string;
};

export type AuditResult = {
  events: AuditEvent[];
  audit_db: string;
  limit: number;
};

export type SafetyApproval = {
  id: string;
  operation: string;
  status: string;
  summary?: string;
  details?: Record<string, unknown>;
  [key: string]: unknown;
};

export type SafetyApprovals = {
  pending: SafetyApproval[];
  policy?: SafetyPolicy;
  [key: string]: unknown;
};

export type WeixinSendApprovalResult = {
  ok: boolean;
  gateway: "weixin";
  status: string;
  approval_required: boolean;
  approval?: SafetyApproval | null;
  delivery?: {
    ok: boolean;
    message?: string;
    sent_text?: boolean;
    sent_files?: number;
    [key: string]: unknown;
  };
  message: string;
};

export type SafetyApprovalDecisionResult = {
  ok?: boolean;
  message?: string;
  approval: SafetyApproval;
  delivery?: {
    ok: boolean;
    message?: string;
    sent_text?: boolean;
    sent_files?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
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

export type DiagnosticsExportResult = {
  ok: boolean;
  diagnostic_id: string;
  file_name: string;
  size_bytes: number;
  message: string;
  audit_event?: AuditEvent;
};
