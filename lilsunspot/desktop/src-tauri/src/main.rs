#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{
    env, fs,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::atomic::{AtomicBool, Ordering},
    thread,
    time::{Duration, Instant},
};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, WindowEvent,
};
use tauri_plugin_updater::UpdaterExt;

const DEFAULT_HOST: &str = "127.0.0.1";
const DEFAULT_PORT: u16 = 8765;
const TOKEN_FILE_NAME: &str = "runtime-token.json";
const RUNTIME_FILE_NAME: &str = "daemon-runtime.json";
const UPDATE_STATE_FILE_NAME: &str = "desktop-update-state.json";
const WINDOWS_SIDECAR_NAME: &str = "lilsunspotd-x86_64-pc-windows-msvc.exe";
const ATTACHMENT_DIR_NAME: &str = "attachments";
const DAEMON_HTTP_DEFAULT_TIMEOUT_MS: u64 = 5_000;
const DAEMON_HTTP_MAX_TIMEOUT_MS: u64 = 30_000;

static SSE_RUNNING: AtomicBool = AtomicBool::new(false);
static EXIT_REQUESTED: AtomicBool = AtomicBool::new(false);
static DAEMON_CONNECTING: AtomicBool = AtomicBool::new(false);

#[derive(Clone)]
struct DaemonEndpoint {
    host: String,
    port: u16,
    base_url: String,
}

#[derive(Serialize)]
struct DaemonDiscovery {
    base_url: String,
    data_dir: String,
    runtime_file: String,
}

#[derive(Serialize)]
struct DaemonConnectStatus {
    ok: bool,
    base_url: String,
    data_dir: String,
    runtime_file: String,
    launch_attempted: bool,
    message_cn: String,
}

#[derive(Serialize)]
struct DaemonHttpResponse {
    status: u16,
    body: String,
}

struct DaemonConnectGuard;

#[derive(Serialize, Clone)]
struct AppUpdateInfo {
    version: String,
    current_version: String,
    published_at: String,
    notes: String,
    size: Option<u64>,
    critical: bool,
}

#[derive(Serialize)]
struct AppUpdateStatus {
    state: String,
    update: Option<AppUpdateInfo>,
    message: String,
}

#[derive(Serialize)]
struct AppUpdateInstallResult {
    ok: bool,
    version: String,
    message: String,
}

#[derive(Deserialize, Serialize, Default)]
struct DesktopUpdateState {
    dismissed_version: String,
}

impl DaemonConnectGuard {
    fn enter() -> Option<Self> {
        if DAEMON_CONNECTING.swap(true, Ordering::SeqCst) {
            return None;
        }
        Some(Self)
    }
}

impl Drop for DaemonConnectGuard {
    fn drop(&mut self) {
        DAEMON_CONNECTING.store(false, Ordering::SeqCst);
    }
}

fn data_dir() -> Result<PathBuf, String> {
    if let Ok(value) = env::var("LILSUNSPOT_DATA_DIR") {
        return Ok(PathBuf::from(value));
    }

    #[cfg(target_os = "macos")]
    if let Ok(value) = env::var("HOME") {
        return Ok(macos_data_dir(Path::new(&value)));
    }

    if let Ok(value) = env::var("LOCALAPPDATA") {
        return Ok(PathBuf::from(value).join("Lilsunspot").join("data"));
    }
    Err("无法找到小黑子的本地数据目录。".to_string())
}

#[cfg(any(target_os = "macos", test))]
fn macos_data_dir(home: &Path) -> PathBuf {
    home.join("Library")
        .join("Application Support")
        .join("Lilsunspot")
        .join("data")
}

fn update_state_path(data_path: &Path) -> PathBuf {
    data_path.join(UPDATE_STATE_FILE_NAME)
}

fn read_dismissed_update_version(data_path: &Path) -> Option<String> {
    let raw = fs::read_to_string(update_state_path(data_path)).ok()?;
    let state = serde_json::from_str::<DesktopUpdateState>(&raw).ok()?;
    let version = state.dismissed_version.trim();
    if version.is_empty() {
        None
    } else {
        Some(version.to_string())
    }
}

