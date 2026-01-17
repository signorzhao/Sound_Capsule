# Windows 版本打包指南

**日期**: 2026-01-12  
**目标**: 为 Windows 用户打包 Sound Capsule 应用程序

---

## 📋 前置要求

### 1. 开发环境要求

#### Windows 系统要求
- Windows 10/11 (64-bit)
- 至少 8GB RAM（推荐 16GB）
- 至少 10GB 可用磁盘空间

#### 必需软件
1. **Node.js** (v18+)
   ```bash
   # 下载: https://nodejs.org/
   node --version  # 验证安装
   ```

2. **Rust** (最新稳定版)
   ```bash
   # 下载: https://rustup.rs/
   rustc --version  # 验证安装
   ```

3. **Python 3.10+**
   ```bash
   # 下载: https://www.python.org/downloads/
   python --version  # 验证安装
   ```

4. **Microsoft Visual C++ Build Tools**
   - 下载: https://visualstudio.microsoft.com/visual-cpp-build-tools/
   - 安装 "Desktop development with C++" 工作负载

5. **WiX Toolset** (可选，用于创建安装程序)
   ```bash
   # 下载: https://wixtoolset.org/
   # 或使用 chocolatey: choco install wix
   ```

---

## 🚀 打包步骤

### 第一步：打包 Python Sidecar (后端 API)

#### 1.1 准备 Python 环境

```bash
# 进入后端目录
cd data-pipeline

# 创建虚拟环境（如果还没有）
python -m venv venv

# 激活虚拟环境
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat

# 安装依赖
pip install -r requirements.txt
pip install pyinstaller
```

#### 1.2 创建 PyInstaller Spec 文件（Windows 版本）

创建 `data-pipeline/capsules_api_windows.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None
current_dir = Path.cwd()

a = Analysis(
    ['capsule_api.py'],
    pathex=[],
    binaries=[],
    datas=[
        (str(current_dir / 'lua_scripts'), 'lua_scripts'),
        (str(current_dir / 'master_lexicon_v3.csv'), '.'),
    ],
    hiddenimports=[
        'sentence_transformers',
        'flask',
        'flask_cors',
        'torch',
        'transformers',
        'numpy',
        'pandas',
        'sklearn',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='capsules_api',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Windows: 保留控制台窗口用于调试
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'  # 可选：添加图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='capsules_api'
)
```

#### 1.3 执行打包

```bash
# 在 data-pipeline 目录下
pyinstaller capsules_api_windows.spec

# 输出文件会在 dist/capsules_api/ 目录
# 可执行文件: dist/capsules_api/capsules_api.exe
```

**预期结果**:
- ✅ `dist/capsules_api/capsules_api.exe` (~150-200 MB)
- ✅ 包含所有依赖 DLL 文件
- ✅ 包含 `lua_scripts` 和 `master_lexicon_v3.csv`

#### 1.4 测试 Sidecar

```bash
# 测试可执行文件
.\dist\capsules_api\capsules_api.exe --help

# 启动服务器
.\dist\capsules_api\capsules_api.exe --port 5002

# 在另一个终端测试
curl http://localhost:5002/api/capsules
```

---

### 第二步：打包 Tauri 应用 (前端)

#### 2.1 准备前端环境

```bash
# 进入前端目录
cd webapp

# 安装依赖
npm install

# 构建前端资源
npm run build
```

#### 2.2 配置 Tauri (Windows 特定)

检查 `webapp/src-tauri/tauri.conf.json`:

```json
{
  "$schema": "https://schema.tauri.app/config/2.0.0",
  "productName": "Sound Capsule",
  "version": "1.0.0",
  "identifier": "com.soundcapsule.app",
  "build": {
    "beforeBuildCommand": "npm run build",
    "frontendDist": "../dist"
  },
  "bundle": {
    "active": true,
    "targets": ["msi", "nsis"],  // Windows 安装程序格式
    "icon": [
      "icons/icon.ico"  // Windows 图标
    ],
    "windows": {
      "certificateThumbprint": null,  // 代码签名证书（可选）
      "digestAlgorithm": "sha256",
      "timestampUrl": ""
    }
  }
}
```

#### 2.3 配置 Sidecar 路径（Windows）

修改 `webapp/src-tauri/src/sidecar.rs` 中的路径处理：

