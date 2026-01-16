use std::fs;
use std::path::PathBuf;
use serde::{Serialize, Deserialize};

// 定义应用的关键路径结构
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AppPaths {
    pub app_data_dir: PathBuf,    // 应用数据 (Config, DB)
    pub resources_dir: PathBuf,   // 静态资源 (Bundled assets)
    pub scripts_dir: PathBuf,     // Lua 脚本路径 (Phase D3 预留)
    pub python_env_dir: PathBuf,  // Python 环境路径 (Phase D2 预留)
    pub temp_dir: PathBuf,        // 临时目录
}

impl AppPaths {
    // 初始化方法
    pub fn new() -> Result<Self, String> {
        // 1. 获取系统标准路径
        let app_data_dir = dirs::config_dir()
            .map(|p| p.join("com.soundcapsule.app"))
            .ok_or("Failed to resolve config directory")?;

        // 资源目录：开发环境使用项目根目录，生产环境使用应用目录
        let resources_dir = if cfg!(debug_assertions) {
            // 开发环境
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("..")
                .join("data-pipeline")
        } else {
            // 生产环境：使用 Contents/Resources/_up_/_up_/data-pipeline/
            std::env::current_exe()
                .ok()
                .and_then(|p| {
                    // 从 Contents/MacOS/synesth 到 Contents/Resources/_up_/_up_/data-pipeline
                    p.parent()? // Contents/MacOS
                        .parent()? // Contents
                        .join("Resources")
                        .join("_up_")
                        .join("_up_")
                        .join("data-pipeline")
                        .into()
                })
                .ok_or("Failed to resolve resource directory")?
        };

        // 2. 定义子目录结构
        let scripts_dir = resources_dir.join("lua_scripts");
        let python_env_dir = resources_dir.join("exporters");

        // 临时目录使用系统临时目录下的专用文件夹
        let temp_dir = std::env::temp_dir().join("soundcapsule");

        // 3. 确保必要的目录存在 (mkdir -p)
        if !app_data_dir.exists() {
            fs::create_dir_all(&app_data_dir).map_err(|e| e.to_string())?;
        }
        // 确保临时目录存在
        if !temp_dir.exists() {
            fs::create_dir_all(&temp_dir).map_err(|e| e.to_string())?;
        }

        Ok(Self {
            app_data_dir,
            resources_dir,
            scripts_dir,
            python_env_dir,
            temp_dir,
        })
    }
}

// 暴露给前端的 Command
#[tauri::command]
pub fn get_app_paths(state: tauri::State<AppPaths>) -> AppPaths {
    state.inner().clone()
}