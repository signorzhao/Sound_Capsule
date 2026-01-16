-- ==========================================
-- 添加 Supabase User ID 字段到本地 users 表
-- ==========================================
-- 这个字段用于关联本地用户和 Supabase 云端用户

-- 添加 supabase_user_id 字段
ALTER TABLE users ADD COLUMN supabase_user_id TEXT;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_users_supabase_id ON users(supabase_user_id);