```rust
// Windows 路径处理
#[cfg(target_os = "windows")]
fn get_sidecar_path() -> Result<PathBuf, String> {
    let exe_path = std::env::current_exe()
        .map_err(|e| format!("无法获取可执行文件路径: {}", e))?;
    
    let exe_dir = exe_path.parent()
        .ok_or("无法获取可执行文件目录")?;
    
    // Windows: 可执行文件在 exe 目录下
    let sidecar_path = exe_dir.join("capsules_api").join("capsules_api.exe");
    
    if !sidecar_path.exists() {
        return Err(format!("Sidecar 可执行文件不存在: {:?}", sidecar_path));
    }
    
    Ok(sidecar_path)
}
```

#### 2.4 构建 Tauri 应用

```bash
# 在 webapp 目录下
cd src-tauri

# 构建 Windows 版本
cargo tauri build --target x86_64-pc-windows-msvc

# 或者使用 npm 脚本
cd ..
npm run tauri build
```

**预期输出**:
- ✅ `webapp/src-tauri/target/release/sound-capsule.exe` (主应用)
- ✅ `webapp/src-tauri/target/release/bundle/msi/` (MSI 安装程序)
- ✅ `webapp/src-tauri/target/release/bundle/nsis/` (NSIS 安装程序)

---

### 第三步：组合打包（完整分发）

#### 3.1 创建分发目录结构

```bash
# 创建分发目录
mkdir -p dist/windows/SoundCapsule

# 目录结构:
# SoundCapsule/
#   ├── SoundCapsule.exe          # Tauri 主应用
#   ├── capsules_api/             # Python Sidecar
#   │   ├── capsules_api.exe
#   │   ├── *.dll                 # 依赖 DLL
#   │   ├── lua_scripts/
#   │   └── master_lexicon_v3.csv
#   └── README.txt                # 用户说明
```

#### 3.2 复制文件

```bash
# 复制 Tauri 应用
cp webapp/src-tauri/target/release/sound-capsule.exe dist/windows/SoundCapsule/SoundCapsule.exe

# 复制 Sidecar
cp -r data-pipeline/dist/capsules_api dist/windows/SoundCapsule/

# 创建 README
cat > dist/windows/SoundCapsule/README.txt << 'EOF'
Sound Capsule - 声音胶囊应用程序

安装说明:
1. 解压所有文件到任意目录（例如 C:\Program Files\SoundCapsule）
2. 双击 SoundCapsule.exe 启动应用
3. 首次运行会提示配置 REAPER 路径和导出目录

系统要求:
- Windows 10/11 (64-bit)
- 至少 4GB RAM
- 至少 2GB 可用磁盘空间

注意事项:
- 请勿删除 capsules_api 文件夹
- 首次启动可能需要 10-30 秒加载时间
- 如果遇到问题，请查看日志文件:
  %APPDATA%\com.soundcapsule.app\export_debug.log
EOF
```

#### 3.3 创建安装程序（可选）

##### 选项 A: 使用 NSIS（推荐）

创建 `installer.nsi`:

```nsis
!include "MUI2.nsh"

Name "Sound Capsule"
OutFile "SoundCapsule-Setup.exe"
InstallDir "$PROGRAMFILES\SoundCapsule"
RequestExecutionLevel admin

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

Section "MainSection" SEC01
    SetOutPath "$INSTDIR"
    File /r "SoundCapsule\*"
    
    # 创建开始菜单快捷方式
    CreateDirectory "$SMPROGRAMS\Sound Capsule"
    CreateShortCut "$SMPROGRAMS\Sound Capsule\Sound Capsule.lnk" "$INSTDIR\SoundCapsule.exe"
    CreateShortCut "$SMPROGRAMS\Sound Capsule\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    
    # 创建桌面快捷方式
    CreateShortCut "$DESKTOP\Sound Capsule.lnk" "$INSTDIR\SoundCapsule.exe"
    
    # 写入注册表（卸载信息）
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundCapsule" "DisplayName" "Sound Capsule"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundCapsule" "UninstallString" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
    RMDir /r "$INSTDIR"
    RMDir /r "$SMPROGRAMS\Sound Capsule"
    Delete "$DESKTOP\Sound Capsule.lnk"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundCapsule"
SectionEnd
```

编译安装程序:
```bash
makensis installer.nsi
```

##### 选项 B: 使用 WiX Toolset

创建 `installer.wxs`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Product Id="*" Name="Sound Capsule" Language="1033" Version="1.0.0" 
           Manufacturer="Sound Capsule" UpgradeCode="YOUR-GUID-HERE">
    <Package InstallerVersion="200" Compressed="yes" InstallScope="perMachine" />
    
    <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />
    <MediaTemplate />
    
    <Feature Id="ProductFeature" Title="Sound Capsule" Level="1">
      <ComponentGroupRef Id="ProductComponents" />
    </Feature>
  </Product>
  
  <Fragment>
    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="ProgramFilesFolder">
        <Directory Id="INSTALLFOLDER" Name="SoundCapsule" />
      </Directory>
    </Directory>
  </Fragment>
  
  <Fragment>
    <ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER">
      <Component Id="SoundCapsule.exe">
        <File Source="SoundCapsule.exe" />
      </Component>
      <!-- 添加其他文件 -->
    </ComponentGroup>
  </Fragment>
