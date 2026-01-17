

  

**日期**: 2026-01-10

**状态**: 规划中

**优先级**: 高

  

---

  

## 📋 项目概述

  

将 Sound Capsule 从单机应用升级为**多人协作的云端化版本**，并解决生产环境打包分发问题。

  

---

  

## 🎯 核心目标

  

### 1. 云端数据中心化

- 数据从本地 SQLite 迁移到云端 PostgreSQL

- 实现 API 与 Sidecar 的分离架构

- 支持多用户协作和实时同步

  

### 2. 生产环境就绪

- 解决打包后的路径问题

- 实现 Python Sidecar 打包集成

- 提供初始化向导和配置管理

  

### 3. 按需下载资产管理

- 云端存储胶囊文件（RPP、预览音频）

- 本地缓存机制

- 状态管理和自动更新

  

---

  

## 📊 Phase 分类

  

```

Phase A: 云端架构重构 [✅ 已完成]

├─ A1: Cloud API 设计 ✅

├─ A2: Local Sidecar 瘦身 ✅

├─ A3: 用户鉴权系统 ✅

└─ A4: 棱镜同步机制 ✅

  

Phase B: 资产管理与下载 [🔄 进行中 - 本次规划]

├─ B1: 对象存储集成 ✅ (Supabase Storage 已集成)

├─ B2: 胶囊库状态管理 🆕 (混合存储策略)

├─ B3: 按需下载实现 🆕 (WAV 断点续传)

└─ B4: 版本控制 ✅ (已有版本控制)

  

Phase C: 数据一致性 [待规划]

├─ C1: 棱镜版本号

├─ C2: 云端 Embedding API

└─ C3: 客户端缓存策略

  

Phase D: 路径管理重构 [高优先级] ⚠️

├─ D1: Tauri 路径管理器

├─ D2: Python 路径适配

└─ D3: Lua 脚本路径修复

  

Phase E: Sidecar 打包 [高优先级] ⚠️

├─ E1: PyInstaller 配置

├─ E2: Tauri Sidecar 集成

└─ E3: 动态端口管理

  

Phase F: 初始化向导 [高优先级] ⚠️

├─ F1: 配置持久化

├─ F2: 首次运行向导

└─ F3: Python 配置传递

```

  

---

  

## 🚀 Phase D: 路径管理重构（生产环境优先）

  

### D1: Tauri 路径管理器

  

**目标**: 在 Rust 端实现统一的路径管理

  

**实现内容**:

  

#### 1.1 定义应用路径结构

  

```rust

// src-tauri/src/paths.rs

use std::path::PathBuf;

  

pub struct AppPaths {

pub config_dir: PathBuf, // %APPDATA%/com.soundcapsule.app/

pub database_path: PathBuf, // config_dir/capsules.db

pub export_dir: PathBuf, // ~/Documents/SoundCapsule/Exports/

pub cache_dir: PathBuf, // config_dir/cache/

pub temp_dir: PathBuf, // config_dir/temp/

}

  

#[tauri::command]

pub fn get_app_paths() -> Result<AppPaths, String> {

// 使用 dirs crate 计算路径

}

  

#[tauri::command]

pub fn ensure_app_dirs() -> Result<(), String> {

// 自动创建所有必要目录

}

```

  

**文件路径**:

- 新建: `webapp/src-tauri/src/paths.rs`

- 修改: `webapp/src-tauri/src/main.rs` (调用 ensure_app_dirs)

- 修改: `webapp/src-tauri/src/lib.rs` (注册 commands)

  

#### 1.2 废弃 .env 文件

  

**移除的依赖**:

- `dotenv` (Python)

- 环境变量读取 (Python)

  

**替代方案**:

- Rust 在启动时计算路径

- 通过命令行参数传递给 Python

  

---

  

### D2: Python 路径适配

  

**目标**: Python 后端接收 Rust 传递的路径参数

  

#### 2.1 修改启动逻辑

  

```python

# data-pipeline/capsule_api.py

import argparse

  

def main():

parser = argparse.ArgumentParser(description='Sound Capsule API')

parser.add_argument('--config-dir', required=True, help='配置目录路径')

parser.add_argument('--export-dir', required=True, help='导出目录路径')

parser.add_argument('--port', type=int, default=5002, help='API 端口')

parser.add_argument('--resource-dir', help='资源目录路径（打包后）')

  

args = parser.parse_args()

  

# 初始化路径

init_paths(args.config_dir, args.export_dir, args.resource_dir)

  

# 启动 Flask

app.run(port=args.port, debug=False)

  

def init_paths(config_dir: str, export_dir: str, resource_dir: Optional[str]):

global CONFIG_DIR, EXPORT_DIR, RESOURCE_DIR

  

CONFIG_DIR = Path(config_dir)

EXPORT_DIR = Path(export_dir)

  

# 资源目录处理

if resource_dir:

RESOURCE_DIR = Path(resource_dir)

else:

# 开发环境：使用相对路径

RESOURCE_DIR = Path(__file__).parent

  

# 更新数据库路径

DB_PATH = CONFIG_DIR / "capsules.db"

```

  

**文件路径**:

- 修改: `data-pipeline/capsule_api.py` (main 函数)

  

#### 2.2 资源路径函数

  

