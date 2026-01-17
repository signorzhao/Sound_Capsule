# Phase C1: 棱镜版本号机制 - 详细实施方案

**日期**: 2026-01-11
**状态**: 📋 详细规划中
**预计耗时**: 5-7 天
**依赖**: Phase B 已完成 ✅

---

## 📋 背景分析

### 什么是"棱镜"（Prism/Lens）？

在你的 Sound Capsule 系统中，**棱镜**定义了语义空间的维度配置：

```python
# 4 个默认棱镜
PRISMS = {
    "texture": "质感 - 描述声音的质感特征",
    "source": "来源 - 描述声音的来源属性",
    "materiality": "材料性 - 描述声音的材料特性",
    "temperament": "性格 - 描述声音的情绪性格"
}

# 每个棱镜包含:
# 1. 锚点（anchors）: 定义该维度的基准点
# 2. 词汇表（lexicon）: 该维度使用的词汇
# 3. 坐标空间: 2D 平面用于映射胶囊
```

### 当前棱镜配置结构

```python
# anchor_editor.py 中定义的配置格式
prism_config = {
    "texture": {
        "active": True,
        "anchors": {
            "soft": {"x": -0.5, "y": 0.0},
            "hard": {"x": 0.5, "y": 0.0},
            "dry": {"x": 0.0, "y": -0.5},
            "wet": {"x": 0.0, "y": 0.5}
        },
        "lexicon": "lexicon_texture.csv"  # 词汇表文件
    },
    # ... source, materiality, temperament
}
```

### 为什么需要版本控制？

**冲突场景**:
```
时间线:
Day 1: 设备 A 修改 texture 棱镜 → 版本 1
Day 2: 设备 B 也修改 texture 棱镜 → 版本 1（基于 Day 1 之前）
Day 3: 设备 A 上传到云端 → 版本 1
Day 4: 设备 B 上传到云端 → 版本 1
→ 冲突！谁的修改是正确的？
```

**需要版本控制的原因**:
1. **多设备协作** - 用户在多个设备上使用 Sound Capsule
2. **配置变更追踪** - 记录棱镜配置的修改历史
3. **冲突解决** - 当多设备同时修改时，智能解决冲突
4. **回滚能力** - 如果新配置有问题，可以回滚到旧版本

---

## 🎯 C1 实施方案

### C1.1 数据库改造

#### 1.1.1 创建棱镜配置表

**新文件**: `data-pipeline/database/prism_schema.sql`

