use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// 用户配置结构
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    /// REAPER 安装路径
    pub reaper_path: Option<String>,
    /// REAPER IP 地址（如果通过网络连接）
    pub reaper_ip: Option<String>,
    /// 导出数据的本地目录路径
    pub export_dir: Option<String>,
    /// 用户名
    pub username: Option<String>,
    /// 语言设置
    pub language: Option<String>,
    /// API 服务器基地址（开发/私有部署时连到本机或局域网服务器，如 http://192.168.1.100:5002，不填则默认 http://localhost:5002）
    pub api_base_url: Option<String>,
}

impl Default for AppConfig {
    fn default() -> Self {
        AppConfig {
            reaper_path: None,
            reaper_ip: None,
            export_dir: None,
            username: None,
            language: Some("zh-CN".to_string()),
            api_base_url: None,
        }
    }
}

/// 配置文件路径（跨平台）
fn get_config_path() -> PathBuf {
    // Tauri 会自动处理跨平台路径
    // macOS: ~/Library/Application Support/com.soundcapsule.app/config.json
    // Windows: C:\Users\用户名\AppData\Roaming\com.soundcapsule.app\config.json
    // Linux: ~/.config/com.soundcapsule.app/config.json
    dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("com.soundcapsule.app")
        .join("config.json")
}

/// 读取应用配置
#[tauri::command]
pub async fn get_app_config() -> Result<AppConfig, String> {
    let config_path = get_config_path();

    // 如果配置文件不存在，返回默认配置
    if !config_path.exists() {
        return Ok(AppConfig::default());
    }

    // 读取配置文件
    let content = std::fs::read_to_string(&config_path)
        .map_err(|e| format!("读取配置文件失败: {}", e))?;

    // 解析 JSON
    let config: AppConfig = serde_json::from_str(&content)
        .map_err(|e| format!("解析配置文件失败: {}", e))?;

    Ok(config)
}

/// 保存应用配置
#[tauri::command]
pub async fn save_app_config(config: AppConfig) -> Result<(), String> {
    let config_path = get_config_path();

    // 确保配置目录存在
    if let Some(parent) = config_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("创建配置目录失败: {}", e))?;
    }

    // 序列化配置为 JSON（美化格式）
    let content = serde_json::to_string_pretty(&config)
        .map_err(|e| format!("序列化配置失败: {}", e))?;

    // 写入配置文件
    std::fs::write(&config_path, content)
        .map_err(|e| format!("写入配置文件失败: {}", e))?;

    Ok(())
}

/// 重置配置为默认值
#[tauri::command]
pub async fn reset_app_config() -> Result<(), String> {
    let config_path = get_config_path();

    // 如果配置文件存在，删除它
    if config_path.exists() {
        std::fs::remove_file(&config_path)
            .map_err(|e| format!("删除配置文件失败: {}", e))?;
    }

    Ok(())
}