```python

# data-pipeline/utils.py

import sys

  

def get_resource_path(relative_path: str) -> Path:

"""

获取资源文件路径

  

开发环境: 使用相对路径

生产环境: 使用 sys._MEIPASS (PyInstaller)

"""

if getattr(sys, 'frozen', False):

# PyInstaller 打包后

base_path = Path(sys._MEIPASS)

else:

# 开发环境

base_path = Path(__file__).parent

  

return base_path / relative_path

  

# 使用示例

LEXICON_PATH = get_resource_path("master_lexicon_v3.csv")

LUA_SCRIPTS_DIR = get_resource_path("lua_scripts")

```

  

**文件路径**:

- 新建: `data-pipeline/utils.py`

- 修改: `data-pipeline/capsule_scanner.py` (使用 get_resource_path)

- 修改: `data-pipeline/capsule_api.py` (使用 get_resource_path)

  

---

  

### D3: Lua 脚本路径修复

  

**目标**: Lua 使用绝对路径导出，避免回退到开发路径

  

#### 3.1 修复 Python 生成 JSON

  

```python

# data-pipeline/exporters/reaper_webui_export.py

def prepare_export_config(self, config: Dict[str, Any]) -> bool:

# 确保 export_dir 是绝对路径

export_dir = config.get('export_dir')

  

if not Path(export_dir).is_absolute():

raise ValueError(f"export_dir 必须是绝对路径: {export_dir}")

  

# 写入 JSON

config_data = {

"export_dir": str(export_dir), # 绝对路径

# ...

}

```

  

**文件路径**:

- 修改: `data-pipeline/exporters/reaper_webui_export.py`

  

#### 3.2 Lua 路径处理

  

```lua

-- data-pipeline/lua_scripts/auto_export_from_config.lua

local function LoadConfig()

local config_file = "/tmp/synest_export/webui_export_config.json"

local file = io.open(config_file, "r")

local content = file:read("*a")

file:close()

  

-- 读取 export_dir (已经是绝对路径)

local export_dir = content:match('"export_dir"%s*:%s*"([^"]*)"')

  

if not export_dir or export_dir == "" then

error("export_dir 未配置或为空")

end

  

reaper.ShowConsoleMsg("导出目录: " .. export_dir .. "\n")

  

return {

export_dir = export_dir,

-- ...

}

end

```

  

**文件路径**:

- 修改: `data-pipeline/lua_scripts/auto_export_from_config.lua`

- 修改: `data-pipeline/lua_scripts/main_export2.lua` (添加路径日志)

  

#### 3.3 路径分隔符处理

  

```python

# data-pipeline/exporters/reaper_webui_export.py

import json

  

def sanitize_path_for_lua(path: str) -> str:

"""

将路径转换为 Lua 兼容格式

  

Windows: C:\\Users\\xxx -> C:/Users/xxx

Unix: /home/xxx -> /home/xxx

"""

return Path(path).as_posix()

  

# 在生成 JSON 时使用

config_data = {

"export_dir": sanitize_path_for_lua(export_dir),

}

```

  

**文件路径**:

- 修改: `data-pipeline/exporters/reaper_webui_export.py`

  

---

  

## 📦 Phase E: Sidecar 打包

  

### E1: PyInstaller 配置

  

#### 1.1 安装依赖

  

```bash

pip install pyinstaller

```

  

#### 1.2 创建 spec 文件

  

```python

# data-pipeline/capsules_api.spec

a = Analysis(

['capsule_api.py'],

pathex=[],

binaries=[],

datas=[

('lua_scripts', 'lua_scripts'),

('master_lexicon_v3.csv', '.'),

('database', 'database'),

],

hiddenimports=[

'sentence_transformers',

'flask',

'flask_cors',

],

# ...

)

```

  

#### 1.3 打包命令

  

```bash

# 开发环境测试

pyinstaller capsules_api.spec --onefile --name capsules_api

  

# 生产环境

pyinstaller capsules_api.spec --onefile --name capsules_api --noconsole

```

  

**文件路径**:

- 新建: `data-pipeline/capsules_api.spec`

  

---

  

### E2: Tauri Sidecar 集成

  

#### 2.1 tauri.conf.json 配置

  

```json

{

"bundle": {

"externalBin": [

{

"name": "capsules-api",

"path": "../data-pipeline/dist/capsules_api" // 打包后的路径

}

]

}

}

```

  

**文件路径**:

- 修改: `webapp/src-tauri/tauri.conf.json`

  

#### 2.2 Rust 启动/停止管理

  

```rust

// webapp/src-tauri/src/sidecar.rs

use std::process::{Child, Command};

  

pub struct SidecarProcess {

child: Option<Child>,

}

  

impl SidecarProcess {

pub fn start(config_dir: String, export_dir: String, port: u16) -> Result<Self, String> {

let exe_path = get_sidecar_path(); // 获取打包后的可执行文件路径

  

let child = Command::new(exe_path)

.arg("--config-dir")

.arg(config_dir)

.arg("--export-dir")

.arg(export_dir)

.arg("--port")

.arg(port.to_string())

.spawn()

.map_err(|e| format!("启动 Sidecar 失败: {}", e))?;

  

Ok(SidecarProcess {

child: Some(child),

})

}

  

pub fn stop(&mut self) {

if let Some(mut child) = self.child.take() {

let _ = child.kill();

}

}

}

```

  

**文件路径**:

- 新建: `webapp/src-tauri/src/sidecar.rs`

- 修改: `webapp/src-tauri/src/main.rs` (集成 SidecarProcess)

  

---

  

### E3: 动态端口管理

  