</Wix>
```

编译:
```bash
candle installer.wxs
light installer.wixobj
```

---

## 📦 最终分发文件

### 方案 1: 便携版（推荐用于测试）

```
SoundCapsule-Portable-v1.0.0.zip
├── SoundCapsule.exe
├── capsules_api/
│   └── ...
└── README.txt
```

**优点**:
- ✅ 无需安装，解压即用
- ✅ 适合快速测试和分发
- ✅ 用户可以直接运行

### 方案 2: 安装程序（推荐用于正式发布）

```
SoundCapsule-Setup-v1.0.0.exe
```

**优点**:
- ✅ 专业的分发方式
- ✅ 自动创建快捷方式
- ✅ 支持卸载
- ✅ 可以添加注册表项

---

## 🧪 测试清单

### 在干净的 Windows 系统上测试

- [ ] 解压/安装成功
- [ ] 首次启动正常（配置向导）
- [ ] Sidecar 自动启动
- [ ] API 服务器正常运行
- [ ] 前端界面正常显示
- [ ] 胶囊创建功能正常
- [ ] 导出功能正常
- [ ] REAPER 集成正常
- [ ] 日志文件正常生成
- [ ] 卸载功能正常（如果使用安装程序）

### 性能测试

- [ ] 启动时间 < 30 秒
- [ ] 内存占用 < 2GB
- [ ] CPU 使用率正常
- [ ] 文件大小合理（< 500MB 总大小）

---

## 🔧 常见问题

### Q1: 构建失败 - "找不到 MSVC"

**解决方案**:
```bash
# 安装 Visual Studio Build Tools
# 或使用 rustup 安装 MSVC 工具链
rustup toolchain install stable-x86_64-pc-windows-msvc
rustup default stable-x86_64-pc-windows-msvc
```

### Q2: PyInstaller 打包失败 - "缺少模块"

**解决方案**:
```bash
# 检查所有依赖是否安装
pip install -r requirements.txt

# 手动添加隐藏导入
# 在 spec 文件的 hiddenimports 中添加
```

### Q3: Tauri 构建失败 - "无法找到资源文件"

**解决方案**:
```bash
# 确保前端已构建
cd webapp
npm run build

# 检查 dist 目录是否存在
ls webapp/dist
```

### Q4: 运行时错误 - "找不到 DLL"

**解决方案**:
- 确保所有 DLL 文件都在 `capsules_api` 目录下
- 检查 PyInstaller 是否正确打包了所有依赖
- 尝试在目标机器上安装 Visual C++ Redistributable

---

## 📝 发布清单

### 发布前检查

- [ ] 版本号已更新（`tauri.conf.json`, `package.json`, `Cargo.toml`）
- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] 图标和资源文件正确
- [ ] 代码签名（可选，但推荐）
- [ ] 创建发布说明（CHANGELOG）

### 发布文件

1. **主安装程序**: `SoundCapsule-Setup-v1.0.0.exe`
2. **便携版**: `SoundCapsule-Portable-v1.0.0.zip`
3. **发布说明**: `RELEASE_NOTES.md`
4. **用户手册**: `USER_MANUAL.md`（可选）

---

## 🚀 自动化构建（可选）

### GitHub Actions 示例

创建 `.github/workflows/build-windows.yml`:

```yaml
name: Build Windows

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Setup Rust
        uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Build Python Sidecar
        run: |
          cd data-pipeline
          pip install -r requirements.txt pyinstaller
          pyinstaller capsules_api_windows.spec
      
      - name: Build Tauri App
        run: |
          cd webapp
          npm install
          npm run build
          cd src-tauri
          cargo tauri build --target x86_64-pc-windows-msvc
      
      - name: Upload Artifacts
        uses: actions/upload-artifact@v3
        with:
          name: windows-build
          path: webapp/src-tauri/target/release/bundle/
```

---

## 📚 相关文档

- [Tauri 官方文档 - Windows 打包](https://tauri.app/v1/guides/building/windows)
- [PyInstaller 官方文档](https://pyinstaller.org/)
- [NSIS 文档](https://nsis.sourceforge.io/Docs/)
- [WiX Toolset 文档](https://wixtoolset.org/documentation/)

---

**最后更新**: 2026-01-12  
**维护者**: Sound Capsule 开发团队
