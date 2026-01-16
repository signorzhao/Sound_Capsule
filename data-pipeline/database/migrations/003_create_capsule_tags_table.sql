-- ============================================
-- Supabase 云端 capsule_tags 表创建脚本
-- 用于存储棱镜关键词（动态数据）
-- ============================================

-- 创建 capsule_tags 表（如果不存在）
CREATE TABLE IF NOT EXISTS capsule_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    capsule_id UUID NOT NULL,
    lens_id TEXT NOT NULL,  -- 棱镜类型：texture, source, materiality, temperament
    word_id TEXT NOT NULL,  -- 关键词 ID
    word_cn TEXT,           -- 中文关键词
    word_en TEXT,           -- 英文关键词
    x REAL,                 -- X 坐标
    y REAL,                 -- Y 坐标
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_capsule_tags_capsule_id ON capsule_tags(capsule_id);
CREATE INDEX IF NOT EXISTS idx_capsule_tags_lens_id ON capsule_tags(lens_id);
CREATE INDEX IF NOT EXISTS idx_capsule_tags_word_id ON capsule_tags(word_id);

-- 启用行级安全策略（RLS）
ALTER TABLE capsule_tags ENABLE ROW LEVEL SECURITY;

-- 删除旧策略（如果存在）
DROP POLICY IF EXISTS "所有人可查看标签" ON capsule_tags;
DROP POLICY IF EXISTS "仅所有者可修改标签" ON capsule_tags;

-- 策略 1：所有认证用户可以查看所有标签
CREATE POLICY "所有人可查看标签"
ON capsule_tags
FOR SELECT
USING (true);

-- 策略 2：仅胶囊所有者可以插入、更新、删除标签
-- 注意：这里需要关联 capsules 表来验证所有权
CREATE POLICY "仅所有者可修改标签"
ON capsule_tags
FOR ALL
USING (
    EXISTS (
        SELECT 1 FROM capsules
        WHERE capsules.id = capsule_tags.capsule_id
        AND capsules.user_id = auth.uid()
    )
);

-- 创建触发器：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_capsule_tags_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_capsule_tags_updated_at ON capsule_tags;

CREATE TRIGGER trigger_update_capsule_tags_updated_at
BEFORE UPDATE ON capsule_tags
FOR EACH ROW
EXECUTE FUNCTION update_capsule_tags_updated_at();

-- ============================================
-- 验证脚本
-- ============================================

-- 查看表结构
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'capsule_tags'
-- ORDER BY ordinal_position;

-- 查看索引
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'capsule_tags';

-- 查看 RLS 策略
-- SELECT policyname, permissive, roles, cmd, qual, with_check
-- FROM pg_policies
-- WHERE tablename = 'capsule_tags';