```rust

// webapp/src-tauri/src/port_manager.rs

use std::net::{SocketAddr, TcpListener};

  

pub fn find_available_port(start_port: u16) -> Option<u16> {

for port in start_port..(start_port + 100) {

if let Ok(_) = TcpListener::bind(format!("127.0.0.1:{}", port)) {

return Some(port);

}

}

None

}

  

// 使用示例

let port = find_available_port(5002).unwrap_or(5002);

```

  

**文件路径**:

- 新建: `webapp/src-tauri/src/port_manager.rs`

  

---

  

## 🎨 Phase F: 初始化向导

  

### F1: 配置持久化

  

#### 1.1 安装 tauri-plugin-store

  

```bash

cd webapp/src-tauri

cargo add tauri-plugin-store

```

  

#### 1.2 Rust Commands

  

```rust

// webapp/src-tauri/src/config.rs

use serde::{Deserialize, Serialize};

  

#[derive(Debug, Clone, Serialize, Deserialize)]

pub struct AppConfig {

pub reaper_web_url: Option<String>,

pub export_directory: Option<String>,

pub username: Option<String>,

pub language: Option<String>,

}

  

#[tauri::command]

pub async fn get_app_config(store: tauri_plugin_store::Store) -> Result<AppConfig, String> {

store.get("app_config")

.map_err(|e| format!("读取配置失败: {}", e))?

.ok_or_else(|| "配置不存在".to_string())

}

  

#[tauri::command]

pub async fn save_app_config(config: AppConfig, store: tauri_plugin_store::Store) -> Result<(), String> {

store.insert("app_config", config)

.map_err(|e| format!("保存配置失败: {}", e))

}

```

  

**文件路径**:

- 新建: `webapp/src-tauri/src/config.rs` (如果不存在)

- 修改: `webapp/src-tauri/src/lib.rs` (注册 commands 和 plugins)

  

---

  

### F2: 首次运行向导 (React)

  

**组件结构**:

```

webapp/src/

├── components/

│ ├── InitialSetup.jsx (已有，需要增强)

│ ├── SetupStep1_Directory.jsx (步骤1: 目录选择)

│ ├── SetupStep2_Reaper.jsx (步骤2: Reaper 连接)

│ └── InitialSetup.css (已有)

```

  

#### 2.1 步骤 1: 目录选择

  

```jsx

// webapp/src/components/SetupStep1_Directory.jsx

import { open } from '@tauri-apps/plugin-dialog';

  

export default function SetupStep1_Directory({ config, setConfig }) {

const selectDirectory = async () => {

const selected = await open({

directory: true,

multiple: false,

title: "选择胶囊导出目录"

});

  

if (selected) {

setConfig({ ...config, export_directory: selected });

}

};

  

return (

<div className="setup-step">

<h3>步骤 1: 设置导出目录</h3>

<p>选择保存音频胶囊的文件夹</p>

  

<div className="input-group">

<input

type="text"

value={config.export_directory || ''}

onChange={(e) => setConfig({ ...config, export_directory: e.target.value })}

placeholder="~/Documents/SoundCapsule/Exports"

/>

<button onClick={selectDirectory}>浏览...</button>

</div>

</div>

);

}

```

  

#### 2.2 步骤 2: Reaper 连接

  

```jsx

// webapp/src/components/SetupStep2_Reaper.jsx

import { invoke } from '@tauri-apps/api/core';

  

export default function SetupStep2_Reaper({ config, setConfig }) {

const [testing, setTesting] = useState(false);

const [status, setStatus] = useState(null);

  

const testConnection = async () => {

setTesting(true);

setStatus('testing');

  

try {

// 通过 Rust 代理请求 Reaper WebUI

const result = await invoke('test_reaper_connection', {

url: config.reaper_web_url

});

  

if (result.success) {

setStatus('success');

} else {

setStatus('failed');

}

} catch (error) {

setStatus('error');

} finally {

setTesting(false);

}

};

  

return (

<div className="setup-step">

<h3>步骤 2: 连接 REAPER</h3>

<p>输入 REAPER Web Interface 地址</p>

  

<input

type="text"

value={config.reaper_web_url || ''}

onChange={(e) => setConfig({ ...config, reaper_web_url: e.target.value })}

placeholder="http://localhost:9000"

/>

  

<button

onClick={testConnection}

disabled={testing || !config.reaper_web_url}

>

{testing ? '测试中...' : '测试连接'}

</button>

  

{status === 'success' && <p className="success">✓ 连接成功</p>}

{status === 'failed' && <p className="error">✗ 连接失败</p>}

</div>

);

}

```

  

**文件路径**:

- 新建: `webapp/src/components/SetupStep1_Directory.jsx`

- 新建: `webapp/src/components/SetupStep2_Reaper.jsx`

- 修改: `webapp/src/components/InitialSetup.jsx` (集成步骤)

  

---

  

### F3: Python 配置传递

  

#### 3.1 方案选择

  

**推荐方案**: 环境变量传递

  

**理由**:

- 简单直接

- Python 读取方便

- 不需要额外文件 I/O

  

#### 3.2 Rust 实现

  

```rust

// webapp/src-tauri/src/sidecar.rs

use std::env;

  

pub fn start_with_config(config: &AppConfig, port: u16) -> Result<Child, String> {

let exe_path = get_sidecar_path();

  

// 设置环境变量

let mut cmd = Command::new(exe_path);

  

// 通过环境变量传递配置（JSON 格式）

let config_json = serde_json::to_string(config).unwrap();

cmd.env("SYNESTH_CONFIG", config_json);

  

// 或者分别传递

if let Some(export_dir) = &config.export_directory {

cmd.env("SYNESTH_EXPORT_DIR", export_dir);

}

  

// 命令行参数传递路径

cmd.arg("--config-dir")

.arg(get_config_dir().to_str().unwrap())

.arg("--export-dir")

.arg(config.export_directory.as_ref().unwrap())

.arg("--port")

.arg(port.to_string());

  

cmd.spawn().map_err(|e| format!("启动失败: {}", e))

}

```

  

