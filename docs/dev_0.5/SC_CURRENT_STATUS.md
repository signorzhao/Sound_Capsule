🛠️ Sound Capsule 核心架构与同步机制备忘录 (v0.5.2)
最后更新: 2026-01-15 核心变更: 完善了动静分离架构，解决了重复数据问题，新增了细粒度的音频上传状态管理。

1. 🏛️ 核心架构决策 (Architecture Decisions)
A. 动静分离存储 (Dynamic-Static Separation)
静态数据 (Immutable) → Storage:

内容: metadata.json (BPM, Plugins, Waveform), .rpp, .ogg, Audio/WAVs。

原则: 生成后不再修改，通过覆盖上传更新。

动态数据 (Mutable) → Database:

内容: capsule_tags (Tags), 描述, 评分。

原则: 以数据库为“唯一真理源”，频繁读写。

B. 文件命名规范 (Naming Convention)
强制标准: 所有上传文件必须使用动态名称 {capsule_name}.ext。

Audio 源文件: 保持原始文件名，存储在 Audio/ 子目录下。

2. ⚡️ 关键同步逻辑 (Sync Logic)
A. 原子化上传 (Atomic Upload)
流程: 数据库写入 -> OGG -> RPP -> Metadata -> Audio Files。

原则: 只有当所有文件（含 Audio 文件夹）都上传成功，才将本地状态标记为 synced。

B. 智能去重策略 (De-duplication Strategy) - New
问题: 曾出现同名胶囊重复插入数据库的情况。

解决:

上传时: 按 name + file_path 分组，自动保留一条，删除多余记录。

下载时: 采用多级匹配策略 (cloud_id > uuid > name + file_path)，匹配到任意一项则视为已存在，执行 Update 而非 Insert。

C. 状态双重校验 (Dual State Tracking) - New
为了解决“元数据已同步但音频没传完”的 UI 歧义，引入新状态字段：

cloud_status: 仅代表元数据是否同步 (Synced/Local/Remote)。

audio_uploaded: (Boolean) 仅代表 Audio 源文件 是否已完整上传。

UI 表现: 若 cloud_status=synced 但 audio_uploaded=false，云图标仍显示为“需上传”状态。

3. 🖥️ 交互与反馈优化 (UX/UI Refinements) - New
实时进度反馈:

前端轮询 /api/sync/upload-progress。

后端缓存上传进度（当前文件/总进度），解决大文件上传时的“假死”现象。

即时刷新 (Instant Refresh):

上传/同步结束后，前端直接调用 loadCapsules() 重绘界面，无需切换页面或重启。

Toast 优化:

适配 207 Multi-Status 响应，防止部分成功部分失败导致提示框卡死。

4. ⚙️ 底层并发优化 (Concurrency)
SQLite WAL 模式: 开启 Write-Ahead Logging，彻底解决高频操作下的 database is locked。

Timeout: 数据库连接超时设定增加至 30s。

5. ⚠️ 遗留问题与待办 (Backlog)
历史数据清洗 (Data Migration):

部分旧胶囊虽然文件在云端，但本地 audio_uploaded 字段仍为 0。

Action: 需要编写脚本，通过检查云端 Audio/ 文件夹是否存在，批量回填此字段。

Owner ID 缺失:

同步日志偶尔报 没有 owner_id，跳过下载。

Action: 需在同步逻辑中增加兜底，若本地缺失，强制从云端 Capsule 记录回填。

Tags 端到端验证:

代码层面已修复 sqlite3.Row 错误，需进行多用户 Tags 修改同步测试。

🔧 涉及核心文件 (Modified Files)
Backend: sync_service.py (核心逻辑), routes/sync_routes.py (API入口), capsule_db.py (WAL模式).

Frontend: CapsuleLibrary.jsx (UI逻辑), CloudSyncIcon.jsx (新状态图标).

1月17日修复内容
主要修复:
1. 关键词同步: 顶部同步时同步 capsule_tags + metadata.keywords
2. 关键词聚合: 所有标签更新路径都会自动聚合到 capsules.keywords
3. 胶囊匹配: 使用多级匹配策略 (cloud_id -> name) 防止切换文件夹后重复
4. 状态检测: 创建胶囊时自动检测本地文件设置 asset_status
5. audio_uploaded: 从云端同步或本地扫描时正确设置状态
6. RPP 文件: 修复 rpp_file 为空导致的打开失败问题
7. UI 刷新: 下载/上传完成后自动刷新胶囊状态

修改文件:
- capsule_api.py: 增加 rpp_file 空值处理
- capsule_scanner.py: 本地扫描时设置 audio_uploaded
- supabase_client.py: 多级匹配防止重复上传
- sync_service.py: 完善云端同步逻辑和状态设置
- CapsuleLibrary.jsx: 操作完成后清除缓存并刷新

1. main_export2_windows.lua - Windows 导出脚本
媒体文件处理：
修复了 CopyFile 函数，使用 Lua 原生 io 库复制文件（替代不可靠的 os.execute）
增加了详细的调试输出
轨道清理：
添加了依赖追踪逻辑，只保留相关轨道（Item 所在轨道、父级轨道、Send 目标轨道）
删除不相关的 TRACK 块和未选中的 ITEM 块
渲染设置修复：
整合所有渲染参数到一个块，一次性写入 RPP
RENDER_FILE = 目录路径
RENDER_PATTERN = 文件名
RENDER_RANGE 2 startTime endTime 0 1000 = 按选中 items 时间范围渲染
RENDER_CFG = OGG 编码器配置
metadata.json：
添加了 UUID 生成
改用 "id" 字段（与 Mac 版保持一致）
2. capsule_scanner.py - Python 后端
修复 UUID 读取：metadata.get('uuid') or metadata.get('id')，兼容两种格式
3. reaper_webui_export.py - Python 后端
移除基于时间戳的"旧文件"检测逻辑
改用文件大小稳定性检测
4. auto_export_from_config_windows.lua - 入口脚本
改进了 main() 返回值处理和调试输出
⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ 
待改进方向
1. 同步冲突处理
当前策略：本地优先（如果本地有标签就上传，只有本地没有才下载）
改进方向：基于时间戳的冲突检测，允许用户选择保留哪个版本
2. 增量同步
当前：每次同步都检查所有胶囊
改进方向：只同步有 pending 状态的胶囊，减少 API 调用
3. metadata.keywords 冗余
现状：云端同时存储 cloud_capsule_tags 和 metadata.keywords
改进方向：考虑废弃 metadata.keywords，只使用 cloud_capsule_tags 作为权威来源
4. 离线支持
当前：需要网络连接才能同步
改进方向：完善离线队列，网络恢复后自动同步
5. 性能优化
当前：启动同步检查所有胶囊的所有文件
改进方向：本地缓存文件哈希，只检查变更
⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ 