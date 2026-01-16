-- ============================================
-- Sound Capsule - 云端同步系统数据库 Schema
-- 版本: 1.0
-- 创建日期: 2026-01-10
-- ============================================

-- 同步状态表
CREATE TABLE IF NOT EXISTS sync_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    sync_state TEXT NOT NULL,  -- 'synced', 'pending', 'conflict', 'deleted'
    local_version INTEGER NOT NULL DEFAULT 1,
    cloud_version INTEGER,
    last_sync_at TIMESTAMP,
    last_sync_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, record_id)
);

-- 同步状态表索引
CREATE INDEX IF NOT EXISTS idx_sync_status_state ON sync_status(sync_state);
CREATE INDEX IF NOT EXISTS idx_sync_status_updated ON sync_status(updated_at);

-- 同步日志表
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,  -- 'create', 'update', 'delete'
    record_id INTEGER NOT NULL,
    direction TEXT NOT NULL,  -- 'to_cloud', 'from_cloud'
    status TEXT NOT NULL,     -- 'success', 'failed', 'conflict'
    error_message TEXT,
    local_version INTEGER,
    cloud_version INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 同步日志表索引
CREATE INDEX IF NOT EXISTS idx_sync_log_table ON sync_log(table_name);
CREATE INDEX IF NOT EXISTS idx_sync_log_status ON sync_log(status);
CREATE INDEX IF NOT EXISTS idx_sync_log_created ON sync_log(created_at);

-- 冲突记录表
CREATE TABLE IF NOT EXISTS sync_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    local_data TEXT NOT NULL,  -- JSON 格式
    cloud_data TEXT NOT NULL,  -- JSON 格式
    conflict_type TEXT NOT NULL,  -- 'version_conflict', 'delete_conflict', 'data_conflict'
    resolved BOOLEAN DEFAULT 0,
    resolution TEXT,             -- 'local', 'cloud', 'merge'
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 冲突记录表索引
CREATE INDEX IF NOT EXISTS idx_sync_conflicts_unresolved ON sync_conflicts(resolved);
CREATE INDEX IF NOT EXISTS idx_sync_conflicts_table ON sync_conflicts(table_name);

-- 触发器：自动更新 updated_at
CREATE TRIGGER IF NOT EXISTS update_sync_status_timestamp
AFTER UPDATE ON sync_status
FOR EACH ROW
BEGIN
    UPDATE sync_status SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
