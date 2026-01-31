-- ==========================================
-- 3) 可选：001_add_global_read_policies.sql
-- 全局读策略。在 004 迁移之后、创建 bucket 之后执行
-- ==========================================
-- 目标: 允许所有认证用户读取胶囊数据，写入权限仍限制为所有者

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

-- Storage (capsule-files): 所有认证用户可读
CREATE POLICY "Public Read Access for capsule-files"
  ON storage.objects
  FOR SELECT
  USING (
    bucket_id = 'capsule-files' AND
    auth.role() = 'authenticated'
  );
