use serde::Serialize;
use std::{
    env, fs,
    path::{Path, PathBuf},
};

const TOKEN_FILE_NAME: &str = "runtime-token.json";
const RUNTIME_FILE_NAME: &str = "daemon-runtime.json";

#[derive(Serialize)]
struct DaemonDiscovery {
    base_url: String,
    token: String,
    data_dir: String,
    token_file: String,
    runtime_file: String,
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

#[tauri::command]
fn read_runtime_token() -> Result<String, String> {
    read_runtime_token_from_path(data_dir()?.join(TOKEN_FILE_NAME))
}

fn read_runtime_token_from_path(token_path: PathBuf) -> Result<String, String> {
    let raw =
        fs::read_to_string(token_path).map_err(|_| "还没有找到 runtime token。".to_string())?;
    let payload: serde_json::Value =
        serde_json::from_str(&raw).map_err(|_| "runtime token 文件格式不正确。".to_string())?;
    let token = payload
        .get("token")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    if token.is_empty() {
        return Err("runtime token 文件为空。".to_string());
    }
    Ok(token)
}

fn read_daemon_base_url(runtime_path: &Path) -> Result<String, String> {
    let raw = fs::read_to_string(runtime_path)
        .map_err(|_| "还没有发现正在运行的 lilsunspotd。".to_string())?;
    let payload: serde_json::Value =
        serde_json::from_str(&raw).map_err(|_| "daemon 发现文件格式不正确。".to_string())?;
    let descriptor_type = payload
        .get("type")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    if descriptor_type != "lilsunspot-daemon-runtime" {
        return Err("daemon 发现文件类型不正确。".to_string());
    }

    let host = payload
        .get("host")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    if host != "127.0.0.1" {
        return Err("lilsunspotd 必须绑定到 127.0.0.1。".to_string());
    }

    let port = payload
        .get("port")
        .and_then(|value| value.as_u64())
        .ok_or_else(|| "daemon 端口不正确。".to_string())?;
    if port == 0 || port > 65535 {
        return Err("daemon 端口不正确。".to_string());
    }

    Ok(format!("http://{}:{}", host, port))
}

#[tauri::command]
fn discover_daemon() -> Result<DaemonDiscovery, String> {
    let data_path = data_dir()?;
    let runtime_path = data_path.join(RUNTIME_FILE_NAME);
    let token_path = data_path.join(TOKEN_FILE_NAME);
    Ok(DaemonDiscovery {
        base_url: read_daemon_base_url(&runtime_path)?,
        token: read_runtime_token_from_path(token_path.clone())?,
        data_dir: data_path.to_string_lossy().to_string(),
        token_file: token_path.to_string_lossy().to_string(),
        runtime_file: runtime_path.to_string_lossy().to_string(),
    })
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![read_runtime_token, discover_daemon])
        .run(tauri::generate_context!())
        .expect("error while running lilsunspot desktop");
}
