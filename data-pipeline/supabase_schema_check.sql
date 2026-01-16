-- ==========================================
-- Supabase 云端同步数据库 Schema - 检查并创建
-- ==========================================
--
-- 这个脚本会检查表是否存在，只创建缺失的部分
--

-- ==========================================
-- 1. 检查并创建云端胶囊表
-- ==========================================
CREATE TABLE IF NOT EXISTS cloud_capsules (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,

  -- 本地数据库 ID（用于关联）
  local_id INTEGER,

  -- 胶囊基本信息
  name TEXT NOT NULL,
  description TEXT,
  capsule_type_id INTEGER,
  reaper_project_path TEXT,

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_write_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  deleted_at TIMESTAMP WITH TIME ZONE, -- 软删除

  -- 版本控制
  version INTEGER DEFAULT 1,
  data_hash TEXT, -- SHA256 哈希

  -- 元数据（JSON 格式）
  metadata JSONB DEFAULT '{}'::jsonb,

  -- 唯一约束
  UNIQUE(user_id, local_id)
);

-- ==========================================
-- 2. 检查并创建云端标签表
-- ==========================================
CREATE TABLE IF NOT EXISTS cloud_capsule_tags (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,
  capsule_id UUID REFERENCES cloud_capsules(id) ON DELETE CASCADE,

  -- 标签信息
  lens_id TEXT,
  x REAL,
  y REAL,

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- 唯一约束
  UNIQUE(user_id, capsule_id, lens_id)
);

-- ==========================================
-- 3. 检查并创建云端坐标表
-- ==========================================
CREATE TABLE IF NOT EXISTS cloud_capsule_coordinates (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,
  capsule_id UUID REFERENCES cloud_capsules(id) ON DELETE CASCADE,

  -- 坐标信息
  lens_id TEXT,
  dimension TEXT,
  value REAL,

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- 唯一约束
  UNIQUE(user_id, capsule_id, lens_id, dimension)
);

-- ==========================================
-- 4. 检查并创建云端同步日志表
-- ==========================================
CREATE TABLE IF NOT EXISTS sync_log_cloud (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,

  -- 同步信息
  table_name TEXT NOT NULL,
  operation TEXT NOT NULL, -- 'create', 'update', 'delete'
  record_id UUID NOT NULL,
  direction TEXT NOT NULL, -- 'to_cloud', 'from_cloud'
  status TEXT NOT NULL, -- 'success', 'failed', 'conflict'

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- 元数据
  metadata JSONB DEFAULT '{}'::jsonb
);

-- ==========================================
-- 5. 创建索引（如果不存在）
-- ==========================================

-- cloud_capsules 索引
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_user_id ON cloud_capsules(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_local_id ON cloud_capsules(local_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_updated_at ON cloud_capsules(updated_at);
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_last_write_at ON cloud_capsules(last_write_at);
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_deleted_at ON cloud_capsules(deleted_at);

-- cloud_capsule_tags 索引
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_tags_user_id ON cloud_capsule_tags(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_tags_capsule_id ON cloud_capsule_tags(capsule_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_tags_lens_id ON cloud_capsule_tags(lens_id);

-- cloud_capsule_coordinates 索引
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_coordinates_user_id ON cloud_capsule_coordinates(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_coordinates_capsule_id ON cloud_capsule_coordinates(capsule_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_coordinates_lens_id ON cloud_capsule_coordinates(lens_id);

-- sync_log_cloud 索引
CREATE INDEX IF NOT EXISTS idx_sync_log_cloud_user_id ON sync_log_cloud(user_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_cloud_created_at ON sync_log_cloud(created_at);
CREATE INDEX IF NOT EXISTS idx_sync_log_cloud_table_name ON sync_log_cloud(table_name);

-- ==========================================
-- 6. 检查表是否创建成功
-- ==========================================
SELECT
  '✓ 数据库表检查完成' as status,
  (SELECT COUNT(*) FROM cloud_capsules) as capsule_count,
  (SELECT COUNT(*) FROM cloud_capsule_tags) as tag_count,
  (SELECT COUNT(*) FROM cloud_capsule_coordinates) as coord_count,
  (SELECT COUNT(*) FROM sync_log_cloud) as log_count;
