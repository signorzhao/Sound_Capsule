# Sound Capsule Windows 开发环境配置指南

本指南帮助你在 Windows 上搭建 Sound Capsule 的开发环境。

---

## 安装前须知

| 项目 | 预估值 |
|------|--------|
| **磁盘空间** | 约 5-8 GB（含依赖和模型文件） |
| **安装时间** | 首次安装约 15-30 分钟（取决于网络速度） |
| **网络要求** | 需要访问 PyPI、npm、Hugging Face 等 |

**主要下载内容**：
- Python 依赖：约 1.5 GB（含 PyTorch 和 sentence-transformers 模型）
- Node.js 依赖：约 200 MB
- Rust/Tauri 编译缓存：约 2-3 GB（首次编译时生成）

---

## 系统要求

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| Windows | 10 (1803+) / 11 (64-bit) | 需要 WebView2 Runtime |
| Node.js | 18+ LTS | 推荐使用 nvm-windows 管理 |
| Python | 3.10+ | 推荐 3.11 |
| Rust | 最新稳定版 | 通过 rustup 安装 |
| Visual Studio Build Tools | 2019+ | 需要 C++ 桌面开发工作负载 |

---

## 一、安装基础依赖

### 1. 安装 Node.js

推荐使用 [nvm-windows](https://github.com/coreybutler/nvm-windows) 管理 Node 版本。

**PowerShell**：
```powershell
# 安装 nvm-windows 后
nvm install 18
nvm use 18

# 验证
node -v
npm -v
```

或直接从 [Node.js 官网](https://nodejs.org/) 下载 LTS 版本。

### 2. 安装 Python

从 [Python 官网](https://www.python.org/downloads/) 下载 3.11 版本。

安装时勾选：
- [x] Add Python to PATH
- [x] Install pip

```powershell
# 验证
python --version
pip --version
```

### 3. 安装 Rust 工具链

从 [rustup.rs](https://rustup.rs/) 下载并运行安装程序。

```powershell
# 验证
rustc --version
cargo --version
```

### 4. 安装 Visual Studio Build Tools

从 [Visual Studio Downloads](https://visualstudio.microsoft.com/downloads/) 下载 Build Tools。

安装时选择：
- [x] **Desktop development with C++** 工作负载

这是编译 Tauri 原生模块和部分 Python 包的必要依赖。

### 5. 检查 WebView2

Windows 10/11 通常已预装 WebView2 Runtime。如果没有，从 [Microsoft](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) 下载。

---

## 二、项目配置

### 1. 克隆项目

```powershell
git clone https://github.com/signorzhao/Sound_Capsule.git
cd Sound_Capsule
```

### 2. 配置后端 (Python)

> **注意**：以下命令在 **PowerShell** 中执行。如果使用 CMD，请参考下方的 CMD 语法。

**PowerShell**：
```powershell
cd data-pipeline

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 安装依赖（首次安装约 10-20 分钟）
pip install -r requirements.txt
```

**CMD**：
```cmd
cd data-pipeline

:: 创建虚拟环境
python -m venv venv

:: 激活虚拟环境
venv\Scripts\activate

:: 安装依赖
pip install -r requirements.txt
```

**安装须知**：
- `sentence-transformers` 首次安装会自动下载 PyTorch（约 800MB）和模型文件（约 500MB）
- 如果网络较慢，可能需要 20 分钟以上
- 如果安装中断，可重新运行 `pip install -r requirements.txt` 继续

### 3. 配置前端 (Node.js + Tauri)

```powershell
cd webapp

# 安装 npm 依赖（约 200MB）
npm install

# 安装 Tauri CLI（如果尚未安装）
npm install -g @tauri-apps/cli
```

### 4. 配置 Supabase（云同步和认证必需）

> **重要**：`.env.supabase` 文件被 `.gitignore` 忽略，**不会通过 Git 同步**。每台开发机器需要手动创建。

创建 `data-pipeline/.env.supabase` 文件：

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**获取这些值**：
1. 登录 [Supabase Dashboard](https://app.supabase.com/)
2. 选择项目 → Settings → API
3. `SUPABASE_URL`: 复制 "Project URL"
4. `SUPABASE_SERVICE_ROLE_KEY`: 复制 "service_role" key（**不是** anon key）

**验证配置**：启动后端时，日志应显示：
```
✓ Supabase 客户端已初始化: https://your-project-id.supabase.co
```

如果显示 `无法初始化 Supabase 客户端: Supabase 配置缺失`，说明配置文件未找到或格式错误。

---

## 三、启动开发环境

### 方式一：使用启动脚本（推荐）

双击项目根目录的 `start-all.bat`，会自动：
1. 创建必需的配置和导出目录
2. 启动后端 API 服务器（端口 5002）
3. 启动 Tauri 前端开发服务器

**默认目录**：
- 配置目录：`%USERPROFILE%\.soundcapsule`
- 导出目录：`%USERPROFILE%\Documents\SoundCapsule\Exports`

### 方式二：手动启动

> **重要**：后端 API 需要 `--config-dir` 和 `--export-dir` 参数。

#### PowerShell 版本

**终端 1 - 后端**：
```powershell
cd data-pipeline
.\venv\Scripts\activate

# 创建目录（如果不存在）
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.soundcapsule"
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\Documents\SoundCapsule\Exports"

# 启动 API（必须带参数）
python capsule_api.py --config-dir "$env:USERPROFILE\.soundcapsule" --export-dir "$env:USERPROFILE\Documents\SoundCapsule\Exports"
```

**终端 2 - 前端**：
```powershell
cd webapp
npm run tauri dev
```

#### CMD 版本

**终端 1 - 后端**：
```cmd
cd data-pipeline
venv\Scripts\activate

:: 创建目录（如果不存在）
mkdir "%USERPROFILE%\.soundcapsule" 2>nul
mkdir "%USERPROFILE%\Documents\SoundCapsule\Exports" 2>nul

:: 启动 API（必须带参数）
python capsule_api.py --config-dir "%USERPROFILE%\.soundcapsule" --export-dir "%USERPROFILE%\Documents\SoundCapsule\Exports"
```

**终端 2 - 前端**：
```cmd
cd webapp
npm run tauri dev
```

### 方式三：仅启动后端

双击 `start-backend-dev.bat`，会自动配置路径并启动后端。

---

## 四、常见问题

### Q: 后端启动失败，提示"缺少必需的命令行参数"

**A**: `capsule_api.py` 必须通过 Tauri 启动或手动传递参数。使用 `start-all.bat` 或 `start-backend-dev.bat` 脚本，它们会自动传递参数。

### Q: `pip install` 安装依赖失败

**A**: 分步骤排查：

1. **确保 Visual Studio Build Tools 已安装**（部分包需要 C++ 编译器）

2. **单独安装失败的包**：
   ```powershell
   # 如果某个包安装失败，单独安装它
   pip install package-name
   
   # 常见需要单独处理的包
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   pip install sentence-transformers
   pip install supabase
   ```

3. **使用国内镜像**（如果网络慢）：
   ```powershell
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

4. **清理缓存重试**：
   ```powershell
   pip cache purge
   pip install -r requirements.txt
   ```

### Q: `npm run tauri dev` 报错 "linker 'link.exe' not found"

**A**: 需要安装 Visual Studio Build Tools 的 C++ 工作负载。

### Q: WebView2 相关错误

**A**: 从 Microsoft 官网重新安装 WebView2 Runtime。

### Q: 后端 API 端口被占用

**A**: 检查是否有其他进程占用 5002 端口：
```powershell
netstat -ano | findstr :5002
```

### Q: 数据库锁定错误

**A**: 确保没有其他进程正在访问 `capsules.db`，或等待几秒后重试。

### Q: 云同步功能不工作

**A**: 
1. 确保已配置 `data-pipeline/.env.supabase` 文件（每台机器需要手动创建）
2. 确保使用的是 `SUPABASE_SERVICE_ROLE_KEY`（不是 anon key）
3. 确保已安装 supabase 包：
   ```powershell
   pip install supabase
   ```

### Q: 登录后提示"no such table"或"no such column"错误

**A**: 数据库 schema 不完整或过时。删除旧数据库后重启后端，让它自动重新初始化：

```powershell
# 删除旧数据库
Remove-Item "$env:USERPROFILE\.soundcapsule\database\capsules.db" -Force

# 重启后端（会自动创建新数据库）
cd data-pipeline
.\venv\Scripts\activate
python capsule_api.py
```

启动时应看到日志：`数据库不存在，正在初始化... ✓ 数据库初始化成功`

### Q: 胶囊类型（颜色/名称）与 Mac 不一致

**A**: 这是数据库 schema 不一致导致的。请按上面的方法删除数据库重新初始化，然后重新登录让云同步拉取最新数据。

### Q: 找不到 REAPER 可执行文件

**A**: REAPER 路径需要在初始化设置中配置，或手动编辑配置文件：

```powershell
# 配置文件路径
$env:APPDATA\com.soundcapsule.app\config.json
```

编辑该文件，添加或修改 `reaper_path`：
```json
{
  "reaper_path": "C:\\Program Files\\REAPER (x64)\\reaper.exe",
  "export_dir": "..."
}
```

常见 REAPER 安装路径：
- `C:\Program Files\REAPER (x64)\reaper.exe`
- `C:\Program Files\REAPER\reaper.exe`
- `C:\Program Files (x86)\REAPER\reaper.exe`

### Q: 首次运行 Tauri 编译很慢

**A**: 这是正常的。Rust 首次编译会下载和编译大量依赖（约 2-3GB 缓存），后续编译会快很多。

---

## 五、目录结构

```
Sound_Capsule/
├── data-pipeline/          # Python 后端
│   ├── venv/               # Python 虚拟环境（不提交）
│   ├── database/           # SQLite 数据库（不提交）
│   ├── routes/             # API 路由模块
│   │   ├── library_routes.py
│   │   └── sync_routes.py
│   ├── capsule_api.py      # API 入口
│   ├── requirements.txt    # Python 依赖
│   └── .env.supabase       # Supabase 配置（不提交）
│
├── webapp/                 # 前端 + Tauri
│   ├── src/                # React 源码
│   ├── src-tauri/          # Tauri/Rust 源码
│   │   ├── src/            # Rust 源代码
│   │   └── tauri.conf.json # Tauri 配置
│   └── package.json
│
├── start-all.bat           # Windows 一键启动
├── start-backend-dev.bat   # Windows 后端启动
├── start-all.sh            # macOS/Linux 一键启动
├── start-backend-dev.sh    # macOS/Linux 后端启动
└── docs/
    └── WINDOWS_SETUP.md    # 本文档
```

---

## 六、从 Mac 同步代码到 Windows

如果你主要在 Mac 上开发，需要在 Windows 上同步测试，请注意以下事项：

### 1. 拉取最新代码

```powershell
cd C:\WIN_DEV\Sound_Capsule  # 或你的项目路径
git pull origin main
```

### 2. 手动创建被 gitignore 忽略的文件

以下文件不会通过 Git 同步，需要手动创建：

| 文件 | 路径 | 说明 |
|------|------|------|
| `.env.supabase` | `data-pipeline/.env.supabase` | Supabase 配置（从 Mac 复制内容） |
| `config.json` | `%APPDATA%\com.soundcapsule.app\config.json` | 用户配置（首次登录时自动创建） |
| `capsules.db` | `%USERPROFILE%\.soundcapsule\database\capsules.db` | 本地数据库（自动创建） |

### 3. Schema 更新后重置数据库

如果 Mac 上更新了 `capsule_schema.sql`，Windows 的旧数据库可能不兼容。删除后重新初始化：

```powershell
Remove-Item "$env:USERPROFILE\.soundcapsule\database\capsules.db" -Force
```

### 4. 重新触发初始化设置

如果需要重新进行初始化设置（选择导出目录、REAPER 路径等）：

```powershell
# 删除用户配置
Remove-Item "$env:APPDATA\com.soundcapsule.app" -Recurse -Force

# 删除本地配置
Remove-Item "$env:USERPROFILE\.soundcapsule" -Recurse -Force

# 重启应用，会触发初始化设置向导
```

---

## 七、编译发布版本（高级）

如果需要打包分发，需要将 Python 后端编译为 Windows 可执行文件，并集成到 Tauri sidecar 中。

### 步骤 1：编译 Python 后端

> **说明**：`capsules_api.spec` 文件已包含在项目中（位于 `data-pipeline/` 目录），无需手动创建。

```powershell
cd data-pipeline

# 激活虚拟环境
.\venv\Scripts\activate

# 安装 PyInstaller
pip install pyinstaller

# 编译（需要几分钟）
pyinstaller capsules_api.spec
```

**输出**：生成的文件位于 `dist/capsules_api/` 目录，主程序是 `capsules_api.exe`。

### 步骤 2：集成到 Tauri Sidecar

1. 创建 sidecar 目录（如果不存在）：
   ```powershell
   mkdir ..\webapp\src-tauri\binaries -ErrorAction SilentlyContinue
   ```

2. 复制并重命名可执行文件（根据你的 CPU 架构选择）：
   ```powershell
   # 文件名格式：{name}-{target-triple}
   
   # Windows x64 (Intel/AMD):
   Copy-Item dist\capsules_api.exe ..\webapp\src-tauri\binaries\capsules_api-x86_64-pc-windows-msvc.exe
   
   # Windows ARM64 (如 Surface Pro X, Snapdragon 笔记本):
   Copy-Item dist\capsules_api.exe ..\webapp\src-tauri\binaries\capsules_api-aarch64-pc-windows-msvc.exe
   ```
   
   > **注意**：PyInstaller 输出的是单个 `capsules_api.exe` 文件（在 `dist/` 目录下），不是目录。

3. 确保 `tauri.conf.json` 中配置了 sidecar：
   ```json
   {
     "bundle": {
       "externalBin": ["binaries/capsules_api"]
     }
   }
   ```

### 步骤 3：构建 Tauri 应用

```powershell
cd webapp
npm run tauri build
```

**输出**：安装包位于 `src-tauri/target/release/bundle/`。

> **注意**：编译后的可执行文件仍需要 `--config-dir` 和 `--export-dir` 参数，这些由 Tauri Rust 代码自动传递。

### 步骤 4：生成 NSIS 安装程序（推荐分发方式）

NSIS 会生成**单个 .exe 安装程序**，用户双击即可安装，是最干净的分发方式。

1. 确保 `tauri.conf.json` 中配置了 NSIS：
   ```json
   {
     "bundle": {
       "active": true,
       "targets": ["nsis"],
       "externalBin": ["binaries/capsules_api"]
     }
   }
   ```

2. 执行打包：
   ```powershell
   cd webapp
   npm run tauri build
   ```

3. **输出文件**：
   ```
   webapp/src-tauri/target/release/bundle/nsis/
   └── Sound Capsule_1.0.0_x64-setup.exe   # 单个安装程序
   ```

### 打包格式对比

| 格式 | 配置 `targets` | 输出 | 用途 |
|------|---------------|------|------|
| **NSIS** | `["nsis"]` | `.exe` 安装程序 | ✅ 推荐分发 |
| **MSI** | `["msi"]` | `.msi` 安装包 | 企业部署 |
| **全部** | `"all"` | 所有格式 | 测试用 |

### 关于控制台窗口

- **开发模式** (`npm run tauri dev`)：显示 Python 后端控制台，方便调试
- **发布模式** (`npm run tauri build`)：自动隐藏控制台，只显示主窗口

---

## 更新日志

- **2026-01-18**: 
  - 添加 NSIS 安装程序打包说明，发布模式自动隐藏后端控制台窗口
  - 添加 ARM64 架构支持说明
  - 修复临时工程（未保存的 RPP）导出失败问题
  - 修复开发模式资源路径问题
- **2026-01-17**: 新增跨平台同步章节，完善常见问题：
  - 添加 Supabase 配置详细说明（SERVICE_ROLE_KEY）
  - 添加数据库 schema 更新后重置方法
  - 添加 REAPER 路径配置说明
  - 添加"从 Mac 同步代码到 Windows"章节
- **2026-01-16**: 完善文档：添加安装须知、PowerShell/CMD 双版本语法、依赖安装故障排查、sidecar 集成说明
- **2026-01-16**: 修复 API 启动参数说明，添加 supabase 依赖，更新启动脚本
- **2026-01-16**: 初始版本，支持 Windows 10/11 开发环境配置
