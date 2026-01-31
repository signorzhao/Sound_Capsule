-- ==========================================
-- 验证 SQL 执行结果
-- 在 Supabase Studio → SQL Editor 中执行，检查各表/列/策略是否存在
-- ==========================================

-- 1. 检查表是否存在
SELECT 'Tables' AS check_type, tablename AS name
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('cloud_capsules', 'cloud_capsule_tags', 'cloud_capsule_coordinates', 'sync_log_cloud', 'cloud_prisms')
ORDER BY tablename;

-- 2. 检查 cloud_prisms 是否有 is_active、field_data 列
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'cloud_prisms'
  AND column_name IN ('is_active', 'field_data')
ORDER BY column_name;

-- 3. 检查 RLS 策略数量（每张表应有若干策略）
SELECT tablename, COUNT(*) AS policy_count
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('cloud_capsules', 'cloud_capsule_tags', 'cloud_capsule_coordinates', 'sync_log_cloud', 'cloud_prisms')
GROUP BY tablename
ORDER BY tablename;

-- 4. 检查 storage bucket capsule-files 是否存在
SELECT id, name, public
FROM storage.buckets
WHERE id = 'capsule-files';
