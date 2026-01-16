

# Sound Capsule (原 Synesth) 系统架构文档

版本: 2.0 (Production Ready)

最后更新: 2026-01-13

状态: 核心架构锁定 (Core Architecture Locked)

---

## 1. 系统概览 (System Overview)

Sound Capsule 是一个采用 混合架构 (Hybrid Architecture) 的桌面端声音资产管理系统。

它结合了 Tauri 的轻量级原生能力、Python 的强大的数据处理/AI 能力以及 REAPER 的音频处理能力，并通过 Supabase 实现云端协作。

### 1.1 核心设计理念

1. **本地优先 (Local First):** 即使没有网络，核心功能（REAPER 导出、本地检索、坐标计算）必须完全可用。
    
2. **单一数据源 (Single Source of Truth):** * **路径管理：** Tauri (Rust) 是唯一真理，Python 被动接收路径。
    
    - **元数据：** 本地 SQLite 为主，通过“最后写入优先 (Last Write Wins)”策略与云端同步。
        
3. **按需加载 (JIT Asset Delivery):** 轻量级元数据全量同步，重资产（WAV）按需下载。
    

---

## 2. 技术栈 (Tech Stack)

|**层级**|**技术选型**|**职责**|
|---|---|---|
|**Host / OS**|**Tauri v2 (Rust)**|窗口管理、系统托盘、**Sidecar 进程管理**、文件系统权限、**路径分发**。|
|**Frontend**|**React 18 + Vite**|用户界面、状态管理 (Context/Zustand)、可视化 (Canvas/SVG)、音频播放。|
|**Styling**|**Tailwind CSS**|"Deep Space Tech" 设计系统、3D 胶囊渲染。|
|**Sidecar (Backend)**|**Python 3.11 (Flask)**|**核心业务逻辑**、SQLite ORM、REAPER 通信 (Subprocess)、音频转码 (FFmpeg)、AI 推理 (Sentence-Transformers)。|
|**Database (Local)**|**SQLite**|存储胶囊元数据、用户配置、缓存索引。|
|**Cloud (BaaS)**|**Supabase**|PostgreSQL (元数据同步)、Storage (大文件存储)、Auth (JWT 鉴权)、Realtime (更新通知)。|
|**Integration**|**Lua + Python**|REAPER 脚本接口，实现无头模式 (Headless) 导出。|

---

## 3. 应用程序架构 (Application Architecture)

### 3.1 进程模型 (Process Model)

系统由两个主要进程组成，通过 HTTP (REST API) 通信：

代码段

```
graph TD
    A[Tauri Main Process (Rust)] -->|Spawns & Manages| B[Python Sidecar (Flask)]
    A -->|Hosts| C[WebView (React Frontend)]
    C -->|HTTP Requests (localhost:5002)| B
    B -->|SQL| D[(SQLite DB)]
    B -->|Subprocess| E[REAPER DAW]
    B -->|HTTPS| F[Supabase Cloud]
```

### 3.2 关键通信协议

1. **Frontend <-> Sidecar:** * 前端不直接操作数据库或文件系统。
    
    - 所有操作通过 `http://localhost:<port>/api/...` 进行。
        
    - **端口管理：** Python 启动时随机寻找可用端口，并通过 stdout 告知 Tauri/Frontend。
        
2. **Sidecar <-> REAPER:**
    
    - **方式：** 命令行调用 (Subprocess)。
        
    - **协议：** Python 生成 JSON 配置文件 -> 调用 REAPER (`reaper -batch script.lua`) -> Lua 读取 JSON -> Lua 执行导出 -> Lua 写入结果 JSON -> Python 读取结果。
        

---

## 4. 核心子系统设计 (Core Subsystems)

### 4.1 路径管理系统 (Path Management) - 🔴 架构铁律

为了解决打包后 (`_MEIPASS`, `.app` 内部路径) 和开发环境的路径差异，**严禁 Python 后端自行猜测路径**。

- **规则：** 所有路径由 Tauri 在启动 Sidecar 时通过 CLI 参数注入。
    
- **参数列表：**
    
    - `--config-dir`: 用户配置存储路径 (e.g., `~/Library/Application Support/com.soundcapsule/`)。
        
    - `--resource-dir`: 静态资源路径 (e.g., `.app/Contents/Resources/assets/`)。
        
    - `--export-dir`: 默认导出路径。
        
- **Python 行为：** 启动时解析 `argparse`，如果没有接收到路径参数，直接报错退出。
    

### 4.2 数据同步引擎 (Sync Engine - Phase B/C)

采用 **"Split-State" (分离状态)** 策略：