```sql
-- ============================================
-- 棱镜配置表（Phase C1）
-- ============================================

CREATE TABLE IF NOT EXISTS prisms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 基本信息
    name TEXT NOT NULL UNIQUE,  -- 棱镜名称（如 'texture', 'source'）
    display_name TEXT NOT NULL,  -- 显示名称（如 '质感'）
    description TEXT,  -- 描述

    -- 版本控制
    version INTEGER NOT NULL DEFAULT 1,  -- 当前版本号
    parent_version INTEGER,  -- 父版本号（用于回溯）

    -- 配置数据
    config_json TEXT NOT NULL,  -- 完整配置（JSON 格式）
    -- 格式:
    -- {
    --   "active": true,
    --   "anchors": {
    --     "soft": {"x": -0.5, "y": 0.0},
    --     "hard": {"x": 0.5, "y": 0.0}
    --   },
    --   "lexicon": "lexicon_texture.csv"
    -- }

    -- 元数据
    is_system INTEGER DEFAULT 0,  -- 是否为系统内置棱镜（不可删除）
    is_active INTEGER DEFAULT 1,  -- 是否在主界面显示

    -- 云端同步
    cloud_prism_id TEXT,  -- 云端棱镜 ID
    cloud_status TEXT DEFAULT 'local',  -- 'local', 'synced', 'pending', 'conflict'

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,  -- 最后同步时间

    -- 用户关联
    user_id TEXT,  -- 创建者用户 ID

    -- 版本历史关联
    FOREIGN KEY (parent_version) REFERENCES prisms(id) ON DELETE SET NULL
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_prisms_name ON prisms(name);
CREATE INDEX IF NOT EXISTS idx_prisms_version ON prisms(version);
CREATE INDEX IF NOT EXISTS idx_prisms_cloud_status ON prisms(cloud_status);
CREATE INDEX IF NOT EXISTS idx_prisms_user_id ON prisms(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_prisms_name_version ON prisms(name, version);

-- ============================================
-- 棱镜版本历史表
-- ============================================

CREATE TABLE IF NOT EXISTS prism_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 关联
    prism_id INTEGER NOT NULL,  -- 棱镜 ID
    version INTEGER NOT NULL,  -- 版本号

    -- 版本数据
    config_json TEXT NOT NULL,  -- 该版本的完整配置

    -- 变更信息
    change_description TEXT,  -- 变更说明
    change_type TEXT,  -- 'create', 'update', 'anchor_change', 'lexicon_change'

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,  -- 创建者用户 ID

    -- 差异对比
    diff_json TEXT,  -- 与前一版本的差异（JSON 格式）

    FOREIGN KEY (prism_id) REFERENCES prisms(id) ON DELETE CASCADE,
    UNIQUE(prism_id, version)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_prism_versions_prism_version
ON prism_versions(prism_id, version);
CREATE INDEX IF NOT EXISTS idx_prism_versions_created_at
ON prism_versions(created_at DESC);

-- ============================================
-- 棱镜同步日志表
-- ============================================

CREATE TABLE IF NOT EXISTS prism_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 操作信息
    prism_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- 'create', 'update', 'delete', 'conflict_resolved'

    -- 版本信息
    from_version INTEGER,
    to_version INTEGER,

    -- 冲突解决
    conflict_detected INTEGER DEFAULT 0,  -- 是否检测到冲突
    conflict_resolution_strategy TEXT,  -- 'latest', 'local', 'cloud', 'manual'

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,

    FOREIGN KEY (prism_id) REFERENCES prisms(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prism_sync_log_prism
ON prism_sync_log(prism_id, created_at DESC);
```

#### 1.1.2 数据迁移

**问题**: 当前系统中没有 `prisms` 表，棱镜配置硬编码在代码中。

**解决方案**: 创建初始化脚本

**新文件**: `data-pipeline/database/init_default_prisms.sql`

```sql
-- ============================================
-- 初始化默认棱镜配置
-- ============================================

-- 插入 4 个默认棱镜
INSERT INTO prisms (name, display_name, description, version, config_json, is_system, is_active) VALUES
(
    'texture',
    '质感',
    '描述声音的质感特征',
    1,
    '{
        "active": true,
        "anchors": {
            "soft": {"x": -0.5, "y": 0.0, "label": "柔软"},
            "hard": {"x": 0.5, "y": 0.0, "label": "坚硬"},
            "dry": {"x": 0.0, "y": -0.5, "label": "干燥"},
            "wet": {"x": 0.0, "y": 0.5, "label": "湿润"}
        },
        "lexicon": "lexicon_texture.csv"
    }',
    1,
    1
),
(
    'source',
    '来源',
    '描述声音的来源属性',
    1,
    '{
        "active": true,
        "anchors": {
            "synthetic": {"x": -0.5, "y": 0.0, "label": "合成"},
            "acoustic": {"x": 0.5, "y": 0.0, "label": "原声"},
            "percussive": {"x": 0.0, "y": -0.5, "label": "打击性"},
            "sustained": {"x": 0.0, "y": 0.5, "label": "延续性"}
        },
        "lexicon": "lexicon_source.csv"
    }',
    1,
    1
),
(
    'materiality',
    '材料性',
    '描述声音的材料特性',
    1,
    '{
        "active": true,
        "anchors": {
            "organic": {"x": -0.5, "y": 0.0, "label": "有机"},
            "metallic": {"x": 0.5, "y": 0.0, "label": "金属"},
            "granular": {"x": 0.0, "y": -0.5, "label": "颗粒感"},
            "smooth": {"x": 0.0, "y": 0.5, "label": "平滑"}
        },
        "lexicon": "lexicon_materiality.csv"
    }',
    1,
    1
),
(
    'temperament',
    '性格',
    '描述声音的情绪性格',
    1,
    '{
        "active": true,
        "anchors": {
            "calm": {"x": -0.5, "y": 0.0, "label": "平静"},
            "energetic": {"x": 0.5, "y": 0.0, "label": "活力"},
            "dark": {"x": 0.0, "y": -0.5, "label": "暗黑"},
            "bright": {"x": 0.0, "y": 0.5, "label": "明亮"}
        },
        "lexicon": "lexicon_temperament.csv"
    }',
    1,
    1
);

-- 为每个默认棱镜创建初始版本历史记录
INSERT INTO prism_versions (prism_id, version, config_json, change_type, created_by)
SELECT
    id,
    1,
    config_json,
    'create',
    'system'
FROM prisms
WHERE name IN ('texture', 'source', 'materiality', 'temperament');
```

