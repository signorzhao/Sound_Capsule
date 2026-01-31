-- ============================================================
-- Storage: capsule-files 允许认证用户上传（与云端策略一致）
-- ============================================================
-- 原因: 001 仅配置了 SELECT（读），未配置 INSERT（写）。
--       自建 Supabase 若缺少 INSERT 策略，上传会 403（new row violates row-level security policy）。
-- 执行: Supabase SQL Editor 中执行（自建/私有化部署必做）。
-- ============================================================

DROP POLICY IF EXISTS "Allow authenticated uploads" ON storage.objects;

CREATE POLICY "Allow authenticated uploads"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'capsule-files');
