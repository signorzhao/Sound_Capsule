# 查看 GitHub Actions 测试结果指南

## 方法 1: GitHub 网页（最简单）

### 步骤：

1. **打开仓库**
   ```
   https://github.com/signorzhao/Sound_Capsule
   ```

2. **进入 Actions 页面**
   - 点击仓库顶部的 "Actions" 标签

3. **选择工作流**
   - 在左侧选择 "Build and Test Windows"

4. **查看运行历史**
   - 点击最新的运行（绿色 ✓ 表示成功，红色 ✗ 表示失败）

5. **查看详细输出**
   - 点击每个步骤查看输出
   - 重要步骤：
     - ✅ **Test Application - Extract**: 查看解压后的文件结构
     - ✅ **Test Application - Check Files**: 查看文件是否找到
     - ✅ **Test Application - Run with Timeout**: 查看应用是否运行
     - ✅ **Test Application - Check Logs**: 查看应用日志和错误

6. **下载测试结果**
   - 滚动到页面底部
   - 在 "Artifacts" 部分下载：
     - `Test-Results-{数字}`: 包含测试文件、截图
     - `App-Log-{数字}`: 应用日志文件（如果存在）
     - `SoundCapsule-Windows-Portable`: 构建产物 ZIP

---

## 方法 2: GitHub CLI（命令行）

### 安装 GitHub CLI

```bash
# macOS
brew install gh

# 或从官网下载
# https://cli.github.com/
```

### 登录

```bash
gh auth login
```

### 查看运行列表

```bash
# 进入项目目录
cd /Users/ianzhao/Desktop/Sound_Capsule/synesth

# 查看最近的运行
gh run list --workflow="Build and Test Windows"

# 输出示例：
# STATUS  TITLE                    WORKFLOW                  BRANCH  EVENT         ID        ELAPSED  AGE
# ✓       Build and Test Windows   Build and Test Windows    main    push          12345678  15m      2h
```

### 查看特定运行的输出

```bash
# 查看最新运行的输出
gh run view --log

# 查看特定运行 ID 的输出
gh run view 12345678 --log

# 只查看失败的步骤
gh run view --log | grep -A 20 "✗"
```

### 下载 Artifacts

```bash
# 下载最新运行的所有 Artifacts
gh run download

# 下载特定运行 ID 的 Artifacts
gh run download 12345678

# 下载特定名称的 Artifact
gh run download --name "Test-Results-123"
```

---

## 方法 3: 直接访问 URL

### 工作流页面
```
https://github.com/signorzhao/Sound_Capsule/actions/workflows/build-and-test-windows.yml
```

### 特定运行页面
```
https://github.com/signorzhao/Sound_Capsule/actions/runs/{RUN_ID}
```

将 `{RUN_ID}` 替换为实际的运行 ID（从运行列表获取）

---

## 如何解读测试结果

### ✅ 成功的标志

1. **所有步骤都是绿色 ✓**
2. **"Test Application - Check Files" 显示**：
   ```
   ✓ SoundCapsule.exe 找到: ...
   ✓ capsules_api.exe 找到: ...
   ```
3. **"Test Application - Run with Timeout" 显示**：
   ```
   应用已启动，PID: ...
   运行中... (2/30 秒)
   运行中... (4/30 秒)
   ...
   应用仍在运行，正常结束进程...
   ```
4. **"Test Application - Check Logs" 显示**：
   ```
   ✓ 日志文件存在
   ✓ 未发现明显错误
   ```

### ❌ 失败的标志

1. **红色 ✗ 标记的步骤**
2. **常见错误**：
   - `✗ SoundCapsule.exe 未找到` → 构建失败或文件路径错误
   - `应用已退出（运行了 X 秒）` → 应用闪退
   - `日志文件不存在` → 应用未启动或崩溃
   - `发现错误信息` → 查看具体错误内容

### 📊 关键信息位置

1. **文件结构**：查看 "Test Application - Extract" 步骤
2. **文件检查**：查看 "Test Application - Check Files" 步骤
3. **运行状态**：查看 "Test Application - Run with Timeout" 步骤
4. **错误信息**：查看 "Test Application - Check Logs" 步骤
5. **系统错误**：查看 "Test Application - Check Windows Event Log" 步骤

---

## 下载和查看 Artifacts

### 在网页上下载

1. 进入运行页面
2. 滚动到底部
3. 点击 Artifact 名称下载 ZIP 文件
4. 解压后查看：
   - `test-extract/`: 解压后的应用文件
   - `test-screenshot.png`: 截图（如果成功）
   - `export_debug.log`: 应用日志（如果存在）

### 使用 GitHub CLI 下载

```bash
# 下载所有 Artifacts
gh run download

# 下载后查看
cd artifacts
unzip Test-Results-*.zip
cat export_debug.log  # 查看日志
```

---

## 快速诊断命令

### 查看最近的失败运行

```bash
gh run list --workflow="Build and Test Windows" --status failure --limit 5
```

### 查看特定步骤的输出

```bash
gh run view --log | grep -A 50 "Test Application - Check Logs"
```

### 查看错误信息

```bash
gh run view --log | grep -i "error\|失败\|异常"
```

---

## 提示

1. **Artifacts 保留时间**：
   - Test-Results: 7 天
   - App-Log: 7 天
   - Build Artifact: 30 天

2. **如果测试失败**：
   - 先查看 "Test Application - Check Logs" 步骤
   - 下载 App-Log Artifact 查看详细日志
   - 检查 Windows Event Log 步骤的系统错误

3. **截图可能为空**：
   - GitHub Actions 的 Windows 环境可能无法捕获窗口
   - 主要依赖日志分析

4. **重新运行测试**：
   - 在运行页面点击 "Re-run all jobs"
   - 或手动触发工作流