fn write_dismissed_update_version(data_path: &Path, version: &str) -> Result<(), String> {
    fs::create_dir_all(data_path).map_err(|_| "无法保存更新提醒设置。".to_string())?;
    let state = DesktopUpdateState {
        dismissed_version: version.trim().to_string(),
    };
    let payload =
        serde_json::to_string_pretty(&state).map_err(|_| "无法保存更新提醒设置。".to_string())?;
    fs::write(update_state_path(data_path), payload)
        .map_err(|_| "无法保存更新提醒设置。".to_string())
}

fn validate_update_version(version: &str) -> Result<String, String> {
    let value = version.trim();
    if value.is_empty()
        || value.len() > 80
        || !value
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '.' | '-' | '_' | '+'))
    {
        return Err("更新版本号不正确。".to_string());
    }
    Ok(value.to_string())
}

fn version_is_dismissed(data_path: &Path, version: &str) -> bool {
    read_dismissed_update_version(data_path).as_deref() == Some(version)
}

fn raw_json_string(raw: &serde_json::Value, key: &str) -> String {
    raw.get(key)
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .trim()
        .to_string()
}

fn raw_json_bool(raw: &serde_json::Value, key: &str) -> bool {
    raw.get(key)
        .and_then(|value| value.as_bool())
        .unwrap_or(false)
}

fn raw_json_size(raw: &serde_json::Value) -> Option<u64> {
    raw.get("size")
        .and_then(|value| value.as_u64())
        .or_else(|| {
            raw.pointer("/platforms/windows-x86_64/size")
                .and_then(|value| value.as_u64())
        })
        .or_else(|| {
            raw.pointer("/platforms/windows-x86_64-nsis/size")
                .and_then(|value| value.as_u64())
        })
}

fn app_update_info(update: &tauri_plugin_updater::Update) -> AppUpdateInfo {
    let raw_pub_date = raw_json_string(&update.raw_json, "pub_date");
    let published_at = if raw_pub_date.is_empty() {
        update.date.map(|value| value.to_string()).unwrap_or_default()
    } else {
        raw_pub_date
    };
    AppUpdateInfo {
        version: update.version.clone(),
        current_version: update.current_version.clone(),
        published_at,
        notes: update.body.clone().unwrap_or_default(),
        size: raw_json_size(&update.raw_json),
        critical: raw_json_bool(&update.raw_json, "critical"),
    }
}

fn failed_update_status(message: impl Into<String>) -> AppUpdateStatus {
    AppUpdateStatus {
        state: "failed".to_string(),
        update: None,
        message: message.into(),
    }
}

fn endpoint_from_parts(host: &str, port: u16) -> Result<DaemonEndpoint, String> {
    if host != DEFAULT_HOST {
        return Err("小黑子本地服务必须运行在 127.0.0.1。".to_string());
    }
    if port == 0 {
        return Err("小黑子本地服务端口不正确。".to_string());
    }
    Ok(DaemonEndpoint {
        host: host.to_string(),
        port,
        base_url: format!("http://{}:{}", host, port),
    })
}

fn default_endpoint() -> DaemonEndpoint {
    endpoint_from_parts(DEFAULT_HOST, DEFAULT_PORT).expect("default daemon endpoint is valid")
}

fn read_runtime_token_from_path(token_path: PathBuf) -> Result<String, String> {
    let raw = fs::read_to_string(token_path).map_err(|_| "还没有找到本地连接凭据。".to_string())?;
    let payload: serde_json::Value =
        serde_json::from_str(&raw).map_err(|_| "本地连接凭据格式不正确。".to_string())?;
    let token = payload
        .get("token")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    if token.is_empty() {
        return Err("本地连接凭据为空。".to_string());
    }
    Ok(token)
}

fn read_runtime_endpoint(runtime_path: &Path) -> Result<DaemonEndpoint, String> {
    let raw = fs::read_to_string(runtime_path)
        .map_err(|_| "还没有发现正在运行的小黑子本地服务。".to_string())?;
    let payload: serde_json::Value =
        serde_json::from_str(&raw).map_err(|_| "本地服务发现文件格式不正确。".to_string())?;
    let descriptor_type = payload
        .get("type")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    if descriptor_type != "lilsunspot-daemon-runtime" {
        return Err("本地服务发现文件类型不正确。".to_string());
    }

    let host = payload
        .get("host")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    let port = payload
        .get("port")
        .and_then(|value| value.as_u64())
        .and_then(|value| u16::try_from(value).ok())
        .ok_or_else(|| "本地服务端口不正确。".to_string())?;
    endpoint_from_parts(host, port)
}

