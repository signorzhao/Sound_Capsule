-- ============================================
-- 初始化默认棱镜配置
-- 版本: 1.0
-- 创建日期: 2026-01-11
--
-- 说明：将现有的 4 个默认棱镜迁移到数据库
-- ============================================

-- 插入 4 个默认棱镜
INSERT INTO prisms (name, display_name, description, version, config_json, is_system, is_active, user_id) VALUES
(
    'texture',
    '质感',
    '描述声音的质感特征（如柔软、坚硬、干燥、湿润）',
    1,
    '{
        "active": true,
        "anchors": {
            "soft": {"x": -0.5, "y": 0.0, "label": "柔软"},
            "hard": {"x": 0.5, "y": 0.0, "label": "坚硬"},
            "dry": {"x": 0.0, "y": -0.5, "label": "干燥"},
            "wet": {"x": 0.0, "y": 0.5, "label": "湿润"}
        },
        "lexicon": "lexicon_texture.csv",
        "color": "#FF6B6B"
    }',
    1,
    1,
    'system'
),
(
    'source',
    '来源',
    '描述声音的来源属性（如合成、原声、打击性、延续性）',
    1,
    '{
        "active": true,
        "anchors": {
            "synthetic": {"x": -0.5, "y": 0.0, "label": "合成"},
            "acoustic": {"x": 0.5, "y": 0.0, "label": "原声"},
            "percussive": {"x": 0.0, "y": -0.5, "label": "打击性"},
            "sustained": {"x": 0.0, "y": 0.5, "label": "延续性"}
        },
        "lexicon": "lexicon_source.csv",
        "color": "#4ECDC4"
    }',
    1,
    1,
    'system'
),
(
    'materiality',
    '材料性',
    '描述声音的材料特性（如有机、金属、颗粒感、平滑）',
    1,
    '{
        "active": true,
        "anchors": {
            "organic": {"x": -0.5, "y": 0.0, "label": "有机"},
            "metallic": {"x": 0.5, "y": 0.0, "label": "金属"},
            "granular": {"x": 0.0, "y": -0.5, "label": "颗粒感"},
            "smooth": {"x": 0.0, "y": 0.5, "label": "平滑"}
        },
        "lexicon": "lexicon_materiality.csv",
        "color": "#95E1D3"
    }',
    1,
    1,
    'system'
),
(
    'temperament',
    '性格',
    '描述声音的情绪性格（如平静、活力、暗黑、明亮）',
    1,
    '{
        "active": true,
        "anchors": {
            "calm": {"x": -0.5, "y": 0.0, "label": "平静"},
            "energetic": {"x": 0.5, "y": 0.0, "label": "活力"},
            "dark": {"x": 0.0, "y": -0.5, "label": "暗黑"},
            "bright": {"x": 0.0, "y": 0.5, "label": "明亮"}
        },
        "lexicon": "lexicon_temperament.csv",
        "color": "#FFD93D"
    }',
    1,
    1,
    'system'
);

-- 为每个默认棱镜创建初始版本历史记录
INSERT INTO prism_versions (prism_id, version, config_json, change_description, change_type, created_by, diff_json)
SELECT
    id,
    1,
    config_json,
    '初始化默认棱镜配置',
    'create',
    'system',
    NULL
FROM prisms
WHERE name IN ('texture', 'source', 'materiality', 'temperament');

-- 记录初始化日志
INSERT INTO prism_sync_log (prism_id, action, to_version, user_id, details)
SELECT
    id,
    'create',
    1,
    'system',
    '{"init_type": "default_prism", "migration_source": "system_defaults"}'
FROM prisms
WHERE name IN ('texture', 'source', 'materiality', 'temperament');
