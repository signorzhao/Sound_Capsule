-- ==========================================
-- 临时禁用 RLS 策略（仅用于测试）
-- ==========================================
-- 注意：在生产环境中，应该启用 RLS 并使用正确的 service_role key

-- 禁用 RLS（允许所有操作）
ALTER TABLE cloud_capsules DISABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_capsule_tags DISABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_capsule_coordinates DISABLE ROW LEVEL SECURITY;
ALTER TABLE sync_log_cloud DISABLE ROW LEVEL SECURITY;

-- 验证
SELECT
  '✓ RLS 已禁用 - 表可以自由访问' as status,
  (SELECT COUNT(*) FROM cloud_capsules) as capsule_count,
  (SELECT COUNT(*) FROM cloud_capsule_tags) as tag_count,
  (SELECT COUNT(*) FROM cloud_capsule_coordinates) as coord_count,
  (SELECT COUNT(*) FROM sync_log_cloud) as log_count;