#### 3.3 Python 读取环境变量

  

```python

# data-pipeline/capsule_api.py

import os

import json

  

def load_config_from_env():

"""从环境变量加载配置"""

config_json = os.getenv("SYNESTH_CONFIG")

  

if config_json:

return json.loads(config_json)

else:

# 回退到命令行参数

return parse_args()

  

# 在 main 中使用

def main():

# 优先环境变量，其次命令行参数

if "SYNESTH_CONFIG" in os.environ:

config = load_config_from_env()

else:

config = parse_args()

  

init_paths(config['config_dir'], config['export_dir'])

# ...

```

  

**文件路径**:

- 修改: `webapp/src-tauri/src/sidecar.rs`

- 修改: `data-pipeline/capsule_api.py`

  

---

  

## 🎯 Phase B: 混合存储策略（本次规划重点）

  

**主题**: 元数据实时同步 + 资产按需下载

  

### 核心目标

  

实现混合存储策略，优化带宽和本地存储：

  

| 数据类型 | 示例 | 存储位置 | 同步策略 |

|---------|------|---------|---------|

| **元数据** (Light) | 名称、关键词、插件名 | PostgreSQL + SQLite | 双向实时同步 |

| **预览资产** (Light) | preview.ogg (小体积) | 对象存储 (Hot Storage) | 自动预加载 |

| **源资产** (Heavy) | source.wav (大文件) | 对象存储 (Cold Storage) | 按需下载 + 缓存 |

  

---

  

## 📊 B2: 胶囊库状态管理

  

### B2.1 数据库字段扩展

  

**新增字段** (capsules 表):

  

```sql

-- 文件同步状态（细粒度控制）

ALTER TABLE capsules ADD COLUMN file_sync_status TEXT DEFAULT 'unknown';

-- 'unknown' - 未知（旧数据）

-- 'synced' - 元数据+预览音频已同步

-- 'partial' - 仅元数据同步（预览音频未下载）

-- 'downloading' - 正在下载源文件

-- 'full' - 完整下载（元数据+预览+源文件）

  

-- 本地文件路径缓存

ALTER TABLE capsules ADD COLUMN local_wav_path TEXT;

-- 存储本地 WAV 文件的绝对路径，用于断点续传和缓存检查

  

-- 文件大小（字节）

ALTER TABLE capsules ADD COLUMN local_wav_size INTEGER;

-- 用于校验文件完整性

  

-- 文件哈希（SHA256）

ALTER TABLE capsules ADD COLUMN local_wav_hash TEXT;

-- 用于断点续传校验

  

-- 下载进度（0-100）

ALTER TABLE capsules ADD COLUMN download_progress INTEGER DEFAULT 0;

-- 实时下载进度

  

-- 下载开始时间

ALTER TABLE capsules ADD COLUMN download_started_at TIMESTAMP;

  

-- 预览音频下载状态

ALTER TABLE capsules ADD COLUMN preview_downloaded BOOLEAN DEFAULT 0;

```

  

**新表：下载任务队列表**

  

```sql

CREATE TABLE IF NOT EXISTS download_tasks (

id INTEGER PRIMARY KEY AUTOINCREMENT,

capsule_id INTEGER NOT NULL,

file_type TEXT NOT NULL, -- 'preview', 'wav', 'rpp'

status TEXT NOT NULL, -- 'pending', 'downloading', 'completed', 'failed', 'paused'

remote_url TEXT NOT NULL,

local_path TEXT NOT NULL,

file_size INTEGER,

downloaded_bytes INTEGER DEFAULT 0,

progress INTEGER DEFAULT 0,

  

-- 断点续传支持

etag TEXT, -- HTTP ETag

last_modified TEXT, -- HTTP Last-Modified

  

-- 错误处理

error_message TEXT,

retry_count INTEGER DEFAULT 0,

max_retries INTEGER DEFAULT 3,

  

created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

completed_at TIMESTAMP,

  

FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE

);

  

CREATE INDEX idx_download_tasks_status ON download_tasks(status);

CREATE INDEX idx_download_tasks_capsule_id ON download_tasks(capsule_id);

```

  

**新表：本地缓存管理表**

  

```sql

CREATE TABLE IF NOT EXISTS local_cache (

id INTEGER PRIMARY KEY AUTOINCREMENT,

capsule_id INTEGER NOT NULL,

file_type TEXT NOT NULL, -- 'preview', 'wav', 'rpp'

file_path TEXT NOT NULL,

file_size INTEGER,

file_hash TEXT,

last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

access_count INTEGER DEFAULT 0,

  

-- 缓存策略

is_pinned BOOLEAN DEFAULT 0, -- 用户固定缓存（不会被清理）

cache_priority INTEGER DEFAULT 0,

  

created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  

FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE,

UNIQUE(capsule_id, file_type)

);

  

CREATE INDEX idx_local_cache_accessed ON local_cache(last_accessed_at);

CREATE INDEX idx_local_cache_priority ON local_cache(cache_priority DESC);

```

  

**关键文件**:

- 新建: `data-pipeline/database/mix_storage_schema.sql`

  

---

  

### B2.2 用户交互流程

  

**浏览状态**:

- 胶囊列表与本地一致

