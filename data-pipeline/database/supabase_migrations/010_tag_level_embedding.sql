-- ============================================
-- 010: 标签级细粒度向量化 (Tag-Level Embedding)
-- 1. cloud_capsule_tags 增加 embedding 列
-- 2. 新 RPC：取 max(主体相似度, 标签相似度) 排序
-- ============================================

-- 1. cloud_capsule_tags 增加 embedding 列（每个标签单独向量）
ALTER TABLE cloud_capsule_tags
ADD COLUMN IF NOT EXISTS embedding vector(384);

-- 2. 标签级语义搜索函数：score = MAX(主体相似度, 所有标签相似度的最大值)
CREATE OR REPLACE FUNCTION semantic_search_capsules_tag_level(
  query_embedding float8[],
  match_limit int DEFAULT 20,
  match_user_id uuid DEFAULT NULL
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
  WITH body_sim AS (
    SELECT c.id, (1 - (c.embedding <=> q_vec))::float AS s
    FROM cloud_capsules c
    WHERE c.deleted_at IS NULL
      AND c.embedding IS NOT NULL
      AND (
        (match_user_id IS NOT NULL AND c.user_id = match_user_id)
        OR (match_user_id IS NULL AND c.user_id = auth.uid())
      )
  ),
  tag_sim AS (
    SELECT ct.capsule_id, MAX((1 - (ct.embedding <=> q_vec))::float) AS s
    FROM cloud_capsule_tags ct
    JOIN cloud_capsules c ON c.id = ct.capsule_id
    WHERE ct.embedding IS NOT NULL
      AND c.deleted_at IS NULL
      AND (
        (match_user_id IS NOT NULL AND c.user_id = match_user_id)
        OR (match_user_id IS NULL AND c.user_id = auth.uid())
      )
    GROUP BY ct.capsule_id
  ),
  combined AS (
    SELECT
      c.id,
      GREATEST(COALESCE(bs.s, 0), COALESCE(ts.s, 0)) AS best_sim
    FROM cloud_capsules c
    LEFT JOIN body_sim bs ON bs.id = c.id
    LEFT JOIN tag_sim ts ON ts.capsule_id = c.id
    WHERE c.deleted_at IS NULL
      AND (
        (match_user_id IS NOT NULL AND c.user_id = match_user_id)
        OR (match_user_id IS NULL AND c.user_id = auth.uid())
      )
      AND (bs.s IS NOT NULL OR ts.s IS NOT NULL)
  )
  SELECT
    c.id,
    c.user_id,
    c.local_id,
    c.name,
    c.description,
    c.capsule_type_id,
    c.created_at,
    c.updated_at,
    comb.best_sim AS similarity
  FROM cloud_capsules c
  JOIN combined comb ON comb.id = c.id
  ORDER BY comb.best_sim DESC
  LIMIT match_limit;
END;
$$;

GRANT EXECUTE ON FUNCTION semantic_search_capsules_tag_level(float8[], int, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION semantic_search_capsules_tag_level(float8[], int, uuid) TO service_role;
