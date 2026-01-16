"""
Tags 同步服务模块

提供棱镜关键词（Tags）的云端同步功能
实现动静分离架构：Tags 主要存储在数据库，metadata.json 仅作为快照
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TagsService:
    """Tags 同步服务类"""

    def __init__(self, db, supabase_client=None):
        """
        初始化 Tags 服务

        Args:
            db: 本地数据库实例（CapsuleDatabase）
            supabase_client: Supabase 客户端实例（可选）
        """
        self.db = db
        self.supabase = supabase_client

    def sync_tags_to_cloud(self, capsule_id: int, cloud_id: str, user_id: str) -> bool:
        """
        将本地 Tags 上传到云端数据库

        数据流：SQLite capsule_tags 表 → Supabase capsule_tags 表

        Args:
            capsule_id: 本地胶囊 ID
            cloud_id: 云端胶囊 ID
            user_id: 用户 ID

        Returns:
            是否成功
        """
        try:
            if not self.supabase:
                logger.warning("Supabase 客户端未初始化，跳过 Tags 云端同步")
                return False

            # 1. 从本地数据库读取 Tags
            self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT lens, word_id, word_cn, word_en, x, y
                FROM capsule_tags
                WHERE capsule_id = ?
            """, (capsule_id,))

            tags = []
            for row in cursor.fetchall():
                tags.append({
                    'lens': row[0],
                    'word_id': row[1],
                    'word_cn': row[2],
                    'word_en': row[3],
                    'x': row[4],
                    'y': row[5],
                })

            self.db.close()

            if not tags:
                logger.info(f"[TagsService] 胶囊 {capsule_id} 没有 Tags，跳过上传")
                return True

            # 2. 调用 Supabase 上传 Tags
            logger.info(f"[TagsService] → 上传 {len(tags)} 个 Tags 到云端...")
            success = self.supabase.upload_tags(user_id, cloud_id, tags)

            if success:
                logger.info(f"[TagsService]   ✓ Tags 上传成功")
                return True
            else:
                logger.error(f"[TagsService]   ✗ Tags 上传失败")
                return False

        except Exception as e:
            logger.error(f"[TagsService] 上传 Tags 异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def sync_tags_from_cloud(self, capsule_id: int, cloud_id: str) -> bool:
        """
        从云端数据库拉取 Tags 到本地

        数据流：Supabase capsule_tags 表 → SQLite capsule_tags 表

        Args:
            capsule_id: 本地胶囊 ID
            cloud_id: 云端胶囊 ID

        Returns:
            是否成功
        """
        try:
            if not self.supabase:
                logger.warning("Supabase 客户端未初始化，跳过 Tags 云端拉取")
                return False

            # 1. 从云端下载 Tags
            logger.info(f"[TagsService] ← 从云端拉取 Tags...")
            cloud_tags = self.supabase.download_capsule_tags(cloud_id)

            if not cloud_tags:
                logger.info(f"[TagsService]   ℹ 云端无 Tags")
                return True

            # 2. 更新本地数据库
            self.db.connect()
            cursor = self.db.conn.cursor()

            # 先删除旧的 Tags
            cursor.execute("DELETE FROM capsule_tags WHERE capsule_id = ?", (capsule_id,))

            # 插入新的 Tags
            for tag in cloud_tags:
                cursor.execute("""
                    INSERT INTO capsule_tags (capsule_id, lens, word_id, word_cn, word_en, x, y)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    capsule_id,
                    tag.get('lens_id') or tag.get('lens'),  # 兼容不同字段名
                    tag.get('word_id'),
                    tag.get('word_cn'),
                    tag.get('word_en'),
                    tag.get('x'),
                    tag.get('y')
                ))

            self.db.conn.commit()
            self.db.close()

            logger.info(f"[TagsService]   ✓ 已拉取 {len(cloud_tags)} 个 Tags 到本地")
            
            # 🔥 关键：聚合到 capsules.keywords 用于搜索
            self.db.aggregate_and_update_keywords(capsule_id)
            logger.info(f"[TagsService]   ✓ 已聚合关键词到 capsules.keywords")
            
            return True

        except Exception as e:
            logger.error(f"[TagsService] 拉取 Tags 异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def merge_tags_from_metadata(self, capsule_id: int, metadata_path: Path) -> bool:
        """
        从 metadata.json 文件导入 Tags 到本地数据库

        用于兼容旧胶囊或离线场景

        Args:
            capsule_id: 本地胶囊 ID
            metadata_path: metadata.json 文件路径

        Returns:
            是否成功
        """
        try:
            if not metadata_path.exists():
                logger.warning(f"[TagsService] metadata.json 不存在: {metadata_path}")
                return False

            # 1. 读取 metadata.json 中的 Tags
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                file_tags = metadata.get('tags', [])

            if not file_tags:
                logger.info(f"[TagsService] metadata.json 中无 Tags")
                return True

            # 2. 检查本地数据库是否已有 Tags
            self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM capsule_tags WHERE capsule_id = ?", (capsule_id,))
            existing_count = cursor.fetchone()[0]

            if existing_count > 0:
                logger.info(f"[TagsService] 本地已有 {existing_count} 个 Tags，跳过导入")
                self.db.close()
                return True

            # 3. 导入 Tags 到数据库
            for tag in file_tags:
                cursor.execute("""
                    INSERT INTO capsule_tags (capsule_id, lens, word_id, word_cn, word_en, x, y)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    capsule_id,
                    tag.get('lens'),
                    tag.get('word_id'),
                    tag.get('word_cn'),
                    tag.get('word_en'),
                    tag.get('x'),
                    tag.get('y')
                ))

            self.db.conn.commit()
            self.db.close()

            logger.info(f"[TagsService]   ✓ 已从 metadata.json 导入 {len(file_tags)} 个 Tags")
            
            # 🔥 关键：聚合到 capsules.keywords 用于搜索
            self.db.aggregate_and_update_keywords(capsule_id)
            logger.info(f"[TagsService]   ✓ 已聚合关键词到 capsules.keywords")
            
            return True

        except Exception as e:
            logger.error(f"[TagsService] 导入 Tags 异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def export_tags_to_metadata(self, capsule_id: int, metadata_path: Path) -> bool:
        """
        将数据库中的 Tags 导出到 metadata.json 文件

        用于生成 Tags 快照，便于离线查看

        Args:
            capsule_id: 本地胶囊 ID
            metadata_path: metadata.json 文件路径

        Returns:
            是否成功
        """
        try:
            # 1. 从数据库读取 Tags
            self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT lens, word_id, word_cn, word_en, x, y
                FROM capsule_tags
                WHERE capsule_id = ?
            """, (capsule_id,))

            tags = []
            for row in cursor.fetchall():
                tags.append({
                    'lens': row[0],
                    'word_id': row[1],
                    'word_cn': row[2],
                    'word_en': row[3],
                    'x': row[4],
                    'y': row[5],
                })

            self.db.close()

            # 2. 读取现有的 metadata.json
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            else:
                metadata = {}

            # 3. 更新 Tags 字段
            metadata['tags'] = tags
            metadata['tags_source'] = 'database'  # 标注数据来源

            # 4. 写回文件
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            logger.info(f"[TagsService]   ✓ 已导出 {len(tags)} 个 Tags 到 metadata.json")
            return True

        except Exception as e:
            logger.error(f"[TagsService] 导出 Tags 异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_tags(self, capsule_id: int) -> List[Dict[str, Any]]:
        """
        获取胶囊的 Tags

        Args:
            capsule_id: 本地胶囊 ID

        Returns:
            Tags 列表
        """
        try:
            self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT id, lens, word_id, word_cn, word_en, x, y
                FROM capsule_tags
                WHERE capsule_id = ?
            """, (capsule_id,))

            tags = []
            for row in cursor.fetchall():
                tags.append({
                    'id': row[0],
                    'lens': row[1],
                    'word_id': row[2],
                    'word_cn': row[3],
                    'word_en': row[4],
                    'x': row[5],
                    'y': row[6],
                })

            self.db.close()
            return tags

        except Exception as e:
            logger.error(f"[TagsService] 获取 Tags 异常: {e}")
            return []

    def update_tags(self, capsule_id: int, tags: List[Dict[str, Any]]) -> bool:
        """
        更新胶囊的 Tags

        Args:
            capsule_id: 本地胶囊 ID
            tags: Tags 列表

        Returns:
            是否成功
        """
        try:
            self.db.connect()
            cursor = self.db.conn.cursor()

            # 删除旧的 Tags
            cursor.execute("DELETE FROM capsule_tags WHERE capsule_id = ?", (capsule_id,))

            # 插入新的 Tags
            for tag in tags:
                cursor.execute("""
                    INSERT INTO capsule_tags (capsule_id, lens, word_id, word_cn, word_en, x, y)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    capsule_id,
                    tag.get('lens'),
                    tag.get('word_id'),
                    tag.get('word_cn'),
                    tag.get('word_en'),
                    tag.get('x'),
                    tag.get('y')
                ))

            self.db.conn.commit()
            self.db.close()

            logger.info(f"[TagsService]   ✓ 已更新 {len(tags)} 个 Tags")
            return True

        except Exception as e:
            logger.error(f"[TagsService] 更新 Tags 异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


# ==========================================
# 全局实例
# ==========================================

_tags_service_instance: Optional[TagsService] = None


def get_tags_service(db=None, supabase_client=None) -> TagsService:
    """
    获取 Tags 服务实例（单例模式）

    Args:
        db: 数据库实例（可选）
        supabase_client: Supabase 客户端（可选）

    Returns:
        TagsService 实例
    """
    global _tags_service_instance

    if _tags_service_instance is None:
        if db is None:
            from capsule_db import get_database
            db = get_database()
        
        if supabase_client is None:
            try:
                from supabase_client import get_supabase_client
                supabase_client = get_supabase_client()
            except:
                logger.warning("无法初始化 Supabase 客户端，Tags 云端同步功能将受限")

        _tags_service_instance = TagsService(db, supabase_client)

    return _tags_service_instance
