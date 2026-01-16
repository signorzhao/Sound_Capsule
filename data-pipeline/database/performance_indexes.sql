-- Phase B.5: 性能优化索引
-- 为混合存储策略添加必要的数据库索引

-- ============================================================
-- 1. 胶囊资产状态索引
-- ============================================================

-- 加速按 asset_status 查询（用于筛选云端/本地胶囊）
CREATE INDEX IF NOT EXISTS idx_capsules_asset_status
ON capsules(asset_status);

-- 加速按 cloud_status 查询（用于同步状态筛选）
CREATE INDEX IF NOT EXISTS idx_capsules_cloud_status
ON capsules(cloud_status);

-- 复合索引：同时按 asset_status 和 cloud_status 筛选
CREATE INDEX IF NOT EXISTS idx_capsules_asset_cloud_status
ON capsules(asset_status, cloud_status);

-- ============================================================
-- 2. 下载任务索引
-- ============================================================

-- 加速按状态查询待处理任务
CREATE INDEX IF NOT EXISTS idx_download_tasks_status
ON download_tasks(status);

-- 加速按胶囊 ID 查询该胶囊的所有下载任务
CREATE INDEX IF NOT EXISTS idx_download_tasks_capsule_id
ON download_tasks(capsule_id);

-- 复合索引：查询特定胶囊的特定状态任务
CREATE INDEX IF NOT EXISTS idx_download_tasks_capsule_status
ON download_tasks(capsule_id, status);

-- 加速按优先级排序（用于优先级队列）
CREATE INDEX IF NOT EXISTS idx_download_tasks_priority
ON download_tasks(priority DESC, created_at ASC);

-- ============================================================
-- 3. 本地缓存索引
-- ============================================================

-- 加速 LRU 查询（按最后访问时间升序）
CREATE INDEX IF NOT EXISTS idx_local_cache_last_accessed
ON local_cache(last_accessed_at ASC);

-- 加速按固定状态查询（保护固定缓存）
CREATE INDEX IF NOT EXISTS idx_local_cache_pinned
ON local_cache(is_pinned);

-- 复合索引：LRU + 固定状态（跳过固定缓存）
CREATE INDEX IF NOT EXISTS idx_local_cache_lru_pinned
ON local_cache(is_pinned, last_accessed_at ASC);

-- 加速按类型查询缓存统计
CREATE INDEX IF NOT EXISTS idx_local_cache_type
ON local_cache(file_type);

-- ============================================================
-- 4. 同步状态索引
-- ============================================================

-- 加速查询待同步记录
CREATE INDEX IF NOT EXISTS idx_sync_status_state
ON sync_status(sync_state);

-- 加速按表名查询同步状态
CREATE INDEX IF NOT EXISTS idx_sync_status_table
ON sync_status(table_name);

-- 复合索引：表名 + 状态（高效查询特定表的待同步记录）
CREATE INDEX IF NOT EXISTS idx_sync_status_table_state
ON sync_status(table_name, sync_state);

-- ============================================================
-- 5. 棱镜标签索引（如果存在）
-- ============================================================

-- 检查棱镜标签表是否存在并添加索引
-- 这里使用 CREATE INDEX IF NOT EXISTS 确保兼容性

-- ============================================================
-- 6. 元数据索引
-- ============================================================

-- 加速按创建时间排序（用于时间线视图）
CREATE INDEX IF NOT EXISTS idx_capsules_created_at
ON capsules(created_at DESC);

-- 加速按类型筛选（用于类型过滤）
CREATE INDEX IF NOT EXISTS idx_capsules_type
ON capsules(capsule_type);

-- 全文搜索支持（SQLite FTS5）
-- 为名称和关键词创建全文搜索虚拟表
-- CREATE VIRTUAL TABLE IF NOT EXISTS capsules_fts USING fts5(
--     name,
--     keywords,
--     content='capsules'
-- );

-- ============================================================
-- 7. 下载任务历史清理
-- ============================================================

-- 为下载日志表添加索引（如果存在）
-- CREATE INDEX IF NOT EXISTS idx_download_log_created_at
-- ON download_log(created_at DESC);

-- ============================================================
-- 索引创建验证
-- ============================================================

-- 查询所有创建的索引
SELECT
    name AS index_name,
    tbl_name AS table_name,
    sql AS index_sql
FROM sqlite_master
WHERE type = 'index'
  AND sql IS NOT NULL
  AND name LIKE 'idx_%'
ORDER BY tbl_name, name;

-- 预期结果：约 20+ 个新索引