---

### C1.2 版本管理服务

**新文件**: `data-pipeline/prism_version_manager.py`

```python
"""
棱镜版本管理器（Phase C1）

功能：
1. 创建新版本
2. 版本冲突检测
3. 冲突解决
4. 版本历史查询
5. 版本回滚
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from capsule_db import CapsuleDatabase


class PrismVersionManager:
    """棱镜版本管理器"""

    def __init__(self, db_path: str = "database/capsules.db"):
        """
        初始化版本管理器

        Args:
            db_path: 数据库路径
        """
        self.db = CapsuleDatabase(db_path)

    def create_version(
        self,
        prism_name: str,
        config: Dict[str, Any],
        user_id: str,
        change_description: str = None,
        change_type: str = "update"
    ) -> Dict[str, Any]:
        """
        创建新版本

        Args:
            prism_name: 棱镜名称
            config: 新配置数据
            user_id: 用户 ID
            change_description: 变更说明
            change_type: 变更类型

        Returns:
            {
                "success": bool,
                "prism_id": int,
                "new_version": int,
                "previous_version": int,
                "message": str
            }
        """
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()

            # 1. 获取当前棱镜信息
            cursor.execute("""
                SELECT id, version, config_json
                FROM prisms
                WHERE name = ?
                ORDER BY version DESC
                LIMIT 1
            """, (prism_name,))

            row = cursor.fetchone()

            if row:
                # 棱镜已存在，创建新版本
                prism_id, current_version, old_config = row
                new_version = current_version + 1

                # 计算差异
                diff = self._calculate_config_diff(
                    json.loads(old_config),
                    config
                )

                # 更新棱镜
                config_json = json.dumps(config, ensure_ascii=False)
                cursor.execute("""
                    UPDATE prisms
                    SET
                        version = ?,
                        parent_version = ?,
                        config_json = ?,
                        updated_at = ?,
                        cloud_status = 'pending'
                    WHERE id = ?
                """, (
                    new_version,
                    current_version,
                    config_json,
                    datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    prism_id
                ))

            else:
                # 新棱镜，创建版本 1
                new_version = 1
                config_json = json.dumps(config, ensure_ascii=False)

                cursor.execute("""
                    INSERT INTO prisms (
                        name, display_name, description,
                        version, config_json,
                        is_system, is_active,
                        user_id, cloud_status
                    ) VALUES (?, ?, ?, ?, ?, 0, 1, ?, 'pending')
                """, (
                    prism_name,
                    config.get('display_name', prism_name),
                    config.get('description', ''),
                    new_version,
                    config_json,
                    user_id
                ))

                prism_id = cursor.lastrowid
                diff = None

            # 2. 保存版本历史
            cursor.execute("""
                INSERT INTO prism_versions (
                    prism_id, version, config_json,
                    change_description, change_type,
                    created_by, diff_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                prism_id,
                new_version,
                config_json,
                change_description,
                change_type,
                user_id,
                json.dumps(diff) if diff else None
            ))

            # 3. 记录同步日志
            cursor.execute("""
                INSERT INTO prism_sync_log (
                    prism_id, action, to_version, user_id
                ) VALUES (?, 'update', ?, ?)
            """, (prism_id, new_version, user_id))

            conn.commit()

            return {
                "success": True,
                "prism_id": prism_id,
                "new_version": new_version,
                "previous_version": current_version if row else None,
                "message": f"创建版本 {new_version} 成功"
            }

        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            conn.close()

    def detect_conflict(
        self,
        prism_name: str,
        local_version: int,
        cloud_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        检测版本冲突

        Args:
            prism_name: 棱镜名称
            local_version: 本地版本号
            cloud_config: 云端配置

        Returns:
            {
                "has_conflict": bool,
                "local_version": int,
                "cloud_version": int,
                "conflict_type": str,  # 'version_mismatch', 'concurrent_edit', 'none'
                "resolution_strategy": str  # 推荐的解决策略
            }
        """
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()

            # 获取本地棱镜信息
            cursor.execute("""
                SELECT id, version, config_json, updated_at
                FROM prisms
                WHERE name = ?
                ORDER BY version DESC
                LIMIT 1
            """, (prism_name,))

            row = cursor.fetchone()

            if not row:
                # 本地没有这个棱镜
                return {
                    "has_conflict": False,
                    "conflict_type": "new_prism",
                    "resolution_strategy": "use_cloud"
                }

            prism_id, current_db_version, local_config_json, local_updated = row

            # 计算配置哈希来检测实际变更
            local_config_hash = hashlib.md5(local_config_json.encode()).hexdigest()
            cloud_config_hash = hashlib.md5(json.dumps(cloud_config).encode()).hexdigest()

            # 场景 1: 版本号相同但配置不同
            if local_version == current_db_version:
                if local_config_hash != cloud_config_hash:
                    # 云端版本更新了，但本地版本号没变
                    return {
                        "has_conflict": True,
                        "local_version": current_db_version,
                        "cloud_version": local_version,  # 云端也是这个版本
                        "conflict_type": "config_diverged",
                        "resolution_strategy": "latest"  # 使用最新的 updated_at
                    }

            # 场景 2: 版本号不同
            if local_version != current_db_version:
                # 版本号不一致，需要合并
                return {
                    "has_conflict": True,
                    "local_version": current_db_version,
                    "cloud_version": local_version,
                    "conflict_type": "version_mismatch",
                    "resolution_strategy": "latest"  # 默认使用最新时间
                }

            # 无冲突
            return {
                "has_conflict": False,
                "conflict_type": "none"
            }

        except Exception as e:
            return {
                "has_conflict": False,
                "error": str(e)
            }
        finally:
            conn.close()

    def resolve_conflict(
        self,
        prism_name: str,
        local_config: Dict[str, Any],
        cloud_config: Dict[str, Any],
        strategy: str = "latest",
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        解决冲突

        Args:
            prism_name: 棱镜名称
            local_config: 本地配置
            cloud_config: 云端配置
            strategy: 解决策略
                - 'latest': 使用最新修改时间的版本
                - 'local': 保留本地版本
                - 'cloud': 使用云端版本
                - 'manual': 需要手动选择（返回两者供用户选择）
            user_id: 用户 ID

        Returns:
            {
                "success": bool,
                "resolution": str,  # 'local' 或 'cloud' 或 'merged'
                "new_version": int,
                "message": str
            }
        """
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()

            # 获取本地棱镜的时间戳
            cursor.execute("""
                SELECT id, version, updated_at
                FROM prisms
                WHERE name = ?
                ORDER BY version DESC
                LIMIT 1
            """, (prism_name,))

            row = cursor.fetchone()
            if not row:
                # 本地不存在，直接使用云端
                return self.create_version(
                    prism_name,
                    cloud_config,
                    user_id or 'system',
                    change_description="从云端恢复",
                    change_type="conflict_resolved"
                )

            prism_id, local_version, local_updated = row

            # 根据策略选择
            if strategy == "latest":
                # 比较时间戳（需要从 cloud_config 获取 updated_at）
                local_time = datetime.strptime(local_updated, '%Y-%m-%d %H:%M:%S')
                cloud_time = datetime.strptime(
                    cloud_config.get('updated_at', local_updated),
                    '%Y-%m-%d %H:%M:%S'
                )

                resolution = 'cloud' if cloud_time > local_time else 'local'

            elif strategy == "local":
                resolution = 'local'
            elif strategy == "cloud":
                resolution = 'cloud'
            elif strategy == "manual":
                # 返回两个配置让用户选择
                return {
                    "success": False,
                    "requires_manual_selection": True,
                    "local_config": local_config,
                    "cloud_config": cloud_config,
                    "message": "需要用户手动选择版本"
                }
            else:
                return {
                    "success": False,
                    "error": f"未知的策略: {strategy}"
                }

            # 应用解决方案
            if resolution == 'cloud':
                # 使用云端配置，创建新版本
                result = self.create_version(
                    prism_name,
                    cloud_config,
                    user_id or 'system',
                    change_description="冲突解决：使用云端版本",
                    change_type="conflict_resolved"
                )

            else:  # resolution == 'local'
                # 保留本地版本，上传到云端
                result = {
                    "success": True,
                    "resolution": "local",
                    "message": "冲突解决：保留本地版本，将同步到云端"
                }

            # 记录冲突解决日志
            cursor.execute("""
                INSERT INTO prism_sync_log (
                    prism_id, action, conflict_detected,
                    conflict_resolution_strategy, user_id
                ) VALUES (?, 'conflict_resolved', 1, ?, ?)
            """, (prism_id, strategy, user_id))

            conn.commit()

            return result

        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            conn.close()

    def get_version_history(self, prism_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取版本历史

        Args:
            prism_name: 棱镜名称
            limit: 返回数量限制

        Returns:
            版本历史列表
        """
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    pv.version,
                    pv.config_json,
                    pv.change_description,
                    pv.change_type,
                    pv.created_at,
                    pv.created_by,
                    pv.diff_json
                FROM prism_versions pv
                JOIN prisms p ON pv.prism_id = p.id
                WHERE p.name = ?
                ORDER BY pv.version DESC
                LIMIT ?
            """, (prism_name, limit))

            history = []
            for row in cursor.fetchall():
                history.append({
                    "version": row[0],
                    "config": json.loads(row[1]),
                    "description": row[2],
                    "change_type": row[3],
                    "created_at": row[4],
                    "created_by": row[5],
                    "diff": json.loads(row[6]) if row[6] else None
                })

            return history

        finally:
            conn.close()

    def restore_version(
        self,
        prism_name: str,
        target_version: int,
        user_id: str
    ) -> Dict[str, Any]:
        """
        回滚到指定版本

        Args:
            prism_name: 棱镜名称
            target_version: 目标版本号
            user_id: 用户 ID

        Returns:
            操作结果
        """
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()

            # 1. 获取目标版本的配置
            cursor.execute("""
                SELECT pv.prism_id, pv.config_json, p.version as current_version
                FROM prism_versions pv
                JOIN prisms p ON pv.prism_id = p.id
                WHERE p.name = ? AND pv.version = ?
            """, (prism_name, target_version))

            row = cursor.fetchone()
            if not row:
                return {
                    "success": False,
                    "error": f"版本 {target_version} 不存在"
                }

            prism_id, config_json, current_version = row
            old_config = json.loads(config_json)

            # 2. 创建新版本（基于旧配置）
            new_version = current_version + 1

            cursor.execute("""
                UPDATE prisms
                SET
                    version = ?,
                    parent_version = ?,
                    config_json = ?,
                    updated_at = ?,
                    cloud_status = 'pending'
                WHERE id = ?
            """, (
                new_version,
                target_version,  # 父版本设为目标版本
                config_json,
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                prism_id
            ))

            # 3. 保存版本历史
            cursor.execute("""
                INSERT INTO prism_versions (
                    prism_id, version, config_json,
                    change_description, change_type, created_by
                ) VALUES (?, ?, ?, 'restore', ?, ?)
            """, (
                prism_id,
                new_version,
                config_json,
                user_id,
                f"回滚到版本 {target_version}"
            ))

            conn.commit()

            return {
                "success": True,
                "new_version": new_version,
                "restored_from": target_version,
                "message": f"成功回滚到版本 {target_version}"
            }

        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            conn.close()

    def _calculate_config_diff(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        计算配置差异

        Returns:
            {
                "anchors_changed": ["soft", "hard"],  # 变更的锚点
                "lexicon_changed": bool,
                "added": [...],
                "removed": [...],
                "modified": {...}
            }
        """
        diff = {
            "anchors_changed": [],
            "lexicon_changed": False,
            "added": [],
            "removed": [],
            "modified": {}
        }

        # 比较锚点
        old_anchors = old_config.get('anchors', {})
        new_anchors = new_config.get('anchors', {})

        for anchor_name in set(list(old_anchors.keys()) + list(new_anchors.keys())):
            old_val = old_anchors.get(anchor_name)
            new_val = new_anchors.get(anchor_name)

            if old_val is None:
                diff['added'].append(anchor_name)
            elif new_val is None:
                diff['removed'].append(anchor_name)
            elif old_val != new_val:
                diff['anchors_changed'].append(anchor_name)
                diff['modified'][anchor_name] = {
                    "old": old_val,
                    "new": new_val
                }

        # 比较词汇表
        if old_config.get('lexicon') != new_config.get('lexicon'):
            diff['lexicon_changed'] = True

        return diff


# 便捷函数
def get_prism_version_manager(db_path: str = None) -> PrismVersionManager:
    """
    获取棱镜版本管理器实例

    Args:
        db_path: 数据库路径（可选）

    Returns:
        PrismVersionManager 实例
    """
    if db_path is None:
        from pathlib import Path
        current_dir = Path(__file__).parent
        db_path = str(current_dir / "database" / "capsules.db")

    return PrismVersionManager(db_path)
```

