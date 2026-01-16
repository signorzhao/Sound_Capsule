-- ============================================================================
-- Phase B: 混合存储策略 - 数据库迁移脚本
-- ============================================================================
--
-- 目的：在不破坏现有 Phase A 功能的基础上，添加 Phase B 所需字段
--
-- 设计原则：
-- 1. cloud_status 管理 元数据（Row Data）的同步状态
-- 2. asset_status 管理 物理文件（WAV/RPP）的存储位置
-- 3. 两者分离，互不干扰
--
-- 使用方法：
--   sqlite3 capsules.db < mix_storage_schema.sql
--
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. 为 capsules 表添加资产状态字段
-- ----------------------------------------------------------------------------

-- 资产状态（asset_status）：标识物理文件的存储位置
-- 'local' - 文件在本地（旧数据的默认值）
-- 'cloud_only' - 仅元数据在本地，文件在云端
-- 'downloading' - 正在从云端下载文件
-- 'cached' - 文件已从云端下载并缓存到本地
ALTER TABLE capsules ADD COLUMN asset_status TEXT DEFAULT 'local';

-- 音频是否已上传（本地有 Audio 但云端可能缺失）
ALTER TABLE capsules ADD COLUMN audio_uploaded BOOLEAN DEFAULT 0;

-- 本地 WAV 文件路径（绝对路径）
-- 用于断点续传和缓存检查
ALTER TABLE capsules ADD COLUMN local_wav_path TEXT;

-- 本地 WAV 文件大小（字节）
-- 用于校验文件完整性
ALTER TABLE capsules ADD COLUMN local_wav_size INTEGER;

-- 本地 WAV 文件哈希（SHA256）
-- 用于断点续传校验和去重
ALTER TABLE capsules ADD COLUMN local_wav_hash TEXT;

-- 下载进度（0-100）
-- 实时下载进度百分比
ALTER TABLE capsules ADD COLUMN download_progress INTEGER DEFAULT 0;

-- 下载开始时间
ALTER TABLE capsules ADD COLUMN download_started_at TIMESTAMP;

-- 预览音频是否已下载（从云端）
ALTER TABLE capsules ADD COLUMN preview_downloaded BOOLEAN DEFAULT 0;

-- 最后访问时间（用于 LRU 缓存清理）
ALTER TABLE capsules ADD COLUMN asset_last_accessed_at TIMESTAMP;

-- 访问次数（用于 LRU 缓存清理）
ALTER TABLE capsules ADD COLUMN asset_access_count INTEGER DEFAULT 0;

-- 用户是否固定缓存（不会被自动清理）
ALTER TABLE capsules ADD COLUMN is_cache_pinned BOOLEAN DEFAULT 0;

