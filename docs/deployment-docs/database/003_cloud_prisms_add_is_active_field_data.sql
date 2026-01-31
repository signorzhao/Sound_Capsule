-- ==========================================
-- 2b) 004 迁移：给 cloud_prisms 加 is_active、field_data
-- 在 cloud_prisms_schema_fixed.sql 之后执行
-- ==========================================

ALTER TABLE cloud_prisms
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

ALTER TABLE cloud_prisms
  ADD COLUMN IF NOT EXISTS field_data JSONB DEFAULT '{}'::jsonb;