---

## 📝 实施步骤

### Day 1-2: 数据库改造

**任务清单**:
- [ ] 创建 `prism_schema.sql`
- [ ] 创建 `init_default_prisms.sql`
- [ ] 执行数据库迁移
- [ ] 验证表结构

**测试**:
```bash
cd data-pipeline
sqlite3 database/capsules.db < database/prism_schema.sql
sqlite3 database/capsules.db < database/init_default_prisms.sql

# 验证
sqlite3 database/capsules.db "
SELECT name, display_name, version FROM prisms;
"
```

### Day 3-4: 版本管理服务

**任务清单**:
- [ ] 实现 `PrismVersionManager`
- [ ] 单元测试
- [ ] 集成到 `sync_service.py`

### Day 5: REST API 端点

**任务清单**:
- [ ] GET /api/prisms - 获取所有棱镜
- [ ] GET /api/prisms/{name}/versions - 获取版本历史
- [ ] POST /api/prisms/{name}/versions/{version}/restore - 回滚
- [ ] POST /api/prisms/{name}/resolve-conflict - 解决冲突

### Day 6-7: 测试和文档

**任务清单**:
- [ ] 单元测试
- [ ] 集成测试
- [ ] API 文档
- [ ] 用户手册

---

## ❓ 需要你确认的问题

