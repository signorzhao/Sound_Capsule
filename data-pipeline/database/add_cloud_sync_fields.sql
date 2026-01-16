-- 添加云端同步状态字段到 capsules 表
-- 用于跟踪胶囊在云端的状态

-- 1. 添加云端同步状态字段
-- 'local' - 仅在本地
-- 'synced' - 已同步到云端
-- 'remote' - 仅在云端
ALTER TABLE capsules ADD COLUMN cloud_status TEXT DEFAULT 'local';

-- 2. 添加云端记录 ID（外键）
ALTER TABLE capsules ADD COLUMN cloud_id TEXT;

-- 3. 添加云端版本号
ALTER TABLE capsules ADD COLUMN cloud_version INTEGER DEFAULT 1;

-- 4. 添加文件是否已下载的标记（对于 remote 状态）
ALTER TABLE capsules ADD COLUMN files_downloaded BOOLEAN DEFAULT 1;

-- 5. 添加最后同步时间
ALTER TABLE capsules ADD COLUMN last_synced_at TIMESTAMP;

-- 6. 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_capsules_cloud_status ON capsules(cloud_status);
CREATE INDEX IF NOT EXISTS idx_capsules_cloud_id ON capsules(cloud_id);

-- 7. 添加注释（SQLite 使用 PRAGMA table_info 查看）
-- 示例查询：
-- SELECT id, name, cloud_status, cloud_id, files_downloaded FROM capsules;
