use std::process::{Child, Command};
use std::path::{Path, PathBuf};
use std::io::BufRead;

/// 从配置目录读取 .env.supabase 或 supabase.env，解析 Supabase 关键环境变量。
/// 返回 (url, service_role_key, anon_key)；若任一缺失则返回错误。
fn load_supabase_env_from_config_dir(config_dir: &str) -> Result<(String, String, String), String> {
    let base = Path::new(config_dir);
    let candidates = [".env.supabase", "supabase.env"];
    let mut url = None::<String>;
    let mut service_key = None::<String>;
    let mut anon_key = None::<String>;
    let mut loaded_from = None::<String>;
    for name in candidates.iter() {
        let path = base.join(name);
        if let Ok(f) = std::fs::File::open(&path) {
            loaded_from = Some(path.display().to_string());
            let reader = std::io::BufReader::new(f);
            for line in reader.lines().filter_map(Result::ok) {
                let line = line.trim();
                if line.is_empty() || line.starts_with('#') {
                    continue;
                }
                if let Some(eq) = line.find('=') {
                    let k = line[..eq].trim();
                    let v = line[eq + 1..].trim().trim_matches('"').trim_matches('\'').to_string();
                    if k == "SUPABASE_URL" && !v.is_empty() {
                        url = Some(v);
                    } else if k == "SUPABASE_SERVICE_ROLE_KEY" && !v.is_empty() {
                        service_key = Some(v);
                    } else if (k == "SUPABASE_ANON_KEY" || k == "SUPABASE_PUBLISHABLE_KEY") && !v.is_empty() {
                        anon_key = Some(v);
                    }
                }
            }
            break;
        }
    }
    match (url, service_key, anon_key) {
        (Some(u), Some(sk), Some(ak)) => Ok((u, sk, ak)),
        _ => {
            let source = loaded_from.unwrap_or_else(|| format!("{}/.env.supabase", config_dir));
            Err(format!(
                "Supabase 配置缺失：需要 SUPABASE_URL、SUPABASE_SERVICE_ROLE_KEY、SUPABASE_ANON_KEY（或 SUPABASE_PUBLISHABLE_KEY）。配置文件: {}",
                source
            ))
        }
    }
}

/// Sidecar 进程管理器
///
/// 负责启动和停止 Python API 服务器进程
pub struct SidecarProcess {
    child: Option<Child>,
    port: u16,
}

impl SidecarProcess {
    /// 启动新的 Sidecar 进程
    ///
    /// # 参数
    /// * `config_dir` - 配置目录路径
    /// * `export_dir` - 导出目录路径
    /// * `resource_dir` - 资源目录路径（可选）
    /// * `port` - API 服务器端口
    ///
    /// # 返回
    /// 成功返回 SidecarProcess 实例，失败返回错误信息
    pub fn start(
        config_dir: String,
        export_dir: String,
        resource_dir: Option<String>,
        port: u16,
    ) -> Result<Self, String> {
        // 获取 Sidecar 可执行文件路径
        let exe_path = get_sidecar_path()?;
        
        // 写入日志文件用于调试
        if let Some(home) = dirs::home_dir() {
            let log_dir = home.join(".soundcapsule");
            let _ = std::fs::create_dir_all(&log_dir);
            let log_path = log_dir.join("tauri_debug.log");
            if let Ok(mut file) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&log_path)
            {
                use std::io::Write;
                let _ = writeln!(file, "[Sidecar] 可执行文件路径: {}", exe_path.display());
                let _ = writeln!(file, "[Sidecar] 文件存在: {}", exe_path.exists());
            }
        }

        println!("🚀 启动 Sidecar 进程:");
        println!("   可执行文件: {}", exe_path.display());
        println!("   配置目录: {}", config_dir);
        println!("   导出目录: {}", export_dir);
        println!("   资源目录: {}", resource_dir.as_ref().unwrap_or(&"默认".to_string()));
        println!("   端口: {}", port);

        // 构建命令
        let mut cmd = Command::new(&exe_path);

        // 添加命令行参数
        cmd.arg("--config-dir")
            .arg(&config_dir)
            .arg("--export-dir")
            .arg(&export_dir)
            .arg("--port")
            .arg(port.to_string());

        // 可选的资源目录
        if let Some(ref res_dir) = resource_dir {
            cmd.arg("--resource-dir").arg(res_dir);
        }

        // 安全约束：必须从配置文件读取 Supabase 配置，不允许内置默认高权限 key 回退
        let (supabase_url, supabase_key, supabase_anon_key) = load_supabase_env_from_config_dir(&config_dir)?;
        cmd.env("SUPABASE_URL", &supabase_url);
        cmd.env("SUPABASE_SERVICE_ROLE_KEY", &supabase_key);
        cmd.env("SUPABASE_ANON_KEY", &supabase_anon_key);

