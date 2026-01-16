### 🚀 项目概况

Sound Capsule 是一个基于 **Tauri (Rust) + React** 和 **Python Sidecar** 的混合架构应用。

- **前端** 负责展示和轻交互。
    
- **Python 后端** 是真正的大脑，负责数据库 (SQLite)、AI 计算和文件操作。
    
- **Tauri** 负责操作系统层面的交互。
    

### ⚠️ 核心原则 (黄金法则)

1. **永远不要阻塞 UI 线程**：所有的下载、同步、AI 计算必须在 Python 后台线程或异步任务中完成。
    
2. **本地数据库是单一真实源 (Source of Truth)**：前端只渲染本地 SQLite 的数据。云端数据必须先同步到本地 SQLite，才能被前端显示。
    
3. **文件完整性**：如果数据库显示 `asset_status='synced'`，那么磁盘上 **必须** 真的有那个 WAV 文件。不要欺骗用户。
    

### 🛠️ 调试技巧

- **后端日志**: 只要运行 `npm run tauri dev`，Python 的日志会输出在终端。关注 `[SYNC]` 和 `[DOWNLOAD]` 开头的日志。
    
- **数据库查看**: 使用 DBeaver 或类似工具打开 `data-pipeline/capsules.db`，这是理解数据流最快的方式。
    
- **模拟多用户**: 你可以在 Supabase 控制台手动修改某行数据的 `user_id`，然后在本地刷新同步，看看是否能把“别人的”数据拉下来。

### 📅 开发路线建议

建议按照 **Step 1 (数据库权限) -> Step 2 (后端同步) -> Step 4 (前端展示) -> Step 3 (JIT 下载)** 的顺序开发。先让数据跑通，再优化下载体验。