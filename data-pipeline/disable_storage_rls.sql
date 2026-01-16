-- 禁用 Supabase Storage 的 RLS 策略（用于开发测试）

-- 注意：这个脚本会允许所有用户上传/下载文件
-- 生产环境应该配置更严格的策略

-- 禁用 capsules-files bucket 的 RLS
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- 删除默认的 RLS 策略（如果存在）
DROP POLICY IF EXISTS "Authenticated users can upload files" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can download files" ON storage.objects;
DROP POLICY IF EXISTS "Public Access" ON storage.objects;

-- 创建宽松的开发策略
CREATE POLICY "Dev: Allow all uploads"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'capsule-files');

CREATE POLICY "Dev: Allow all downloads"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'capsule-files');

CREATE POLICY "Dev: Allow all updates"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'capsule-files')
WITH CHECK (bucket_id = 'capsule-files');

CREATE POLICY "Dev: Allow all deletes"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'capsule-files');

-- 或者完全禁用 RLS（更简单，但不推荐生产环境）
-- ALTER TABLE storage.objects DISABLE ROW LEVEL SECURITY;