        // Windows Release 模式下隐藏控制台窗口
        // 开发模式下保留控制台以便查看日志
        #[cfg(all(windows, not(debug_assertions)))]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            cmd.creation_flags(CREATE_NO_WINDOW);
            println!("   (控制台窗口已隐藏 - Release 模式)");
        }

        // 启动进程
        let child = cmd.spawn().map_err(|e| {
            // 写入错误日志
            if let Some(home) = dirs::home_dir() {
                let log_path = home.join(".soundcapsule").join("tauri_debug.log");
                if let Ok(mut file) = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(&log_path)
                {
                    use std::io::Write;
                    let _ = writeln!(file, "[Sidecar] 启动失败: {}", e);
                }
            }
            format!(
                "启动 Sidecar 失败: {}\n可执行文件路径: {}",
                e,
                exe_path.display()
            )
        })?;

        // 记录成功启动
        if let Some(home) = dirs::home_dir() {
            let log_path = home.join(".soundcapsule").join("tauri_debug.log");
            if let Ok(mut file) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&log_path)
            {
                use std::io::Write;
                let _ = writeln!(file, "[Sidecar] 进程已启动 PID: {:?}", child.id());
            }
        }

        println!("✓ Sidecar 进程已启动 (PID: {:?})", child.id());

        Ok(SidecarProcess {
            child: Some(child),
            port,
        })
    }

    /// 停止 Sidecar 进程
    pub fn stop(&mut self) {
        if let Some(mut child) = self.child.take() {
            println!("🛑 正在停止 Sidecar 进程 (PID: {:?})...", child.id());

            match child.kill() {
                Ok(_) => {
                    // 等待进程结束
                    match child.wait() {
                        Ok(status) => {
                            println!("✓ Sidecar 进程已停止 (退出码: {:?})", status.code());
                        }
                        Err(e) => {
                            eprintln!("⚠️  等待 Sidecar 进程结束失败: {}", e);
                        }
                    }
                }
                Err(e) => {
                    eprintln!("⚠️  停止 Sidecar 进程失败: {}", e);
                }
            }
        } else {
            println!("⚠️  Sidecar 进程未运行");
        }
    }

    /// 获取端口号
    pub fn port(&self) -> u16 {
        self.port
    }

    /// 检查进程是否仍在运行
    pub fn is_running(&mut self) -> bool {
        if let Some(ref mut child) = self.child {
            match child.try_wait() {
                Ok(None) => true,  // 进程仍在运行
                Ok(Some(_)) => false, // 进程已结束
                Err(_) => false,     // 错误，假定进程不运行
            }
        } else {
            false
        }
    }
}

impl Drop for SidecarProcess {
    fn drop(&mut self) {
        // 当 SidecarProcess 被销毁时自动停止进程
        self.stop();
    }
}