fn http_request(
    endpoint: &DaemonEndpoint,
    method: &str,
    path: &str,
    body: Option<&str>,
    token: Option<&str>,
    read_timeout: Duration,
) -> Result<DaemonHttpResponse, String> {
    if !matches!(method, "GET" | "POST" | "PATCH" | "DELETE") {
        return Err("只支持 GET、POST、PATCH 和 DELETE 请求。".to_string());
    }
    if !path.starts_with('/') || path.contains(' ') {
        return Err("请求路径不正确。".to_string());
    }

    let addr: SocketAddr = format!("{}:{}", endpoint.host, endpoint.port)
        .parse()
        .map_err(|_| "本地服务地址不正确。".to_string())?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(700))
        .map_err(|_| "小黑子本地服务没有响应。".to_string())?;
    let _ = stream.set_read_timeout(Some(read_timeout));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(5)));

    let body = body.unwrap_or("");
    let mut request = format!(
        "{method} {path} HTTP/1.1\r\nHost: {}:{}\r\nAccept: application/json\r\nConnection: close\r\n",
        endpoint.host, endpoint.port
    );
    if let Some(value) = token {
        request.push_str(&format!("X-Lilsunspot-Token: {value}\r\n"));
    }
    if !body.is_empty() {
        request.push_str("Content-Type: application/json\r\n");
        request.push_str(&format!("Content-Length: {}\r\n", body.as_bytes().len()));
    }
    request.push_str("\r\n");
    request.push_str(body);

    stream
        .write_all(request.as_bytes())
        .map_err(|_| "无法发送本地服务请求。".to_string())?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|_| "无法读取本地服务响应。".to_string())?;
    let (headers, response_body) = response
        .split_once("\r\n\r\n")
        .ok_or_else(|| "本地服务响应格式不正确。".to_string())?;
    let status = headers
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(|| "本地服务响应状态不正确。".to_string())?;

    Ok(DaemonHttpResponse {
        status,
        body: response_body.to_string(),
    })
}

fn daemon_read_timeout(timeout_ms: Option<u64>) -> Duration {
    let value = timeout_ms
        .unwrap_or(DAEMON_HTTP_DEFAULT_TIMEOUT_MS)
        .clamp(1_000, DAEMON_HTTP_MAX_TIMEOUT_MS);
    Duration::from_millis(value)
}

fn validate_attachment_id(attachment_id: &str) -> Result<(), String> {
    if attachment_id.is_empty()
        || attachment_id.len() > 80
        || !attachment_id
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
    {
        return Err("附件编号不正确。".to_string());
    }
    Ok(())
}

fn attachment_path_from_response(body: &str) -> Result<PathBuf, String> {
    let payload: serde_json::Value =
        serde_json::from_str(body).map_err(|_| "附件信息格式不正确。".to_string())?;
    let safe_path = payload
        .get("attachment")
        .and_then(|value| value.get("safe_path"))
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .trim();
    if safe_path.is_empty() {
        return Err("附件路径为空。".to_string());
    }
    Ok(PathBuf::from(safe_path))
}

fn open_path_in_file_manager(file_path: &Path) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        let mut command = Command::new("explorer.exe");
        command.arg("/select,").arg(file_path);
        hide_child_window(&mut command);
        command
            .spawn()
            .map(|_| ())
            .map_err(|_| "无法打开附件所在位置。".to_string())
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg("-R")
            .arg(file_path)
            .spawn()
            .map(|_| ())
            .map_err(|_| "无法打开附件所在位置。".to_string())
    }

    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        let parent = file_path.parent().unwrap_or_else(|| Path::new("."));
        Command::new("xdg-open")
            .arg(parent)
            .spawn()
            .map(|_| ())
            .map_err(|_| "无法打开附件所在位置。".to_string())
    }
}

fn parse_sse_block(block: &str, app: &AppHandle, last_event_id: &mut u64) {
    let mut id: Option<u64> = None;
    let mut event_name = String::from("message");
    let mut data_lines: Vec<String> = Vec::new();
    for line in block.lines() {
        let line = line.trim_end();
        if line.is_empty() || line.starts_with(':') {
            continue;
        }
        if let Some(value) = line.strip_prefix("id:") {
            id = value.trim().parse::<u64>().ok();
            continue;
        }
        if let Some(value) = line.strip_prefix("event:") {
            event_name = value.trim().to_string();
            continue;
        }
        if let Some(value) = line.strip_prefix("data:") {
            data_lines.push(value.trim_start().to_string());
        }
    }
    let Some(event_id) = id else {
        return;
    };
    let data_text = data_lines.join("\n");
    let data = serde_json::from_str::<serde_json::Value>(&data_text)
        .unwrap_or_else(|_| serde_json::Value::String(data_text));
    *last_event_id = event_id;
    let _ = app.emit(
        "lilsunspot:event",
        json!({
            "id": event_id,
            "event": event_name,
            "data": data,
        }),
    );
}

