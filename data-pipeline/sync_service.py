"""
云端同步服务模块

提供本地数据库与云端 API 之间的数据同步功能
"""

import sqlite3
import hashlib
import json
import logging
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)
_UPLOAD_PROGRESS = {}
_UPLOAD_PROGRESS_LOCK = threading.Lock()


def _set_upload_progress(capsule_id: int, data: Dict[str, Any]) -> None:
    with _UPLOAD_PROGRESS_LOCK:
        _UPLOAD_PROGRESS[capsule_id] = {
            **data,
            'capsule_id': capsule_id,
            'updated_at': datetime.utcnow().isoformat()
        }


def _get_upload_progress(capsule_id: int) -> Optional[Dict[str, Any]]:
    with _UPLOAD_PROGRESS_LOCK:
        return _UPLOAD_PROGRESS.get(capsule_id)


def _clear_upload_progress(capsule_id: int) -> None:
    with _UPLOAD_PROGRESS_LOCK:
        _UPLOAD_PROGRESS.pop(capsule_id, None)
from pathlib import Path


class SyncService:
    """同步服务类"""

    def __init__(self, db_path: str, api_base_url: str = None):
        """
        初始化同步服务

        Args:
            db_path: 本地数据库路径
            api_base_url: 云端 API 基础 URL（可选）
        """
        self.db_path = db_path
        self.api_base_url = api_base_url or "https://api.soundcapsule.com/api/v2"

    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,  # 增加超时时间到 30 秒，避免并发时的锁等待
            check_same_thread=False  # 允许多线程访问
        )
        conn.row_factory = sqlite3.Row
        return conn

    def _has_local_audio_files(self, capsule_dir: Path) -> bool:
        """检查本地 Audio 文件夹是否包含音频文件"""
        audio_dir = capsule_dir / "Audio"
        if not audio_dir.exists() or not audio_dir.is_dir():
            return False
        for entry in audio_dir.iterdir():
            if entry.is_file() and not entry.name.startswith('.'):
                return True
        return False

    def _update_asset_status_if_needed(self, capsule_id: int, current_status: Optional[str], new_status: str) -> bool:
        """仅在需要时更新 asset_status"""
        if current_status == new_status:
            return False
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE capsules
                SET asset_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_status, capsule_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.warning(f"   ⚠️  更新 asset_status 失败: {capsule_id} - {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _save_metadata_to_db(self, capsule_id: int, metadata_path: Path) -> bool:
        """
        从 metadata.json 文件读取技术元数据并写入 capsule_metadata 表
        
        Args:
            capsule_id: 胶囊 ID
            metadata_path: metadata.json 文件路径
            
        Returns:
            是否成功
        """
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # 🔥 修复：支持两种 plugins 格式
            # 格式 1 (嵌套): {"plugins": {"count": 1, "list": [...]}}
            # 格式 2 (扁平): {"plugin_count": 1, "plugin_list": [...]}
            plugins = metadata.get('plugins', {})
            if isinstance(plugins, dict):
                plugin_count = plugins.get('count', metadata.get('plugin_count'))
                plugin_list = plugins.get('list', metadata.get('plugin_list', []))
            else:
                plugin_count = metadata.get('plugin_count')
                plugin_list = metadata.get('plugin_list', [])
            
            # 从 metadata.json 提取技术信息
            tech_metadata = {
                'bpm': metadata.get('bpm'),
                'duration': metadata.get('duration'),
                'sample_rate': metadata.get('sample_rate'),
                'plugin_count': plugin_count,
                'plugin_list': plugin_list,
                'has_sends': metadata.get('has_sends'),
                'has_folder_bus': metadata.get('has_folder_bus'),
                'tracks_included': metadata.get('tracks_included')
            }
            
            # 调用数据库方法保存
            from capsule_db import get_database
            db = get_database()
            success = db.save_capsule_metadata(capsule_id, tech_metadata)
            
            if success:
                logger.info(f"   📊 技术元数据已写入数据库")
            return success
            
        except json.JSONDecodeError as e:
            logger.warning(f"   ⚠️  metadata.json 解析失败: {e}")
            return False
        except Exception as e:
            logger.warning(f"   ⚠️  保存元数据失败: {e}")
            return False

    def repair_missing_metadata(self) -> Dict[str, Any]:
        """
        修复缺失的 capsule_metadata 数据
        
        扫描所有胶囊，检查 capsule_metadata 表是否有对应记录，
        如果没有，尝试从本地 metadata.json 文件读取并写入数据库。
        
        Returns:
            修复结果统计
        """
        from capsule_db import get_database
        from common import PathManager
        
        logger.info("🔧 开始修复缺失的技术元数据...")
        
        repaired = 0
        skipped = 0
        failed = 0
        errors = []
        
        try:
            pm = PathManager.get_instance()
            export_dir = pm.export_dir
            
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 查找缺失 capsule_metadata 的胶囊
                cursor.execute("""
                    SELECT c.id, c.name, c.file_path
                    FROM capsules c
                    LEFT JOIN capsule_metadata m ON c.id = m.capsule_id
                    WHERE m.capsule_id IS NULL
                """)
                missing_capsules = cursor.fetchall()
                
            finally:
                conn.close()
            
            if not missing_capsules:
                logger.info("   ✓ 所有胶囊都有技术元数据，无需修复")
                return {
                    'success': True,
                    'repaired': 0,
                    'skipped': 0,
                    'failed': 0,
                    'message': '所有胶囊都有技术元数据'
                }
            
            logger.info(f"   发现 {len(missing_capsules)} 个胶囊缺失技术元数据")
            
            for capsule in missing_capsules:
                cap_id = capsule['id'] if isinstance(capsule, sqlite3.Row) else capsule[0]
                cap_name = capsule['name'] if isinstance(capsule, sqlite3.Row) else capsule[1]
                cap_file_path = capsule['file_path'] if isinstance(capsule, sqlite3.Row) else capsule[2]
                
                # 构建 metadata.json 路径
                capsule_rel_path = cap_file_path or cap_name
                capsule_dir = Path(export_dir) / capsule_rel_path
                metadata_path = capsule_dir / "metadata.json"
                
                if not metadata_path.exists():
                    logger.warning(f"   ⚠️  {cap_name}: metadata.json 不存在，跳过")
                    skipped += 1
                    continue
                
                # 读取并写入数据库
                success = self._save_metadata_to_db(cap_id, metadata_path)
                
                if success:
                    logger.info(f"   ✓ {cap_name}: 技术元数据已修复")
                    repaired += 1
                else:
                    logger.error(f"   ✗ {cap_name}: 修复失败")
                    failed += 1
                    errors.append(f"{cap_name}: 写入数据库失败")
            
            logger.info(f"🔧 修复完成: 成功 {repaired}, 跳过 {skipped}, 失败 {failed}")
            
            return {
                'success': True,
                'repaired': repaired,
                'skipped': skipped,
                'failed': failed,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"❌ 修复失败: {e}")
            return {
                'success': False,
                'repaired': repaired,
                'skipped': skipped,
                'failed': failed,
                'errors': [str(e)]
            }

    def _dedupe_local_capsules(self) -> None:
        """去重本地同名同路径胶囊，保留一条记录"""
        from capsule_db import get_database

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, file_path, COUNT(*) as cnt
                FROM capsules
                WHERE name IS NOT NULL AND file_path IS NOT NULL
                GROUP BY name, file_path
                HAVING cnt > 1
            """)
            groups = cursor.fetchall()
        finally:
            conn.close()

        if not groups:
            return

        db = get_database()
        for group in groups:
            name = group['name'] if isinstance(group, sqlite3.Row) else group[0]
            file_path = group['file_path'] if isinstance(group, sqlite3.Row) else group[1]

            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, cloud_id, updated_at
                    FROM capsules
                    WHERE name = ? AND file_path = ?
                    ORDER BY updated_at DESC, id DESC
                """, (name, file_path))
                rows = cursor.fetchall()
            finally:
                conn.close()

            if not rows:
                continue

            # 优先保留有 cloud_id 的记录，其次按 updated_at/ID 取最新
            keep_id = None
            for row in rows:
                row_id = row['id'] if isinstance(row, sqlite3.Row) else row[0]
                row_cloud_id = row['cloud_id'] if isinstance(row, sqlite3.Row) else row[1]
                if row_cloud_id:
                    keep_id = row_id
                    break
            if keep_id is None:
                keep_id = rows[0]['id'] if isinstance(rows[0], sqlite3.Row) else rows[0][0]

            for row in rows:
                row_id = row['id'] if isinstance(row, sqlite3.Row) else row[0]
                if row_id == keep_id:
                    continue
                try:
                    db.delete_capsule(row_id)
                    logger.info(f"🧹 去重：删除重复胶囊 ID {row_id} ({name})")
                except Exception as e:
                    logger.warning(f"⚠️ 去重失败: {name} (ID {row_id}) - {e}")

    def upload_audio_folders(self, user_id: str, capsule_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        批量上传本地 Audio 文件夹（用于整体同步）
        """
        from supabase_client import get_supabase_client
        from common import PathManager

        supabase = get_supabase_client()
        if not supabase:
            return {
                'success': False,
                'uploaded': 0,
                'errors': ['Supabase 客户端未初始化']
            }

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if capsule_ids:
                placeholders = ",".join(["?"] * len(capsule_ids))
                cursor.execute(f"""
                    SELECT id, name, file_path, asset_status
                    FROM capsules
                    WHERE id IN ({placeholders})
                    ORDER BY id
                """, capsule_ids)
            else:
                cursor.execute("""
                    SELECT id, name, file_path, asset_status
                    FROM capsules
                    WHERE asset_status = 'local'
                    ORDER BY id
                """)

            rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            return {'success': True, 'uploaded': 0, 'errors': []}

        pm = PathManager.get_instance()
        uploaded = 0
        errors = []

        for row in rows:
            cap_id, cap_name, cap_file_path, asset_status = row
            capsule_rel_path = cap_file_path or cap_name
            capsule_dir = Path(pm.export_dir) / capsule_rel_path
            audio_dir = capsule_dir / "Audio"

            if not self._has_local_audio_files(capsule_dir):
                continue

            try:
                local_files = [
                    entry for entry in audio_dir.iterdir()
                    if entry.is_file() and not entry.name.startswith('.')
                    and entry.suffix.lower() in ['.wav', '.mp3', '.ogg', '.flac', '.aiff']
                ]
                remote_files = set(supabase.list_audio_files(user_id, capsule_rel_path))
                missing_files = [f for f in local_files if f.name not in remote_files]

                if not missing_files:
                    conn = self._get_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE capsules
                            SET audio_uploaded = 1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (cap_id,))
                        conn.commit()
                    finally:
                        conn.close()
                    continue

                result = supabase.upload_audio_files(
                    user_id=user_id,
                    capsule_folder_name=capsule_rel_path,
                    audio_files=missing_files
                )
                if result and result.get('success', False):
                    uploaded += 1
                    conn = self._get_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE capsules
                            SET audio_uploaded = 1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (cap_id,))
                        conn.commit()
                    finally:
                        conn.close()
                else:
                    errors.append(f"{cap_name}: Audio 上传失败")
            except Exception as e:
                errors.append(f"{cap_name}: {e}")

        return {
            'success': len(errors) == 0,
            'uploaded': uploaded,
            'errors': errors
        }

    def sync_tags_only(self, user_id: str) -> Dict[str, Any]:
        """
        只同步关键词数据（capsule_tags）
        
        双向同步：
        1. 上传本地修改过的关键词到云端
        2. 下载云端更新的关键词到本地
        
        只同步有变化的数据，通过 updated_at 比对
        """
        from supabase_client import get_supabase_client
        from tags_service import get_tags_service
        from capsule_db import get_database

        supabase = get_supabase_client()
        if not supabase:
            return {
                'success': False,
                'uploaded': 0,
                'downloaded': 0,
                'errors': ['Supabase 客户端未初始化']
            }

        uploaded = 0
        downloaded = 0
        errors = []

        try:
            db = get_database()
            tags_service = get_tags_service(db, supabase)
            
            # 1. 获取所有本地胶囊及其 cloud_id
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, cloud_id, updated_at
                    FROM capsules
                    WHERE cloud_id IS NOT NULL AND cloud_id != ''
                """)
                local_capsules = cursor.fetchall()
            finally:
                conn.close()

            logger.info(f"🏷️  开始关键词同步，共 {len(local_capsules)} 个已关联云端的胶囊（有 cloud_id）")
            if not local_capsules:
                logger.warning("🏷️  没有已同步到云端的胶囊（cloud_id 为空），请先对胶囊执行一次「同步到云端」再修改关键词并同步")

            for row in local_capsules:
                cap_id, cap_name, cloud_id, local_updated_at = row
                
                try:
                    # 2. 获取本地标签
                    local_tags = tags_service.get_tags(cap_id)
                    
                    # 2.1 获取本地 name, keywords, description（用于 embedding）
                    conn_kw = self._get_connection()
                    try:
                        cursor_kw = conn_kw.cursor()
                        cursor_kw.execute("SELECT name, keywords, description FROM capsules WHERE id = ?", (cap_id,))
                        row_kw = cursor_kw.fetchone()
                        cap_name_for_emb = row_kw[0] if row_kw else cap_name
                        local_keywords = row_kw[1] if row_kw and len(row_kw) > 1 else None
                        local_description = row_kw[2] if row_kw and len(row_kw) > 2 else None
                    finally:
                        conn_kw.close()
                    
                    # 3. 获取云端标签
                    cloud_tags = supabase.download_capsule_tags(cloud_id)
                    
                    # 4. 比对并决定同步方向
                    # 简单策略：以本地为准上传（因为用户只在本地修改）
                    if local_tags:
                        # 语义搜索（标签级）：先算主体+标签 embedding，再上传
                        tag_embeddings = []
                        try:
                            from capsule_embedding_service import update_embedding_for_cloud_capsule
                            ok, tag_embeddings = update_embedding_for_cloud_capsule(
                                supabase,
                                cloud_id,
                                name=cap_name_for_emb or "",
                                keywords=(local_keywords or ""),
                                description=(local_description or ""),
                                tags=local_tags,
                            )
                            if ok:
                                logger.info(f"   ✓ 已更新胶囊主体 embedding: {cap_name}")
                        except Exception as emb_ex:
                            logger.warning(f"更新胶囊 embedding 失败: {emb_ex}")

                        # 将本地标签上传到云端（含标签 embedding）
                        logger.info(f"   → 上传标签: {cap_name} (cloud_id={cloud_id}, {len(local_tags)} 个)")
                        success = supabase.upload_tags(user_id, cloud_id, local_tags, tag_embeddings=tag_embeddings or [])
                        if success:
                            uploaded += 1
                            logger.info(f"   ✓ 上传标签: {cap_name} ({len(local_tags)} 个)")
                            if local_keywords:
                                supabase.update_capsule_keywords(user_id, cap_id, local_keywords)
                                logger.info(f"   ✓ 更新云端 keywords: {local_keywords[:30]}...")
                        else:
                            err_msg = f"{cap_name}: 标签上传失败（请查看后端日志；若为 column 不存在，请在 Supabase 执行 005_cloud_capsule_tags_add_keyword_columns.sql）"
                            errors.append(err_msg)
                            logger.warning(f"   ✗ {err_msg}")
                    elif cloud_tags:
                        # 本地没有标签，从云端下载
                        conn = self._get_connection()
                        try:
                            cursor = conn.cursor()
                            # 先清除本地标签
                            cursor.execute("DELETE FROM capsule_tags WHERE capsule_id = ?", (cap_id,))
                            # 插入云端标签
                            for tag in cloud_tags:
                                cursor.execute("""
                                    INSERT INTO capsule_tags
                                    (capsule_id, lens, word_id, word_cn, word_en, x, y)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    cap_id,
                                    tag.get('lens') or tag.get('lens_id'),
                                    tag.get('word_id'),
                                    tag.get('word_cn'),
                                    tag.get('word_en'),
                                    tag.get('x'),
                                    tag.get('y')
                                ))
                            conn.commit()
                            downloaded += 1
                            logger.info(f"   ✓ 下载标签: {cap_name} ({len(cloud_tags)} 个)")
                            
                            # 🔥 关键：下载后立即聚合到 capsules.keywords（用于搜索）
                            self.db.aggregate_and_update_keywords(cap_id)
                            logger.info(f"   ✓ 聚合关键词到 capsules.keywords")
                        finally:
                            conn.close()
                            
                except Exception as e:
                    errors.append(f"{cap_name}: {str(e)}")
                    logger.warning(f"   ⚠️ 同步标签失败 {cap_name}: {e}")

            # 5. 清除 pending 状态（标签已同步）
            self._clear_tags_pending_status()

            logger.info(f"🏷️  关键词同步完成: 上传 {uploaded}, 下载 {downloaded}")

            return {
                'success': len(errors) == 0,
                'uploaded': uploaded,
                'downloaded': downloaded,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"关键词同步失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'uploaded': uploaded,
                'downloaded': downloaded,
                'errors': [str(e)]
            }

    def _clear_tags_pending_status(self):
        """清除标签相关的 pending 状态"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sync_status
                SET sync_state = 'synced',
                    last_sync_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE table_name = 'capsule_tags' AND sync_state = 'pending'
            """)
            conn.commit()
        finally:
            conn.close()

    def _generate_hash(self, data: Dict) -> str:
        """
        生成数据哈希值

        Args:
            data: 数据字典

        Returns:
            SHA256 哈希值
        """
        # 将字典转换为排序后的 JSON 字符串
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def mark_for_sync(self, table_name: str, record_id: int, operation: str = 'update') -> bool:
        """
        标记记录为待同步

        Args:
            table_name: 表名
            record_id: 记录 ID
            operation: 操作类型 ('create', 'update', 'delete')

        Returns:
            是否成功
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 检查记录是否已存在
            cursor.execute("""
                SELECT sync_state FROM sync_status
                WHERE table_name = ? AND record_id = ?
            """, (table_name, record_id))

            existing = cursor.fetchone()

            if existing:
                # 更新现有记录
                cursor.execute("""
                    UPDATE sync_status
                    SET sync_state = 'pending',
                        updated_at = ?
                    WHERE table_name = ? AND record_id = ?
                """, (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), table_name, record_id))
            else:
                # 插入新记录
                cursor.execute("""
                    INSERT INTO sync_status (table_name, record_id, sync_state)
                    VALUES (?, ?, 'pending')
                """, (table_name, record_id))

            # 记录日志
            cursor.execute("""
                INSERT INTO sync_log (table_name, operation, record_id, direction, status)
                VALUES (?, ?, ?, 'to_cloud', 'pending')
            """, (table_name, operation, record_id))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"❌ 标记同步失败: {e}")
            return False
        finally:
            conn.close()

    def get_pending_records(self, table_name: str = None) -> List[Dict]:
        """
        获取待同步的记录

        Args:
            table_name: 表名（可选，不指定则返回所有表）

        Returns:
            待同步记录列表
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            if table_name:
                cursor.execute("""
                    SELECT table_name, record_id, sync_state, local_version, cloud_version
                    FROM sync_status
                    WHERE sync_state = 'pending' AND table_name = ?
                    ORDER BY updated_at ASC
                """, (table_name,))
            else:
                cursor.execute("""
                    SELECT table_name, record_id, sync_state, local_version, cloud_version
                    FROM sync_status
                    WHERE sync_state = 'pending'
                    ORDER BY updated_at ASC
                """)

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def mark_as_synced(self, table_name: str, record_id: int, cloud_version: int = None) -> bool:
        """
        标记为已同步

        Args:
            table_name: 表名
            record_id: 记录 ID
            cloud_version: 云端版本号

        Returns:
            是否成功
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 获取当前记录
            cursor.execute("""
                SELECT local_version FROM sync_status
                WHERE table_name = ? AND record_id = ?
            """, (table_name, record_id))

            current = cursor.fetchone()
            if not current:
                return False

            # 更新为已同步状态
            new_local_version = current['local_version'] + 1

            cursor.execute("""
                UPDATE sync_status
                SET sync_state = 'synced',
                    local_version = ?,
                    cloud_version = ?,
                    last_sync_at = ?,
                    updated_at = ?
                WHERE table_name = ? AND record_id = ?
            """, (
                new_local_version,
                cloud_version,
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                table_name,
                record_id
            ))

            # 记录成功日志
            cursor.execute("""
                INSERT INTO sync_log (table_name, operation, record_id, direction, status, local_version, cloud_version)
                VALUES (?, 'sync', ?, 'to_cloud', 'success', ?, ?)
            """, (table_name, record_id, new_local_version, cloud_version))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"❌ 标记已同步失败: {e}")
            return False
        finally:
            conn.close()

    def record_sync_error(self, table_name: str, operation: str, record_id: int, error_message: str) -> bool:
        """
        记录同步错误

        Args:
            table_name: 表名
            operation: 操作类型
            record_id: 记录 ID
            error_message: 错误信息

        Returns:
            是否成功
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO sync_log (table_name, operation, record_id, direction, status, error_message)
                VALUES (?, ?, ?, 'to_cloud', 'failed', ?)
            """, (table_name, operation, record_id, error_message))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"❌ 记录错误失败: {e}")
            return False
        finally:
            conn.close()

    def get_sync_status(self) -> Dict[str, Any]:
        """
        获取同步状态概览

        Returns:
            同步状态字典，包含云端待下载数量
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 统计各种状态的记录数
            # 🔧 只统计 capsule_tags 的 pending 状态，云图标只显示关键词同步状态
            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN sync_state = 'synced' THEN 1 END) as synced_count,
                    COUNT(CASE WHEN sync_state = 'pending' AND table_name = 'capsule_tags' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN sync_state = 'conflict' THEN 1 END) as conflict_count,
                    MAX(last_sync_at) as last_sync_at
                FROM sync_status
            """)

            stats = cursor.fetchone()

            # 统计本地胶囊总数
            cursor.execute("SELECT COUNT(*) as local_count FROM capsules")
            local_capsules = cursor.fetchone()['local_count']

            # 获取云端胶囊数量（通过 cloud_capsules 表或 API）
            # 这里我们先简单实现：检查有多少个云端胶囊不在本地
            remote_count = 0
            try:
                # 本地 sidecar 场景允许不配置 service_role，此时跳过云端计数，
                # 避免每次 /sync/status 都触发 Supabase 初始化错误日志。
                if os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
                    from supabase_client import get_supabase_client
                    supabase = get_supabase_client()
                    if supabase:
                        # 获取当前激活用户（修复：使用 is_active 而不是固定 id = 1）
                        cursor.execute("SELECT supabase_user_id FROM users WHERE is_active = 1")
                        user_row = cursor.fetchone()
                        if user_row and user_row[0]:  # user_row 是元组，使用索引 [0]
                            user_id = user_row[0]

                            # 查询云端胶囊总数
                            remote_count = supabase.get_capsule_count(user_id)
                            if remote_count is None:
                                remote_count = 0
            except Exception:
                # 如果查询云端失败，remote_count 保持为 0
                pass

            # 计算待下载数量 = 云端总数 - 本地已同步的胶囊数
            # 如果云端有胶囊但本地没有，则需要下载
            remote_pending = max(0, remote_count - local_capsules)

            return {
                'synced_count': stats['synced_count'] or 0,
                'pending_count': stats['pending_count'] or 0,
                'conflict_count': stats['conflict_count'] or 0,
                'remote_count': remote_count,  # 云端胶囊总数
                'remote_pending': remote_pending,  # 待下载的胶囊数
                'last_sync_at': stats['last_sync_at']
            }

        finally:
            conn.close()

    def detect_conflicts(self, table_name: str, local_data: Dict, cloud_data: Dict) -> Optional[Dict]:
        """
        检测数据冲突

        Args:
            table_name: 表名
            local_data: 本地数据
            cloud_data: 云端数据

        Returns:
            冲突信息字典，如果没有冲突返回 None
        """
        # 生成哈希
        local_hash = self._generate_hash(local_data)
        cloud_hash = self._generate_hash(cloud_data)

        if local_hash == cloud_hash:
            return None  # 无冲突

        # 检测冲突类型
        if local_data.get('deleted_at') and not cloud_data.get('deleted_at'):
            return {'type': 'delete_conflict', 'local': local_data, 'cloud': cloud_data}
        elif cloud_data.get('deleted_at') and not local_data.get('deleted_at'):
            return {'type': 'delete_conflict', 'local': local_data, 'cloud': cloud_data}
        else:
            return {'type': 'data_conflict', 'local': local_data, 'cloud': cloud_data}

    def record_conflict(self, table_name: str, record_id: int, local_data: Dict, cloud_data: Dict, conflict_type: str) -> bool:
        """
        记录冲突

        Args:
            table_name: 表名
            record_id: 记录 ID
            local_data: 本地数据
            cloud_data: 云端数据
            conflict_type: 冲突类型

        Returns:
            是否成功
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO sync_conflicts (table_name, record_id, local_data, cloud_data, conflict_type)
                VALUES (?, ?, ?, ?, ?)
            """, (
                table_name,
                record_id,
                json.dumps(local_data),
                json.dumps(cloud_data),
                conflict_type
            ))

            # 更新同步状态为冲突
            cursor.execute("""
                UPDATE sync_status
                SET sync_state = 'conflict',
                    updated_at = ?
                WHERE table_name = ? AND record_id = ?
            """, (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), table_name, record_id))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"❌ 记录冲突失败: {e}")
            return False
        finally:
            conn.close()

    def resolve_conflict(self, conflict_id: int, resolution: str) -> bool:
        """
        解决冲突

        Args:
            conflict_id: 冲突记录 ID
            resolution: 解决方案 ('local', 'cloud', 'merge')

        Returns:
            是否成功
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 获取冲突记录
            cursor.execute("""
                SELECT table_name, record_id, local_data, cloud_data
                FROM sync_conflicts
                WHERE id = ?
            """, (conflict_id,))

            conflict = cursor.fetchone()
            if not conflict:
                return False

            # 根据解决方案处理
            table_name = conflict['table_name']
            record_id = conflict['record_id']

            if resolution == 'local':
                # 使用本地数据，上传到云端
                local_data = json.loads(conflict['local_data'])
                # TODO: 实现上传逻辑

            elif resolution == 'cloud':
                # 使用云端数据，下载到本地
                cloud_data = json.loads(conflict['cloud_data'])
                # TODO: 实现下载逻辑

            elif resolution == 'merge':
                # 合并数据
                # TODO: 实现合并逻辑
                pass

            # 标记冲突已解决
            cursor.execute("""
                UPDATE sync_conflicts
                SET resolved = 1,
                    resolution = ?,
                    resolved_at = ?
                WHERE id = ?
            """, (resolution, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), conflict_id))

            # 更新同步状态
            cursor.execute("""
                UPDATE sync_status
                SET sync_state = 'synced',
                    updated_at = ?
                WHERE table_name = ? AND record_id = ?
            """, (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), table_name, record_id))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"❌ 解决冲突失败: {e}")
            return False
        finally:
            conn.close()

    # ========== Phase G2: 仅下载模式（启动同步专用） ==========

    def download_only(self, user_id: str, include_previews: bool = True) -> Dict[str, Any]:
        """
        仅下载模式：只从云端下载数据，不上传本地变更

        用途：启动同步（BootSync），避免每次启动都上传本地数据

        Args:
            user_id: Supabase 用户 ID
            include_previews: 是否自动下载预览音频（默认 True）

        Returns:
            同步结果：{
                'success': bool,
                'downloaded_count': int,
                'preview_downloaded': int,
                'errors': List[str],
                'duration_seconds': float
            }
        """
        import time
        from supabase_client import get_supabase_client

        start_time = time.time()
        errors = []
        downloaded_count = 0
        preview_downloaded = 0

        logger.info("=" * 60)
        logger.info("🔄 仅下载模式（启动同步）")
        logger.info("=" * 60)
        logger.info(f"用户 ID: {user_id}")
        logger.info("⚠️  跳过本地数据上传")
        logger.info("")

        try:
            # 步骤 1: 下载云端胶囊元数据
            logger.info("📥 步骤 1: 下载全球胶囊元数据...")
            supabase = get_supabase_client()
            if supabase:
                cloud_capsules = supabase.download_capsules(user_id)

                if cloud_capsules:
                    logger.info(f"   发现 {len(cloud_capsules)} 个全球胶囊")

                    for cloud_capsule in cloud_capsules:
                        try:
                            # 检查本地是否存在（多级匹配：cloud_id -> name）
                            local_capsule = self._get_local_capsule_by_cloud_id(cloud_capsule['id'])
                            
                            # 🔥 如果 cloud_id 匹配失败，尝试用 name 匹配（防止本地扫描的胶囊未关联）
                            if not local_capsule:
                                local_capsule = self._get_local_capsule_by_name(cloud_capsule['name'])
                                if local_capsule:
                                    # 关联 cloud_id
                                    self._set_capsule_cloud_id(local_capsule['id'], cloud_capsule['id'])
                                    logger.info(f"   ℹ️ 通过名称匹配并关联 cloud_id: {cloud_capsule['name']}")

                            if local_capsule:
                                # 更新本地元数据（不覆盖本地修改）
                                self._update_local_capsule_metadata(local_capsule['id'], cloud_capsule)
                                owner_id = cloud_capsule.get('user_id', 'unknown')[:8]
                                logger.info(f"   ✓ 更新胶囊 {cloud_capsule['name']} (by {owner_id}...)")
                            else:
                                # 创建新胶囊（仅元数据）
                                new_capsule_id = self._create_local_capsule_from_cloud(cloud_capsule)
                                owner_id = cloud_capsule.get('user_id', 'unknown')[:8]
                                logger.info(f"   ✓ 新增胶囊 {cloud_capsule['name']} (by {owner_id}...)")
                                downloaded_count += 1

                        except Exception as e:
                            error_msg = f"同步胶囊 {cloud_capsule.get('name', 'Unknown')} 失败: {e}"
                            errors.append(error_msg)
                            logger.error(f"   ✗ {error_msg}")
                else:
                    logger.info("   云端暂无胶囊数据")
            else:
                logger.warning("   ⚠️  Supabase 客户端未初始化，跳过云端下载")

            logger.info("")

            # 步骤 2: 下载轻量资产文件（OGG 预览 + RPP 项目文件）
            logger.info("📥 步骤 2: 下载轻量资产文件（OGG + RPP）...")

            from capsule_db import get_database
            db = get_database()
            db.connect()
            cursor = db.conn.cursor()

            cursor.execute("""
                SELECT id, name, uuid, preview_audio, cloud_status, asset_status,
                       owner_supabase_user_id, cloud_id, file_path
                FROM capsules
                WHERE cloud_id IS NOT NULL
                ORDER BY id
            """)
            local_capsules = cursor.fetchall()

            db.close()

            if local_capsules:
                logger.info(f"   检查 {len(local_capsules)} 个胶囊的轻量资产...")

                for idx, cap in enumerate(local_capsules, 1):
                    cap_id, cap_name, cap_uuid, preview_audio, cloud_status, asset_status, owner_id, cloud_id, cap_file_path = cap

                    # 准备本地路径 - 从 PathManager 获取导出目录
                    from common import PathManager
                    pm = PathManager.get_instance()
                    export_dir = pm.export_dir
                    logger.info(f"   使用导出目录: {export_dir}")

                    capsule_rel_path = cap_file_path or cap_name
                    capsule_dir = Path(export_dir) / capsule_rel_path

                    # ✅ 状态自愈：如果本地有 Audio 文件夹，更新 asset_status
                    if self._has_local_audio_files(capsule_dir):
                        if self._update_asset_status_if_needed(cap_id, asset_status, 'local'):
                            logger.info(f"   ✨ 检测到本地音频，修正资产状态: {cap_name} -> local")
                        asset_status = 'local'
                    needs_download = []

                    try:
                        # 检查 metadata.json 文件
                        metadata_path = capsule_dir / "metadata.json"
                        if not metadata_path.exists():
                            needs_download.append(('metadata', 'metadata.json'))
                        
                        # 检查 OGG 预览文件
                        if preview_audio:
                            ogg_path = capsule_dir / preview_audio
                            if not ogg_path.exists():
                                needs_download.append(('preview', preview_audio))

                        # 检查 RPP 项目文件（使用胶囊名称）
                        rpp_filename = f"{cap_name}.rpp"
                        rpp_path = capsule_dir / rpp_filename
                        if not rpp_path.exists():
                            needs_download.append(('rpp', rpp_filename))

                        # 下载缺失的文件
                        if needs_download and owner_id:
                            if not supabase:
                                logger.warning(f"   ⚠️  Supabase 客户端未初始化，跳过文件下载")
                                break

                            for file_type, filename in needs_download:
                                try:
                                    print(f"   [{idx}/{len(local_capsules)}] 下载 {filename}", end='\r')

                                    # 构建本地路径
                                    local_path = capsule_dir / filename

                                    # 确保目录存在
                                    capsule_dir.mkdir(parents=True, exist_ok=True)

                                    # 调用下载
                                    # 注意：云端文件夹使用胶囊名称，而不是 uuid
                                    success = supabase.download_file(
                                        user_id=owner_id,
                                        capsule_folder_name=cap_name,
                                        file_type=file_type,
                                        local_path=str(local_path)
                                    )

                                    if success:
                                        if file_type == 'preview':
                                            preview_downloaded += 1
                                        logger.info(f"   ✓ [{idx}/{len(local_capsules)}] {filename}")
                                    else:
                                        logger.warning(f"   ✗ [{idx}/{len(local_capsules)}] {filename} 下载失败")

                                except Exception as e:
                                    error_msg = f"下载 {cap_name}/{filename} 失败: {e}"
                                    errors.append(error_msg)
                                    logger.error(f"   ✗ {error_msg}")

                        # 🏷️ 处理 Tags：优先使用云端数据库，文件作为备份
                        try:
                            from tags_service import get_tags_service
                            tags_service = get_tags_service()
                            
                            # 使用已解包的 cloud_id 变量
                            if cloud_id and supabase:
                                # 尝试从云端数据库拉取 Tags
                                logger.info(f"   🏷️  尝试从云端数据库拉取 Tags...")
                                tags_synced = tags_service.sync_tags_from_cloud(cap_id, cloud_id)
                                
                                if tags_synced:
                                    logger.info(f"   ✓ Tags 已从云端同步")
                                else:
                                    # 如果云端没有 Tags，尝试从 metadata.json 导入
                                    metadata_path = capsule_dir / "metadata.json"
                                    if metadata_path.exists():
                                        logger.info(f"   ⚠️  云端无 Tags，尝试从 metadata.json 导入...")
                                        tags_service.merge_tags_from_metadata(cap_id, metadata_path)
                            else:
                                # 离线模式：从 metadata.json 导入
                                metadata_path = capsule_dir / "metadata.json"
                                if metadata_path.exists():
                                    logger.info(f"   ℹ️  离线模式，从 metadata.json 导入 Tags...")
                                    tags_service.merge_tags_from_metadata(cap_id, metadata_path)
                        except Exception as e:
                            logger.warning(f"   ⚠️  Tags 处理失败: {e}")

                        # 📊 处理技术元数据：从 metadata.json 写入 capsule_metadata 表
                        try:
                            metadata_path = capsule_dir / "metadata.json"
                            if metadata_path.exists():
                                self._save_metadata_to_db(cap_id, metadata_path)
                        except Exception as e:
                            logger.warning(f"   ⚠️  元数据写入失败: {e}")

                    except Exception as e:
                        error_msg = f"检查 {cap_name} 资产失败: {e}"
                        errors.append(error_msg)
                        logger.error(f"   ✗ {error_msg}")

                logger.info("")
                logger.info(f"   ✓ 预览音频下载: {preview_downloaded} 个")
                logger.info("")

            else:
                logger.info("   ✓ 无需下载资产（本地暂无胶囊）")
                logger.info("")

        except Exception as e:
            error_msg = f"下载过程出错: {e}"
            errors.append(error_msg)
            logger.error(f"❌ {error_msg}")

        # 计算耗时
        duration = time.time() - start_time

        # 打印总结
        logger.info("=" * 60)
        logger.info("📊 仅下载完成")
        logger.info("=" * 60)
        logger.info(f"下载胶囊数: {downloaded_count}")
        logger.info(f"预览音频下载: {preview_downloaded}")
        logger.info(f"错误数量: {len(errors)}")
        logger.info(f"耗时: {duration:.2f} 秒")

        if errors:
            logger.info("")
            logger.error("错误详情:")
            for error in errors:
                logger.error(f"  • {error}")

        logger.info("=" * 60)
        logger.info("")

        return {
            'success': len(errors) == 0,
            'downloaded_count': downloaded_count,
            'preview_downloaded': preview_downloaded,
            'errors': errors,
            'duration_seconds': duration
        }

    # ========== Phase B.4: 轻量级同步（元数据 + 预览音频） ==========

    def sync_metadata_lightweight(self, user_id: str, include_previews: bool = True, capsule_ids: list = None) -> Dict[str, Any]:
        """
        轻量级同步：仅同步元数据 + 预览音频（可选）

        Args:
            user_id: Supabase 用户 ID
            include_previews: 是否自动下载预览音频（默认 True）
            capsule_ids: 指定要同步的胶囊 ID 列表（可选，为 None 则同步所有）

        Returns:
            同步结果：{
                'success': bool,
                'synced_count': int,
                'preview_downloaded': int,
                'errors': List[str],
                'duration_seconds': float
            }
        """
        import time
        from supabase_client import get_supabase_client

        start_time = time.time()
        errors = []
        synced_count = 0
        preview_downloaded = 0

        print("=" * 60)
        print("🔄 轻量级同步开始")
        print("=" * 60)
        print(f"用户 ID: {user_id}")
        print(f"包含预览音频: {include_previews}")
        print()

        try:
            # 0. 启动同步前先去重本地胶囊（避免同名重复）
            self._dedupe_local_capsules()

            # 1. 上传本地变更（元数据 + 文件）
            print("📤 步骤 1: 上传本地元数据变更...")
            
            # 🔧 关键修复：如果指定了 capsule_ids，强制上传这些胶囊（忽略同步状态）
            if capsule_ids:
                print(f"   🎯 强制上传指定的 {len(capsule_ids)} 个胶囊（忽略同步状态）")
                # 直接构造待上传列表，不检查 sync_status
                local_pending = [{'record_id': cid} for cid in capsule_ids]
            else:
                # 正常流程：只上传未同步的胶囊
                local_pending = self.get_pending_records('capsules')

            if local_pending:
                print(f"   发现 {len(local_pending)} 个待上传的胶囊")

                supabase = get_supabase_client()
                if not supabase:
                    print("   ⚠️  Supabase 客户端未初始化")
                    return {
                        'success': False,
                        'synced_count': 0,
                        'preview_downloaded': 0,
                        'errors': ['Supabase 客户端未初始化'],
                        'duration_seconds': time.time() - start_time
                    }

                for record in local_pending:
                    try:
                        record_id = record['record_id']
                        print(f"\n   🔍 [DEBUG] 开始处理胶囊 ID: {record_id}")
                        _set_upload_progress(record_id, {
                            'status': 'uploading',
                            'stage': '准备上传',
                            'percent': 5,
                            'message': '准备上传胶囊数据...'
                        })
                        
                        # 获取本地胶囊数据（仅元数据，不含 WAV）
                        capsule_data = self._get_capsule_metadata_only(record_id)
                        capsule_name = capsule_data.get('name', 'Unknown')
                        capsule_dir = capsule_data.get('file_path', '')
                        
                        print(f"   🔍 [DEBUG] 胶囊名称: {capsule_name}")
                        print(f"   🔍 [DEBUG] 胶囊目录: {capsule_dir}")

                        # 上传元数据到 Supabase Database（仅 keywords 更新）
                        print(f"   🔍 [DEBUG] 准备上传元数据到 Database...")
                        # 🔥 传入胶囊名称，防止切换文件夹后 local_id 变化导致重复上传
                        existing_cloud = supabase.get_cloud_capsule_by_local_id(user_id, capsule_data.get('id'), capsule_name)
                        result = None
                        if existing_cloud:
                            cloud_id = existing_cloud.get('id')
                            remote_meta = existing_cloud.get('metadata') or {}
                            remote_keywords = remote_meta.get('keywords') if isinstance(remote_meta, dict) else None
                            local_keywords = capsule_data.get('keywords')
                            if local_keywords != remote_keywords:
                                result = supabase.update_capsule_keywords(user_id, capsule_data.get('id'), local_keywords)
                            else:
                                result = existing_cloud
                        else:
                            result = supabase.upload_capsule(user_id, capsule_data)
                        print(f"   🔍 [DEBUG] 元数据上传结果: {result is not None}")

                        if result:
                            cloud_id = result.get('id') if result else None
                            print(f"   ✓ 上传胶囊元数据: {capsule_name} (cloud_id={cloud_id})")
                            _set_upload_progress(record_id, {
                                'status': 'uploading',
                                'stage': '上传元数据',
                                'percent': 10,
                                'message': '元数据上传完成'
                            })
                            
                            # 🔧 立即更新 cloud_id（防止文件上传失败导致数据不一致）
                            conn = self._get_connection()
                            try:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE capsules
                                    SET cloud_id = ?,
                                        cloud_version = ?
                                    WHERE id = ?
                                """, (cloud_id, result.get('version', 1), record_id))
                                conn.commit()
                                print(f"   ✓ 已设置 cloud_id")
                            finally:
                                conn.close()
                            
                            # 📁 上传文件到 Supabase Storage（原子化操作）
                            from common import PathManager
                            pm = PathManager.get_instance()
                            full_capsule_dir = pm.export_dir / capsule_dir
                            
                            print(f"\n   🔍 [DEBUG] ========== 文件上传检查 ==========")
                            print(f"   🔍 [DEBUG] 导出目录: {pm.export_dir}")
                            print(f"   🔍 [DEBUG] 胶囊目录: {capsule_dir}")
                            print(f"   🔍 [DEBUG] 完整路径: {full_capsule_dir}")
                            print(f"   🔍 [DEBUG] 目录是否存在? {full_capsule_dir.exists()}")
                            
                            # 🔒 原子化操作：所有文件必须全部上传成功
                            all_files_uploaded = True
                            upload_errors = []
                            
                            if full_capsule_dir.exists():
                                print(f"   🔍 [DEBUG] ✓ 目录存在，开始检查文件...")
                                _set_upload_progress(record_id, {
                                    'status': 'uploading',
                                    'stage': '检查文件',
                                    'percent': 15,
                                    'message': '检查本地文件...'
                                })
                                
                                # 🎵 上传预览音频
                                preview_audio = capsule_data.get('preview_audio')
                                print(f"   🔍 [DEBUG] 预览音频文件名: {preview_audio}")
                                if preview_audio:
                                    preview_path = full_capsule_dir / preview_audio
                                    print(f"   🔍 [DEBUG] 预览音频路径: {preview_path}")
                                    print(f"   🔍 [DEBUG] 预览音频存在? {preview_path.exists()}")
                                    if preview_path.exists():
                                        preview_exists = supabase.storage_file_exists(user_id, capsule_dir, preview_audio)
                                        if preview_exists:
                                            print(f"   ✓ 预览音频已存在于云端，跳过上传")
                                            _set_upload_progress(record_id, {
                                                'status': 'uploading',
                                                'stage': '上传预览音频',
                                                'percent': 20,
                                                'message': '预览音频已存在'
                                            })
                                        else:
                                            print(f"   → 上传预览音频: {preview_audio}")
                                            try:
                                                preview_result = supabase.upload_file(
                                                    user_id=user_id,
                                                    capsule_folder_name=capsule_dir,
                                                    file_type='preview',
                                                    file_path=str(preview_path)
                                                )
                                                if preview_result:
                                                    print(f"   ✓ 预览音频上传成功")
                                                    _set_upload_progress(record_id, {
                                                        'status': 'uploading',
                                                        'stage': '上传预览音频',
                                                        'percent': 20,
                                                        'message': '预览音频上传完成'
                                                    })
                                                else:
                                                    _err = getattr(supabase, 'get_last_storage_error', lambda: '')()
                                                    print(f"   ✗ 预览音频上传失败" + (f": {_err}" if _err else ""))
                                                    all_files_uploaded = False
                                                    upload_errors.append("预览音频上传失败" + (f": {_err}" if _err else ""))
                                            except Exception as e:
                                                print(f"   ✗ 预览音频上传异常: {e}")
                                                all_files_uploaded = False
                                                upload_errors.append(f"预览音频上传异常: {e}")
                                    else:
                                        print(f"   ✗ 预览音频文件不存在")
                                        all_files_uploaded = False
                                        upload_errors.append("预览音频文件不存在")
                                
                                # 📄 上传 RPP 项目文件
                                rpp_file = capsule_data.get('rpp_file')
                                print(f"   🔍 [DEBUG] RPP 文件名: {rpp_file}")
                                if rpp_file:
                                    rpp_path = full_capsule_dir / rpp_file
                                    print(f"   🔍 [DEBUG] RPP 路径: {rpp_path}")
                                    print(f"   🔍 [DEBUG] RPP 存在? {rpp_path.exists()}")
                                    if rpp_path.exists():
                                        rpp_exists = supabase.storage_file_exists(user_id, capsule_dir, rpp_file)
                                        if rpp_exists:
                                            print(f"   ✓ RPP 已存在于云端，跳过上传")
                                            _set_upload_progress(record_id, {
                                                'status': 'uploading',
                                                'stage': '上传 RPP',
                                                'percent': 30,
                                                'message': 'RPP 已存在'
                                            })
                                        else:
                                            print(f"   → 上传 RPP 文件: {rpp_file}")
                                            try:
                                                rpp_result = supabase.upload_file(
                                                    user_id=user_id,
                                                    capsule_folder_name=capsule_dir,
                                                    file_type='rpp',
                                                    file_path=str(rpp_path)
                                                )
                                                if rpp_result:
                                                    print(f"   ✓ RPP 文件上传成功")
                                                    _set_upload_progress(record_id, {
                                                        'status': 'uploading',
                                                        'stage': '上传 RPP',
                                                        'percent': 30,
                                                        'message': 'RPP 上传完成'
                                                    })
                                                else:
                                                    _err = getattr(supabase, 'get_last_storage_error', lambda: '')()
                                                    print(f"   ✗ RPP 文件上传失败" + (f": {_err}" if _err else ""))
                                                    all_files_uploaded = False
                                                    upload_errors.append("RPP 文件上传失败" + (f": {_err}" if _err else ""))
                                            except Exception as e:
                                                print(f"   ✗ RPP 文件上传异常: {e}")
                                                all_files_uploaded = False
                                                upload_errors.append(f"RPP 文件上传异常: {e}")
                                    else:
                                        print(f"   ✗ RPP 文件不存在")
                                        all_files_uploaded = False
                                        upload_errors.append("RPP 文件不存在")
                                
                                # 📋 上传 metadata.json 文件
                                metadata_file = full_capsule_dir / "metadata.json"
                                print(f"   🔍 [DEBUG] metadata.json 路径: {metadata_file}")
                                print(f"   🔍 [DEBUG] metadata.json 存在? {metadata_file.exists()}")
                                if metadata_file.exists():
                                    metadata_exists = supabase.storage_file_exists(user_id, capsule_dir, "metadata.json")
                                    if metadata_exists:
                                        print(f"   ✓ metadata.json 已存在于云端，跳过上传")
                                        _set_upload_progress(record_id, {
                                            'status': 'uploading',
                                            'stage': '上传 metadata.json',
                                            'percent': 40,
                                            'message': 'metadata.json 已存在'
                                        })
                                    else:
                                        print(f"   → 上传 metadata.json...")
                                        try:
                                            metadata_result = supabase.upload_file(
                                                user_id=user_id,
                                                capsule_folder_name=capsule_dir,
                                                file_type='metadata',
                                                file_path=str(metadata_file)
                                            )
                                            if metadata_result:
                                                print(f"   ✓ metadata.json 上传成功")
                                                _set_upload_progress(record_id, {
                                                    'status': 'uploading',
                                                    'stage': '上传 metadata.json',
                                                    'percent': 40,
                                                    'message': 'metadata.json 上传完成'
                                                })
                                            else:
                                                _err = getattr(supabase, 'get_last_storage_error', lambda: '')()
                                                print(f"   ✗ metadata.json 上传失败" + (f": {_err}" if _err else ""))
                                                all_files_uploaded = False
                                                upload_errors.append("metadata.json 上传失败" + (f": {_err}" if _err else ""))
                                        except Exception as e:
                                            print(f"   ✗ metadata.json 上传异常: {e}")
                                            all_files_uploaded = False
                                            upload_errors.append(f"metadata.json 上传异常: {e}")
                                else:
                                    print(f"   ⚠ metadata.json 不存在（可选文件，不影响同步）")

                                # 🎧 上传 Audio 文件夹（完整数据）
                                audio_folder = full_capsule_dir / "Audio"
                                print(f"   🔍 [DEBUG] Audio 路径: {audio_folder}")
                                print(f"   🔍 [DEBUG] Audio 存在? {audio_folder.exists()}")
                                if audio_folder.exists() and audio_folder.is_dir():
                                    audio_files = [
                                        entry for entry in audio_folder.iterdir()
                                        if entry.is_file() and not entry.name.startswith('.')
                                        and entry.suffix.lower() in ['.wav', '.mp3', '.ogg', '.flac', '.aiff']
                                    ]
                                    has_audio_files = len(audio_files) > 0
                                    if has_audio_files:
                                        remote_files = set(supabase.list_audio_files(user_id, capsule_dir))
                                        missing_files = [f for f in audio_files if f.name not in remote_files]
                                        if not missing_files:
                                            print(f"   ✓ Audio 文件夹已完整存在于云端，跳过上传")
                                            conn = self._get_connection()
                                            try:
                                                cursor = conn.cursor()
                                                cursor.execute("""
                                                    UPDATE capsules
                                                    SET audio_uploaded = 1,
                                                        updated_at = CURRENT_TIMESTAMP
                                                    WHERE id = ?
                                                """, (record_id,))
                                                conn.commit()
                                            finally:
                                                conn.close()
                                            _set_upload_progress(record_id, {
                                                'status': 'uploading',
                                                'stage': '上传 Audio',
                                                'percent': 100,
                                                'message': 'Audio 已存在'
                                            })
                                        else:
                                            print(f"   → 上传 Audio 文件夹（缺失 {len(missing_files)} 个文件）...")
                                            try:
                                                total_files = len(missing_files)

                                                def _audio_progress(uploaded, total, filename):
                                                    if total <= 0:
                                                        percent = 95
                                                    else:
                                                        percent = 40 + int((uploaded / total) * 60)
                                                    _set_upload_progress(record_id, {
                                                        'status': 'uploading',
                                                        'stage': '上传 Audio',
                                                        'percent': min(99, percent),
                                                        'current_file': filename,
                                                        'uploaded_files': uploaded,
                                                        'total_files': total,
                                                        'message': '上传音频文件...'
                                                    })

                                                audio_result = supabase.upload_audio_files(
                                                    user_id=user_id,
                                                    capsule_folder_name=capsule_dir,
                                                    audio_files=missing_files,
                                                    progress_callback=_audio_progress
                                                )
                                                if audio_result and audio_result.get('success', False):
                                                    print(f"   ✓ Audio 文件夹上传成功")
                                                    conn = self._get_connection()
                                                    try:
                                                        cursor = conn.cursor()
                                                        cursor.execute("""
                                                            UPDATE capsules
                                                            SET audio_uploaded = 1,
                                                                updated_at = CURRENT_TIMESTAMP
                                                            WHERE id = ?
                                                        """, (record_id,))
                                                        conn.commit()
                                                    finally:
                                                        conn.close()
                                                    _set_upload_progress(record_id, {
                                                        'status': 'uploading',
                                                        'stage': '上传 Audio',
                                                        'percent': 100,
                                                        'message': 'Audio 上传完成'
                                                    })
                                                else:
                                                    _err = getattr(supabase, 'get_last_storage_error', lambda: '')()
                                                    print(f"   ✗ Audio 文件夹上传失败" + (f": {_err}" if _err else ""))
                                                    all_files_uploaded = False
                                                    upload_errors.append("Audio 文件夹上传失败" + (f": {_err}" if _err else ""))
                                            except Exception as e:
                                                print(f"   ✗ Audio 文件夹上传异常: {e}")
                                                all_files_uploaded = False
                                                upload_errors.append(f"Audio 文件夹上传异常: {e}")
                                    else:
                                        print(f"   ✗ Audio 文件夹为空")
                                        all_files_uploaded = False
                                        upload_errors.append("Audio 文件夹为空")
                                else:
                                    print(f"   ✗ Audio 文件夹不存在")
                                    all_files_uploaded = False
                                    upload_errors.append("Audio 文件夹不存在")
                            else:
                                print(f"   ✗ 胶囊目录不存在: {full_capsule_dir}")
                                all_files_uploaded = False
                                upload_errors.append("胶囊目录不存在")
                            
                            # 🔒 关键决断点：只有所有文件都上传成功，才标记为 synced
                            if all_files_uploaded:
                                # 🏷️ 自动上传关键词到 cloud_capsule_tags 表
                                # 确保其他用户同步后能看到关键词
                                try:
                                    conn_tags = self._get_connection()
                                    cursor_tags = conn_tags.cursor()
                                    cursor_tags.execute("""
                                        SELECT lens, word_id, word_cn, word_en, x, y
                                        FROM capsule_tags
                                        WHERE capsule_id = ?
                                    """, (record_id,))
                                    local_tags = []
                                    for row in cursor_tags.fetchall():
                                        local_tags.append({
                                            'lens': row[0],
                                            'word_id': row[1],
                                            'word_cn': row[2],
                                            'word_en': row[3],
                                            'x': row[4],
                                            'y': row[5],
                                        })
                                    conn_tags.close()
                                    
                                    if local_tags and cloud_id:
                                        tag_embeddings = []
                                        try:
                                            from capsule_embedding_service import update_embedding_for_cloud_capsule
                                            ok, tag_embeddings = update_embedding_for_cloud_capsule(
                                                supabase,
                                                cloud_id,
                                                name=capsule_name or "",
                                                keywords=(capsule_data.get("keywords") or ""),
                                                description=(capsule_data.get("description") or ""),
                                                tags=local_tags,
                                            )
                                            if ok:
                                                print(f"   ✓ 已更新胶囊主体 embedding")
                                        except Exception as emb_ex:
                                            print(f"   ⚠️ 更新胶囊 embedding 失败: {emb_ex}")

                                        print(f"   🏷️  上传 {len(local_tags)} 个关键词到 cloud_capsule_tags...")
                                        tags_uploaded = supabase.upload_tags(user_id, cloud_id, local_tags, tag_embeddings=tag_embeddings or [])
                                        if tags_uploaded:
                                            print(f"   ✓ 关键词上传成功")
                                        else:
                                            print(f"   ⚠️ 关键词上传失败（不影响胶囊同步状态）")
                                    elif not local_tags:
                                        print(f"   ℹ️  该胶囊暂无关键词")
                                except Exception as tags_err:
                                    print(f"   ⚠️ 上传关键词异常: {tags_err}（不影响胶囊同步状态）")
                                
                                # 更新 sync_status 表
                                self.mark_as_synced('capsules', record_id)
                                
                                # 🔧 关键修复：同时更新 capsules 表的 cloud_status 字段
                                # 前端通过 capsule.cloud_status 判断状态，必须更新此字段
                                conn = self._get_connection()
                                try:
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE capsules
                                        SET cloud_status = 'synced',
                                            last_synced_at = CURRENT_TIMESTAMP
                                        WHERE id = ?
                                    """, (record_id,))
                                    conn.commit()
                                    print(f"   ✓ 已更新 capsules.cloud_status = 'synced'")
                                finally:
                                    conn.close()
                                
                                synced_count += 1
                                print(f"   ✅ 胶囊 {record_id} 完全同步成功")
                                _set_upload_progress(record_id, {
                                    'status': 'completed',
                                    'stage': '完成',
                                    'percent': 100,
                                    'message': '上传完成'
                                })
                            else:
                                error_msg = f"胶囊 {record_id} 文件上传不完整: {', '.join(upload_errors)}"
                                errors.append(error_msg)
                                print(f"   ⚠️ {error_msg}")
                                print(f"   ℹ️  状态保持为 'local'，下次同步时会重试")
                                _set_upload_progress(record_id, {
                                    'status': 'error',
                                    'stage': '失败',
                                    'percent': 100,
                                    'message': error_msg
                                })

                        else:
                            error_msg = f"上传胶囊 {record_id} 失败: result is None"
                            errors.append(error_msg)
                            print(f"   ✗ {error_msg}")
                            _set_upload_progress(record_id, {
                                'status': 'error',
                                'stage': '失败',
                                'percent': 100,
                                'message': error_msg
                            })

                    except Exception as e:
                        error_msg = f"上传胶囊 {record['record_id']} 失败: {e}"
                        errors.append(error_msg)
                        print(f"   ✗ {error_msg}")
                        import traceback
                        print(traceback.format_exc())
                        _set_upload_progress(record_id, {
                            'status': 'error',
                            'stage': '失败',
                            'percent': 100,
                            'message': error_msg
                        })
            else:
                print("   ✓ 无待上传的元数据")

            print()

            # 2. 下载云端变更（元数据）
            print("📥 步骤 2: 下载全球胶囊元数据...")
            print("   [GLOBAL SYNC] 拉取所有用户的胶囊（仅元数据）")
            supabase = get_supabase_client()
            if supabase:
                # 获取云端所有胶囊的元数据（Phase G: 全球同步）
                cloud_capsules = supabase.download_capsules(user_id)

                if cloud_capsules:
                    print(f"   [GLOBAL SYNC] 发现 {len(cloud_capsules)} 个全球胶囊")

                    # 统计不同用户的胶囊
                    user_stats = {}
                    for cap in cloud_capsules:
                        uid = cap.get('user_id', 'unknown')
                        user_stats[uid] = user_stats.get(uid, 0) + 1

                    print(f"   [GLOBAL SYNC] 用户分布: {user_stats}")

                    for cloud_capsule in cloud_capsules:
                        try:
                            # 检查本地是否存在
                            local_capsule = self._get_local_capsule_by_cloud_id(cloud_capsule['id'])

                            if local_capsule:
                                # 更新本地元数据
                                self._update_local_capsule_metadata(local_capsule['id'], cloud_capsule)
                                owner_id = cloud_capsule.get('user_id', 'unknown')[:8]
                                print(f"   ✓ 更新胶囊 {cloud_capsule['name']} (by {owner_id}...)")
                            else:
                                # 创建新胶囊（仅元数据）
                                new_capsule_id = self._create_local_capsule_from_cloud(cloud_capsule)
                                owner_id = cloud_capsule.get('user_id', 'unknown')[:8]
                                print(f"   ✓ 新增胶囊 {cloud_capsule['name']} (by {owner_id}...)")
                                synced_count += 1

                        except Exception as e:
                            error_msg = f"同步胶囊 {cloud_capsule.get('name', 'Unknown')} 失败: {e}"
                            errors.append(error_msg)
                            print(f"   ✗ {error_msg}")
                else:
                    print("   [GLOBAL SYNC] 云端暂无胶囊数据")
            else:
                print("   ⚠️  Supabase 客户端未初始化，跳过云端下载")

            print()

            # 3. 下载轻量资产文件（OGG 预览 + RPP 项目文件）
            logger.info("📥 步骤 3: 下载轻量资产文件（OGG + RPP）...")

            # 获取所有需要检查的本地胶囊（包括新增和更新的）
            from capsule_db import get_database
            db = get_database()
            db.connect()
            cursor = db.conn.cursor()

            cursor.execute("""
                SELECT id, name, uuid, preview_audio, cloud_status, asset_status,
                       owner_supabase_user_id, cloud_id, file_path
                FROM capsules
                WHERE cloud_id IS NOT NULL
                ORDER BY id
            """)
            local_capsules = cursor.fetchall()

            db.close()

            logger.info(f"   查询到 {len(local_capsules)} 个胶囊需要检查轻量资产")

            if local_capsules:
                logger.info(f"   检查 {len(local_capsules)} 个胶囊的轻量资产...")

                for idx, cap in enumerate(local_capsules, 1):
                    cap_id, cap_name, cap_uuid, preview_audio, cloud_status, asset_status, owner_id, cloud_id, cap_file_path = cap

                    logger.info(f"   [{idx}/{len(local_capsules)}] 检查胶囊: {cap_name}, owner_id: {owner_id}")

                    # 准备本地路径 - 从 PathManager 获取导出目录
                    from common import PathManager
                    pm = PathManager.get_instance()
                    export_dir = pm.export_dir
                    logger.info(f"   使用导出目录: {export_dir}")

                    capsule_rel_path = cap_file_path or cap_name
                    capsule_dir = Path(export_dir) / capsule_rel_path

                    # ✅ 状态自愈：如果本地有 Audio 文件夹，更新 asset_status
                    if self._has_local_audio_files(capsule_dir):
                        if self._update_asset_status_if_needed(cap_id, asset_status, 'local'):
                            logger.info(f"   ✨ 检测到本地音频，修正资产状态: {cap_name} -> local")
                        asset_status = 'local'
                    needs_download = []
                    current_file = ''

                    try:
                        # 检查 metadata.json 文件
                        metadata_path = capsule_dir / "metadata.json"
                        if not metadata_path.exists():
                            needs_download.append(('metadata', 'metadata.json'))
                            current_file = f"{cap_name}/metadata.json"
                            logger.info(f"      - 需要下载元数据: metadata.json")
                        
                        # 检查 OGG 预览文件
                        if preview_audio:
                            ogg_path = capsule_dir / preview_audio
                            if not ogg_path.exists():
                                needs_download.append(('preview', preview_audio))
                                if not current_file:
                                    current_file = f"{cap_name}/preview.{preview_audio.split('.')[-1]}"
                                logger.info(f"      - 需要下载预览音频: {preview_audio}")

                        # 检查 RPP 项目文件（使用胶囊名称）
                        rpp_filename = f"{cap_name}.rpp"
                        rpp_path = capsule_dir / rpp_filename
                        if not rpp_path.exists():
                            needs_download.append(('rpp', rpp_filename))
                            if not current_file:
                                current_file = f"{cap_name}/{rpp_filename}"
                            logger.info(f"      - 需要下载项目文件: {rpp_filename}")

                        if not needs_download:
                            logger.info(f"      ✓ 所有轻量资产已存在")

                        # 下载缺失的文件
                        if needs_download and owner_id:
                            supabase = get_supabase_client()
                            if not supabase:
                                logger.warning(f"   ⚠️  Supabase 客户端未初始化，跳过文件下载")
                                break

                            for file_type, filename in needs_download:
                                try:
                                    logger.info(f"   [{idx}/{len(local_capsules)}] 正在下载 {filename}...")

                                    # 构建本地路径
                                    local_path = capsule_dir / filename

                                    # 确保目录存在
                                    capsule_dir.mkdir(parents=True, exist_ok=True)

                                    # 调用下载
                                    # 注意：云端文件夹使用胶囊名称，而不是 uuid
                                    success = supabase.download_file(
                                        user_id=owner_id,
                                        capsule_folder_name=cap_name,
                                        file_type=file_type,
                                        local_path=str(local_path)
                                    )

                                    if success:
                                        if file_type == 'preview':
                                            preview_downloaded += 1
                                        logger.info(f"   ✓ [{idx}/{len(local_capsules)}] {filename} 下载成功")
                                    else:
                                        logger.error(f"   ✗ [{idx}/{len(local_capsules)}] {filename} 下载失败")

                                except Exception as e:
                                    error_msg = f"下载 {cap_name}/{filename} 失败: {e}"
                                    errors.append(error_msg)
                                    logger.error(f"   ✗ {error_msg}")
                        
                        # 🏷️ 处理 Tags：优先使用云端数据库，文件作为备份
                        try:
                            from tags_service import get_tags_service
                            tags_service = get_tags_service()
                            
                            # 使用已解包的 cloud_id 变量
                            if cloud_id and supabase:
                                # 尝试从云端数据库拉取 Tags
                                logger.info(f"   🏷️  尝试从云端数据库拉取 Tags...")
                                tags_synced = tags_service.sync_tags_from_cloud(cap_id, cloud_id)
                                
                                if tags_synced:
                                    logger.info(f"   ✓ Tags 已从云端同步")
                                else:
                                    # 如果云端没有 Tags，尝试从 metadata.json 导入
                                    metadata_path = capsule_dir / "metadata.json"
                                    if metadata_path.exists():
                                        logger.info(f"   ⚠️  云端无 Tags，尝试从 metadata.json 导入...")
                                        tags_service.merge_tags_from_metadata(cap_id, metadata_path)
                            else:
                                # 离线模式：从 metadata.json 导入
                                metadata_path = capsule_dir / "metadata.json"
                                if metadata_path.exists():
                                    logger.info(f"   ℹ️  离线模式，从 metadata.json 导入 Tags...")
                                    tags_service.merge_tags_from_metadata(cap_id, metadata_path)
                        except Exception as e:
                            logger.warning(f"   ⚠️  Tags 处理失败: {e}")

                        # 📊 处理技术元数据：从 metadata.json 写入 capsule_metadata 表
                        try:
                            metadata_path = capsule_dir / "metadata.json"
                            if metadata_path.exists():
                                self._save_metadata_to_db(cap_id, metadata_path)
                        except Exception as e:
                            logger.warning(f"   ⚠️  元数据写入失败: {e}")

                    except Exception as e:
                        error_msg = f"检查 {cap_name} 资产失败: {e}"
                        errors.append(error_msg)
                        logger.error(f"   ✗ {error_msg}")

                logger.info(f"   ✓ 预览音频下载: {preview_downloaded} 个")

            else:
                logger.info("   ✓ 无需下载资产（本地暂无胶囊）")

            # 4. 不自动下载源 WAV（按需下载）
            print("📥 步骤 4: 源 WAV 文件")
            print("   ℹ️  源 WAV 文件采用按需下载策略")
            print("   ℹ️  用户点击\"导入\"时才会下载 WAV")
            print()

        except Exception as e:
            error_msg = f"同步过程出错: {e}"
            errors.append(error_msg)
            print(f"❌ {error_msg}")

        # 计算耗时
        duration = time.time() - start_time

        # 打印总结
        print("=" * 60)
        print("📊 同步完成")
        print("=" * 60)
        print(f"同步胶囊数: {synced_count}")
        print(f"预览音频下载: {preview_downloaded}")
        print(f"错误数量: {len(errors)}")
        print(f"耗时: {duration:.2f} 秒")

        if errors:
            print()
            print("错误详情:")
            for error in errors:
                print(f"  • {error}")

        print("=" * 60)
        print()

        return {
            'success': len(errors) == 0,
            'synced_count': synced_count,
            'preview_downloaded': preview_downloaded,
            'errors': errors,
            'duration_seconds': duration
        }

    def _get_capsule_metadata_only(self, capsule_id: int) -> Dict[str, Any]:
        """
        获取胶囊元数据（不含 WAV 文件）

        Args:
            capsule_id: 胶囊 ID

        Returns:
            元数据字典
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    id, name, capsule_type, keywords, description,
                    created_at, updated_at, cloud_id,
                    cloud_status, asset_access_count,
                    file_path, preview_audio, rpp_file, owner_supabase_user_id
                FROM capsules
                WHERE id = ?
            """, (capsule_id,))

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"胶囊 {capsule_id} 不存在")

            return dict(row)

        finally:
            conn.close()

    def _get_local_capsule_by_cloud_id(self, cloud_id: str) -> Optional[Dict]:
        """
        根据 cloud_id 查找本地胶囊

        Args:
            cloud_id: 云端胶囊 ID (Supabase record ID)

        Returns:
            本地胶囊字典，不存在返回 None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, cloud_status, asset_status, owner_supabase_user_id
                FROM capsules
                WHERE cloud_id = ?
            """, (cloud_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

        finally:
            conn.close()

    def _get_local_capsule_by_name(self, name: str) -> Optional[Dict]:
        """
        根据名称查找本地胶囊（用于匹配本地扫描创建的胶囊）
        
        Args:
            name: 胶囊名称
            
        Returns:
            本地胶囊字典，不存在返回 None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, cloud_status, asset_status, owner_supabase_user_id, cloud_id
                FROM capsules
                WHERE name = ?
            """, (name,))

            row = cursor.fetchone()
            return dict(row) if row else None

        finally:
            conn.close()

    def _set_capsule_cloud_id(self, local_id: int, cloud_id: str) -> bool:
        """
        设置胶囊的 cloud_id（关联本地扫描的胶囊与云端记录）
        
        Args:
            local_id: 本地胶囊 ID
            cloud_id: 云端胶囊 ID
            
        Returns:
            是否成功
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # 🔥 同时设置 audio_uploaded = 1，因为云端已有完整数据
            cursor.execute("""
                UPDATE capsules
                SET cloud_id = ?, cloud_status = 'synced', audio_uploaded = 1
                WHERE id = ?
            """, (cloud_id, local_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"❌ 设置 cloud_id 失败: {e}")
            return False
        finally:
            conn.close()

    def _update_local_capsule_metadata(self, local_id: int, cloud_data: Dict) -> bool:
        """
        更新本地胶囊元数据（不覆盖 asset_status）

        Phase G: 添加 owner_supabase_user_id 更新
        Phase G2: 添加 preview_audio、keywords、description 等字段从 metadata 提取

        Args:
            local_id: 本地胶囊 ID
            cloud_data: 云端数据

        Returns:
            是否成功
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 先获取本地现有的 preview_audio 值（避免被云端空值覆盖）
            cursor.execute("SELECT preview_audio FROM capsules WHERE id = ?", (local_id,))
            local_row = cursor.fetchone()
            local_preview_audio = local_row['preview_audio'] if local_row else None

            # 从 metadata 中提取完整元数据
            metadata = cloud_data.get('metadata', {})
            if isinstance(metadata, dict):
                cloud_preview_audio = metadata.get('preview_audio')
                keywords = metadata.get('keywords')
                description = metadata.get('description')
                capsule_type = metadata.get('capsule_type', cloud_data.get('capsule_type', 'magic'))
            else:
                cloud_preview_audio = None
                keywords = cloud_data.get('keywords')
                description = cloud_data.get('description')
                capsule_type = cloud_data.get('capsule_type', 'magic')

            # ⚠️ 重要：只有云端有值时才覆盖本地，否则保留本地值
            preview_audio = cloud_preview_audio if cloud_preview_audio else local_preview_audio

            # 只更新元数据字段，保留 asset_status 和 cloud_status
            # ⚠️ 重要：不自动覆盖 cloud_status！
            # 如果本地状态是 'local'（需要上传），保持不变
            # 只有上传成功后才通过 mark_as_synced() 改为 'synced'
            cursor.execute("""
                UPDATE capsules
                SET
                    name = ?,
                    capsule_type = ?,
                    keywords = ?,
                    description = ?,
                    preview_audio = ?,
                    owner_supabase_user_id = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                cloud_data.get('name'),
                capsule_type,
                keywords,
                description,
                preview_audio,  # 优先使用云端值，否则保留本地值
                cloud_data.get('user_id'),  # Phase G: 更新所有者 ID
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                local_id
            ))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"❌ 更新本地胶囊失败: {e}")
            return False
        finally:
            conn.close()

    def _create_local_capsule_from_cloud(self, cloud_data: Dict) -> int:
        """
        从云端数据创建本地胶囊（仅元数据）

        Phase G: 添加 owner_supabase_user_id 字段以支持多用户共享
        Phase G2: 添加 preview_audio、keywords、description 等字段从 metadata 提取

        Args:
            cloud_data: 云端数据

        Returns:
            新创建的本地胶囊 ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 从 metadata 中提取完整元数据
            metadata = cloud_data.get('metadata', {})
            if isinstance(metadata, dict):
                preview_audio = metadata.get('preview_audio')
                keywords = metadata.get('keywords')
                description = metadata.get('description')
                capsule_type = metadata.get('capsule_type', cloud_data.get('capsule_type', 'magic'))
            else:
                preview_audio = None
                keywords = cloud_data.get('keywords')
                description = cloud_data.get('description')
                capsule_type = cloud_data.get('capsule_type', 'magic')

            cloud_uuid = cloud_data.get('uuid', str(cloud_data.get('id')))
            cloud_name = cloud_data.get('name')
            cloud_file_path = cloud_data.get('file_path', cloud_name)
            cloud_id = cloud_data.get('id')

            # 1) 优先按 cloud_id 匹配（防止重复插入）
            if cloud_id:
                cursor.execute("""
                    SELECT id FROM capsules WHERE cloud_id = ?
                """, (cloud_id,))
                existing = cursor.fetchone()
                if existing:
                    existing_id = existing['id'] if isinstance(existing, sqlite3.Row) else existing[0]
                    self._update_local_capsule_metadata(existing_id, cloud_data)
                    conn.commit()
                    return existing_id

            # 2) 按 uuid 匹配（uuid 为空时跳过）
            if cloud_uuid:
                cursor.execute("""
                    SELECT id FROM capsules WHERE uuid = ?
                """, (cloud_uuid,))
                existing = cursor.fetchone()
                if existing:
                    existing_id = existing['id'] if isinstance(existing, sqlite3.Row) else existing[0]
                    cursor.execute("""
                        UPDATE capsules
                        SET
                            name = ?,
                            capsule_type = ?,
                            keywords = ?,
                            description = ?,
                            preview_audio = ?,
                            file_path = ?,
                            cloud_id = ?,
                            cloud_status = 'synced',
                            owner_supabase_user_id = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        cloud_name,
                        capsule_type,
                        keywords,
                        description,
                        preview_audio,
                        cloud_file_path,
                        cloud_id,
                        cloud_data.get('user_id'),
                        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                        existing_id
                    ))
                    conn.commit()
                    return existing_id

            # 3) 兜底：按 name + file_path 匹配（处理本地扫描已存在的胶囊）
            if cloud_name:
                cursor.execute("""
                    SELECT id FROM capsules
                    WHERE name = ? AND file_path = ?
                    LIMIT 1
                """, (cloud_name, cloud_file_path))
                existing = cursor.fetchone()
                if existing:
                    existing_id = existing['id'] if isinstance(existing, sqlite3.Row) else existing[0]
                    cursor.execute("""
                        UPDATE capsules
                        SET
                            uuid = COALESCE(uuid, ?),
                            capsule_type = ?,
                            keywords = ?,
                            description = ?,
                            preview_audio = ?,
                            cloud_id = ?,
                            cloud_status = 'synced',
                            owner_supabase_user_id = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        cloud_uuid,
                        capsule_type,
                        keywords,
                        description,
                        preview_audio,
                        cloud_id,
                        cloud_data.get('user_id'),
                        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                        existing_id
                    ))
                    conn.commit()
                    return existing_id

            # 插入新胶囊
            # rpp_file 使用默认命名规则：{capsule_name}.rpp
            rpp_file = f"{cloud_name}.rpp" if cloud_name else None
            
            # 🔥 检测本地是否已有文件，动态设置 asset_status
            asset_status = 'cloud_only'  # 默认
            try:
                from common import PathManager
                pm = PathManager.get_instance()
                export_dir = pm.export_dir
                capsule_dir = Path(export_dir) / cloud_file_path
                
                # 检测本地文件是否存在
                if capsule_dir.exists():
                    # 检查是否有 Audio 文件夹（完整资产）
                    audio_dir = capsule_dir / "Audio"
                    if audio_dir.exists() and list(audio_dir.glob("*.wav")):
                        asset_status = 'local'
                        logger.info(f"   ℹ️ 检测到本地完整资产: {cloud_name} -> local")
                    # 只有预览文件（OGG）保持 cloud_only，不改为 local
                    # 因为 local 意味着有完整的 Audio/WAV 文件
            except Exception as e:
                logger.warning(f"   ⚠️ 检测本地文件失败: {e}")
            
            cursor.execute("""
                INSERT INTO capsules (
                    uuid, name, capsule_type, keywords, description, preview_audio, file_path,
                    rpp_file,
                    cloud_id, cloud_status, asset_status, audio_uploaded,
                    owner_supabase_user_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?, 1, ?, ?, ?)
            """, (
                cloud_uuid,  # 使用云端 ID 作为 uuid
                cloud_name,
                capsule_type,
                keywords,
                description,
                preview_audio,  # Phase G2: 添加预览音频文件名
                cloud_file_path,  # 文件路径默认为 name
                rpp_file,  # 🔥 添加 RPP 文件名
                cloud_id,  # cloud_id (Supabase record ID)
                asset_status,  # 🔥 动态检测的 asset_status
                # 🔥 audio_uploaded = 1，因为从云端同步的胶囊，Audio 已在云端
                cloud_data.get('user_id'),  # Phase G: 保存所有者 ID
                cloud_data.get('created_at'),
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            ))

            new_id = cursor.lastrowid
            conn.commit()

            return new_id

        except Exception as e:
            conn.rollback()
            print(f"❌ 创建本地胶囊失败: {e}")
            raise
        finally:
            conn.close()


    # ========== Phase C1: 棱镜配置同步 ==========

    def sync_prisms(self, user_id: str, upload: bool = True) -> Dict[str, Any]:
        """
        同步棱镜配置到云端

        Phase C1: 棱镜版本控制

        策略: Last Write Wins
        - 上传本地变更（仅锚点编辑器调用时执行，胶囊客户端只下载）
        - 下载云端变更（应用 Last Write Wins）
        - 冲突自动解决，无需手动干预

        Args:
            user_id: Supabase 用户 ID
            upload: 是否上传本地棱镜到云端。仅锚点编辑器应传 True；胶囊客户端必须传 False，只下载。

        Returns:
            同步结果：{
                'success': bool,
                'uploaded': int,
                'downloaded': int,
                'conflicts_resolved': int,
                'errors': List[str]
            }
        """
        from prism_version_manager import PrismVersionManager
        from dal_cloud_prisms import get_cloud_prism_dal

        errors = []
        uploaded = 0
        downloaded = 0
        conflicts_resolved = 0

        print("=" * 60)
        print("🔄 棱镜配置同步")
        print("=" * 60)
        print(f"用户 ID: {user_id}")
        print()

        try:
            # 初始化管理器和 DAL
            prism_manager = PrismVersionManager(self.db_path)
            prism_dal = get_cloud_prism_dal()

            # 加载 anchor_config（用于上传时带上 is_active，下载后写回 is_active）
            anchor_config = {}
            anchor_config_path = None
            try:
                from common import PathManager
                pm = PathManager.get_instance()
                anchor_config_path = pm.config_dir / "anchor_config_v2.json"
                if anchor_config_path.exists():
                    with open(anchor_config_path, 'r', encoding='utf-8') as f:
                        anchor_config = json.load(f)
            except Exception:
                try:
                    p = Path(__file__).parent / "anchor_config_v2.json"
                    if p.exists():
                        anchor_config_path = p
                        with open(p, 'r', encoding='utf-8') as f:
                            anchor_config = json.load(f)
                except Exception:
                    pass

            # 1. 上传本地变更（仅锚点编辑器调用时执行；胶囊客户端只下载，不上传）
            if upload:
                print("📤 步骤 1: 上传本地棱镜变更...")
                dirty_prisms = prism_manager.get_dirty_prisms()

                if dirty_prisms:
                    print(f"   发现 {len(dirty_prisms)} 个本地变更")

                    for prism in dirty_prisms:
                        try:
                            # 棱镜启用状态从 anchor_config 注入，供云端同步
                            prism['is_active'] = anchor_config.get(prism['id'], {}).get('active', True)
                            # 使用 DAL 上传（含 field_data、is_active）
                            result = prism_dal.upload_prism(
                                user_id,
                                prism['id'],
                                prism  # 直接传递完整的 prism 字典
                            )

                            if result:
                                uploaded += 1
                                print(f"   ✅ 上传棱镜 '{prism['id']}' (v{prism['version']})")
                            else:
                                errors.append(f"上传棱镜 '{prism['id']}' 失败")

                        except Exception as e:
                            error_msg = f"上传棱镜 '{prism['id']}' 失败: {e}"
                            errors.append(error_msg)
                            print(f"   ❌ {error_msg}")
                else:
                    print("   ✅ 无本地变更需要上传")
            else:
                print("📥 胶囊客户端：仅下载棱镜，不上传")

            print()

            # 2. 下载云端变更
            print("📥 步骤 2: 下载云端棱镜变更...")

            try:
                # 通过 DAL 获取云端所有棱镜
                cloud_prisms = prism_dal.download_prisms(user_id)

                if cloud_prisms:
                    print(f"   发现 {len(cloud_prisms)} 个云端棱镜")
                    # 在现有 anchor_config 上只更新各棱镜的 active（保留 name/axes 等）
                    anchor_config_to_save = dict(anchor_config) if anchor_config else {}

                    for cloud_prism in cloud_prisms:
                        try:
                            prism_id = cloud_prism['prism_id']
                            # 棱镜关键词 field_data（云端 JSON 字符串 → 解析为 list）
                            raw_field = cloud_prism.get('field_data')
                            field_data = json.loads(raw_field) if isinstance(raw_field, str) and raw_field else (raw_field if isinstance(raw_field, list) else [])
                            # 棱镜启用状态
                            is_active = cloud_prism.get('is_active')
                            if is_active is None:
                                is_active = True

                            # 检查本地版本
                            local_prism = prism_manager.get_prism(prism_id)

                            if local_prism:
                                # 版本比较
                                local_version = local_prism['version']
                                cloud_version = cloud_prism['version']

                                if cloud_version > local_version:
                                    # 云端版本更新，应用云端配置（含 field_data、Last Write Wins）
                                    prism_data = {
                                        'name': cloud_prism['name'],
                                        'description': cloud_prism['description'],
                                        'axis_config': json.loads(cloud_prism['axis_config']) if isinstance(cloud_prism.get('axis_config'), str) else (cloud_prism.get('axis_config') or {}),
                                        'anchors': json.loads(cloud_prism['anchors']) if isinstance(cloud_prism.get('anchors'), str) else (cloud_prism.get('anchors') or []),
                                        'field_data': field_data,
                                    }

                                    prism_manager.create_or_update_prism(
                                        prism_id,
                                        prism_data,
                                        user_id='cloud_sync'
                                    )
                                    if prism_id not in anchor_config_to_save:
                                        anchor_config_to_save[prism_id] = {}
                                    anchor_config_to_save[prism_id]['active'] = is_active

                                    downloaded += 1
                                    conflicts_resolved += 1
                                    print(f"   ✅ 下载棱镜 '{prism_id}' (v{local_version} → v{cloud_version})")

                                elif cloud_version < local_version:
                                    # 本地版本更新，已在步骤1上传；仍应用云端 is_active
                                    if prism_id not in anchor_config_to_save:
                                        anchor_config_to_save[prism_id] = {}
                                    anchor_config_to_save[prism_id]['active'] = is_active
                                    print(f"   ℹ️  棱镜 '{prism_id}' 本地版本更新 (v{local_version} > v{cloud_version})")
                                else:
                                    # 版本相同，仍应用云端 is_active 到本地配置
                                    if prism_id not in anchor_config_to_save:
                                        anchor_config_to_save[prism_id] = {}
                                    anchor_config_to_save[prism_id]['active'] = is_active
                                    print(f"   ℹ️  棱镜 '{prism_id}' 版本一致 (v{local_version})")
                            else:
                                # 本地不存在，直接创建（含 field_data）
                                prism_data = {
                                    'name': cloud_prism['name'],
                                    'description': cloud_prism['description'],
                                    'axis_config': json.loads(cloud_prism['axis_config']) if isinstance(cloud_prism.get('axis_config'), str) else (cloud_prism.get('axis_config') or {}),
                                    'anchors': json.loads(cloud_prism['anchors']) if isinstance(cloud_prism.get('anchors'), str) else (cloud_prism.get('anchors') or []),
                                    'field_data': field_data,
                                }

                                prism_manager.create_or_update_prism(
                                    prism_id,
                                    prism_data,
                                    user_id='cloud_sync'
                                )
                                if prism_id not in anchor_config_to_save:
                                    anchor_config_to_save[prism_id] = {}
                                anchor_config_to_save[prism_id]['active'] = is_active

                                downloaded += 1
                                print(f"   ✅ 下载新棱镜 '{prism_id}' (v{cloud_prism['version']})")

                        except Exception as e:
                            error_msg = f"处理棱镜 '{cloud_prism['prism_id']}' 失败: {e}"
                            errors.append(error_msg)
                            print(f"   ❌ {error_msg}")

                    # 以云端为准：删除本地存在但云端不存在的棱镜（如旧测试棱镜 mechanics、force_field_test）
                    cloud_ids = [p['prism_id'] for p in cloud_prisms]
                    try:
                        conn = sqlite3.connect(self.db_path)
                        try:
                            cursor = conn.cursor()
                            placeholders = ','.join('?' * len(cloud_ids))
                            cursor.execute(f"DELETE FROM prism_versions WHERE prism_id NOT IN ({placeholders})", cloud_ids)
                            cursor.execute(f"DELETE FROM prisms WHERE id NOT IN ({placeholders})", cloud_ids)
                            removed = cursor.rowcount
                            conn.commit()
                            if removed > 0:
                                print(f"   🗑️ 已移除 {removed} 个本地多余棱镜（以云端为准）")
                        finally:
                            conn.close()
                    except Exception as e:
                        logger.warning(f"[PRISMS] 清理本地多余棱镜失败: {e}")

                    # 写回 anchor_config 时只保留云端棱镜，避免旧测试棱镜仍显示
                    anchor_config_to_save = {k: v for k, v in anchor_config_to_save.items() if k in cloud_ids}

                    # 将云端棱镜的 is_active 写回本地 anchor_config_v2.json（使用与读取时相同的路径）
                    if anchor_config_to_save:
                        try:
                            write_path = anchor_config_path
                            if write_path is None:
                                from common import PathManager
                                pm = PathManager.get_instance()
                                write_path = pm.config_dir / "anchor_config_v2.json"
                            write_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(write_path, 'w', encoding='utf-8') as f:
                                json.dump(anchor_config_to_save, f, ensure_ascii=False, indent=2)
                            logger.info(f"[PRISMS] 已写回棱镜启用状态到 {write_path}")
                        except Exception as e:
                            logger.warning(f"[PRISMS] 写回 anchor_config 失败: {e}")
                else:
                    print("   ✅ 无云端棱镜")

            except Exception as e:
                error_msg = f"下载云端棱镜失败: {e}"
                errors.append(error_msg)
                print(f"   ❌ {error_msg}")

            print()

            # 总结
            print("=" * 60)
            print("✅ 棱镜同步完成")
            print("=" * 60)
            print(f"上传: {uploaded}")
            print(f"下载: {downloaded}")
            print(f"冲突解决: {conflicts_resolved}")
            if errors:
                print(f"错误: {len(errors)}")
                for error in errors:
                    print(f"   - {error}")

            return {
                'success': len(errors) == 0,
                'uploaded': uploaded,
                'downloaded': downloaded,
                'conflicts_resolved': conflicts_resolved,
                'errors': errors
            }

        except Exception as e:
            error_msg = f"棱镜同步失败: {e}"
            errors.append(error_msg)
            print(f"❌ {error_msg}")

            return {
                'success': False,
                'uploaded': uploaded,
                'downloaded': downloaded,
                'conflicts_resolved': conflicts_resolved,
                'errors': errors
            }


# 便捷函数
def get_sync_service(db_path: str = None, api_url: str = None) -> SyncService:
    """
    获取同步服务实例

    Args:
        db_path: 数据库路径（可选，不提供则从 PathManager 获取）
        api_url: 云端 API URL（可选）

    Returns:
        SyncService 实例
    """
    if db_path is None:
        # 从路径管理器获取数据库路径
        from common import PathManager
        pm = PathManager.get_instance()
        db_path = pm.db_path

    return SyncService(str(db_path), api_url)
