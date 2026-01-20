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

---

## 1月18日修复内容 - Windows 胶囊导出完善

### 主要修复:

**1. RPP 渲染设置修复 (main_export2_windows.lua)**
- `RENDER_RANGE 1` → `RENDER_RANGE 2`：使用时间选择模式
- `<RENDER_CFG>` 块移到 `SAMPLERATE` 行后面（REAPER 的正确位置）
- 删除旧的 `<RENDER_CFG>` 块避免格式冲突
- 正确设置 `SELECTION` 和 `SELECTION2` 字段定义渲染时间范围

**2. metadata.json 格式兼容 (capsule_scanner.py)**
- 修改字段读取逻辑，同时兼容两种格式：
  - Windows 版：`preview_audio` / `rpp_file`（顶层字段）
  - Mac 版：`files.preview` / `files.project`（嵌套字段）
- 修复了预览音频无法播放的 404 错误

**3. 正则表达式修复**
- 修复删除 `<RENDER_CFG>` 块时的正则表达式，避免误删 `<TEMPOENVEX>` 等其他块

### 修改文件:
- `data-pipeline/lua_scripts/main_export2_windows.lua`：RPP 渲染参数和格式
- `data-pipeline/capsule_scanner.py`：metadata.json 字段兼容

### 当前状态:
✅ Windows 胶囊导出功能完整可用
✅ OGG 预览音频正确渲染（时间范围正确）
✅ 预览音频可在界面中播放
✅ 胶囊库和棱镜关键词页面功能正常



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
6. ✅ 棱镜全局共享 (Prism Global Sync) - 已实现临时方案
当前实现（2026-01-20）：
   - 使用管理员账户 (ian@ian.com) 作为唯一棱镜数据源
   - 所有用户下载时，强制下载管理员的棱镜（dal_cloud_prisms.py: ADMIN_USER_ID）
   - 只有管理员可以上传棱镜，其他用户的上传请求被静默忽略
   - 棱镜启用/禁用状态通过 anchor_config_v2.json 打包分发
遗留问题：
   - ⚠️ 棱镜启用状态 (active) 目前存储在本地配置文件中，不通过云端同步
   - 如果管理员在锚点编辑器中禁用某个棱镜，需要重新编译分发才能生效
   - 未来可考虑将 active 状态加入 cloud_prisms 表，实现实时同步

7. 🆕 棱镜启用状态云端同步 (Prism Active State Sync)
当前状态：使用本地配置文件 anchor_config_v2.json 管理启用/禁用
问题：管理员禁用棱镜后，需要重新编译才能对用户生效
改进方案：
   - 在 cloud_prisms 表添加 is_active 字段
   - 上传棱镜时同步 active 状态
   - 下载棱镜时读取 active 状态并应用
   - 本地 anchor_config_v2.json 仅作为用户个人偏好（可选覆盖）
优先级：中（当前通过编译分发可解决，但不够灵活）

8. 🆕 空间查询优化 (Capsule Coordinates Sync)
当前状态：预留功能，尚未启用
相关表结构：
   - 本地表 `capsule_coordinates`：存储胶囊在各棱镜的聚合坐标 (texture_x/y, source_x/y 等)
   - 云端表 `cloud_capsule_coordinates`：已创建但未使用
功能说明：
   - 用于加速"查找附近胶囊"的空间查询
   - 一个胶囊可能有多个标签，需要计算平均坐标作为"位置"
   - 避免每次查询都重新计算，提升性能
开发计划：
   1. 在保存标签时自动计算并更新本地 capsule_coordinates
   2. 在同步时上传/下载坐标数据到 cloud_capsule_coordinates
   3. 实现基于坐标的空间搜索 API (如：查找某棱镜坐标附近的胶囊)
优先级：低（当前标签查询性能足够，胶囊数量不多时无需优化）
⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ ⚠️ 