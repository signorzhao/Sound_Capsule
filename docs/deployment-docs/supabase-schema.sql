-- ==========================================
-- Supabase 云端同步数据库 Schema
-- ==========================================
-- 依赖: uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

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
-- 9. Phase G: RLS 全局读取权限
-- ==========================================
-- 目标: 允许所有认证用户读取胶囊数据，写入权限仍限制为所有者
-- 与现有 "Users can view own *" 策略共存（RLS 满足任一策略即可）

-- cloud_capsules: 所有认证用户可读
CREATE POLICY "Enable read access for all authenticated users"
  ON "public"."cloud_capsules"
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- cloud_capsule_tags: 所有认证用户可读
CREATE POLICY "Enable read access for all authenticated users"
  ON "public"."cloud_capsule_tags"
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- cloud_capsule_coordinates: 所有认证用户可读
CREATE POLICY "Enable read access for all authenticated users"
  ON "public"."cloud_capsule_coordinates"
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- Storage (capsule-files): 所有认证用户可读；写入仍由 “Users can upload to own folder” 等策略限制
CREATE POLICY "Public Read Access for capsule-files"
  ON storage.objects
  FOR SELECT
  USING (
    bucket_id = 'capsule-files' AND
    auth.role() = 'authenticated'
  );

-- 回滚（如需撤销 Phase G 策略，可执行）:
-- DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsules";
-- DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsule_tags";
-- DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsule_coordinates";
-- DROP POLICY IF EXISTS "Public Read Access for capsule-files" ON storage.objects;
