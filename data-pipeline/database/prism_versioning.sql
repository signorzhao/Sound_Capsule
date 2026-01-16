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
-- 1. 棱镜配置主表 (Source of Truth)
-- ============================================

CREATE TABLE IF NOT EXISTS prisms (
    id TEXT PRIMARY KEY,          -- 棱镜 ID (如 'texture', 'mechanics')
    name TEXT NOT NULL,           -- 显示名称 (如 'Texture / (质感)')
    description TEXT,             -- 描述

    -- 坐标轴配置 (JSON 存储)
    axis_config TEXT DEFAULT '{}',

    -- 锚点数据 (JSON 存储 + 核心数据)
    anchors TEXT DEFAULT '[]',

    -- 版本控制字段
    version INTEGER DEFAULT 1,     -- 当前版本号
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,               -- 修改者 (device_id 或 user_id)

    -- 状态
    is_deleted BOOLEAN DEFAULT 0
);

-- ============================================
-- 2. 棱镜版本历史表 (用于回滚和冲突解决)
-- ============================================

CREATE TABLE IF NOT EXISTS prism_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prism_id TEXT NOT NULL,
    version INTEGER NOT NULL,

    -- 此时刻的完整配置快照
    snapshot_data TEXT NOT NULL,   -- JSON 格式

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    change_reason TEXT,            -- 修改原因 (e.g. 'user_edit', 'sync_merge')

    FOREIGN KEY (prism_id) REFERENCES prisms (id)
);

-- ============================================
-- 3. 同步日志表 (用于调试)
-- ============================================

CREATE TABLE IF NOT EXISTS prism_sync_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prism_id TEXT,
    action TEXT,                   -- 'upload', 'download', 'conflict_resolve'
    status TEXT,                   -- 'success', 'failed'
    details TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_prism_version ON prism_versions(prism_id, version);
