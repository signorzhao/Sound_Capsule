# Sound Capsule Windows 开发环境配置指南

本指南帮助你在 Windows 上搭建 Sound Capsule 的开发环境。

---

## 系统要求

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| Windows | 10/11 (64-bit) | 需要 WebView2 Runtime |
| Node.js | 18+ LTS | 推荐使用 nvm-windows 管理 |
| Python | 3.10+ | 推荐 3.11 |
| Rust | 最新稳定版 | 通过 rustup 安装 |
| Visual Studio Build Tools | 2019+ | 需要 C++ 桌面开发工作负载 |

---

## 一、安装基础依赖

### 1. 安装 Node.js

推荐使用 [nvm-windows](https://github.com/coreybutler/nvm-windows) 管理 Node 版本：

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

这是编译 Tauri 原生模块的必要依赖。

### 5. 检查 WebView2

Windows 10/11 通常已预装 WebView2 Runtime。如果没有，从 [Microsoft](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) 下载。

---

## 二、项目配置

### 1. 克隆项目

```powershell
git clone <repository-url>
cd synesth
```

### 2. 配置后端 (Python)

```powershell
cd data-pipeline

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置前端 (Node.js + Tauri)

```powershell
cd webapp

# 安装 npm 依赖
npm install

# 安装 Tauri CLI（如果尚未安装）
npm install -g @tauri-apps/cli
```

### 4. 编译 Windows Sidecar（可选但推荐）

如果需要打包分发，需要编译 Python 后端为 Windows 可执行文件：

```powershell
cd data-pipeline

# 激活虚拟环境
.\venv\Scripts\activate

# 安装 PyInstaller
pip install pyinstaller

# 编译
pyinstaller capsules_api.spec

# 复制到 binaries 目录
copy dist\capsules_api\capsules_api.exe ..\webapp\src-tauri\binaries\capsules_api-x86_64-pc-windows-msvc.exe
```

---

## 三、启动开发环境

### 方式一：使用启动脚本（推荐）

双击项目根目录的 `start-all.bat`，会自动：
1. 启动后端 API 服务器（端口 5002）
2. 启动 Tauri 前端开发服务器

### 方式二：手动启动

**终端 1 - 后端**：
```powershell
cd data-pipeline
.\venv\Scripts\activate
python capsule_api.py
```

**终端 2 - 前端**：
```powershell
cd webapp
npm run tauri dev
```

---

## 四、常见问题

### Q: `npm run tauri dev` 报错 "linker 'link.exe' not found"

**A**: 需要安装 Visual Studio Build Tools 的 C++ 工作负载。

### Q: Python 依赖安装失败

**A**: 某些包（如 `sentence-transformers`）需要 C++ 编译器。确保已安装 Visual Studio Build Tools。

### Q: WebView2 相关错误

**A**: 从 Microsoft 官网重新安装 WebView2 Runtime。

### Q: 后端 API 端口被占用

**A**: 检查是否有其他进程占用 5002 端口：
```powershell
netstat -ano | findstr :5002
```

### Q: 数据库锁定错误

**A**: 确保没有其他进程正在访问 `capsules.db`，或等待几秒后重试。

---

## 五、目录结构

```
synesth/
├── data-pipeline/          # Python 后端
│   ├── venv/               # Python 虚拟环境（不提交）
│   ├── database/           # SQLite 数据库（不提交）
│   ├── routes/             # API 路由模块
│   │   ├── library_routes.py
│   │   └── sync_routes.py
│   ├── capsule_api.py      # API 入口
│   └── requirements.txt    # Python 依赖
│
├── webapp/                 # 前端 + Tauri
│   ├── src/                # React 源码
│   ├── src-tauri/          # Tauri/Rust 源码
│   │   └── binaries/       # Sidecar 可执行文件
│   └── package.json
│
├── start-all.bat           # Windows 一键启动
├── start-all.sh            # macOS/Linux 一键启动
└── docs/
    └── WINDOWS_SETUP.md    # 本文档
```

---

## 六、环境变量（可选）

创建 `data-pipeline/.env` 文件配置 Supabase 云同步：

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

---

## 更新日志

- **2026-01-16**: 初始版本，支持 Windows 10/11 开发环境配置
