-- ==========================================
-- 查询 Supabase 云端数据的 SQL 语句
-- ==========================================
-- 在 Supabase Dashboard 的 SQL Editor 中执行

-- 1. 查看所有胶囊
SELECT
    id,
    local_id,
    name,
    description,
    version,
    created_at,
    updated_at
FROM cloud_capsules
ORDER BY created_at DESC;

-- 2. 查看特定胶囊的详细信息
SELECT *
FROM cloud_capsules
WHERE name LIKE '%test_sync%';

-- 3. 查看胶囊统计
SELECT
    COUNT(*) as total_capsules,
    COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) as active_capsules,
    COUNT(CASE WHEN deleted_at IS NOT NULL THEN 1 END) as deleted_capsules
FROM cloud_capsules;

-- 4. 查看最近的同步日志
SELECT
    table_name,
    operation,
    direction,
    status,
    created_at
FROM sync_log_cloud
ORDER BY created_at DESC
LIMIT 10;

-- 5. 查看标签数据
SELECT
    cc.name as capsule_name,
    ct.lens_id,
    ct.x,
    ct.y
FROM cloud_capsule_tags ct
JOIN cloud_capsules cc ON ct.capsule_id = cc.id;

-- 6. 查看坐标数据
SELECT
    cc.name as capsule_name,
    ccoord.lens_id,
    ccoord.dimension,
    ccoord.value
FROM cloud_capsule_coordinates ccoord
JOIN cloud_capsules cc ON ccoord.capsule_id = cc.id;
