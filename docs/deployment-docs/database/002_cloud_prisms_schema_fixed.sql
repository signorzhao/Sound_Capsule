-- ==========================================
-- 2a) cloud_prisms_schema_fixed.sql
-- 创建 cloud_prisms 表
-- 在 supabase_schema.sql 之后执行
-- ==========================================

CREATE TABLE IF NOT EXISTS cloud_prisms (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users NOT NULL,

  -- 本地数据库 ID（用于关联）
  local_id INTEGER,

  -- 棱镜/透镜基本信息
  name TEXT,
  prism_type TEXT,
  capsule_id UUID REFERENCES cloud_capsules(id) ON DELETE CASCADE,

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- 唯一约束
  UNIQUE(user_id, local_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_cloud_prisms_user_id ON cloud_prisms(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_prisms_local_id ON cloud_prisms(local_id);
CREATE INDEX IF NOT EXISTS idx_cloud_prisms_capsule_id ON cloud_prisms(capsule_id);
CREATE INDEX IF NOT EXISTS idx_cloud_prisms_updated_at ON cloud_prisms(updated_at);

-- 启用 RLS
ALTER TABLE cloud_prisms ENABLE ROW LEVEL SECURITY;

-- RLS 策略
CREATE POLICY "Users can view own prisms"
  ON cloud_prisms FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own prisms"
  ON cloud_prisms FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own prisms"
  ON cloud_prisms FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete own prisms"
  ON cloud_prisms FOR DELETE USING (auth.uid() = user_id);

-- updated_at 触发器
CREATE TRIGGER update_cloud_prisms_updated_at
  BEFORE UPDATE ON cloud_prisms
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
