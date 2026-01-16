-- ==========================================
-- Supabase 云端同步数据库 Schema
-- ==========================================
--
-- 在 Supabase SQL Editor 中执行此脚本
-- 创建云端同步所需的所有表和策略
--

-- ==========================================
-- 1. 云端胶囊表
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

-- 索引
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_user_id ON cloud_capsules(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_local_id ON cloud_capsules(local_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_updated_at ON cloud_capsules(updated_at);
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_last_write_at ON cloud_capsules(last_write_at);
CREATE INDEX IF NOT EXISTS idx_cloud_capsules_deleted_at ON cloud_capsules(deleted_at);

-- ==========================================
-- 2. 云端标签表
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

-- 索引
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_tags_user_id ON cloud_capsule_tags(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_tags_capsule_id ON cloud_capsule_tags(capsule_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_tags_lens_id ON cloud_capsule_tags(lens_id);

-- ==========================================
-- 3. 云端坐标表
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

-- 索引
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_coordinates_user_id ON cloud_capsule_coordinates(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_coordinates_capsule_id ON cloud_capsule_coordinates(capsule_id);
CREATE INDEX IF NOT EXISTS idx_cloud_capsule_coordinates_lens_id ON cloud_capsule_coordinates(lens_id);

-- ==========================================
-- 4. 云端同步日志表
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

-- 索引
CREATE INDEX IF NOT EXISTS idx_sync_log_cloud_user_id ON sync_log_cloud(user_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_cloud_created_at ON sync_log_cloud(created_at);
CREATE INDEX IF NOT EXISTS idx_sync_log_cloud_table_name ON sync_log_cloud(table_name);

-- ==========================================
-- 5. Row Level Security (RLS) 策略
-- ==========================================

-- 启用 RLS
ALTER TABLE cloud_capsules ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_capsule_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_capsule_coordinates ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_log_cloud ENABLE ROW LEVEL SECURITY;

-- cloud_capsules 策略
CREATE POLICY "Users can view own capsules"
  ON cloud_capsules
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own capsules"
  ON cloud_capsules
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own capsules"
  ON cloud_capsules
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own capsules"
  ON cloud_capsules
  FOR DELETE
  USING (auth.uid() = user_id);

-- cloud_capsule_tags 策略
CREATE POLICY "Users can view own tags"
  ON cloud_capsule_tags
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own tags"
  ON cloud_capsule_tags
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own tags"
  ON cloud_capsule_tags
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own tags"
  ON cloud_capsule_tags
  FOR DELETE
  USING (auth.uid() = user_id);

-- cloud_capsule_coordinates 策略
CREATE POLICY "Users can view own coordinates"
  ON cloud_capsule_coordinates
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own coordinates"
  ON cloud_capsule_coordinates
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own coordinates"
  ON cloud_capsule_coordinates
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own coordinates"
  ON cloud_capsule_coordinates
  FOR DELETE
  USING (auth.uid() = user_id);

-- sync_log_cloud 策略
CREATE POLICY "Users can view own sync logs"
  ON sync_log_cloud
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sync logs"
  ON sync_log_cloud
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- ==========================================
-- 6. 启用实时功能（Realtime）
-- ==========================================

-- 取消注释以启用实时订阅
-- ALTER PUBLICATION supabase_realtime ADD TABLE cloud_capsules;
-- ALTER PUBLICATION supabase_realtime ADD TABLE cloud_capsule_tags;
-- ALTER PUBLICATION supabase_realtime ADD TABLE cloud_capsule_coordinates;

-- ==========================================
-- 7. 触发器：自动更新 updated_at
-- ==========================================

-- cloud_capsules updated_at 触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_cloud_capsules_updated_at
  BEFORE UPDATE ON cloud_capsules
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cloud_capsule_tags_updated_at
  BEFORE UPDATE ON cloud_capsule_tags
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- 8. 辅助函数
-- ==========================================

-- 获取用户最近同步时间
CREATE OR REPLACE FUNCTION get_last_sync_time(p_user_id UUID)
RETURNS TIMESTAMP WITH TIME ZONE AS $$
BEGIN
  RETURN (
    SELECT MAX(created_at)
    FROM sync_log_cloud
    WHERE user_id = p_user_id
    AND direction = 'to_cloud'
    AND status = 'success'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ==========================================
-- 完成！
-- ==========================================
-- 检查创建的表
SELECT
  table_name,
  (SELECT COUNT(*) FROM cloud_capsules) as capsule_count,
  (SELECT COUNT(*) FROM cloud_capsule_tags) as tag_count,
  (SELECT COUNT(*) FROM cloud_capsule_coordinates) as coord_count
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('cloud_capsules', 'cloud_capsule_tags', 'cloud_capsule_coordinates', 'sync_log_cloud');
