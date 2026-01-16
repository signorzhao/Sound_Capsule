-- ============================================
-- Sound Capsule 完整数据库 Schema
-- 自动生成于初始化时
-- ============================================

CREATE TABLE capsules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    project_name TEXT,
    theme_name TEXT,
    capsule_type TEXT DEFAULT 'magic',
    file_path TEXT NOT NULL,
    preview_audio TEXT,
    rpp_file TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, cloud_status TEXT DEFAULT 'local', cloud_id TEXT, cloud_version INTEGER DEFAULT 1, files_downloaded BOOLEAN DEFAULT 1, last_synced_at TIMESTAMP, asset_status TEXT DEFAULT 'local', audio_uploaded BOOLEAN DEFAULT 0, local_wav_path TEXT, local_wav_size INTEGER, local_wav_hash TEXT, download_progress INTEGER DEFAULT 0, download_started_at TIMESTAMP, preview_downloaded BOOLEAN DEFAULT 0, asset_last_accessed_at TIMESTAMP, asset_access_count INTEGER DEFAULT 0, is_cache_pinned BOOLEAN DEFAULT 0, owner_supabase_user_id TEXT, keywords TEXT, description TEXT);

-- ============================================
-- 索引
-- ============================================

CREATE INDEX idx_capsules_cloud_status ON capsules(cloud_status);

CREATE INDEX idx_capsules_cloud_id ON capsules(cloud_id);

CREATE INDEX idx_capsules_owner_id 
ON capsules(owner_supabase_user_id);

-- ============================================
-- 触发器
-- ============================================

CREATE TRIGGER update_capsules_timestamp
AFTER UPDATE ON capsules
FOR EACH ROW
BEGIN
    UPDATE capsules SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

