-- ============================================
-- 006: 取消 cloud_capsule_tags 按 (user_id, capsule_id, lens_id) 唯一约束
-- 本地每个棱镜可有多个关键词（多行），云端原约束只允许每棱镜一行，导致 409 Conflict
-- ============================================

ALTER TABLE cloud_capsule_tags
DROP CONSTRAINT IF EXISTS cloud_capsule_tags_user_id_capsule_id_lens_id_key;
