-- ============================================
-- Phase C1: 棱镜版本控制数据库 Schema
-- 版本: 1.0
-- 创建日期: 2026-01-11
--
-- 策略选择:
-- - Q1: 完全迁移到数据库（Database as Source of Truth）
-- - Q2: 严格按时间戳（Last Write Wins）
-- - Q3: 可以回滚到任何版本（无硬性限制）
-- ============================================

-- ============================================
-- 1. 棱镜配置表
-- ============================================

CREATE TABLE IF NOT EXISTS prisms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 基本信息
    name TEXT NOT NULL UNIQUE,  -- 棱镜名称（如 'texture', 'source'）
    display_name TEXT NOT NULL,  -- 显示名称（如 '质感'）
    description TEXT,  -- 描述

    -- 版本控制
    version INTEGER NOT NULL DEFAULT 1,  -- 当前版本号
    parent_version INTEGER,  -- 父版本号（用于回溯）

    -- 配置数据
    config_json TEXT NOT NULL,  -- 完整配置（JSON 格式）
    -- 格式:
    -- {
    --   "active": true,
    --   "anchors": {
    --     "soft": {"x": -0.5, "y": 0.0, "label": "柔软"},
    --     "hard": {"x": 0.5, "y": 0.0, "label": "坚硬"}
    --   },
    --   "lexicon": "lexicon_texture.csv"
    -- }

    -- 元数据
    is_system INTEGER DEFAULT 0,  -- 是否为系统内置棱镜（不可删除）
    is_active INTEGER DEFAULT 1,  -- 是否在主界面显示

    -- 云端同步
    cloud_prism_id TEXT,  -- 云端棱镜 ID
    cloud_status TEXT DEFAULT 'local',  -- 'local', 'synced', 'pending', 'conflict'

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,  -- 最后同步时间

    -- 用户关联
    user_id TEXT,  -- 创建者用户 ID

    -- 版本历史关联
    FOREIGN KEY (parent_version) REFERENCES prisms(id) ON DELETE SET NULL
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_prisms_name ON prisms(name);
CREATE INDEX IF NOT EXISTS idx_prisms_version ON prisms(version);
CREATE INDEX IF NOT EXISTS idx_prisms_cloud_status ON prisms(cloud_status);
CREATE INDEX IF NOT EXISTS idx_prisms_user_id ON prisms(user_id);
CREATE INDEX IF NOT EXISTS idx_prisms_updated_at ON prisms(updated_at DESC);

-- 唯一约束：同一棱镜名称的版本号唯一
CREATE UNIQUE INDEX IF NOT EXISTS idx_prisms_name_version ON prisms(name, version);

-- ============================================
-- 2. 棱镜版本历史表
-- ============================================

CREATE TABLE IF NOT EXISTS prism_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 关联
    prism_id INTEGER NOT NULL,  -- 棱镜 ID
    version INTEGER NOT NULL,  -- 版本号

    -- 版本数据
    config_json TEXT NOT NULL,  -- 该版本的完整配置

    -- 变更信息
    change_description TEXT,  -- 变更说明
    change_type TEXT,  -- 'create', 'update', 'anchor_change', 'lexicon_change', 'restore', 'conflict_resolved'

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,  -- 创建者用户 ID

    -- 差异对比
    diff_json TEXT,  -- 与前一版本的差异（JSON 格式）
    -- 格式:
    -- {
    --   "anchors_changed": ["soft", "hard"],
    --   "lexicon_changed": false,
    --   "added": [...],
    --   "removed": [...],
    --   "modified": {"soft": {"old": {...}, "new": {...}}}
    -- }

    FOREIGN KEY (prism_id) REFERENCES prisms(id) ON DELETE CASCADE,
    UNIQUE(prism_id, version)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_prism_versions_prism_version
ON prism_versions(prism_id, version);
CREATE INDEX IF NOT EXISTS idx_prism_versions_created_at
ON prism_versions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prism_versions_prism_id
ON prism_versions(prism_id);

-- ============================================
-- 3. 棱镜同步日志表
-- ============================================

CREATE TABLE IF NOT EXISTS prism_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 操作信息
    prism_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- 'create', 'update', 'delete', 'conflict_resolved', 'restore'

    -- 版本信息
    from_version INTEGER,
    to_version INTEGER,

    -- 冲突解决
    conflict_detected INTEGER DEFAULT 0,  -- 是否检测到冲突
    conflict_resolution_strategy TEXT,  -- 'latest', 'local', 'cloud', 'manual'

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,

    -- 额外信息
    details TEXT,  -- JSON 格式的额外信息

    FOREIGN KEY (prism_id) REFERENCES prisms(id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_prism_sync_log_prism
ON prism_sync_log(prism_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prism_sync_log_action
ON prism_sync_log(action);
CREATE INDEX IF NOT EXISTS idx_prism_sync_log_conflict
ON prism_sync_log(conflict_detected);

-- ============================================
-- 4. 触发器：自动更新 updated_at
-- ============================================

CREATE TRIGGER IF NOT EXISTS update_prisms_timestamp
AFTER UPDATE ON prisms
FOR EACH ROW
BEGIN
    UPDATE prisms SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- ============================================
-- 5. 视图：棱镜状态概览
-- ============================================

CREATE VIEW IF NOT EXISTS prism_status_view AS
SELECT
    p.id,
    p.name,
    p.display_name,
    p.version,
    p.is_active,
    p.cloud_status,
    p.updated_at,
    COUNT(pv.id) as total_versions,
    (
        SELECT GROUP_CONCAT(
            CASE
                WHEN change_type = 'conflict_resolved' THEN 'C'
                ELSE NULL
            END
        )
        FROM prism_sync_log psl
        WHERE psl.prism_id = p.id
        AND psl.created_at >= datetime('now', '-7 days')
    ) as recent_conflicts
FROM prisms p
LEFT JOIN prism_versions pv ON pv.prism_id = p.id
GROUP BY p.id;
