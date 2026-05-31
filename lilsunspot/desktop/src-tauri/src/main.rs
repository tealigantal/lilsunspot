use std::{env, fs, path::PathBuf};

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
    let token_path = data_dir()?.join("runtime-token.json");
    let raw = fs::read_to_string(token_path).map_err(|_| "还没有找到 runtime token。".to_string())?;
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

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![read_runtime_token])
        .run(tauri::generate_context!())
        .expect("error while running lilsunspot desktop");
}