fn drain_sse_buffer(buffer: &mut String, app: &AppHandle, last_event_id: &mut u64) {
    while let Some(index) = buffer.find("\n\n") {
        let block = buffer[..index].to_string();
        let rest = buffer[index + 2..].to_string();
        *buffer = rest;
        parse_sse_block(&block, app, last_event_id);
    }
}

fn run_sse_loop(app: AppHandle, data_path: PathBuf, mut endpoint: DaemonEndpoint, mut token: String) {
    let client = match reqwest::blocking::Client::builder()
        .timeout(None)
        .connect_timeout(Duration::from_secs(5))
        .build()
    {
        Ok(client) => client,
        Err(_) => {
            SSE_RUNNING.store(false, Ordering::SeqCst);
            return;
        }
    };
    let mut last_event_id: u64 = 0;
    while SSE_RUNNING.load(Ordering::SeqCst) {
        if !health_ok(&endpoint) {
            if let Some(next_endpoint) = healthy_endpoint(&data_path) {
                endpoint = next_endpoint;
                if let Ok(next_token) = read_runtime_token_from_path(data_path.join(TOKEN_FILE_NAME)) {
                    token = next_token;
                }
            } else {
                thread::sleep(Duration::from_secs(2));
                continue;
            }
        }
        let url = format!("{}/events/stream", endpoint.base_url);
        let mut request = client
            .get(url)
            .header("Accept", "text/event-stream")
            .header("X-Lilsunspot-Token", token.as_str());
        if last_event_id > 0 {
            request = request.header("Last-Event-ID", last_event_id.to_string());
        }
        let Ok(mut response) = request.send() else {
            thread::sleep(Duration::from_secs(2));
            continue;
        };
        if !response.status().is_success() {
            if matches!(response.status().as_u16(), 401 | 403) {
                if let Ok(next_token) = read_runtime_token_from_path(data_path.join(TOKEN_FILE_NAME)) {
                    token = next_token;
                }
            }
            thread::sleep(Duration::from_secs(2));
            continue;
        }
        let mut buffer = String::new();
        let mut chunk = [0_u8; 4096];
        loop {
            if !SSE_RUNNING.load(Ordering::SeqCst) {
                return;
            }
            match response.read(&mut chunk) {
                Ok(0) => break,
                Ok(size) => {
                    let text = String::from_utf8_lossy(&chunk[..size]).replace("\r\n", "\n");
                    buffer.push_str(&text);
                    drain_sse_buffer(&mut buffer, &app, &mut last_event_id);
                }
                Err(_) => break,
            }
        }
        thread::sleep(Duration::from_millis(800));
    }
}

fn health_ok(endpoint: &DaemonEndpoint) -> bool {
    let Ok(response) = http_request(
        endpoint,
        "GET",
        "/health",
        None,
        None,
        daemon_read_timeout(None),
    ) else {
        return false;
    };
    if response.status != 200 {
        return false;
    }
    serde_json::from_str::<serde_json::Value>(&response.body)
        .ok()
        .and_then(|value| value.get("ok").and_then(|ok| ok.as_bool()))
        == Some(true)
}

fn healthy_endpoint(data_path: &Path) -> Option<DaemonEndpoint> {
    let runtime_path = data_path.join(RUNTIME_FILE_NAME);
    if let Ok(endpoint) = read_runtime_endpoint(&runtime_path) {
        if health_ok(&endpoint) {
            return Some(endpoint);
        }
    }

    let endpoint = default_endpoint();
    if health_ok(&endpoint) {
        return Some(endpoint);
    }
    None
}

fn wait_for_healthy_endpoint(data_path: &Path, timeout: Duration) -> Option<DaemonEndpoint> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if let Some(endpoint) = healthy_endpoint(data_path) {
            return Some(endpoint);
        }
        thread::sleep(Duration::from_millis(250));
    }
    None
}