- 未下载 WAV 的胶囊显示 ☁️ 图标

- 元数据和标签完整显示

  

**预览状态**:

- 点击播放 OGG，直接流畅播放

- 因为 OGG 已经自动同步或流式加载

  

**下载/打开状态**:

```

用户点击"打开胶囊"

↓

系统检测 local_wav_path 是否存在

↓

├─ 已缓存 → 直接打开 REAPER (无延迟)

└─ 未缓存 → 询问用户

↓

├─ 确认下载 → 显示进度条 → 下载 WAV → 自动打开

└─ 取消 → 忽略 WAV 丢失，仅打开 RPP

```

  

---

  

## 📥 B3: 按需下载实现

  

### B3.1 后端 API

  

**新增端点**:

  

```python

# 1. 按需下载 WAV 源文件

POST /api/capsules/<int:capsule_id>/download-wav

请求体: { "force": false, "priority": 5 }

响应: { "success": true, "task_id": 123, "progress": 0, "file_size": 104857600 }

  

# 2. 获取下载进度

GET /api/capsules/<int:capsule_id>/download-status

响应: { "status": "downloading", "progress": 45, "downloaded_bytes": 47185920, "speed": "2.5 MB/s", "eta": "23s" }

  

# 3. 暂停下载

POST /api/download-tasks/<int:task_id>/pause

  

# 4. 恢复下载（支持断点续传）

POST /api/download-tasks/<int:task_id>/resume

  

# 5. 取消下载

POST /api/download-tasks/<int:task_id>/cancel

```

  

**关键文件**:

- 修改: `data-pipeline/capsule_api.py` (新增下载端点)

- 修改: `data-pipeline/supabase_client.py` (支持断点续传)

- 新建: `data-pipeline/download_manager.py` (下载队列管理器)

  

---

  

### B3.2 断点续传实现

  

**核心算法**:

  

```python

class ResumableDownloader:

def download_with_resume(

self,

capsule_id: int,

remote_url: str,

local_path: str,

task_id: int

) -> Dict[str, Any]:

"""

断点续传下载

  

1. 检查本地文件是否存在（断点）

2. 设置 Range 请求头: bytes={downloaded_bytes}-

3. 流式下载（1MB chunks）

4. 实时更新进度到数据库

5. SHA256 校验文件完整性

"""

```

  

**关键特性**:

- HTTP 206 Partial Content 支持

- 分块下载（1MB chunks）

- SQLite 事务性进度更新

- SHA256 完整性校验

- 自动重试（最多3次）

  

**关键文件**:

- 新建: `data-pipeline/resumable_downloader.py`

  

---

  

### B3.3 前端 UI 改造

  

**胶囊卡片状态指示**:

  

```jsx

// CapsuleLibrary.jsx 增强

const CapsuleCard = ({ capsule }) => {

const getFileStatus = () => {

if (capsule.file_sync_status === 'full') {

return { icon: DownloadCheck, color: 'green', text: '已下载' };

}

if (capsule.file_sync_status === 'downloading') {

return { icon: Loader, color: 'blue', text: '下载中' };

}

if (capsule.cloud_status === 'remote') {

return { icon: Cloud, color: 'blue', text: '云端' };

}

return { icon: HardDrive, color: 'gray', text: '本地' };

};

  

return (

<div className="capsule-card">

<div className={`file-status-badge ${fileStatus.color}`}>

<StatusIcon size={12} />

<span>{fileStatus.text}</span>

</div>

  

{capsule.file_sync_status === 'downloading' && (

<div className="download-progress">

<div className="progress-bar" style={{ width: `${capsule.download_progress}%` }}></div>

<span className="progress-text">{capsule.download_progress}%</span>

</div>

)}

</div>

);

};

```

  

**点击"打开"时的交互逻辑**:

  

```jsx

const handleImportToReaper = async (capsule) => {

// 1. 已完整下载 → 直接打开

if (capsule.file_sync_status === 'full') {

await openInReaper(capsule);

return;

}

  

// 2. 云端文件 → 询问用户

const confirmed = await showConfirmDialog({

title: '下载源文件',

message: `该胶囊的源文件（${formatFileSize(capsule.wav_size)}）未下载到本地。\n\n是否现在下载？`

});

  

if (!confirmed) return;

  

// 3. 创建下载任务

const taskId = await createDownloadTask(capsule.id, 'wav');

  

// 4. 显示下载进度对话框

const { completed } = await showDownloadProgress(taskId);

  

if (completed) {

await openInReaper(capsule);

toast.success('下载完成，已在 REAPER 中打开');

}

};

```

  

**关键文件**:

- 修改: `webapp/src/components/CapsuleLibrary.jsx`

- 新建: `webapp/src/components/DownloadProgressDialog.jsx`

- 修改: `webapp/src/contexts/SyncContext.jsx` (增加下载状态管理)

  

---

  

## 💾 缓存管理策略

  

### LRU 缓存清理算法

  

```python

class CacheManager:

def __init__(self, db_path: str, max_cache_size: int = 5 * 1024 * 1024 * 1024):

"""

Args:

max_cache_size: 最大缓存大小（默认5GB）

"""

  

def purge_old_cache(self, keep_pinned: bool = True) -> Dict[str, Any]:

"""

清理旧缓存（LRU策略）

  

1. 计算当前缓存大小

2. 按 last_accessed_at ASC 排序

3. 删除文件直到释放足够空间

4. 保留 is_pinned = 1 的文件

"""

```

  

**缓存管理 API**:

  