### Q1: 棱镜配置存储位置

当前棱镜配置有两个地方：
1. **代码中硬编码** (`anchor_editor.py`)
2. **CSV 文件** (`lexicon_*.csv`)

**问题**: 迁移到数据库后，如何处理？
- **A**: 保留代码作为默认配置，数据库作为用户自定义配置
- **B**: 完全迁移到数据库，废弃代码中的硬编码
- **C**: 混合模式 - 系统棱镜在代码，用户棱镜在数据库

### Q2: 默认冲突策略

你选择了 "latest"（最新时间），但有个细节：

**场景**: 用户在两台设备上同时修改同一棱镜
```
设备 A: 10:00 修改 texture → 版本 2
设备 B: 10:05 修改 texture → 版本 2（基于 10:00 之前的状态）
```

**问题**: 如何处理？
- **A**: 严格按时间戳（10:05 的版本胜出，覆盖 10:00 的修改）
- **B**: 检测到同时修改，提示用户手动选择
- **C**: 创建版本 3，合并两个版本的修改

### Q3: 回滚限制

**问题**: 是否允许回滚到任意历史版本？
- **A**: 是，可以回滚到任何版本
- **B**: 否，只能回滚到最近的 N 个版本（如 5 个）
- **C**: 系统棱镜不能回滚，用户棱镜可以

---

请回答这 3 个问题，我会据此完成最终的实施代码！
