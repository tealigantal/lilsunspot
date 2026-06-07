#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::{
    env, fs,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

const DEFAULT_HOST: &str = "127.0.0.1";
const DEFAULT_PORT: u16 = 8765;
const TOKEN_FILE_NAME: &str = "runtime-token.json";
const RUNTIME_FILE_NAME: &str = "daemon-runtime.json";
const WINDOWS_SIDECAR_NAME: &str = "lilsunspotd-x86_64-pc-windows-msvc.exe";

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

fn data_dir() -> Result<PathBuf, String> {
    if let Ok(value) = env::var("LILSUNSPOT_DATA_DIR") {
        return Ok(PathBuf::from(value));
    }
    if let Ok(value) = env::var("LOCALAPPDATA") {
        return Ok(PathBuf::from(value).join("Lilsunspot").join("data"));
    }
    Err("无法找到小黑子的本地数据目录。".to_string())
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
) -> Result<DaemonHttpResponse, String> {
    if method != "GET" && method != "POST" {
        return Err("只支持 GET 和 POST 请求。".to_string());
    }
    if !path.starts_with('/') || path.contains(' ') {
        return Err("请求路径不正确。".to_string());
    }

    let addr: SocketAddr = format!("{}:{}", endpoint.host, endpoint.port)
        .parse()
        .map_err(|_| "本地服务地址不正确。".to_string())?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(700))
        .map_err(|_| "小黑子本地服务没有响应。".to_string())?;
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
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

fn health_ok(endpoint: &DaemonEndpoint) -> bool {
    let Ok(response) = http_request(endpoint, "GET", "/health", None, None) else {
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

#[cfg(target_os = "windows")]
fn hide_child_window(command: &mut Command) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x08000000;
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(target_os = "windows"))]
fn hide_child_window(_command: &mut Command) {}

fn spawn_candidate(program: PathBuf, args: &[&str]) -> Result<(), String> {
    let mut command = Command::new(program);
    command
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    hide_child_window(&mut command);
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
        }
    }

    if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
        add_sidecar_candidates_from_dir(&mut candidates, Path::new(manifest_dir));
    }

    candidates
}

fn launch_daemon_process() -> Result<(), String> {
    if let Ok(value) = env::var("LILSUNSPOTD_PATH") {
        let path = PathBuf::from(value);
        if path.exists() {
            return spawn_candidate(path, &[]);
        }
    }

    for path in bundled_sidecar_candidates() {
        if path.exists() {
            return spawn_candidate(path, &[]);
        }
    }

    for name in sidecar_file_names() {
        if spawn_candidate(PathBuf::from(name), &[]).is_ok() {
            return Ok(());
        }
    }

    #[cfg(debug_assertions)]
    {
        if spawn_candidate(PathBuf::from("python"), &["-m", "lilsunspot.daemon.launcher"]).is_ok() {
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

    let endpoint = match healthy_endpoint(&data_path) {
        Some(endpoint) => endpoint,
        None => {
            launch_attempted = true;
            if let Err(message) = launch_daemon_process() {
                return DaemonConnectStatus {
                    ok: false,
                    base_url: default_endpoint().base_url,
                    data_dir: data_path.to_string_lossy().to_string(),
                    runtime_file: runtime_file.to_string_lossy().to_string(),
                    launch_attempted,
                    message_cn: message,
                };
            }

            let deadline = Instant::now() + Duration::from_secs(10);
            let mut found = None;
            while Instant::now() < deadline {
                if let Some(endpoint) = healthy_endpoint(&data_path) {
                    found = Some(endpoint);
                    break;
                }
                thread::sleep(Duration::from_millis(250));
            }
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
fn daemon_request(path: String, method: String, body: Option<String>) -> Result<DaemonHttpResponse, String> {
    let data_path = data_dir()?;
    let endpoint = healthy_endpoint(&data_path)
        .ok_or_else(|| "小黑子本地服务没有启动。".to_string())?;
    let token = read_runtime_token_from_path(data_path.join(TOKEN_FILE_NAME))?;
    http_request(&endpoint, &method, &path, body.as_deref(), Some(&token))
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            connect_daemon,
            discover_daemon,
            daemon_request
        ])
        .run(tauri::generate_context!())
        .expect("error while running lilsunspot desktop");
}
