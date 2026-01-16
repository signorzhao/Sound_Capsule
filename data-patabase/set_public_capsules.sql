-- ==========================================
-- 设置胶囊为所有登录用户可见
-- ==========================================
--
-- 在 Supabase SQL Editor 中执行此脚本
--

-- 1. 删除旧的"只能查看自己"的策略
DROP POLICY IF EXISTS "Users can view own capsules" ON cloud_capsules;

-- 2. 创建新策略：所有登录用户都可以查看胶囊
CREATE POLICY "Logged in users can view capsules"
  ON cloud_capsules
  FOR SELECT
  USING (auth.uid() IS NOT NULL);

-- 3. 删除旧的"只能查看自己标签"的策略
DROP POLICY IF EXISTS "Users can view own tags" ON cloud_capsule_tags;

-- 4. 创建新策略：所有登录用户都可以查看标签
CREATE POLICY "Logged in users can view tags"
  ON cloud_capsule_tags
  FOR SELECT
  USING (auth.uid() IS NOT NULL);

-- 5. 删除旧的"只能查看自己坐标"的策略
DROP POLICY IF EXISTS "Users can view own coordinates" ON cloud_capsule_coordinates;

-- 6. 创建新策略：所有登录用户都可以查看坐标
CREATE POLICY "Logged in users can view coordinates"
  ON cloud_capsule_coordinates
  FOR SELECT
  USING (auth.uid() IS NOT NULL);

-- 7. 验证策略是否创建成功
SELECT
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd,
  qual
FROM pg_policies
WHERE tablename IN ('cloud_capsules', 'cloud_capsule_tags', 'cloud_capsule_coordinates')
ORDER BY tablename, policyname;

-- ==========================================
-- 完成！
-- ==========================================
--
-- 现在所有登录用户可以：
-- ✅ 查看所有人的胶囊
-- ✅ 查看所有人的标签
-- ✅ 查看所有人的坐标
-- ✅ 下载和使用别人的胶囊
--
-- 但是：
-- ✅ 只能修改/删除自己的胶囊（原有的 INSERT/UPDATE/DELETE 策略保持不变）
--
