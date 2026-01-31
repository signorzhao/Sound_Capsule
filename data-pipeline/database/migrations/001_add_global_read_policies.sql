-- ============================================================
-- Phase G: Step 1 - 云端 RLS 全局读取权限配置
-- ============================================================
-- 目标: 允许所有认证用户读取胶囊数据,写入权限仍限制为所有者
-- 执行位置: Supabase SQL Editor
-- 可重复执行: 先 DROP 再 CREATE，避免 "policy already exists" 报错
-- ============================================================

-- 先删除已存在的同名策略（若存在），再创建
DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsules";
DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsule_tags";
DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsule_coordinates";
DROP POLICY IF EXISTS "Public Read Access for capsule-files" ON storage.objects;

-- ============================================================
-- 1. cloud_capsules 表策略更新
-- ============================================================
CREATE POLICY "Enable read access for all authenticated users"
ON "public"."cloud_capsules"
FOR SELECT
USING (auth.role() = 'authenticated');

-- ============================================================
-- 2. cloud_capsule_tags 表策略更新
-- ============================================================
CREATE POLICY "Enable read access for all authenticated users"
ON "public"."cloud_capsule_tags"
FOR SELECT
USING (auth.role() = 'authenticated');

-- ============================================================
-- 3. cloud_capsule_coordinates 表策略更新
-- ============================================================
CREATE POLICY "Enable read access for all authenticated users"
ON "public"."cloud_capsule_coordinates"
FOR SELECT
USING (auth.role() = 'authenticated');

-- ============================================================
-- 4. Storage 策略更新 (capsule-files bucket)
-- ============================================================
CREATE POLICY "Public Read Access for capsule-files"
ON storage.objects
FOR SELECT
USING (
  bucket_id = 'capsule-files' AND
  auth.role() = 'authenticated'
);

-- 确保写入权限仅限于所有者
-- 这个策略应该已经存在,不需要修改:
-- "Users can upload to own folder" - foldername(name)[1] = auth.uid()::text

-- ============================================================
-- 5. 验证策略是否创建成功
-- ============================================================

-- 查看 cloud_capsules 表的所有策略
SELECT
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd,
  qual,
  with_check
FROM pg_policies
WHERE tablename = 'cloud_capsules'
  OR tablename = 'cloud_capsule_tags'
  OR tablename = 'cloud_capsule_coordinates'
ORDER BY tablename, policyname;

-- 查看 Storage 策略（自建 Supabase 可能无 storage.policies 视图，可跳过）
-- SELECT * FROM storage.policies WHERE bucket_id = 'capsule-files';

-- ============================================================
-- 6. 测试查询 (需要在 Supab SQL Editor 中手动执行)
-- ============================================================

-- 测试: 以当前登录用户身份查询所有胶囊
-- SELECT COUNT(*), user_id FROM cloud_capsules GROUP BY user_id;
-- 预期结果: 应该能看到多个用户的胶囊

-- ============================================================
-- 回滚脚本 (如果需要回滚,执行以下 SQL)
-- ============================================================

-- DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsules";
-- DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsule_tags";
-- DROP POLICY IF EXISTS "Enable read access for all authenticated users" ON "public"."cloud_capsule_coordinates";
-- DROP POLICY IF EXISTS "Public Read Access for capsule-files" ON storage.objects;
