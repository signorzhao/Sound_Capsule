-- ==========================================
-- 移除外键约束（本地管理用户）
-- ==========================================
-- 说明：我们在本地管理用户，不需要 Supabase auth.users 的外键约束

-- 删除外键约束
ALTER TABLE cloud_capsules DROP CONSTRAINT IF EXISTS cloud_capsules_user_id_fkey;
ALTER TABLE cloud_capsule_tags DROP CONSTRAINT IF EXISTS cloud_capsule_tags_user_id_fkey;
ALTER TABLE cloud_capsule_coordinates DROP CONSTRAINT IF EXISTS cloud_capsule_coordinates_user_id_fkey;
ALTER TABLE sync_log_cloud DROP CONSTRAINT IF EXISTS sync_log_cloud_user_id_fkey;

-- 验证
SELECT
  '✓ 外键约束已移除 - 可以使用任意 UUID' as status,
  (SELECT COUNT(*) FROM cloud_capsules) as capsule_count,
  (SELECT COUNT(*) FROM cloud_capsule_tags) as tag_count,
  (SELECT COUNT(*) FROM cloud_capsule_coordinates) as coord_count,
  (SELECT COUNT(*) FROM sync_log_cloud) as log_count;
