-- ============================================
-- 棱镜启用状态 + 棱镜关键词(field_data) 云端同步
-- 在 Supabase 上执行：cloud_prisms 表增加 is_active、field_data
-- ============================================

-- 1. 棱镜启用状态（管理员在锚点编辑器关/开棱镜后同步到云端，客户端同步时拉取）
ALTER TABLE cloud_prisms
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- 2. 棱镜关键词/力场词数据（锚点编辑器生成的 points，同步到云端分发给所有客户端）
ALTER TABLE cloud_prisms
ADD COLUMN IF NOT EXISTS field_data TEXT;

-- 旧数据：is_active 默认为 true，field_data 为 NULL（同步时由管理员端补全）
