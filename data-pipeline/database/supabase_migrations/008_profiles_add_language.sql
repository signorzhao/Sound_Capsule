-- 008: profiles 表增加 language 列，用于云端同步用户语言偏好
-- 若 001～007 未创建 profiles（常见于仅跑基础迁移），先创建最小表结构再加列，避免报错
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID REFERENCES auth.users ON DELETE CASCADE PRIMARY KEY
);
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'zh-CN';
