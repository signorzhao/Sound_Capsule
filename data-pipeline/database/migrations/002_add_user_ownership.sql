-- ============================================================
-- Phase G: Step 2 - 本地数据库迁移（用户所有权）
-- ============================================================
-- 目标: 为本地数据库添加用户所有权字段，支持多用户数据共存
-- 执行位置: 本地 SQLite 数据库
-- 数据库: data-pipeline/database/capsules.db
-- ============================================================

-- ============================================================
-- 1. 添加胶囊所有权字段
-- ============================================================

-- 添加 Supabase 用户 ID 字段（用于识别云端所有者）
ALTER TABLE capsules ADD COLUMN owner_supabase_user_id TEXT;

-- 添加本地用户 ID 字段（用于关联本地 users 表）
ALTER TABLE capsules ADD COLUMN created_by INTEGER REFERENCES users(id);

-- ============================================================
-- 2. 创建索引以提高查询性能
-- ============================================================

-- 为 owner_supabase_user_id 创建索引
CREATE INDEX IF NOT EXISTS idx_capsules_owner_supabase_user_id
ON capsules(owner_supabase_user_id);

-- 为 created_by 创建索引
CREATE INDEX IF NOT EXISTS idx_capsules_created_by
ON capsules(created_by);

-- ============================================================
-- 3. 验证迁移结果
-- ============================================================

-- 查看更新后的表结构（只显示最后几个字段）
PRAGMA table_info(capsules);

-- 统计现有胶囊数量
SELECT COUNT(*) as total_capsules FROM capsules;

-- 统计有 owner_supabase_user_id 的胶囊数量
SELECT COUNT(*) as capsules_with_owner FROM capsules
WHERE owner_supabase_user_id IS NOT NULL;

-- 统计有 created_by 的胶囊数量
SELECT COUNT(*) as capsules_with_creator FROM capsules
WHERE created_by IS NOT NULL;