1. **轻数据同步 (Light Sync):**
    
    - **对象：** `metadata.json`, `preview.ogg`, `project.rpp`。
        
    - **时机：** 应用启动/登录/接收到 Realtime 通知时。
        
    - **行为：** 自动拉取，覆盖本地（基于版本号）。
        
2. **重数据同步 (Heavy Sync / JIT):**
    
    - **对象：** 源音频文件夹 (`Audio Files/*.wav`)。
        
    - **时机：** 用户点击 "Open in REAPER" 且本地缺失时。
        
    - **行为：** 触发下载队列，显示进度条。
        

### 4.3 权限与安全模型 (Security Model)

基于 **"公共库，私有权" (Public Library, Private Ownership)** 模型：

- **数据库层 (Supabase RLS):**
    
    - `SELECT`: `auth.role() = 'authenticated'` (所有人可读)。
        
    - `INSERT/UPDATE/DELETE`: `auth.uid() = user_id` (仅作者可写)。
        
- **应用层校验：**
    
    - 后端 API 在执行修改操作前，必须校验 `Authorization` Header 中的 Token `uid` 是否匹配资源 `user_id`。
        
    - 如果不匹配，返回 `403 Forbidden`。
        

### 4.4 语义棱镜系统 (Semantic Prism)

- **混合计算 (Hybrid Embedding):**
    
    1. 优先调用云端 Embedding API (FastAPI) 获取坐标 (Latency < 50ms)。
        
    2. 如果离线或超时，降级使用本地 Python `sentence-transformers` 模型 (Latency ~200ms)。
        
- **动态配置：** 棱镜定义（轴标签、锚点词）存储在数据库中，支持版本控制和动态更新，**严禁硬编码棱镜 ID**。
    

---

## 5. 数据流向图 (Data Flow)

### 场景：从 REAPER 导出 (Ingestion)

1. **User Action:** 在 REAPER 选中 Item -> 点击 App "Save"。
    
2. **Tauri:** 发送指令给 Python Sidecar。
    
3. **Python:** * 生成 `export_config.json`。
    
    - 调用 `subprocess.run(['reaper', '-batch', 'export_script.lua'])`。
        
4. **REAPER (Lua):** * 渲染 `preview.ogg`。
    
    - 保存 `.rpp` 片段。
        
    - 复制源文件。
        
5. **Python:** 扫描输出目录 -> 生成语义向量 -> 存入 SQLite -> 返回前端。
    
6. **React:** 刷新胶囊库视图。
    

### 场景：云端同步 (Sync)

1. **React:** 收到 Supabase Realtime `UPDATE` 事件。
    
2. **React:** 提示用户 "Update Available"。
    
3. **User Action:** 点击同步图标。
    
4. **Python:** 调用 Supabase SDK -> 下载 `metadata.json` & `preview.ogg` -> 更新 SQLite。
    
5. **React:** 胶囊卡片更新，位置在地图上移动。
    

---

## 6. 目录结构规范 (Directory Structure)

Plaintext

```
/
├── src-tauri/           # Rust Host (Tauri)
│   ├── src/
│   │   ├── main.rs      # 入口，Sidecar 启动，系统托盘
│   │   ├── config.rs    # 配置读写
│   │   └── paths.rs     # 🔴 路径解析逻辑 (OS 适配)
│   └── tauri.conf.json
│
├── src/                 # React Frontend
│   ├── components/      # UI 组件 (CapsuleLibrary, Prism...)
│   └── services/        # API 客户端
│
├── data-pipeline/       # Python Sidecar (Backend)
│   ├── capsule_api.py   # Flask 入口 (接收 CLI 参数)
│   ├── capsule_db.py    # 数据库层
│   ├── sync_service.py  # 同步逻辑
│   ├── lua_scripts/     # REAPER 脚本
│   └── requirements.txt
│
└── architecture/        # 设计文档
    └── ARCHITECTURE.md  # 本文件
```

---

## 7. 部署与构建 (Build & Distribution)

1. **Python 打包:** 使用 `pyinstaller` 将 `data-pipeline` 打包为单文件可执行程序 (`capsule-backend`).
    
2. **Sidecar 配置:** 在 `tauri.conf.json` 中配置 `externalBin` 指向打包后的 Python 程序。
    
3. **Tauri 构建:** 运行 `npm run tauri build`。Tauri 会将 React 编译为静态资源，并将 Python 可执行文件捆绑进最终的安装包 (`.dmg` / `.exe`)。
    

---

**给开发者的特别提示：**

> 在修改任何 Python 后端代码时，请务必检查 **路径获取方式**。如果你发现代码中使用了 `__file__` 或相对路径来定位资源，**请立即重构**，改为使用 `ARGS.resource_dir` 全局变量。这是生产环境稳定运行的基石。