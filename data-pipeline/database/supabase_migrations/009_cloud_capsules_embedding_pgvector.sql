-- ============================================
-- 009: 语义搜索 - pgvector 扩展与 cloud_capsules.embedding
-- 模型: paraphrase-multilingual-MiniLM-L12-v2 → 384 维
-- ============================================

-- 1. 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. cloud_capsules 增加 embedding 列（可空，旧数据无向量）
ALTER TABLE cloud_capsules
ADD COLUMN IF NOT EXISTS embedding vector(384);

-- 3. 可选：向量索引，数据量较大时加速相似度查询
-- CREATE INDEX IF NOT EXISTS idx_cloud_capsules_embedding
-- ON cloud_capsules USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 4. 语义搜索函数：按余弦相似度返回胶囊（供 rpc 调用）
-- 调用方传入 query_embedding (float8[]，JSON 数组)，match_limit，match_user_id
CREATE OR REPLACE FUNCTION semantic_search_capsules(
  query_embedding float8[],
  match_limit int DEFAULT 20,
  match_user_id uuid DEFAULT NULL  -- NULL 时用 auth.uid()；传值则只搜该用户的胶囊
)
RETURNS TABLE (
  id uuid,
  user_id uuid,
  local_id int,
  name text,
  description text,
  capsule_type_id int,
  created_at timestamptz,
  updated_at timestamptz,
  similarity float
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  q_vec vector(384);
BEGIN
  q_vec := query_embedding::vector(384);
  RETURN QUERY
  SELECT
    c.id,
    c.user_id,
    c.local_id,
    c.name,
    c.description,
    c.capsule_type_id,
    c.created_at,
    c.updated_at,
    1 - (c.embedding <=> q_vec) AS similarity
  FROM cloud_capsules c
  WHERE c.deleted_at IS NULL
    AND c.embedding IS NOT NULL
    AND (
      (match_user_id IS NOT NULL AND c.user_id = match_user_id)
      OR (match_user_id IS NULL AND c.user_id = auth.uid())
    )
  ORDER BY c.embedding <=> q_vec
  LIMIT match_limit;
END;
$$;

-- 允许认证用户执行（RLS 由函数内 user_id 条件保证）
GRANT EXECUTE ON FUNCTION semantic_search_capsules(float8[], int, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION semantic_search_capsules(float8[], int, uuid) TO service_role;