fn daemon_status_from_endpoint(
    endpoint: DaemonEndpoint,
    data_path: &Path,
    runtime_file: &Path,
    launch_attempted: bool,
) -> DaemonConnectStatus {
    let token_path = data_path.join(TOKEN_FILE_NAME);
    if let Err(message) = read_runtime_token_from_path(token_path) {
        return DaemonConnectStatus {
            ok: false,
            base_url: endpoint.base_url,
            data_dir: data_path.to_string_lossy().to_string(),
            runtime_file: runtime_file.to_string_lossy().to_string(),
            launch_attempted,
            message_cn: message,
        };
    }

    DaemonConnectStatus {
        ok: true,
        base_url: endpoint.base_url,
        data_dir: data_path.to_string_lossy().to_string(),
        runtime_file: runtime_file.to_string_lossy().to_string(),
        launch_attempted,
        message_cn: "小黑子本地服务已连接。".to_string(),
    }
}

#[cfg(target_os = "windows")]
fn hide_child_window(command: &mut Command) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x08000000;
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(target_os = "windows"))]
fn hide_child_window(_command: &mut Command) {}

#[cfg(target_os = "macos")]
fn configure_daemon_command(command: &mut Command, data_path: &Path) {
    command.env("LILSUNSPOT_DATA_DIR", data_path);
}

#[cfg(not(target_os = "macos"))]
fn configure_daemon_command(_command: &mut Command, _data_path: &Path) {}

fn spawn_candidate(program: PathBuf, args: &[&str], data_path: &Path) -> Result<(), String> {
    let mut command = Command::new(program);
    command
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    hide_child_window(&mut command);
    configure_daemon_command(&mut command, data_path);
    command
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("启动本地服务失败：{error}"))
}

fn sidecar_file_names() -> &'static [&'static str] {
    #[cfg(target_os = "windows")]
    {
        &["lilsunspotd.exe", WINDOWS_SIDECAR_NAME]
    }

    #[cfg(not(target_os = "windows"))]
    {
        &["lilsunspotd"]
    }
}

fn add_sidecar_candidates_from_dir(candidates: &mut Vec<PathBuf>, dir: &Path) {
    for name in sidecar_file_names() {
        candidates.push(dir.join("binaries").join("lilsunspotd").join(name));
        candidates.push(
            dir.join("resources")
                .join("binaries")
                .join("lilsunspotd")
                .join(name),
        );
        candidates.push(dir.join(name));
        candidates.push(dir.join("binaries").join(name));
        candidates.push(dir.join("resources").join(name));
        candidates.push(dir.join("resources").join("binaries").join(name));
    }
}

fn bundled_sidecar_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(current_exe) = env::current_exe() {
        if let Some(dir) = current_exe.parent() {
            add_sidecar_candidates_from_dir(&mut candidates, dir);

            #[cfg(target_os = "macos")]
            if let Some(contents_dir) = dir.parent() {
                add_sidecar_candidates_from_dir(&mut candidates, &contents_dir.join("Resources"));
            }
        }
    }

    if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
        add_sidecar_candidates_from_dir(&mut candidates, Path::new(manifest_dir));
    }

    candidates
}

fn launch_daemon_process(data_path: &Path) -> Result<(), String> {
    if let Ok(value) = env::var("LILSUNSPOTD_PATH") {
        let path = PathBuf::from(value);
        if path.exists() {
            return spawn_candidate(path, &[], data_path);
        }
    }

    for path in bundled_sidecar_candidates() {
        if path.exists() {
            return spawn_candidate(path, &[], data_path);
        }
    }

    for name in sidecar_file_names() {
        if spawn_candidate(PathBuf::from(name), &[], data_path).is_ok() {
            return Ok(());
        }
    }

    #[cfg(debug_assertions)]
    {
        if spawn_candidate(
            PathBuf::from("python"),
            &["-m", "lilsunspot.daemon.launcher"],
            data_path,
        )
        .is_ok()
        {
            return Ok(());
        }
    }

    Err("没有找到小黑子本地服务启动器。".to_string())
}

