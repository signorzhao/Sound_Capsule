"""
胶囊数据库管理模块

提供 SQLite 数据库的初始化、连接和基本操作
"""

import sqlite3
import os
import logging
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


logger = logging.getLogger(__name__)


def _parse_plugin_list_value(raw_value):
    """
    容错解析 plugin_list：
    - 已是 list 直接返回
    - JSON 字符串（["a","b"]）优先 json.loads
    - Python 列表字面量（['a','b']）回退 ast.literal_eval
    - 其他格式返回 []
    """
    if isinstance(raw_value, list):
        return raw_value
    if raw_value is None:
        return []

    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


class CapsuleDatabase:
    """胶囊数据库管理类"""

    def __init__(self, db_path: str):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径（SQLite 格式）
        """
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """建立数据库连接"""
        try:
            self.conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,  # 增加超时时间到 30 秒，避免并发时的锁等待
                check_same_thread=False  # 允许多线程访问
            )
            self.conn.row_factory = sqlite3.Row  # 返回字典格式
            # 启用 WAL，降低读写并发锁冲突
            self.conn.execute("PRAGMA journal_mode=WAL;")
            return self.conn
        except sqlite3.Error as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def wal_checkpoint(self):
        """
        执行 WAL checkpoint，确保数据立即对其他连接可见
        
        修复：解决首次保存胶囊后预览音频无法播放的问题
        """
        self.connect()
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            logger.info("✓ [DB] WAL checkpoint 完成，数据已同步")
        except Exception as e:
            logger.warning(f"⚠️ [DB] WAL checkpoint 失败: {e}")
        finally:
            self.close()

    def get_capsule_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取胶囊

        Args:
            name: 胶囊名称

        Returns:
            胶囊数据字典或 None
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT * FROM capsules WHERE name = ?
            """, (name,))

            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        finally:
            self.close()

    def initialize(self, schema_file: str = None):
        """
        初始化数据库（创建表和索引）

        Args:
            schema_file: Schema 文件路径（可选）
        """
        if schema_file is None:
            # 从路径管理器获取 schema 路径
            from common import PathManager
            pm = PathManager.get_instance()
            schema_file = pm.schema_path

        if not Path(schema_file).exists():
            raise FileNotFoundError(f"Schema 文件不存在: {schema_file}")

        # 读取 Schema 文件
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # 执行 Schema
        self.connect()
        try:
            self.conn.executescript(schema_sql)
            # 保护性唯一约束：非空 cloud_id 在本地必须唯一，防止同一云胶囊出现重复本地记录
            try:
                self.conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_capsules_cloud_id_nonempty
                    ON capsules(cloud_id)
                    WHERE cloud_id IS NOT NULL AND TRIM(cloud_id) != ''
                """)
            except sqlite3.IntegrityError as e:
                # 历史库若已存在重复 cloud_id，不阻断启动，先告警后由清理逻辑处理
                logger.warning(f"⚠️ 无法创建 cloud_id 唯一索引（存在历史重复数据）: {e}")
            self.conn.commit()
            print(f"✓ 数据库初始化成功: {self.db_path}")
        finally:
            self.close()

    def verify_schema(self) -> Dict[str, Any]:
        """
        验证数据库 schema 是否完整
        
        检查所有必要的字段和表是否存在
        
        Returns:
            {
                'valid': bool,
                'missing_fields': List[str],
                'missing_tables': List[str]
            }
        """
        self.connect()
        
        try:
            cursor = self.conn.cursor()
            
            # 必需的字段列表（从完整数据库中提取）
            required_fields = {
                'id', 'uuid', 'name', 'project_name', 'theme_name', 'capsule_type',
                'file_path', 'preview_audio', 'rpp_file', 'created_at', 'updated_at',
                'cloud_status', 'cloud_id', 'cloud_version', 'files_downloaded', 'last_synced_at',
                'asset_status', 'local_wav_path', 'local_wav_size', 'local_wav_hash',
                'download_progress', 'download_started_at', 'preview_downloaded',
                'asset_last_accessed_at', 'asset_access_count', 'is_cache_pinned',
                'audio_uploaded',
                'owner_supabase_user_id', 'created_by', 'description', 'keywords'
            }
            
            # 获取当前字段
            cursor.execute("PRAGMA table_info(capsules)")
            current_fields = {row[1] for row in cursor.fetchall()}
            
            # 找出缺失的字段
            missing_fields = required_fields - current_fields
            
            # 检查必要的表
            required_tables = {'capsules', 'capsule_types', 'sync_status', 'prisms', 'prism_versions'}
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            current_tables = {row[0] for row in cursor.fetchall()}
            missing_tables = required_tables - current_tables
            
            # 检查表的列结构
            invalid_tables = []
            
            # 检查 sync_status 表
            if 'sync_status' in current_tables:
                cursor.execute("PRAGMA table_info(sync_status)")
                sync_status_fields = {row[1] for row in cursor.fetchall()}
                if 'sync_state' not in sync_status_fields:
                    invalid_tables.append('sync_status')
            
            # 检查 prisms 表
            if 'prisms' in current_tables:
                cursor.execute("PRAGMA table_info(prisms)")
                prisms_fields = {row[1] for row in cursor.fetchall()}
                # prisms 表必须包含 is_deleted 和 field_data 列
                if 'is_deleted' not in prisms_fields or 'field_data' not in prisms_fields:
                    invalid_tables.append('prisms')
            
            # 检查 capsule_types 表结构（必须包含 name_cn 和 gradient）
            if 'capsule_types' in current_tables:
                cursor.execute("PRAGMA table_info(capsule_types)")
                capsule_types_fields = {row[1] for row in cursor.fetchall()}
                if 'name_cn' not in capsule_types_fields or 'gradient' not in capsule_types_fields:
                    invalid_tables.append('capsule_types')
            
            is_valid = len(missing_fields) == 0 and len(missing_tables) == 0 and len(invalid_tables) == 0
            
            return {
                'valid': is_valid,
                'missing_fields': list(missing_fields),
                'missing_tables': list(missing_tables),
                'invalid_tables': invalid_tables,
                'current_fields_count': len(current_fields),
                'required_fields_count': len(required_fields)
            }
        finally:
            self.close()

    def insert_capsule(self, capsule_data: Dict[str, Any]) -> int:
        """
        插入胶囊记录

        Args:
            capsule_data: 胶囊数据字典

        Returns:
            新插入记录的 ID
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 插入胶囊主表
            # 🔐 包含 owner_supabase_user_id 用于所有权控制
            cursor.execute("""
                INSERT INTO capsules (
                    uuid, name, project_name, theme_name, capsule_type,
                    file_path, preview_audio, rpp_file, owner_supabase_user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                capsule_data['uuid'],
                capsule_data['name'],
                capsule_data.get('project_name'),
                capsule_data.get('theme_name'),
                capsule_data.get('capsule_type', 'magic'),  # 默认为 'magic'
                capsule_data['file_path'],
                capsule_data.get('preview_audio'),
                capsule_data.get('rpp_file'),
                capsule_data.get('owner_supabase_user_id')  # 🔐 胶囊所有者
            ))

            capsule_id = cursor.lastrowid

            # 插入元数据
            if 'metadata' in capsule_data:
                metadata = capsule_data['metadata']
                cursor.execute("""
                    INSERT INTO capsule_metadata (
                        capsule_id, bpm, duration, sample_rate,
                        plugin_count, plugin_list, has_sends,
                        has_folder_bus, tracks_included
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    capsule_id,
                    metadata.get('bpm'),
                    metadata.get('duration'),
                    metadata.get('sample_rate'),
                    metadata.get('plugin_count'),
                    json.dumps(metadata.get('plugin_list', [])),
                    metadata.get('has_sends'),
                    metadata.get('has_folder_bus'),
                    metadata.get('tracks_included')
                ))

            # 注意：不再为新胶囊创建 sync_status 记录
            # 云图标只显示关键词同步状态，胶囊上传通过单独的上传按钮完成
            # 这样 pending_count 只反映关键词待同步数量

            self.conn.commit()
            return capsule_id

        except sqlite3.IntegrityError as e:
            self.conn.rollback()
            raise ValueError(f"数据库约束违反: {e}")
        finally:
            self.close()

    def delete_capsule(self, capsule_id: int) -> bool:
        """
        删除胶囊及其所有关联数据
        
        Args:
            capsule_id: 胶囊 ID
            
        Returns:
            是否成功
        """
        self.connect()
        try:
            cursor = self.conn.cursor()
            
            # 删除标签
            cursor.execute('DELETE FROM capsule_tags WHERE capsule_id = ?', (capsule_id,))
            
            # 删除坐标
            cursor.execute('DELETE FROM capsule_coordinates WHERE capsule_id = ?', (capsule_id,))
            
            # 删除元数据
            cursor.execute('DELETE FROM capsule_metadata WHERE capsule_id = ?', (capsule_id,))
            
            # 删除同步状态（包括 capsules 和 capsule_tags 的记录）
            # 注意：mark_for_sync('capsule_tags', capsule_id) 存的是 capsule_id，所以用 capsule_id 匹配
            try:
                cursor.execute("DELETE FROM sync_status WHERE table_name='capsules' AND record_id=?", (capsule_id,))
                cursor.execute("DELETE FROM sync_status WHERE table_name='capsule_tags' AND record_id=?", (capsule_id,))
            except Exception:
                pass  # 表可能不存在

            # 删除胶囊
            cursor.execute('DELETE FROM capsules WHERE id = ?', (capsule_id,))
            
            if cursor.rowcount > 0:
                self.conn.commit()
                return True
            else:
                return False
                
        except Exception as e:
            self.conn.rollback()
            raise ValueError(f"删除胶囊失败: {e}")
        finally:
            self.close()

    def save_capsule_metadata(self, capsule_id: int, metadata: Dict[str, Any]) -> bool:
        """
        保存胶囊技术元数据到 capsule_metadata 表（插入或更新）
        
        用于同步下载 metadata.json 后写入数据库，或修复缺失的元数据。
        
        Args:
            capsule_id: 胶囊 ID
            metadata: 元数据字典，包含 bpm, duration, sample_rate, plugin_count, 
                     plugin_list, has_sends, has_folder_bus, tracks_included 等字段
        
        Returns:
            是否成功
        """
        self.connect()
        try:
            cursor = self.conn.cursor()
            
            # 解析 plugin_list：支持列表或已经是 JSON 字符串
            plugin_list = metadata.get('plugin_list', [])
            if isinstance(plugin_list, list):
                plugin_list_json = json.dumps(plugin_list)
            elif isinstance(plugin_list, str):
                # 已经是 JSON 字符串
                plugin_list_json = plugin_list
            else:
                plugin_list_json = '[]'
            
            # 使用 INSERT OR REPLACE 实现插入或更新
            cursor.execute("""
                INSERT OR REPLACE INTO capsule_metadata (
                    capsule_id, bpm, duration, sample_rate,
                    plugin_count, plugin_list, has_sends,
                    has_folder_bus, tracks_included
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                capsule_id,
                metadata.get('bpm'),
                metadata.get('duration'),
                metadata.get('sample_rate'),
                metadata.get('plugin_count'),
                plugin_list_json,
                metadata.get('has_sends'),
                metadata.get('has_folder_bus'),
                metadata.get('tracks_included')
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"[DB] 保存胶囊元数据失败 (capsule_id={capsule_id}): {e}")
            return False
        finally:
            self.close()

    def add_capsule_tags(self, capsule_id: int, tags: List[Dict[str, Any]]) -> bool:
        """
        添加语义标签

        Args:
            capsule_id: 胶囊 ID
            tags: 标签列表

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            print(f"[DB] 准备插入 {len(tags)} 个标签到胶囊 {capsule_id}")

            for idx, tag in enumerate(tags):
                word_id = tag.get('word_id')
                word_cn = tag.get('word_cn')
                word_en = tag.get('word_en')
                lens = tag.get('lens')
                x = tag.get('x')
                y = tag.get('y')

                # 如果 word_id 为空，生成一个默认值
                if not word_id:
                    # 优先使用 word_cn，其次 word_en，最后生成一个基于索引的唯一 ID
                    if word_cn:
                        word_id = f"custom_{word_cn}_{idx}"
                    elif word_en:
                        word_id = f"custom_{word_en}_{idx}"
                    else:
                        word_id = f"custom_tag_{capsule_id}_{lens}_{idx}"
                    print(f"[DB] word_id 为空，生成默认值: {word_id}")

                print(f"[DB] 标签 {idx+1}: lens={lens}, word_id={word_id}, word_cn={word_cn}, word_en={word_en}, x={x}, y={y}")

                cursor.execute("""
                    INSERT INTO capsule_tags (
                        capsule_id, lens, word_id, word_cn, word_en, x, y
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    capsule_id,
                    lens,
                    word_id,
                    word_cn,
                    word_en,
                    x,
                    y
                ))

            self.conn.commit()
            print(f"[DB] 成功提交 {len(tags)} 个标签")
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"[DB] 添加标签失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.close()

    def delete_capsule_tags(self, capsule_id: int) -> bool:
        """
        删除胶囊的所有标签

        Args:
            capsule_id: 胶囊 ID

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 删除该胶囊的所有标签
            cursor.execute("DELETE FROM capsule_tags WHERE capsule_id = ?", (capsule_id,))

            # 删除标签的同步状态（防止孤儿记录）
            # 注意：mark_for_sync('capsule_tags', capsule_id) 存的是 capsule_id
            try:
                cursor.execute("DELETE FROM sync_status WHERE table_name='capsule_tags' AND record_id=?", (capsule_id,))
            except Exception:
                pass  # 表可能不存在

            self.conn.commit()
            print(f"✓ 删除胶囊 {capsule_id} 的所有标签")
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"删除标签失败: {e}")
            return False
        finally:
            self.close()

    def replace_capsule_tags(self, capsule_id: int, tags: List[Dict[str, Any]]) -> bool:
        """
        替换胶囊的所有标签（先删除旧的，再添加新的）

        Args:
            capsule_id: 胶囊 ID
            tags: 新的标签列表

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 先删除该胶囊的所有旧标签
            cursor.execute("DELETE FROM capsule_tags WHERE capsule_id = ?", (capsule_id,))

            # 注意：不需要删除 sync_status，因为：
            # 1. mark_for_sync('capsule_tags', capsule_id) 用的是 capsule_id
            # 2. 替换标签后会重新调用 mark_for_sync，会更新或重建记录

            # 添加新标签
            for tag in tags:
                cursor.execute("""
                    INSERT INTO capsule_tags (
                        capsule_id, lens, word_id, word_cn, word_en, x, y
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    capsule_id,
                    tag['lens'],
                    tag['word_id'],
                    tag.get('word_cn'),
                    tag.get('word_en'),
                    tag.get('x'),
                    tag.get('y')
                ))

            self.conn.commit()
            print(f"✓ 替换胶囊 {capsule_id} 的标签: {len(tags)} 个")
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"替换标签失败: {e}")
            return False
        finally:
            self.close()

    def update_capsule_coordinates(self, capsule_id: int, coordinates: Dict[str, Dict[str, float]]) -> bool:
        """
        更新胶囊坐标

        Args:
            capsule_id: 胶囊 ID
            coordinates: 坐标字典
                {'texture': {'x': 50, 'y': 50}, ...}

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO capsule_coordinates (
                    capsule_id, texture_x, texture_y,
                    source_x, source_y, materiality_x, materiality_y,
                    temperament_x, temperament_y
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                capsule_id,
                coordinates.get('texture', {}).get('x'),
                coordinates.get('texture', {}).get('y'),
                coordinates.get('source', {}).get('x'),
                coordinates.get('source', {}).get('y'),
                coordinates.get('materiality', {}).get('x'),
                coordinates.get('materiality', {}).get('y'),
                coordinates.get('temperament', {}).get('x'),
                coordinates.get('temperament', {}).get('y')
            ))

            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"更新坐标失败: {e}")
            return False
        finally:
            self.close()

    def update_capsule_keywords(self, capsule_id: int, keywords: str) -> bool:
        """
        更新胶囊关键词

        Args:
            capsule_id: 胶囊 ID
            keywords: 关键词字符串（逗号分隔）

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                UPDATE capsules SET keywords = ? WHERE id = ?
            """, [keywords, capsule_id])

            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"更新关键词失败: {e}")
            return False
        finally:
            self.close()

    def aggregate_and_update_keywords(self, capsule_id: int) -> bool:
        """
        从 capsule_tags 表聚合所有标签，更新到 capsules.keywords 字段

        Args:
            capsule_id: 胶囊 ID

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 查询该胶囊的所有标签
            cursor.execute("""
                SELECT word_cn, word_en
                FROM capsule_tags
                WHERE capsule_id = ?
                AND (word_cn IS NOT NULL AND word_cn != ''
                     OR word_en IS NOT NULL AND word_en != '')
            """, (capsule_id,))

            tags = cursor.fetchall()

            # 聚合关键词：优先使用 word_cn，如果没有则使用 word_en
            keywords_list = []
            for word_cn, word_en in tags:
                if word_cn and word_cn.strip():
                    keywords_list.append(word_cn.strip())
                elif word_en and word_en.strip():
                    keywords_list.append(word_en.strip())

            # 用逗号连接成字符串
            keywords_str = ', '.join(keywords_list) if keywords_list else None

            print(f"[DB] 胶囊 {capsule_id} 聚合关键词: {keywords_str}")

            # 更新 capsules 表
            cursor.execute("""
                UPDATE capsules
                SET keywords = ?
                WHERE id = ?
            """, (keywords_str, capsule_id))

            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"[DB] 聚合关键词失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.close()

    def get_capsule(self, capsule_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个胶囊详情

        Args:
            capsule_id: 胶囊 ID

        Returns:
            胶囊数据字典或 None
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT * FROM capsules WHERE id = ?
            """, (capsule_id,))

            row = cursor.fetchone()

            if row:
                capsule = dict(row)

                # 获取技术元数据
                cursor.execute("""
                    SELECT bpm, duration, sample_rate, plugin_count, plugin_list,
                           has_sends, has_folder_bus, tracks_included
                    FROM capsule_metadata WHERE capsule_id = ?
                """, (capsule_id,))
                metadata_row = cursor.fetchone()

                if metadata_row:
                    # 解析 plugin_list（兼容 JSON / Python 列表字面量）
                    plugin_list = _parse_plugin_list_value(metadata_row[4])

                    # 构建前端期望的 metadata 格式
                    capsule['metadata'] = {
                        'bpm': metadata_row[0],
                        'duration': metadata_row[1],
                        'sample_rate': metadata_row[2],
                        'plugins': {
                            'count': metadata_row[3],
                            'list': plugin_list
                        },
                        'has_sends': metadata_row[5],
                        'has_folder_bus': metadata_row[6],
                        'tracks_included': metadata_row[7]
                    }

                # 获取标签
                cursor.execute("""
                    SELECT lens, word_id, word_cn, word_en, x, y
                    FROM capsule_tags WHERE capsule_id = ?
                """, (capsule_id,))
                tag_rows = cursor.fetchall()

                if tag_rows:
                    capsule['tags'] = [dict(row) for row in tag_rows]
                else:
                    capsule['tags'] = []

                return capsule
            return None

        finally:
            self.close()

    def get_capsule_tags(self, capsule_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取胶囊的所有标签（按棱镜分组）

        Args:
            capsule_id: 胶囊 ID

        Returns:
            按棱镜分组的标签字典:
            {
                'texture': [{'word_id': 'texture_123', 'word_cn': '粗糙', 'x': 50.0, 'y': 50.0}, ...],
                'source': [...],
                'materiality': [...],
                'temperament': [...]
            }
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT
                    lens,
                    word_id,
                    word_cn,
                    word_en,
                    x,
                    y
                FROM capsule_tags
                WHERE capsule_id = ?
                ORDER BY lens, word_cn
            """, (capsule_id,))

            rows = cursor.fetchall()

            # 动态按棱镜分组（支持任意棱镜，包括新创建的 mechanics 等）
            result = {}

            for row in rows:
                lens = row['lens']

                # 如果棱镜还不存在，初始化空数组
                if lens not in result:
                    result[lens] = []

                result[lens].append({
                    'word_id': row['word_id'],
                    'word_cn': row['word_cn'],
                    'word_en': row['word_en'],
                    'x': row['x'],
                    'y': row['y']
                })

            return result

        finally:
            self.close()

    def get_capsules(
        self,
        lens: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        radius: float = 20,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取胶囊列表（支持空间筛选）

        Args:
            lens: 语义棱镜类型（任意有效棱镜ID，如 texture/source/materiality/temperament/mechanics 等）
            x, y: 中心点坐标
            radius: 搜索半径
            limit: 返回数量限制
            offset: 偏移量（分页）

        Returns:
            胶囊列表
        """
        self.connect()

        try:
            cursor = self.conn.cursor()
            
            # 🔥 执行 WAL checkpoint，确保读取到最新数据
            # 解决上传成功后刷新列表时 metadata 可能不可见的问题
            try:
                cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass  # 忽略 checkpoint 错误

            if lens and x is not None and y is not None:
                # 空间查询
                x_col = f"{lens}_x"
                y_col = f"{lens}_y"

                query = f"""
                    SELECT
                        c.id, c.uuid, c.name, c.project_name,
                        c.theme_name, c.preview_audio, c.created_at,
                        cc.{x_col}, cc.{y_col}
                    FROM capsules c
                    JOIN capsule_coordinates cc ON c.id = cc.capsule_id
                    WHERE SQRT(POW(cc.{x_col} - ?, 2) + POW(cc.{y_col} - ?, 2)) <= ?
                    ORDER BY c.created_at DESC
                    LIMIT ? OFFSET ?
                """

                cursor.execute(query, (x, y, radius, limit, offset))

            else:
                # 普通查询 - 添加标签计数
                query = """
                    SELECT
                        c.*,
                        COUNT(ct.id) as tag_count
                    FROM capsules c
                    LEFT JOIN capsule_tags ct ON c.id = ct.capsule_id
                    GROUP BY c.id
                    ORDER BY c.created_at DESC
                    LIMIT ? OFFSET ?
                """

                cursor.execute(query, (limit, offset))

            rows = cursor.fetchall()
            capsules = [dict(row) for row in rows]

            # 为每个胶囊添加 metadata
            for capsule in capsules:
                cursor.execute("""
                    SELECT bpm, duration, sample_rate, plugin_count, plugin_list,
                           has_sends, has_folder_bus, tracks_included
                    FROM capsule_metadata WHERE capsule_id = ?
                """, (capsule['id'],))
                metadata_row = cursor.fetchone()

                if metadata_row:
                    # 解析 plugin_list（兼容 JSON / Python 列表字面量）
                    plugin_list = _parse_plugin_list_value(metadata_row[4])

                    # 构建前端期望的 metadata 格式
                    capsule['metadata'] = {
                        'bpm': metadata_row[0],
                        'duration': metadata_row[1],
                        'sample_rate': metadata_row[2],
                        'plugins': {
                            'count': metadata_row[3],
                            'list': plugin_list
                        },
                        'has_sends': metadata_row[5],
                        'has_folder_bus': metadata_row[6],
                        'tracks_included': metadata_row[7]
                    }

                # 获取标签
                cursor.execute("""
                    SELECT lens, word_id, word_cn, word_en, x, y
                    FROM capsule_tags WHERE capsule_id = ?
                """, (capsule['id'],))
                tag_rows = cursor.fetchall()

                if tag_rows:
                    capsule['tags'] = [dict(row) for row in tag_rows]
                else:
                    capsule['tags'] = []

            return capsules


        finally:
            self.close()

    def get_all_capsules(self) -> List[Dict[str, Any]]:
        """
        获取所有胶囊（用于库浏览）

        Returns:
            胶囊列表，包含 metadata
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT
                    c.*,
                    GROUP_CONCAT(ct.word_cn) as tags_cn
                FROM capsules c
                LEFT JOIN capsule_tags ct ON c.id = ct.capsule_id
                GROUP BY c.id
                ORDER BY c.created_at DESC
            """)

            rows = cursor.fetchall()
            capsules = [dict(row) for row in rows]

            # 为每个胶囊添加 metadata
            for capsule in capsules:
                cursor.execute("""
                    SELECT bpm, duration, sample_rate, plugin_count, plugin_list,
                           has_sends, has_folder_bus, tracks_included
                    FROM capsule_metadata WHERE capsule_id = ?
                """, (capsule['id'],))
                metadata_row = cursor.fetchone()

                if metadata_row:
                    # 解析 plugin_list（兼容 JSON / Python 列表字面量）
                    plugin_list = _parse_plugin_list_value(metadata_row[4])

                    # 构建前端期望的 metadata 格式
                    capsule['metadata'] = {
                        'bpm': metadata_row[0],
                        'duration': metadata_row[1],
                        'sample_rate': metadata_row[2],
                        'plugins': {
                            'count': metadata_row[3],
                            'list': plugin_list
                        },
                        'has_sends': metadata_row[5],
                        'has_folder_bus': metadata_row[6],
                        'tracks_included': metadata_row[7]
                    }

            return capsules

        finally:
            self.close()

    # ==========================================
    # 胶囊类型管理
    # ==========================================

    def get_all_capsule_types(self) -> List[Dict[str, Any]]:
        """
        获取所有胶囊类型

        Returns:
            胶囊类型列表
        """
        self.connect()

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM capsule_types
                ORDER BY sort_order ASC, created_at ASC
            """)
            rows = cursor.fetchall()

            # 解析JSON字段
            types = []
            for row in rows:
                type_dict = dict(row)
                if type_dict.get('examples'):
                    try:
                        type_dict['examples'] = json.loads(type_dict['examples'])
                    except:
                        type_dict['examples'] = []
                types.append(type_dict)

            return types

        finally:
            self.close()

    def update_capsule_type_and_get(self, capsule_id: int, capsule_type: str) -> Optional[Dict[str, Any]]:
        """
        更新胶囊类型并立即返回更新后的完整胶囊数据

        Args:
            capsule_id: 胶囊 ID
            capsule_type: 新的胶囊类型

        Returns:
            更新后的完整胶囊数据字典或 None
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 更新前先查询当前数据（用于调试）
            cursor.execute("SELECT * FROM capsules WHERE id = ?", (capsule_id,))
            before_row = cursor.fetchone()
            if before_row:
                before_data = dict(before_row)
                print(f"📋 更新前的数据 (ID {capsule_id}):")
                print(f"  - name: {before_data.get('name')}")
                print(f"  - capsule_type: {before_data.get('capsule_type')}")
                print(f"  - preview_audio: {before_data.get('preview_audio')}")
                print(f"  - file_path: {before_data.get('file_path')}")

            # 更新胶囊类型
            cursor.execute("""
                UPDATE capsules SET capsule_type = ? WHERE id = ?
            """, [capsule_type, capsule_id])

            # 提交更新
            self.conn.commit()
            print(f"✓ 已更新胶囊类型: ID {capsule_id} -> {capsule_type}")

            # 立即查询更新后的数据（使用同一个连接）
            cursor.execute("""
                SELECT * FROM capsules WHERE id = ?
            """, (capsule_id,))

            row = cursor.fetchone()

            if row:
                updated_capsule = dict(row)
                print(f"✓ 立即读取到更新后的数据:")
                print(f"  - id: {updated_capsule.get('id')}")
                print(f"  - name: {updated_capsule.get('name')}")
                print(f"  - capsule_type: {updated_capsule.get('capsule_type')}")
                print(f"  - preview_audio: {updated_capsule.get('preview_audio')}")
                print(f"  - file_path: {updated_capsule.get('file_path')}")
                return updated_capsule
            else:
                print(f"⚠ 无法读取胶囊数据: ID {capsule_id}")
                return None

        except Exception as e:
            self.conn.rollback()
            print(f"✗ 更新胶囊类型失败: {e}")
            raise
        finally:
            self.close()

    def get_capsule_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个胶囊类型

        Args:
            type_id: 胶囊类型ID

        Returns:
            胶囊类型数据或 None
        """
        self.connect()

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM capsule_types WHERE id = ?", (type_id,))
            row = cursor.fetchone()

            if not row:
                return None

            type_dict = dict(row)
            if type_dict.get('examples'):
                try:
                    type_dict['examples'] = json.loads(type_dict['examples'])
                except:
                    type_dict['examples'] = []

            return type_dict

        finally:
            self.close()

    def create_capsule_type(self, type_data: Dict[str, Any]) -> bool:
        """
        创建胶囊类型

        Args:
            type_data: 胶囊类型数据

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 处理examples字段
            examples = type_data.get('examples', [])
            if isinstance(examples, list):
                examples = json.dumps(examples, ensure_ascii=False)

            cursor.execute("""
                INSERT INTO capsule_types
                (id, name, name_cn, description, icon, color, gradient, examples, priority_lens, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                type_data['id'],
                type_data['name'],
                type_data['name_cn'],
                type_data.get('description', ''),
                type_data.get('icon', '📦'),
                type_data['color'],
                type_data['gradient'],
                examples,
                type_data.get('priority_lens', 'texture'),
                type_data.get('sort_order', 999)
            ))

            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"创建胶囊类型失败: {e}")
            return False

        finally:
            self.close()

    def update_capsule_type(self, type_id: str, type_data: Dict[str, Any]) -> bool:
        """
        更新胶囊类型

        Args:
            type_id: 胶囊类型ID
            type_data: 更新的数据

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 构建更新SQL
            updates = []
            values = []

            for field in ['name', 'name_cn', 'description', 'icon', 'color', 'gradient', 'priority_lens', 'sort_order']:
                if field in type_data:
                    updates.append(f"{field} = ?")
                    values.append(type_data[field])

            if 'examples' in type_data:
                examples = type_data['examples']
                if isinstance(examples, list):
                    examples = json.dumps(examples, ensure_ascii=False)
                updates.append("examples = ?")
                values.append(examples)

            if not updates:
                return False

            values.append(type_id)
            sql = f"UPDATE capsule_types SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"

            cursor.execute(sql, values)
            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"更新胶囊类型失败: {e}")
            return False

        finally:
            self.close()

    def delete_capsule_type(self, type_id: str) -> bool:
        """
        删除胶囊类型

        Args:
            type_id: 胶囊类型ID

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM capsule_types WHERE id = ?", (type_id,))
            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            self.conn.rollback()
            print(f"删除胶囊类型失败: {e}")
            return False

        finally:
            self.close()

    # ==========================================
    # Phase B: 混合存储策略 - 资产状态管理
    # ==========================================

    def get_capsule_asset_status(self, capsule_id: int) -> Optional[Dict[str, Any]]:
        """
        获取胶囊资产状态摘要（Phase B）

        Args:
            capsule_id: 胶囊 ID

        Returns:
            资产状态字典：
            {
                'capsule_id': int,
                'asset_status': str,  # 'local', 'cloud_only', 'downloading', 'cached'
                'cloud_status': str,  # 'local', 'synced', 'pending', 'conflict'
                'local_wav_path': str or None,
                'local_wav_size': int or None,
                'download_progress': int,  # 0-100
                'preview_downloaded': bool,
                'is_cache_pinned': bool
            }
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT
                    id as capsule_id,
                    asset_status,
                    cloud_status,
                    local_wav_path,
                    local_wav_size,
                    local_wav_hash,
                    download_progress,
                    download_started_at,
                    preview_downloaded,
                    asset_last_accessed_at,
                    asset_access_count,
                    is_cache_pinned
                FROM capsules
                WHERE id = ?
            """, (capsule_id,))

            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        finally:
            self.close()

    def update_asset_status(self, capsule_id: int, asset_status: str) -> bool:
        """
        更新资产状态（Phase B）

        Args:
            capsule_id: 胶囊 ID
            asset_status: 新的资产状态
                'local' - 文件在本地
                'cloud_only' - 仅元数据在本地，文件在云端
                'downloading' - 正在从云端下载文件
                'cached' - 文件已从云端下载并缓存到本地

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                UPDATE capsules
                SET asset_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (asset_status, capsule_id))

            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            self.conn.rollback()
            print(f"更新资产状态失败: {e}")
            return False

        finally:
            self.close()

    def update_local_wav_info(
        self,
        capsule_id: int,
        local_wav_path: str,
        local_wav_size: int,
        local_wav_hash: str
    ) -> bool:
        """
        更新本地 WAV 文件信息（Phase B）

        Args:
            capsule_id: 胶囊 ID
            local_wav_path: 本地 WAV 文件绝对路径
            local_wav_size: 文件大小（字节）
            local_wav_hash: 文件 SHA256 哈希

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                UPDATE capsules
                SET local_wav_path = ?,
                    local_wav_size = ?,
                    local_wav_hash = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (local_wav_path, local_wav_size, local_wav_hash, capsule_id))

            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            self.conn.rollback()
            print(f"更新本地 WAV 信息失败: {e}")
            return False

        finally:
            self.close()

    def update_download_progress(
        self,
        capsule_id: int,
        progress: int,
        downloaded_bytes: int = None
    ) -> bool:
        """
        更新下载进度（Phase B）

        Args:
            capsule_id: 胶囊 ID
            progress: 进度百分比（0-100）
            downloaded_bytes: 已下载字节数（可选）

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            if downloaded_bytes is not None:
                cursor.execute("""
                    UPDATE capsules
                    SET download_progress = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (progress, capsule_id))
            else:
                cursor.execute("""
                    UPDATE capsules
                    SET download_progress = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (progress, capsule_id))

            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            self.conn.rollback()
            print(f"更新下载进度失败: {e}")
            return False

        finally:
            self.close()

    def set_cache_pinned(self, capsule_id: int, pinned: bool) -> bool:
        """
        设置缓存固定状态（Phase B）

        Args:
            capsule_id: 胶囊 ID
            pinned: 是否固定缓存

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                UPDATE capsules
                SET is_cache_pinned = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (1 if pinned else 0, capsule_id))

            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            self.conn.rollback()
            print(f"设置缓存固定状态失败: {e}")
            return False

        finally:
            self.close()

    def update_asset_access_stats(self, capsule_id: int) -> bool:
        """
        更新资产访问统计（LRU 缓存策略）（Phase B）

        每次访问胶囊文件时调用此方法，更新：
        - asset_last_accessed_at: 最后访问时间
        - asset_access_count: 访问次数

        Args:
            capsule_id: 胶囊 ID

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                UPDATE capsules
                SET asset_last_accessed_at = CURRENT_TIMESTAMP,
                    asset_access_count = asset_access_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (capsule_id,))

            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            self.conn.rollback()
            print(f"更新资产访问统计失败: {e}")
            return False

        finally:
            self.close()

    def create_download_task(self, task_data: Dict[str, Any]) -> int:
        """
        创建下载任务（Phase B）

        Args:
            task_data: 下载任务数据
                {
                    'capsule_id': int,
                    'file_type': str,  # 'preview', 'wav', 'rpp', 'audio_folder'
                    'remote_url': str,
                    'local_path': str,
                    'remote_size': int,  # 可选
                    'remote_hash': str,  # 可选
                    'priority': int  # 0-10，数字越大优先级越高
                }

        Returns:
            任务 ID
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                INSERT INTO download_tasks (
                    capsule_id, file_type, status,
                    remote_url, remote_size, remote_hash,
                    local_path,
                    priority
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_data['capsule_id'],
                task_data['file_type'],
                'pending',  # 初始状态
                task_data['remote_url'],
                task_data.get('remote_size'),
                task_data.get('remote_hash'),
                task_data['local_path'],
                task_data.get('priority', 0)
            ))

            self.conn.commit()

            # 更新胶囊状态为下载中
            self.update_asset_status(task_data['capsule_id'], 'downloading')

            return cursor.lastrowid

        except Exception as e:
            self.conn.rollback()
            print(f"创建下载任务失败: {e}")
            raise

        finally:
            self.close()

    def get_download_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        获取下载任务详情（Phase B）

        Args:
            task_id: 任务 ID

        Returns:
            任务数据字典或 None
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT * FROM download_tasks WHERE id = ?
            """, (task_id,))

            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        finally:
            self.close()

    def get_download_tasks_by_capsule(self, capsule_id: int) -> List[Dict[str, Any]]:
        """
        获取胶囊的所有下载任务（Phase B）

        Args:
            capsule_id: 胶囊 ID

        Returns:
            下载任务列表
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT * FROM download_tasks
                WHERE capsule_id = ?
                ORDER BY created_at DESC
            """, (capsule_id,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        finally:
            self.close()

    def get_pending_download_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取待处理的下载任务（按优先级排序）（Phase B）

        Args:
            limit: 返回数量限制

        Returns:
            下载任务列表
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT * FROM download_tasks
                WHERE status IN ('pending', 'paused')
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        finally:
            self.close()

    def update_download_task_status(
        self,
        task_id: int,
        status: str,
        progress: int = None,
        downloaded_bytes: int = None,
        speed: int = None,
        eta_seconds: int = None,
        error_message: str = None
    ) -> bool:
        """
        更新下载任务状态（Phase B）

        Args:
            task_id: 任务 ID
            status: 新状态
                'pending', 'downloading', 'completed', 'failed', 'paused', 'cancelled'
            progress: 进度百分比（0-100）
            downloaded_bytes: 已下载字节数
            speed: 下载速度（字节/秒）
            eta_seconds: 预计剩余时间（秒）
            error_message: 错误信息（失败时）

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 构建更新 SQL
            updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            values = [status]

            if progress is not None:
                updates.append("progress = ?")
                values.append(progress)

            if downloaded_bytes is not None:
                updates.append("downloaded_bytes = ?")
                values.append(downloaded_bytes)

            if speed is not None:
                updates.append("speed = ?")
                values.append(speed)

            if eta_seconds is not None:
                updates.append("eta_seconds = ?")
                values.append(eta_seconds)

            if error_message is not None:
                updates.append("error_message = ?")
                values.append(error_message)

            # 根据状态设置时间戳
            if status == 'downloading' and progress == 0:
                updates.append("started_at = CURRENT_TIMESTAMP")

            if status == 'completed':
                updates.append("completed_at = CURRENT_TIMESTAMP")

            values.append(task_id)

            sql = f"UPDATE download_tasks SET {', '.join(updates)} WHERE id = ?"

            cursor.execute(sql, values)
            self.conn.commit()

            # 如果任务完成，触发器会自动更新胶囊状态
            return cursor.rowcount > 0

        except Exception as e:
            self.conn.rollback()
            print(f"更新下载任务状态失败: {e}")
            return False

        finally:
            self.close()

    def add_to_cache(
        self,
        capsule_id: int,
        file_type: str,
        file_path: str,
        file_size: int,
        file_hash: str,
        is_pinned: bool = False,
        cache_priority: int = 0
    ) -> bool:
        """
        添加到缓存表（Phase B）

        Args:
            capsule_id: 胶囊 ID
            file_type: 文件类型 ('preview', 'wav', 'rpp', 'audio_folder')
            file_path: 本地文件绝对路径
            file_size: 文件大小（字节）
            file_hash: 文件 SHA256 哈希
            is_pinned: 是否固定缓存
            cache_priority: 缓存优先级（0-10）

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO local_cache
                (capsule_id, file_type, file_path, file_size, file_hash,
                 last_accessed_at, access_count, is_pinned, cache_priority,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (capsule_id, file_type, file_path, file_size, file_hash,
                  1 if is_pinned else 0, cache_priority))

            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"添加到缓存表失败: {e}")
            return False

        finally:
            self.close()

    def get_cache_entry(self, capsule_id: int, file_type: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存条目（Phase B）

        Args:
            capsule_id: 胶囊 ID
            file_type: 文件类型

        Returns:
            缓存条目字典或 None
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT * FROM local_cache
                WHERE capsule_id = ? AND file_type = ?
            """, (capsule_id, file_type))

            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        finally:
            self.close()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息（Phase B）

        Returns:
            缓存统计字典：
            {
                'total_cached_files': int,
                'total_cache_size': int,  # 字节
                'avg_access_count': float,
                'pinned_files_count': int,
                'pinned_files_size': int,
                'by_type': {
                    'preview': {'count': int, 'size': int},
                    'wav': {'count': int, 'size': int},
                    'rpp': {'count': int, 'size': int}
                }
            }
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            # 总体统计
            cursor.execute("""
                SELECT
                    COUNT(*) as total_cached_files,
                    SUM(file_size) as total_cache_size,
                    AVG(access_count) as avg_access_count,
                    COUNT(CASE WHEN is_pinned = 1 THEN 1 END) as pinned_files_count,
                    SUM(file_size) FILTER (WHERE is_pinned = 1) as pinned_files_size
                FROM local_cache
            """)
            row = cursor.fetchone()

            stats = {
                'total_cached_files': row[0] or 0,
                'total_cache_size': row[1] or 0,
                'avg_access_count': row[2] or 0.0,
                'pinned_files_count': row[3] or 0,
                'pinned_files_size': row[4] or 0,
                'by_type': {}
            }

            # 按类型统计
            cursor.execute("""
                SELECT
                    file_type,
                    COUNT(*) as count,
                    SUM(file_size) as size
                FROM local_cache
                GROUP BY file_type
            """)
            rows = cursor.fetchall()

            for row in rows:
                stats['by_type'][row[0]] = {
                    'count': row[1],
                    'size': row[2] or 0
                }

            return stats

        finally:
            self.close()

    def get_lru_cache_candidates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取 LRU 缓存清理候选列表（Phase B）

        返回最久未访问的缓存条目（排除固定缓存）

        Args:
            limit: 返回数量限制

        Returns:
            缓存条目列表（按 last_accessed_at ASC 排序）
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT
                    lc.id,
                    lc.capsule_id,
                    lc.file_type,
                    lc.file_path,
                    lc.file_size,
                    lc.last_accessed_at,
                    lc.access_count,
                    c.name as capsule_name
                FROM local_cache lc
                JOIN capsules c ON lc.capsule_id = c.id
                WHERE lc.is_pinned = 0
                ORDER BY lc.last_accessed_at ASC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        finally:
            self.close()

    def delete_cache_entry(self, capsule_id: int, file_type: str) -> bool:
        """
        删除缓存条目（Phase B）

        Args:
            capsule_id: 胶囊 ID
            file_type: 文件类型

        Returns:
            是否成功
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                DELETE FROM local_cache
                WHERE capsule_id = ? AND file_type = ?
            """, (capsule_id, file_type))

            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            self.conn.rollback()
            print(f"删除缓存条目失败: {e}")
            return False

        finally:
            self.close()

    def get_capsule_asset_summary(self, capsule_id: int) -> Optional[Dict[str, Any]]:
        """
        获取胶囊资产摘要（从视图）（Phase B）

        Args:
            capsule_id: 胶囊 ID

        Returns:
            资产摘要字典或 None
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT * FROM capsule_asset_summary
                WHERE id = ?
            """, (capsule_id,))

            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        finally:
            self.close()

    def get_download_queue_status(self) -> Dict[str, Any]:
        """
        获取下载队列状态（从视图）（Phase B）

        Returns:
            队列状态字典
        """
        self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("SELECT * FROM download_queue_status")
            row = cursor.fetchone()

            if row:
                return dict(row)
            return {}

        finally:
            self.close()

    def clear_all_capsules(self) -> Dict[str, int]:
        """
        清空所有胶囊数据（保留用户认证信息）
        
        用于路径变更时清空本地缓存
        
        Returns:
            删除的记录数统计
        """
        self.connect()
        
        try:
            cursor = self.conn.cursor()
            
            # 统计要删除的记录数
            cursor.execute("SELECT COUNT(*) FROM capsules")
            capsules_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM capsule_tags")
            tags_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM capsule_coordinates")
            coords_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM sync_status")
            sync_count = cursor.fetchone()[0]
            
            # 删除所有胶囊相关数据（保留用户表）
            # 使用 IF EXISTS 或 try-except 来安全删除可能不存在的表
            tables_to_clear = [
                "capsule_coordinates",
                "capsule_tags",
                "capsule_metadata",
                "local_cache",
                "download_queue",
                "sync_status",
                "capsules"
            ]
            
            for table in tables_to_clear:
                try:
                    cursor.execute(f"DELETE FROM {table}")
                except Exception as e:
                    # 表不存在时跳过
                    print(f"  跳过表 {table}: {e}")
                    pass
            
            # 重置自增ID
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='capsules'")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='capsule_tags'")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='capsule_coordinates'")
            
            self.conn.commit()
            
            print(f"✓ 已清空本地胶囊数据:")
            print(f"  - 胶囊: {capsules_count} 条")
            print(f"  - 标签: {tags_count} 条")
            print(f"  - 坐标: {coords_count} 条")
            print(f"  - 同步状态: {sync_count} 条")
            
            return {
                'capsules': capsules_count,
                'tags': tags_count,
                'coordinates': coords_count,
                'sync_status': sync_count
            }
            
        except Exception as e:
            self.conn.rollback()
            print(f"清空数据失败: {e}")
            raise
            
        finally:
            self.close()