```python

GET /api/cache/stats

响应: { "total_size": 1073741824, "total_count": 50, "by_type": {...} }

  

POST /api/cache/purge

请求体: { "keep_pinned": true, "older_than": 30, "max_size": 536870912 }

  

PUT /api/capsules/<int:capsule_id>/cache-pin

请求体: { "pinned": true }

```

  

**关键文件**:

- 新建: `data-pipeline/cache_manager.py`

  

---

  

## 🔄 同步流程优化

  

### 元数据实时同步

  

**修改现有同步服务** (sync_service.py):

  

```python

class MetadataSyncService:

def sync_metadata_lightweight(self, user_id: str) -> Dict[str, Any]:

"""

轻量级同步：仅同步元数据 + 预览音频

  

1. 上传本地变更（元数据）

2. 下载云端变更（元数据）

3. 自动下载预览音频（小文件）

4. 不下载源 WAV（大文件）

"""

```

  

**关键文件**:

- 修改: `data-pipeline/sync_service.py`

- 修改: `data-pipeline/capsule_api.py` (/api/sync/upload 逻辑优化)

  

---

  

## 📋 实施步骤

  

### Phase 1: 数据库改造（第1-2周）

  

**任务**:

1. 执行数据库迁移脚本

2. 更新现有数据（设置默认 file_sync_status）

3. 扫描本地文件填充 local_cache 表

4. 编写数据库访问层方法

  

**关键文件**:

- 新建: `data-pipeline/database/mix_storage_schema.sql`

- 修改: `data-pipeline/capsule_db.py` (新增方法)

  

**验证**:

- [ ] 数据库迁移成功

- [ ] 现有胶囊状态正确

- [ ] 本地缓存表正确填充

  

---

  

### Phase 2: 后端 API 开发（第3-4周）

  

**任务**:

1. 实现 ResumableDownloader 类

2. 实现 DownloadQueue 类

3. 开发 REST API 端点

4. 实现 CacheManager 类

5. 单元测试

  

**关键文件**:

- 新建: `data-pipeline/resumable_downloader.py`

- 新建: `data-pipeline/download_manager.py`

- 新建: `data-pipeline/cache_manager.py`

- 修改: `data-pipeline/capsule_api.py`

- 修改: `data-pipeline/supabase_client.py`

  

**验证**:

- [ ] 断点续传功能测试

- [ ] 并发下载测试（3个任务）

- [ ] 缓存清理测试

- [ ] API 端点测试

  

---

  

### Phase 3: 前端 UI 改造（第5-6周）

  

**任务**:

1. 增强胶囊卡片（状态角标）

2. 开发下载进度对话框

3. 修改 handleImportToReaper 逻辑

4. 开发缓存管理界面

5. 集成测试

  

**关键文件**:

- 修改: `webapp/src/components/CapsuleLibrary.jsx`

- 新建: `webapp/src/components/DownloadProgressDialog.jsx`

- 新建: `webapp/src/components/CacheManager.jsx`

- 修改: `webapp/src/contexts/SyncContext.jsx`

  

**验证**:

- [ ] 云端图标正确显示

- [ ] 下载进度实时更新

- [ ] 取消/暂停功能正常

- [ ] 缓存管理界面可用

  

---

  

### Phase 4: 同步流程优化（第7-8周）

  

**任务**:

1. 增强 MetadataSyncService

2. 分离元数据和资产同步

3. 自动同步预览音频

4. 端到端测试

  

**关键文件**:

- 修改: `data-pipeline/sync_service.py`

- 修改: `webapp/src/contexts/SyncContext.jsx`

  

**验证**:

- [ ] 元数据实时同步

- [ ] 预览音频自动下载

- [ ] 源 WAV 按需下载

- [ ] 完整双向同步测试

  

---

  

### Phase 5: 性能优化和文档（第9周）

  

**任务**:

1. 并发下载优化

2. 缓存策略调优

3. 数据库查询优化

4. API 文档

5. 用户手册

  

**验证**:

- [ ] 性能测试（100个胶囊）

- [ ] 压力测试（并发下载）

- [ ] 文档完整性

  

---

  

## 🎯 预期收益

  

| 指标 | 当前 | 优化后 | 改善 |

|------|------|--------|------|

| 首次同步时间 | 10分钟（100个胶囊 × 10MB） | 30秒（仅元数据） | **95% ↓** |

| 本地存储占用 | 1GB（100个胶囊） | 100MB（元数据+预览） | **90% ↓** |

| 浏览体验 | 需要下载全部才能浏览 | 即时浏览（元数据已同步） | **即时** |

| 打开REAPER延迟 | 无（已下载） | 首次需下载（10-30秒） | **可接受** |

  

---

  

## ⚠️ 技术风险与缓解

  

| 风险 | 影响 | 概率 | 缓解措施 |

|------|------|------|---------|

| Supabase Storage 不支持断点续传 | 高 | 低 | ✅ 已验证：支持 Range 请求 |

| SQLite 并发写入性能瓶颈 | 中 | 中 | 队列 + 独立线程 + 连接池 |

| 下载中断导致文件损坏 | 中 | 中 | SHA256 校验 + 自动重试 |

| 缓存清理误删正在使用的文件 | 高 | 低 | 清理前检查文件访问状态 |

  

---

  

## 📁 关键文件清单

  

### 后端核心文件

1. `data-pipeline/resumable_downloader.py` - 断点续传下载器（新建）

2. `data-pipeline/download_manager.py` - 下载队列管理器（新建）

3. `data-pipeline/cache_manager.py` - 缓存管理器（新建）