#[tauri::command]
fn connect_daemon() -> DaemonConnectStatus {
    let data_path = match data_dir() {
        Ok(path) => path,
        Err(message) => {
            return DaemonConnectStatus {
                ok: false,
                base_url: default_endpoint().base_url,
                data_dir: "".to_string(),
                runtime_file: "".to_string(),
                launch_attempted: false,
                message_cn: message,
            };
        }
    };
    let runtime_file = data_path.join(RUNTIME_FILE_NAME);
    let mut launch_attempted = false;
    let Some(_guard) = DaemonConnectGuard::enter() else {
        return match wait_for_healthy_endpoint(&data_path, Duration::from_secs(10)) {
            Some(endpoint) => daemon_status_from_endpoint(endpoint, &data_path, &runtime_file, false),
            None => DaemonConnectStatus {
                ok: false,
                base_url: default_endpoint().base_url,
                data_dir: data_path.to_string_lossy().to_string(),
                runtime_file: runtime_file.to_string_lossy().to_string(),
                launch_attempted: false,
                message_cn: "小黑子本地服务正在启动，请稍后再试。".to_string(),
            },
        };
    };

    let endpoint = match healthy_endpoint(&data_path) {
        Some(endpoint) => endpoint,
        None => {
            launch_attempted = true;
            if let Err(message) = launch_daemon_process(&data_path) {
                return DaemonConnectStatus {
                    ok: false,
                    base_url: default_endpoint().base_url,
                    data_dir: data_path.to_string_lossy().to_string(),
                    runtime_file: runtime_file.to_string_lossy().to_string(),
                    launch_attempted,
                    message_cn: message,
                };
            }

            let found = wait_for_healthy_endpoint(&data_path, Duration::from_secs(10));
            match found {
                Some(endpoint) => endpoint,
                None => {
                    return DaemonConnectStatus {
                        ok: false,
                        base_url: default_endpoint().base_url,
                        data_dir: data_path.to_string_lossy().to_string(),
                        runtime_file: runtime_file.to_string_lossy().to_string(),
                        launch_attempted,
                        message_cn: "小黑子本地服务没有成功启动，可能被安全软件拦截。".to_string(),
                    };
                }
            }
        }
    };
    daemon_status_from_endpoint(endpoint, &data_path, &runtime_file, launch_attempted)
}

#[tauri::command]
fn discover_daemon() -> Result<DaemonDiscovery, String> {
    let data_path = data_dir()?;
    let runtime_path = data_path.join(RUNTIME_FILE_NAME);
    let endpoint = read_runtime_endpoint(&runtime_path)?;
    Ok(DaemonDiscovery {
        base_url: endpoint.base_url,
        data_dir: data_path.to_string_lossy().to_string(),
        runtime_file: runtime_path.to_string_lossy().to_string(),
    })
}

#[tauri::command]
async fn daemon_request(
    path: String,
    method: String,
    body: Option<String>,
    timeout_ms: Option<u64>,
) -> Result<DaemonHttpResponse, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let data_path = data_dir()?;
        let endpoint = healthy_endpoint(&data_path)
            .ok_or_else(|| "小黑子本地服务没有启动。".to_string())?;
        let token = read_runtime_token_from_path(data_path.join(TOKEN_FILE_NAME))?;
        http_request(
            &endpoint,
            &method,
            &path,
            body.as_deref(),
            Some(&token),
            daemon_read_timeout(timeout_ms),
        )
    })
    .await
    .map_err(|_| "本地服务请求被中断。".to_string())?
}

#[tauri::command]
fn subscribe_events(app: AppHandle) -> Result<bool, String> {
    if SSE_RUNNING.swap(true, Ordering::SeqCst) {
        return Ok(true);
    }
    let data_path = data_dir()?;
    let endpoint = healthy_endpoint(&data_path)
        .ok_or_else(|| "小黑子本地服务没有启动。".to_string())?;
    let token = read_runtime_token_from_path(data_path.join(TOKEN_FILE_NAME))?;
    thread::spawn(move || run_sse_loop(app, data_path, endpoint, token));
    Ok(true)
}

#[tauri::command]
fn open_attachment(attachment_id: String) -> Result<bool, String> {
    validate_attachment_id(&attachment_id)?;
    let data_path = data_dir()?;
    let endpoint = healthy_endpoint(&data_path)
        .ok_or_else(|| "小黑子本地服务没有启动。".to_string())?;
    let token = read_runtime_token_from_path(data_path.join(TOKEN_FILE_NAME))?;
    let response = http_request(
        &endpoint,
        "GET",
        &format!("/attachments/{attachment_id}"),
        None,
        Some(&token),
        daemon_read_timeout(None),
    )?;
    if response.status < 200 || response.status >= 300 {
        return Err("附件信息读取失败。".to_string());
    }
    let file_path = attachment_path_from_response(&response.body)?
        .canonicalize()
        .map_err(|_| "附件文件不存在。".to_string())?;
    let attachment_root = data_path
        .join(ATTACHMENT_DIR_NAME)
        .canonicalize()
        .map_err(|_| "附件目录不存在。".to_string())?;
    if !file_path.starts_with(&attachment_root) {
        return Err("附件路径不在小黑子的安全目录内。".to_string());
    }
    open_path_in_file_manager(&file_path)?;
    Ok(true)
}