# 便捷函数
def get_database(db_path: str = None) -> CapsuleDatabase:
    """
    获取数据库实例

    Args:
        db_path: 数据库路径（可选，不提供则从 PathManager 获取）

    Returns:
        CapsuleDatabase 实例
    """
    if db_path is None:
        # 从路径管理器获取数据库路径
        from common import PathManager
        pm = PathManager.get_instance()
        db_path = pm.db_path

    return CapsuleDatabase(str(db_path))


# 测试代码
if __name__ == '__main__':
    import sys

    db_path = "test_capsules.db"

    # 初始化数据库
    print("初始化数据库...")
    db = get_database(db_path)
    db.initialize()

    # 测试插入
    print("\n测试插入胶囊...")
    test_capsule = {
        'uuid': 'test-uuid-001',
        'name': '测试胶囊',
        'project_name': '测试项目',
        'theme_name': '测试主题',
        'file_path': '/test/path',
        'preview_audio': 'preview.ogg',
        'rpp_file': 'source.rpp',
        'metadata': {
            'bpm': 120.0,
            'duration': 10.5,
            'sample_rate': 48000,
            'plugin_count': 3,
            'plugin_list': ['ReaEQ', 'ReaComp', 'ReaDelay'],
            'has_sends': True,
            'has_folder_bus': False,
            'tracks_included': 2
        }
    }

    capsule_id = db.insert_capsule(test_capsule)
    print(f"✓ 插入胶囊 ID: {capsule_id}")

    # 测试添加标签
    print("\n测试添加标签...")
    test_tags = [
        {
            'lens': 'texture',
            'word_id': 'texture_42',
            'word_cn': '纯净',
            'word_en': 'Pure',
            'x': 85.2,
            'y': 30.1
        },
        {
            'lens': 'source',
            'word_id': 'source_12',
            'word_cn': '合成',
            'word_en': 'Synthetic',
            'x': 60.5,
            'y': 45.3
        }
    ]

    db.add_capsule_tags(capsule_id, test_tags)
    print(f"✓ 添加了 {len(test_tags)} 个标签")

    # 测试更新坐标
    print("\n测试更新坐标...")
    coords = {
        'texture': {'x': 75.5, 'y': 35.2},
        'source': {'x': 60.5, 'y': 45.3}
    }

    db.update_capsule_coordinates(capsule_id, coords)
    print(f"✓ 更新了坐标")

    # 测试查询
    print("\n测试查询胶囊...")
    capsule = db.get_capsule(capsule_id)
    print(f"✓ 查询到胶囊: {capsule['name']}")

    # 测试空间查询
    print("\n测试空间查询...")
    capsules = db.get_capsules(lens='texture', x=80, y=40, radius=20)
    print(f"✓ 找到 {len(capsules)} 个胶囊")

    # 清理测试数据库
    if '--cleanup' in sys.argv:
        os.remove(db_path)
        print(f"\n✓ 清理测试数据库: {db_path}")