4. `data-pipeline/sync_service.py` - 同步服务（修改）

5. `data-pipeline/capsule_api.py` - API 端点（修改）

6. `data-pipeline/supabase_client.py` - Supabase 客户端（修改）

7. `data-pipeline/capsule_db.py` - 数据库访问层（修改）

8. `data-pipeline/database/mix_storage_schema.sql` - 数据库迁移（新建）

  

### 前端核心文件

1. `webapp/src/components/CapsuleLibrary.jsx` - 胶囊列表（修改）

2. `webapp/src/components/DownloadProgressDialog.jsx` - 下载进度（新建）

3. `webapp/src/components/CacheManager.jsx` - 缓存管理（新建）

4. `webapp/src/contexts/SyncContext.jsx` - 同步上下文（修改）

  

---

  

## 🌩️ Phase A-C: 云端架构（已完成）

  

#### A1: Cloud API 设计

- 技术栈: Python FastAPI / Node.js Express

- 数据库: PostgreSQL

- 认证: JWT + Refresh Token

- 端点:

- `/api/auth/login`, `/api/auth/refresh`

- `/api/prisms` (CRUD + versioning)

- `/api/capsules` (CRUD + metadata)

- `/api/embedding` (文本 → 坐标)

  

#### A2: Local Sidecar 瘦身

- 移除数据库管理 (改为调用 Cloud API)

- 保留: REAPER 控制、本地缓存管理、文件上传

- 新增: 配置同步、离线模式支持

  

#### A3: 用户鉴权系统

- Tauri 前端添加登录界面

- 存储 JWT token (tauri-plugin-store)

- 自动 token 刷新

- 请求拦截器添加 Authorization header

  

#### A4: 棱镜同步机制

- 启动时拉取最新棱镜配置

- 版本号检查

- 增量更新 (只更新变化的棱镜)

- 离线缓存

  

#### B1-B4: 资产管理

- 对象存储: S3 / MinIO / 内部服务器

- 状态标识: [云端]、[已下载]、[更新可用]

- Tauri Command: `download_and_open_capsule(id)`

- 前端胶囊库改造: 状态徽章、下载进度

  

#### C1-C3: 数据一致性

- 棱镜 version 字段

- 云端 Embedding API (方案 B)

- 前端调用 `/api/embedding` 获取坐标

- 客户端缓存坐标 (LRU 缓存)

  

---

  

## ✅ 验证计划

  

### Phase B 验证（混合存储策略）

  

#### Phase 1: 数据库改造验证

- [ ] 数据库迁移成功执行

- [ ] 现有胶囊 `file_sync_status` 正确设置

- [ ] `local_cache` 表正确填充

- [ ] 索引创建成功

  

#### Phase 2: 后端 API 验证

- [ ] 断点续传功能测试：

- 下载到 50% 时中断网络

- 恢复网络后从断点继续

- 最终文件 SHA256 校验通过

- [ ] 并发下载测试：

- 同时下载 3 个 WAV 文件

- 进度正确更新到数据库

- 无 SQLite 写锁冲突

- [ ] 缓存管理测试：

- 下载文件后自动创建缓存记录

- LRU 清理删除最旧的文件

- 固定缓存不被删除

- [ ] API 端点测试：

- `/api/capsules/<id>/download-wav` 创建任务

- `/api/capsules/<id>/download-status` 返回实时进度

- `/api/download-tasks/<id>/pause` 暂停成功

- `/api/download-tasks/<id>/resume` 恢复成功

- `/api/download-tasks/<id>/cancel` 取消并清理部分文件

  

#### Phase 3: 前端 UI 验证

- [ ] 云端图标正确显示：

- 未下载 WAV 的胶囊显示 ☁️ 图标

- 下载中的胶囊显示进度条

- 已下载的胶囊显示 ✓ 图标

- [ ] 下载交互测试：

- 点击"打开"时弹出确认对话框

- 确认后显示下载进度对话框

- 进度条实时更新（每秒刷新）

- 速度和 ETA 显示正确

- [ ] 控制功能测试：

- 暂停按钮成功暂停下载

- 恢复按钮从断点继续

- 取消按钮删除部分文件

- [ ] 下载完成测试：

- 进度达到 100% 后自动打开 REAPER

- 显示成功提示

- `file_sync_status` 更新为 'full'

  

#### Phase 4: 同步流程验证

- [ ] 元数据实时同步：

- 修改胶囊名称后立即同步到云端

- 添加标签后立即同步到云端

- 其他设备立即看到变更

- [ ] 预览音频自动下载：

- 同步新胶囊时自动下载 preview.ogg

- 预览播放流畅无卡顿

- [ ] 源 WAV 按需下载：

- 元数据同步后不自动下载 WAV

- 只在点击"打开"时下载

- 下载后缓存到本地

  

#### Phase 5: 性能和端到端验证

- [ ] 性能测试：

- 100 个胶囊元数据同步 < 30 秒

- 100MB WAV 文件下载稳定

- 内存占用 < 500MB

- [ ] 压力测试：

- 同时下载 10 个文件

- 下载中断 5 次后成功恢复

- 缓存清理不影响正在下载的文件

- [ ] 端到端测试：

- 设备 A 保存胶囊 → 元数据同步到云端

- 设备 B 立即看到新胶囊（不下载 WAV）

- 设备 B 点击打开 → 询问下载 → 下载完成 → 打开 REAPER

  

### Phase D 验证

  

1. **路径管理测试**

- [ ] 在开发环境测试路径计算

- [ ] 确认所有目录被正确创建

