-- 008: profiles 表增加 language 列，用于云端同步用户语言偏好
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'zh-CN';