#[tauri::command]
async fn check_update(app: AppHandle) -> AppUpdateStatus {
    #[cfg(target_os = "macos")]
    {
        let _ = app;
        return AppUpdateStatus {
            state: "unavailable".to_string(),
            update: None,
            message: "当前私用 macOS 安装包不提供自动更新，请下载新的 DMG 后覆盖安装。".to_string(),
        };
    }

    #[cfg(not(target_os = "macos"))]
    {
    let data_path = match data_dir() {
        Ok(path) => path,
        Err(message) => return failed_update_status(message),
    };
    let updater = match app.updater() {
        Ok(value) => value,
        Err(_) => {
            return failed_update_status("应用更新检查暂时不可用。");
        }
    };
    match updater.check().await {
        Ok(Some(update)) => {
            let info = app_update_info(&update);
            if version_is_dismissed(&data_path, &info.version) {
                AppUpdateStatus {
                    state: "dismissed".to_string(),
                    update: Some(info),
                    message: "这个版本已忽略。".to_string(),
                }
            } else {
                AppUpdateStatus {
                    state: "available".to_string(),
                    update: Some(info),
                    message: "发现新版小黑子。".to_string(),
                }
            }
        }
        Ok(None) => AppUpdateStatus {
            state: "current".to_string(),
            update: None,
            message: "当前已经是最新版本。".to_string(),
        },
        Err(_) => failed_update_status("无法连接更新源，请稍后再试。"),
    }
    }
}

#[tauri::command]
async fn download_and_install_update(app: AppHandle) -> Result<AppUpdateInstallResult, String> {
    #[cfg(target_os = "macos")]
    {
        let _ = app;
        return Err("当前私用 macOS 安装包不提供自动更新，请下载新的 DMG 后覆盖安装。".to_string());
    }

    #[cfg(not(target_os = "macos"))]
    {
    let updater = app
        .updater()
        .map_err(|_| "应用更新检查暂时不可用。".to_string())?;
    let Some(update) = updater
        .check()
        .await
        .map_err(|_| "无法连接更新源，请稍后再试。".to_string())?
    else {
        return Ok(AppUpdateInstallResult {
            ok: true,
            version: "".to_string(),
            message: "当前已经是最新版本。".to_string(),
        });
    };

    update
        .download_and_install(|_, _| {}, || {})
        .await
        .map_err(|_| "更新下载或安装失败，请稍后重试。".to_string())?;
    app.restart()
    }
}