- [ ] 验证前端能获取到正确的路径

  

2. **Python 路径测试**

- [ ] Python 启动时接收参数

- [ ] 资源文件能被正确读取

- [ ] 数据库连接到正确路径

  

3. **Lua 导出测试**

- [ ] 导出文件到用户目录

- [ ] 控制台日志显示正确路径

- [ ] 不再创建文件到开发目录

  

### Phase E 验证

  

1. **PyInstaller 打包测试**

- [ ] 打包成单一可执行文件

- [ ] 静态资源被正确包含

- [ ] 打包后能正常启动

  

2. **Sidecar 集成测试**

- [ ] Tauri 启动时自动启动 Python

- [ ] Tauri 关闭时 Python 进程结束

- [ ] 端口冲突时自动寻找可用端口

  

### Phase F 验证

  

1. **配置持久化测试**

- [ ] 配置能正确保存

- [ ] 重启应用后配置存在

- [ ] 配置能在不同平台迁移

  

2. **初始化向导测试**

- [ ] 首次启动显示向导

- [ ] 目录选择功能正常

- [ ] Reaper 连接测试正常

- [ ] 配置完成后能正常启动主应用

  

---

  

## 📅 实施顺序

  

### 第 1 阶段（优先级：高，9周）

**Phase B: 混合存储策略（本次规划重点）**

- Week 1-2: Phase 1 - 数据库改造

- Week 3-4: Phase 2 - 后端 API 开发

- Week 5-6: Phase 3 - 前端 UI 改造

- Week 7-8: Phase 4 - 同步流程优化

- Week 9: Phase 5 - 性能优化和文档

  

### 第 2 阶段（紧急，1-2天）

**Phase D: 路径管理重构**

- D1: Tauri 路径管理器

- D2: Python 路径适配

- D3: Lua 脚本路径修复

  

### 第 3 阶段（紧急，1-2天）

**Phase E: Sidecar 打包**

- E1: PyInstaller 配置

- E2: Tauri Sidecar 集成

- E3: 动态端口管理

  

### 第 4 阶段（重要，1天）

**Phase F: 初始化向导**

- F1: 配置持久化

- F2: 首次运行向导

- F3: Python 配置传递

  

### 第 5 阶段（待规划）

**Phase C: 数据一致性**

- 等待 B 完成后详细规划

  

---

  

## 🔧 技术栈汇总

  

### 新增依赖

  

**Rust**:

```toml

[dependencies]

tauri-plugin-store = "2.0"

dirs = "5.0"

serde_json = "1.0"

```

  

**Python**:

```txt

pyinstaller

```

  

**前端**:

```json

{

"dependencies": {

"@tauri-apps/plugin-dialog": "^2.0",

"@tauri-apps/plugin-store": "^2.0"

}

}

```

  

---

  

## 📝 注意事项

  

### 跨平台路径处理

- Windows: `C:\Users\...`

- macOS: `/Users/...`

- Linux: `/home/...`

  

**解决方案**: 使用 `Path.as_posix()` 统一转换为 `/` 分隔符

  

### 打包后路径问题

- 开发环境: `__file__` 有效

- 生产环境: `sys._MEIPASS` (PyInstaller)

  

**解决方案**: `get_resource_path()` 函数统一处理

  

### 环境变量大小限制

- 某些系统限制环境变量长度（如 Windows 32KB）

  

**解决方案**: 优先使用命令行参数，环境变量仅作备选

  

---

  

**最后更新**: 2026-01-11

**文档版本**: 2.0

**状态**: ✅ Phase B 混合存储策略规划完成

  

---

  

## 📝 总结

  

### Phase B 核心创新点

  

1. **混合存储策略**

- 元数据实时同步（保证一致性）

- 资产按需下载（节省存储空间）

- 预览音频自动预加载（平衡体验和性能）

  

2. **断点续传机制**

- 支持网络中断恢复

- 分块下载（1MB chunks）

- SHA256 完整性校验

  

3. **智能缓存管理**

- LRU 清理策略

- 用户固定缓存

- 最大缓存限制（5GB）

  

### 关键文件清单

  

**后端核心文件（8个）**:

1. `data-pipeline/database/mix_storage_schema.sql` - 数据库迁移（新建）

2. `data-pipeline/resumable_downloader.py` - 断点续传下载器（新建）

3. `data-pipeline/download_manager.py` - 下载队列管理器（新建）

4. `data-pipeline/cache_manager.py` - 缓存管理器（新建）

5. `data-pipeline/sync_service.py` - 同步服务（修改）

6. `data-pipeline/capsule_api.py` - API 端点（修改）

7. `data-pipeline/supabase_client.py` - Supabase 客户端（修改）

8. `data-pipeline/capsule_db.py` - 数据库访问层（修改）

  

**前端核心文件（4个）**:

1. `webapp/src/components/CapsuleLibrary.jsx` - 胶囊列表（修改）

2. `webapp/src/components/DownloadProgressDialog.jsx` - 下载进度（新建）

3. `webapp/src/components/CacheManager.jsx` - 缓存管理（新建）

4. `webapp/src/contexts/SyncContext.jsx` - 同步上下文（修改）

  

### 预期收益

  

| 指标 | 改善幅度 |

|------|---------|

| 首次同步时间 | **95% ↓** (10分钟 → 30秒) |

| 本地存储占用 | **90% ↓** (1GB → 100MB) |

| 浏览体验 | **即时** (需等待 → 即时浏览) |

| 打开REAPER延迟 | **可接受** (首次 10-30秒) |