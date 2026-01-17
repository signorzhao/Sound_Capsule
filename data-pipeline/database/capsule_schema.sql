-- ============================================
-- Sound Capsule 完整数据库 Schema
-- 版本: 2.0 (Phase G)
-- 包含所有云同步和 JIT 下载字段
-- ============================================

-- ============================================
-- 胶囊主表
-- ============================================
CREATE TABLE IF NOT EXISTS capsules (
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Phase G: 云同步字段
    cloud_status TEXT DEFAULT 'local',  -- 'local', 'synced', 'remote'
    cloud_id TEXT,
    cloud_version INTEGER DEFAULT 1,
    files_downloaded BOOLEAN DEFAULT 1,
    last_synced_at TIMESTAMP,
    
    -- Phase G: JIT 资产管理
    asset_status TEXT DEFAULT 'local',  -- 'local', 'cloud_only', 'synced', 'downloading'
    audio_uploaded BOOLEAN DEFAULT 0,   -- 是否已上传 Audio 文件夹到云端
    local_wav_path TEXT,
    local_wav_size INTEGER,
    local_wav_hash TEXT,
    download_progress INTEGER DEFAULT 0,
    download_started_at TIMESTAMP,
    preview_downloaded BOOLEAN DEFAULT 0,
    asset_last_accessed_at TIMESTAMP,
    asset_access_count INTEGER DEFAULT 0,
    is_cache_pinned BOOLEAN DEFAULT 0,
    
    -- Phase G: 用户所有权
    owner_supabase_user_id TEXT,
    
    -- Phase G: 增强元数据
    keywords TEXT,  -- 聚合的关键词（用于搜索）
    description TEXT
);

-- ============================================
-- 语义标签关联表
-- ============================================
CREATE TABLE IF NOT EXISTS capsule_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capsule_id INTEGER NOT NULL,
    lens TEXT NOT NULL,  -- 'texture', 'source', 'materiality', 'temperament'
    word_id TEXT NOT NULL,
    word_cn TEXT,
    word_en TEXT,
    x REAL,
    y REAL,
    FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE
);

-- ============================================
-- 语义坐标缓存表（性能优化）
-- ============================================
CREATE TABLE IF NOT EXISTS capsule_coordinates (
    capsule_id INTEGER PRIMARY KEY,
    texture_x REAL,
    texture_y REAL,
    source_x REAL,
    source_y REAL,
    materiality_x REAL,
    materiality_y REAL,
    temperament_x REAL,
    temperament_y REAL,
    FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE
);

-- ============================================
-- 技术元信息表
-- ============================================
CREATE TABLE IF NOT EXISTS capsule_metadata (
    capsule_id INTEGER PRIMARY KEY,
    bpm REAL,
    duration REAL,
    sample_rate INTEGER,
    plugin_count INTEGER,
    plugin_list TEXT,  -- JSON array
    has_sends BOOLEAN,
    has_folder_bus BOOLEAN,
    tracks_included INTEGER,
    FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE
);

-- ============================================
-- 用户认证表
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT,
    display_name TEXT,
    avatar_url TEXT,
    bio TEXT,
    preferences TEXT,  -- JSON 格式
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    supabase_user_id TEXT UNIQUE,
    is_active INTEGER DEFAULT 1,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Refresh Token 表（用于 JWT 刷新）
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================
-- 同步状态表（跟踪每条记录的同步状态）
-- ============================================
CREATE TABLE IF NOT EXISTS sync_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,           -- 表名（如 'capsules', 'capsule_tags'）
    record_id INTEGER NOT NULL,         -- 记录 ID
    sync_state TEXT DEFAULT 'pending',  -- 'pending', 'synced', 'conflict'
    local_version INTEGER DEFAULT 1,
    cloud_version INTEGER DEFAULT 0,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, record_id)
);

-- ============================================
-- 棱镜配置表
-- ============================================
CREATE TABLE IF NOT EXISTS prisms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    lens_id TEXT NOT NULL,              -- 棱镜 ID（如 'texture', 'source'）
    config TEXT,                         -- JSON 格式的配置
    version INTEGER DEFAULT 1,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, lens_id)
);

-- ============================================
-- 胶囊类型表
-- ============================================
CREATE TABLE IF NOT EXISTS capsule_types (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_cn TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    color TEXT NOT NULL,
    gradient TEXT NOT NULL,
    examples TEXT,
    priority_lens TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认胶囊类型
INSERT OR IGNORE INTO capsule_types (id, name, name_cn, description, icon, color, gradient, examples, priority_lens, sort_order)
VALUES 
    ('magic', 'MAGIC', '魔法', '神秘、梦幻、超自然', 'Sparkles', '#8B5CF6', 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)', '["粒子合成", "调制噪声", "演变音色"]', 'texture', 1),
    ('impact', 'IMPACT', '打击', '强力、冲击、震撼', 'Flame', '#EF4444', 'linear-gradient(135deg, #EF4444 0%, #F59E0B 100%)', '["鼓点", "打击乐", "贝斯拨奏"]', 'texture', 2),
    ('atmosphere', 'ATMOSPHERE', '环境', '空间、氛围、场景', 'Music', '#10B981', 'linear-gradient(135deg, #10B981 0%, #06B6D4 100%)', '["Pad", "氛围纹理", "音景"]', 'atmosphere', 3);

-- ============================================
-- 性能优化索引
-- ============================================

-- 云同步索引
CREATE INDEX IF NOT EXISTS idx_capsules_cloud_status 
ON capsules(cloud_status);

CREATE INDEX IF NOT EXISTS idx_capsules_cloud_id 
ON capsules(cloud_id);

CREATE INDEX IF NOT EXISTS idx_capsules_owner_id 
ON capsules(owner_supabase_user_id);

-- 坐标查询索引（空间查询优化）
CREATE INDEX IF NOT EXISTS idx_coordinates_texture
ON capsule_coordinates(texture_x, texture_y);

CREATE INDEX IF NOT EXISTS idx_coordinates_source
ON capsule_coordinates(source_x, source_y);

CREATE INDEX IF NOT EXISTS idx_coordinates_materiality
ON capsule_coordinates(materiality_x, materiality_y);

CREATE INDEX IF NOT EXISTS idx_coordinates_temperament
ON capsule_coordinates(temperament_x, temperament_y);

-- 标签查询索引
CREATE INDEX IF NOT EXISTS idx_capsule_tags_capsule_id
ON capsule_tags(capsule_id);

CREATE INDEX IF NOT EXISTS idx_capsule_tags_lens
ON capsule_tags(lens);

CREATE INDEX IF NOT EXISTS idx_capsule_tags_word_id
ON capsule_tags(word_id);

-- ============================================
-- 触发器：自动更新 updated_at
-- ============================================
CREATE TRIGGER IF NOT EXISTS update_capsules_timestamp
AFTER UPDATE ON capsules
FOR EACH ROW
BEGIN
    UPDATE capsules SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_users_timestamp
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;
