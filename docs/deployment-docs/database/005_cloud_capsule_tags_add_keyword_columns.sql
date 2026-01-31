-- ============================================
-- 005: cloud_capsule_tags 增加关键词列（word_id, word_cn, word_en）
-- 与本地 capsule_tags 及 upload_tags 写入字段一致，否则插入会报错、表无数据
-- ============================================

ALTER TABLE cloud_capsule_tags
ADD COLUMN IF NOT EXISTS word_id TEXT;

ALTER TABLE cloud_capsule_tags
ADD COLUMN IF NOT EXISTS word_cn TEXT;

ALTER TABLE cloud_capsule_tags
ADD COLUMN IF NOT EXISTS word_en TEXT;