#[tauri::command]
fn dismiss_update_version(version: String) -> Result<(), String> {
    let version = validate_update_version(&version)?;
    let data_path = data_dir()?;
    write_dismissed_update_version(&data_path, &version)
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn setup_tray(app: &tauri::App) -> tauri::Result<()> {
    let open_item = MenuItem::with_id(app, "open", "打开小黑子", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open_item, &quit_item])?;
    let icon = app.default_window_icon().cloned();
    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "open" => show_main_window(app),
            "quit" => {
                EXIT_REQUESTED.store(true, Ordering::SeqCst);
                SSE_RUNNING.store(false, Ordering::SeqCst);
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            }
            | TrayIconEvent::DoubleClick {
                button: MouseButton::Left,
                ..
            } = event
            {
                show_main_window(&tray.app_handle());
            }
        });
    if let Some(icon) = icon {
        builder = builder.icon(icon);
    }
    builder.build(app)?;
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            app.handle()
                .plugin(tauri_plugin_updater::Builder::new().build())?;
            setup_tray(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if !EXIT_REQUESTED.load(Ordering::SeqCst) {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            connect_daemon,
            discover_daemon,
            daemon_request,
            subscribe_events,
            open_attachment,
            check_update,
            download_and_install_update,
            dismiss_update_version
        ])
        .run(tauri::generate_context!())
        .expect("error while running lilsunspot desktop");
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{Read, Write},
        net::{TcpListener, TcpStream},
        sync::mpsc,
        thread,
    };

    fn request_complete(bytes: &[u8]) -> bool {
        let header_end = bytes
            .windows(4)
            .position(|window| window == b"\r\n\r\n");
        let Some(header_end) = header_end else {
            return false;
        };
        let headers = String::from_utf8_lossy(&bytes[..header_end]);
        let content_length = headers
            .lines()
            .find_map(|line| {
                let (name, value) = line.split_once(':')?;
                if name.eq_ignore_ascii_case("Content-Length") {
                    value.trim().parse::<usize>().ok()
                } else {
                    None
                }
            })
            .unwrap_or(0);
        bytes.len() >= header_end + 4 + content_length
    }

    fn read_request(stream: &mut TcpStream) -> String {
        stream
            .set_read_timeout(Some(Duration::from_secs(2)))
            .expect("set read timeout");
        let mut bytes = Vec::new();
        let mut buffer = [0_u8; 1024];
        loop {
            let size = stream.read(&mut buffer).expect("read request");
            if size == 0 {
                break;
            }
            bytes.extend_from_slice(&buffer[..size]);
            if request_complete(&bytes) {
                break;
            }
        }
        String::from_utf8_lossy(&bytes).to_string()
    }

    fn capture_request(method: &str, body: Option<&str>) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind test listener");
        let port = listener.local_addr().expect("local addr").port();
        let (tx, rx) = mpsc::channel();
        thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept request");
            tx.send(read_request(&mut stream)).expect("send captured request");
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}")
                .expect("write response");
        });

        let endpoint = endpoint_from_parts(DEFAULT_HOST, port).expect("endpoint");
        let response = http_request(
            &endpoint,
            method,
            "/conversations/unit",
            body,
            Some("unit-token"),
            Duration::from_secs(2),
        )
        .expect("http request");
        assert_eq!(response.status, 200);
        rx.recv().expect("captured request")
    }

    #[test]
    fn http_request_allows_patch_with_token_and_body() {
        let request = capture_request("PATCH", Some("{\"title\":\"新名称\"}"));
        assert!(request.starts_with("PATCH /conversations/unit HTTP/1.1"));
        assert!(request.contains("X-Lilsunspot-Token: unit-token"));
        assert!(request.contains("Content-Type: application/json"));
        assert!(request.ends_with("{\"title\":\"新名称\"}"));
    }

    #[test]
    fn http_request_allows_delete_with_token() {
        let request = capture_request("DELETE", None);
        assert!(request.starts_with("DELETE /conversations/unit HTTP/1.1"));
        assert!(request.contains("X-Lilsunspot-Token: unit-token"));
    }

    #[test]
    fn dismissed_update_version_uses_desktop_state_file() {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("time")
            .as_nanos();
        let data_path = std::env::temp_dir().join(format!(
            "lilsunspot-update-state-test-{}-{unique}",
            std::process::id()
        ));

        assert_eq!(read_dismissed_update_version(&data_path), None);
        write_dismissed_update_version(&data_path, "1.2.3").expect("write dismissed version");
        assert_eq!(
            read_dismissed_update_version(&data_path).as_deref(),
            Some("1.2.3")
        );
        assert!(version_is_dismissed(&data_path, "1.2.3"));
        assert!(!version_is_dismissed(&data_path, "1.2.4"));

        let state_path = update_state_path(&data_path);
        assert_eq!(
            state_path.file_name().and_then(|value| value.to_str()),
            Some(UPDATE_STATE_FILE_NAME)
        );
        let _ = fs::remove_dir_all(data_path);
    }

    #[test]
    fn macos_default_data_dir_uses_application_support() {
        assert_eq!(
            macos_data_dir(Path::new("/Users/tester")),
            PathBuf::from("/Users/tester/Library/Application Support/Lilsunspot/data")
        );
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn macos_app_resources_candidate_includes_onedir_executable() {
        let mut candidates = Vec::new();
        add_sidecar_candidates_from_dir(
            &mut candidates,
            Path::new("/Applications/Lilsunspot.app/Contents/Resources"),
        );
        assert!(candidates.contains(&PathBuf::from(
            "/Applications/Lilsunspot.app/Contents/Resources/binaries/lilsunspotd/lilsunspotd"
        )));
    }
}