/// 获取 Sidecar 可执行文件路径
///
/// 优先级:
/// 1. 开发环境: 使用 Python 虚拟环境中的 PyInstaller 构建结果
/// 2. 生产环境: 使用打包后的可执行文件
fn get_sidecar_path() -> Result<PathBuf, String> {
    // 获取当前可执行文件所在目录（Tauri app）
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .ok_or("无法获取可执行文件目录")?;

    // 开发环境检测
    if cfg!(debug_assertions) {
        // 开发环境: 使用项目中的 Python 脚本
        let project_dir = std::env::var("CARGO_MANIFEST_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("."));

        // 尝试多个可能的路径
        let possible_paths = vec![
            // 开发环境: 使用 venv 中的 python 直接运行脚本
            project_dir.join("../../data-pipeline/venv/bin/python"),
            project_dir.join("../../data-pipeline/venv/Scripts/python.exe"),  // Windows
            // 或者使用已构建的可执行文件（如果存在）
            project_dir.join("../../data-pipeline/dist/capsules_api"),
        ];

        for path in possible_paths {
            if path.exists() {
                return Ok(path);
            }
        }

        // 如果都不存在，返回第一个（让错误信息更清晰）
        Ok(project_dir.join("../../data-pipeline/venv/bin/python"))
    } else {
        // 生产环境: 使用打包在应用目录中的可执行文件
        // 尝试多种可能的文件名（支持不同的命名约定）
        let possible_names: Vec<&str> = if cfg!(windows) {
            vec![
                "capsules_api-x86_64-pc-windows-msvc.exe",  // Tauri externalBin 格式
                "capsules_api-aarch64-pc-windows-msvc.exe", // ARM64 Windows
                "capsules-api.exe",                         // 简化名称
                "capsules_api.exe",                         // 下划线版本
            ]
        } else if cfg!(target_os = "macos") {
            vec![
                "capsules_api-aarch64-apple-darwin",        // Apple Silicon
                "capsules_api-x86_64-apple-darwin",         // Intel Mac
                "capsules_api",
            ]
        } else {
            vec!["capsules_api"]
        };

        for name in &possible_names {
            let sidecar_path = exe_dir.join(name);
            if sidecar_path.exists() {
                println!("✓ 找到 Sidecar: {}", sidecar_path.display());
                return Ok(sidecar_path);
            }
        }

        Err(format!(
            "Sidecar 可执行文件不存在。已尝试以下路径:\n{}",
            possible_names.iter()
                .map(|n| format!("  - {}", exe_dir.join(n).display()))
                .collect::<Vec<_>>()
                .join("\n")
        ))
    }
}

/// 检查 Sidecar 可执行文件是否存在
pub fn check_sidecar_available() -> Result<PathBuf, String> {
    let path = get_sidecar_path()?;
    if path.exists() {
        Ok(path)
    } else {
        Err(format!("Sidecar 可执行文件不存在: {}", path.display()))
    }
}

#[tauri::command]
pub fn start_sidecar(
    config_dir: String,
    export_dir: String,
    resource_dir: Option<String>,
    port: u16,
) -> Result<String, String> {
    // 启动 Sidecar
    // 注意: 这个实现需要改进，因为进程管理器需要在应用状态中维护
    // 这里只是简单演示，实际应该使用 Arc<Mutex<>> 来管理全局进程状态

    let _sidecar = SidecarProcess::start(config_dir, export_dir, resource_dir, port)?;

    // 返回成功消息
    // ⚠️ 实际实现中，sidecar 不应该被立即丢弃！
    // 需要在 main.rs 中使用 app.manage() 来管理进程状态

    Ok(format!("Sidecar 启动成功，端口: {}", port))
}

#[tauri::command]
pub fn check_sidecar() -> Result<String, String> {
    let path = check_sidecar_available()?;
    Ok(format!("Sidecar 可用: {}", path.display()))
}

/// 在 REAPER 中打开 RPP 文件
///
/// 使用系统默认应用打开 .rpp 文件（通常是 REAPER）
///
/// # 参数
/// * `path` - RPP 文件的完整路径
///
/// # 返回
/// 成功返回成功消息，失败返回错误信息
#[tauri::command]
pub fn open_rpp_in_reaper(path: String) -> Result<String, String> {
    use std::path::Path;

    println!("📄 正在打开 RPP 文件: {}", path);

    // 检查文件是否存在
    let file_path = Path::new(&path);
    if !file_path.exists() {
        let error_msg = format!("文件不存在: {}", path);
        println!("❌ {}", error_msg);
        return Err(error_msg);
    }

    println!("✓ 文件存在，准备打开...");

    #[cfg(target_os = "macos")]
    {
        // macOS: 使用 'open' 命令
        println!("🍎 macOS: 使用 'open' 命令");
        let result = Command::new("open")
            .arg(&path)
            .spawn();

        match result {
            Ok(mut child) => {
                println!("✓ 命令已执行，进程 ID: {:?}", child.id());
                // 等待一小会儿，确保命令执行
                std::thread::sleep(std::time::Duration::from_millis(100));
                Ok(format!("✓ 已在系统默认应用中打开: {}", path))
            },
            Err(e) => {
                let error_msg = format!("无法执行 open 命令: {}", e);
                println!("❌ {}", error_msg);
                Err(error_msg)
            },
        }
    }

    #[cfg(target_os = "windows")]
    {
        // Windows: 使用 'start' 命令打开 .rpp 文件
        println!("🪟 Windows: 使用 'start' 命令");
        let result = Command::new("cmd")
            .args(["/C", "start", "", &path])
            .spawn();

        match result {
            Ok(_) => Ok(format!("✓ 已在系统默认应用中打开: {}", path)),
            Err(e) => {
                let error_msg = format!("无法执行 start 命令: {}", e);
                println!("❌ {}", error_msg);
                Err(error_msg)
            },
        }
    }

    #[cfg(target_os = "linux")]
    {
        // Linux: 使用 'xdg-open' 命令
        println!("🐧 Linux: 使用 'xdg-open' 命令");
        let result = Command::new("xdg-open")
            .arg(&path)
            .spawn();

        match result {
            Ok(_) => Ok(format!("✓ 已在系统默认应用中打开: {}", path)),
            Err(e) => {
                let error_msg = format!("无法执行 xdg-open 命令: {}", e);
                println!("❌ {}", error_msg);
                Err(error_msg)
            },
        }
    }
}
