## 📖 1. 开发前言 (Preface)

### 项目愿景

Sound Capsule 不仅仅是一个本地音频管理工具，它正在演变为一个**去中心化的声音资产社交网络**。

- **任何用户**都可以上传自己的胶囊。
    
- **任何用户**都能看到、搜索并下载世界上其他用户创建的胶囊。
    
- **只有作者**拥有修改和删除自己胶囊的权限。
    
- **本地优先**：所有数据优先存储在本地 SQLite，通过后台静默同步实现“伪实时”的云端体验。
    

### 技术栈速览

- **核心逻辑 & API**: Python 3.9+ (Flask) - 处理复杂的本地文件、数据库和嵌入计算。
    
- **桌面壳**: Tauri (Rust) - 提供跨平台的原生能力（启动 Sidecar、文件关联、系统通知）。
    
- **前端**: React + Vite + Tailwind CSS - 现代化、响应式的 UI。
    
- **云端**: Supabase (PostgreSQL + Storage) - 处理鉴权、元数据同步和大文件存储。
    
- **AI**: Sentence-transformers - 本地/云端混合运行，计算语义向量。
    

---

## 🏗️ 2. 核心架构设计：开放世界模型 (Open World Architecture)

为了实现“查看所有人数据”但“保护写权限”，我们需要在三个层面进行架构调整。

### A. 数据库层：Supabase RLS (Row Level Security) 🛡️

这是最关键的安全防线。我们不再在 API 代码里写复杂的 `if user == owner` 判断，而是把规则下沉到数据库引擎。

- **SELECT (读取)**: 允许 `public` (所有认证用户) 读取 `cloud_capsules` 表的所有行。
    
- **INSERT/UPDATE/DELETE (写入)**: 仅允许 `auth.uid() == user_id` 的行被操作。
    
- **Storage (文件)**:
    
    - `Read`: Public (所有登录用户可下载)。
        
    - `Write`: Owner Only (只能上传到自己的文件夹)。
        

### B. 同步逻辑层：双轨制同步 (Dual-Track Sync) 🔄

目前的同步逻辑是“只同步我自己的”。现在需要改为：

1. **上行 (Push)**: 依然只上传“我”的数据。
    
2. **下行 (Pull)**:
    
    - **全量元数据**: 下载云端所有人的胶囊元数据 (JSON, Tags, Coordinates)。这部分数据很小（文本），可以全量存入本地 SQLite。
        
    - **按需资产**: **绝不**自动下载音频文件 (WAV)。只在用户点击时触发 JIT 下载。
        
    - **预览音频**: 策略可选。建议：_懒加载_ (在列表滚动到时下载) 或 _JIT_ (点击播放时流式传输)。
        

### C. 本地数据层：所有权标识 🏷️

本地 SQLite 的 `capsules` 表需要明确区分“我的”和“别人的”。

- 前端 UI 逻辑：
    
    - `is_mine = (local_user_id == capsule_owner_id)`
        
    - 如果 `is_mine` 为 `false` -> 禁用“编辑/删除”按钮，显示“作者：UserB”。
        

---

## 📅 3. 详细开发计划 (Phase G: Global Sync)

### 🚨 注意事项 (Pre-flight Checklist)

1. **性能陷阱**: 随着用户增加，云端可能有 10 万条胶囊。`SELECT *` 会很慢。
    
    - _解法_: 实现**增量同步 (Incremental Sync)**。本地记录 `last_sync_timestamp`，只拉取云端 `updated_at > last_sync` 的数据。
        
2. **文件路径地狱**: 如果 UserA 和 UserB 都有一个叫 `magic_sound` 的胶囊，下载到本地如何区分？
    
    - _解法_: 我们之前的命名规范 `{type}_{username}_{timestamp}` 已经完美解决了这个问题！保持住。
        
3. **大文件流量**: 预览音频 (.ogg) 虽然小，但量大也很恐怖。
    
    - _解法_: 使用 Supabase 的 CDN URL 直接播放，**不要下载预览文件到本地**，除非用户明确想离线使用。