-- ----------------------------------------------------------------------------
-- 2. 创建下载任务队列表
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS download_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 关联的胶囊
    capsule_id INTEGER NOT NULL,

    -- 文件类型
    file_type TEXT NOT NULL,  -- 'preview', 'wav', 'rpp', 'audio_folder'

    -- 任务状态
    status TEXT NOT NULL,     -- 'pending', 'downloading', 'completed', 'failed', 'paused', 'cancelled'

    -- 远程文件信息
    remote_url TEXT NOT NULL,
    remote_size INTEGER,      -- 远程文件总大小（字节）
    remote_hash TEXT,         -- 远程文件哈希（用于校验）

    -- 本地文件信息
    local_path TEXT NOT NULL,
    local_size INTEGER,       -- 已下载的文件大小（字节）
    local_hash TEXT,          -- 本地文件哈希

    -- 进度信息
    progress INTEGER DEFAULT 0,  -- 进度百分比（0-100）
    downloaded_bytes INTEGER DEFAULT 0,  -- 已下载字节数
    speed INTEGER DEFAULT 0,          -- 当前下载速度（字节/秒）
    eta_seconds INTEGER,              -- 预计剩余时间（秒）

    -- 断点续传支持
    etag TEXT,                -- HTTP ETag
    last_modified TEXT,       -- HTTP Last-Modified
    range_start INTEGER DEFAULT 0,  -- 断点续传起始位置
    range_end INTEGER,         -- 断点续传结束位置

    -- 错误处理
    error_message TEXT,
    error_code TEXT,          -- 错误代码（便于分类处理）
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- 优先级（0-10，数字越大优先级越高）
    priority INTEGER DEFAULT 0,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE
);

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_download_tasks_status ON download_tasks(status);
CREATE INDEX IF NOT EXISTS idx_download_tasks_capsule_id ON download_tasks(capsule_id);
CREATE INDEX IF NOT EXISTS idx_download_tasks_priority ON download_tasks(priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_download_tasks_created_at ON download_tasks(created_at DESC);

-- ----------------------------------------------------------------------------
-- 3. 创建本地缓存管理表（local_cache）
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS local_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 关联的胶囊
    capsule_id INTEGER NOT NULL,

    -- 文件类型
    file_type TEXT NOT NULL,  -- 'preview', 'wav', 'rpp', 'audio_folder'

    -- 文件信息
    file_path TEXT NOT NULL,  -- 本地绝对路径
    file_size INTEGER,        -- 文件大小（字节）
    file_hash TEXT,           -- 文件哈希（SHA256）

    -- 访问统计（用于 LRU 缓存清理）
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,

    -- 缓存策略
    is_pinned BOOLEAN DEFAULT 0,     -- 用户固定缓存（不会被清理）
    cache_priority INTEGER DEFAULT 0,  -- 缓存优先级（0-10，数字越大越重要）

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束和唯一性约束
    FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE,
    UNIQUE(capsule_id, file_type)
);

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_local_cache_accessed_at ON local_cache(last_accessed_at ASC);
CREATE INDEX IF NOT EXISTS idx_local_cache_priority ON local_cache(cache_priority DESC, last_accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_local_cache_pinned ON local_cache(is_pinned, cache_priority DESC);

-- ----------------------------------------------------------------------------
-- 4. 数据迁移：更新现有数据
-- ----------------------------------------------------------------------------

-- 4.1 为现有的胶囊设置默认 asset_status
-- 假设旧数据的文件都在本地，因此设置为 'local'
UPDATE capsules
SET asset_status = 'local',
    asset_last_accessed_at = updated_at
WHERE asset_status IS NULL OR asset_status = 'unknown';

-- 4.2 为现有的本地文件扫描并填充缓存表
-- 注意：这里需要根据实际的导出目录来调整路径
-- 下面的 SQL 是一个示例，实际执行时需要修改为正确的路径

-- 假设导出目录在 /Users/ianzhao/Documents/testout
-- 每个胶囊的文件夹名为 capsules.file_path
-- WAV 文件通常在 Audio/ 子文件夹中

-- 由于 SQLite 不支持直接扫描文件系统，
-- 我们需要通过应用代码来完成本地文件的扫描和缓存表的填充
-- 这里创建一个临时表来标记需要扫描的胶囊

CREATE TABLE IF NOT EXISTS _pending_cache_scan (
    capsule_id INTEGER PRIMARY KEY,
    file_path TEXT,
    needs_scan BOOLEAN DEFAULT 1
);

-- 插入所有需要扫描的胶囊（只有本地文件存在且尚未缓存记录的）
INSERT OR IGNORE INTO _pending_cache_scan (capsule_id, file_path, needs_scan)
SELECT id, file_path, 1
FROM capsules
WHERE cloud_status = 'local'
  AND file_path IS NOT NULL
  AND asset_status = 'local'
  AND id NOT IN (SELECT capsule_id FROM local_cache WHERE file_type = 'wav');

-- 创建一个触发器：当新的下载任务完成时，自动更新胶囊的 asset_status
CREATE TRIGGER IF NOT EXISTS update_asset_on_download_complete
AFTER UPDATE ON download_tasks
WHEN NEW.status = 'completed' AND OLD.status != 'completed'
BEGIN
    -- 更新胶囊的资产状态为已缓存
    UPDATE capsules
    SET asset_status = 'cached',
        download_progress = 100,
        download_started_at = NULL,
        asset_last_accessed_at = CURRENT_TIMESTAMP
    WHERE id = NEW.capsule_id;

    -- 插入或更新缓存记录
    INSERT OR REPLACE INTO local_cache
    (capsule_id, file_type, file_path, file_size, file_hash,
     last_accessed_at, access_count, is_pinned, cache_priority, updated_at)
    VALUES
    (NEW.capsule_id, NEW.file_type, NEW.local_path, NEW.local_size, NEW.local_hash,
     CURRENT_TIMESTAMP, 1, 0, 0, CURRENT_TIMESTAMP);
END;

-- 创建一个触发器：当删除下载任务时，清理已下载的部分文件
CREATE TRIGGER IF NOT EXISTS cleanup_partial_download_on_delete
AFTER DELETE ON download_tasks
WHEN OLD.status = 'downloading' OR OLD.status = 'paused'
BEGIN
    -- 这里可以添加清理逻辑，但为了安全起见，暂时只记录日志
    -- 实际的文件清理应该由应用代码来完成
    SELECT 'Partial download task deleted, cleanup needed' AS log_message;
END;

-- ----------------------------------------------------------------------------
-- 5. 创建视图以简化常用查询
-- ----------------------------------------------------------------------------

-- 视图：胶囊资产状态摘要
CREATE VIEW IF NOT EXISTS capsule_asset_summary AS
SELECT
    c.id,
    c.name,
    c.file_path,
    c.asset_status,
    c.cloud_status,

    -- 本地 WAV 文件信息
    c.local_wav_path,
    c.local_wav_size,
    c.local_wav_hash,

    -- 下载进度
    c.download_progress,
    c.download_started_at,

    -- 预览音频状态
    c.preview_downloaded,

    -- 缓存统计
    c.asset_last_accessed_at,
    c.asset_access_count,
    c.is_cache_pinned,

    -- 下载任务信息（如果有正在进行的下载）
    dt.id as download_task_id,
    dt.status as download_status,
    dt.progress as download_task_progress,
    dt.speed as download_speed,
    dt.eta_seconds as download_eta,

    -- 云端文件信息
    (SELECT COUNT(*) FROM download_tasks WHERE capsule_id = c.id AND status = 'completed') as cached_files_count,
    (SELECT COUNT(*) FROM local_cache WHERE capsule_id = c.id) as total_cached_files

FROM capsules c
LEFT JOIN download_tasks dt ON c.id = dt.capsule_id AND dt.status IN ('pending', 'downloading', 'paused');

-- 视图：下载队列状态
CREATE VIEW IF NOT EXISTS download_queue_status AS
SELECT
    COUNT(*) as total_tasks,
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
    SUM(CASE WHEN status = 'downloading' THEN 1 ELSE 0 END) as downloading_count,
    SUM(CASE WHEN status = 'paused' THEN 1 ELSE 0 END) as paused_count,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
    SUM(downloaded_bytes) as total_downloaded_bytes,
    SUM(remote_size) as total_remote_bytes,
    CAST(SUM(downloaded_bytes) AS FLOAT) / NULLIF(SUM(remote_size), 0) * 100 as overall_progress
FROM download_tasks;

-- 视图：缓存统计
CREATE VIEW IF NOT EXISTS cache_stats AS
SELECT
    COUNT(*) as total_cached_files,
    SUM(file_size) as total_cache_size,
    AVG(access_count) as avg_access_count,
    COUNT(CASE WHEN is_pinned = 1 THEN 1 END) as pinned_files_count,
    SUM(file_size) FILTER (WHERE is_pinned = 1) as pinned_files_size
FROM local_cache;

-- ----------------------------------------------------------------------------
-- 6. 创建辅助函数（SQLite 3.35.0+ 支持）
-- ----------------------------------------------------------------------------

-- 如果 SQLite 版本支持自定义函数，可以创建以下函数
-- 注意：这些函数需要在应用代码中注册

-- 示例：格式化文件大小
-- CREATE OR REPLACE FUNCTION format_file_size(bytes INTEGER)
-- RETURNS TEXT AS
-- SELECT
--     CASE
--         WHEN bytes < 1024 THEN bytes || ' B'
--         WHEN bytes < 1024*1024 THEN (bytes / 1024) || ' KB'
--         WHEN bytes < 1024*1024*1024 THEN (bytes / (1024*1024)) || ' MB'
--         ELSE (bytes / (1024*1024*1024)) || ' GB'
--     END;

-- 示例：计算缓存清理策略
-- CREATE OR REPLACE FUNCTION should_purge_cache(
--     capsule_id INTEGER,
--     max_cache_size INTEGER,
--     current_cache_size INTEGER
-- )
-- RETURNS INTEGER AS
-- SELECT
--     CASE
--         WHEN is_pinned = 1 THEN 0  -- 不清理固定缓存
--         WHEN current_cache_size > max_cache_size THEN 1  -- 缓存超限，建议清理
--         ELSE 0
--     END
-- FROM local_cache
-- WHERE capsule_id = capsule_id;

-- ============================================================================
-- 迁移完成标记
-- ============================================================================

-- 创建一个版本标记表，记录数据库架构版本
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- 插入当前版本
INSERT OR REPLACE INTO schema_version (version, description)
VALUES (2, 'Phase B: 混合存储策略 - 资产状态管理');

-- ============================================================================
-- 验证迁移结果
-- ============================================================================

-- 验证新字段是否创建成功
SELECT
    '✓ 数据库迁移完成' as status,
    'capsules 表新增字段数量' as check_1,
    COUNT(*) as new_fields_count
FROM pragma_table_info('capsules')
WHERE name IN (
    'asset_status', 'local_wav_path', 'local_wav_size', 'local_wav_hash',
    'download_progress', 'download_started_at', 'preview_downloaded',
    'asset_last_accessed_at', 'asset_access_count', 'is_cache_pinned'
);

-- 验证新表是否创建成功
SELECT
    '✓ 新表创建完成' as status,
    'download_tasks' as table_1,
    (SELECT COUNT(*) FROM download_tasks) as row_count_1,
    'local_cache' as table_2,
    (SELECT COUNT(*) FROM local_cache) as row_count_2;

-- ============================================================================
-- 使用说明
-- ============================================================================
--
-- 1. 迁移完成后，需要运行应用代码的文件扫描功能：
--    python -m capsule_scanner --scan-local --fill-cache
--
-- 2. 验证迁移结果：
--    SELECT * FROM capsule_asset_summary LIMIT 10;
--    SELECT * FROM download_queue_status;
--    SELECT * FROM cache_stats;
--
-- 3. 如果需要回滚此迁移（不推荐）：
--    DROP TABLE IF EXISTS schema_version;
--    DROP TABLE IF EXISTS download_tasks;
--    DROP TABLE IF EXISTS local_cache;
--    DROP VIEW IF EXISTS capsule_asset_summary;
--    DROP VIEW IF EXISTS download_queue_status;
--    DROP VIEW IF EXISTS cache_stats;
--    -- 然后手动删除 ALTER TABLE 添加的字段
--
-- ============================================================================
