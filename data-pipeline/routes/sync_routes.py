"""
Flask Blueprint for Sync Routes

This module contains all synchronization-related routes for the Sound Capsule API.
Migrated from capsule_api.py as part of the API modularization effort (Phase G).

Routes:
- GET  /api/sync/status - Get sync status overview
- GET  /api/sync/pending - Get pending sync records
- POST /api/sync/mark-pending - Mark record for sync
- POST /api/sync/upload - Upload data to cloud
- GET  /api/sync/download - Download data from cloud
- GET  /api/sync/conflicts - Get unresolved conflicts
- POST /api/sync/resolve-conflict - Resolve a conflict
- POST /api/sync/lightweight - Lightweight metadata sync
"""

import sqlite3
import os
import logging
from flask import Blueprint, request, jsonify
from functools import wraps

# Import dependencies from parent modules
from pathlib import Path

# Note: token_required and APIError are defined in common module
from sync_service import get_sync_service
from capsule_db import get_database
from auth import get_auth_manager
from common import APIError, PathManager

logger = logging.getLogger(__name__)

# Define Blueprint
sync_bp = Blueprint('sync_bp', __name__)


# ============================================
# Error Handling & Auth
# ============================================


def get_current_user():
    """
    从请求中获取当前用户

    Returns:
        用户信息字典或 None

    Raises:
        APIError: 如果认证失败
    """
    auth_header = request.headers.get('Authorization')

    if not auth_header:
        return None  # 未提供 Token，返回 None（允许匿名访问）

    try:
        # 解析 Bearer token
        token = auth_header.split(' ')[1]
    except IndexError:
        raise APIError('Token 格式错误', 401)

    # 验证 token
    auth_manager = get_auth_manager()
    payload = auth_manager.verify_access_token(token)

    if not payload:
        raise APIError('Token 无效或已过期', 401)

    # 获取用户信息
    user = auth_manager.get_user_by_id(payload['user_id'])

    if not user:
        raise APIError('用户不存在', 401)

    return user


def token_required(f):
    """
    Token 认证装饰器

    用于保护需要认证的端点
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 允许 OPTIONS 预检请求通过（CORS）
        if request.method == 'OPTIONS':
            return jsonify({'success': True}), 200

        user = get_current_user()

        if not user:
            raise APIError('需要认证', 401)

        # 将用户信息传递给视图函数
        return f(current_user=user, *args, **kwargs)

    # 保留原始函数的名称
    decorated.__name__ = f.__name__
    return decorated


# ============================================================
# Sync Status Routes
# ============================================================

@sync_bp.route('/status', methods=['GET'])
def get_sync_status_endpoint():
    """
    获取同步状态概览

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "synced_count": 10,
                "pending_count": 3,
                "conflict_count": 0,
                "last_sync_at": "2026-01-10T10:00:00Z"
            }
        }
    """
    try:
        sync_service = get_sync_service()
        status = sync_service.get_sync_status()

        return jsonify({
            'success': True,
            'data': status
        })

    except Exception as e:
        raise APIError(f"获取同步状态失败: {e}", 500)


@sync_bp.route('/pending', methods=['GET'])
def get_pending_records():
    """
    获取待同步的记录

    Query Parameters:
        - table: 表名（可选）

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "records": [...]
            }
        }
    """
    try:
        table_name = request.args.get('table')

        sync_service = get_sync_service()
        records = sync_service.get_pending_records(table_name)

        return jsonify({
            'success': True,
            'data': {
                'records': records,
                'count': len(records)
            }
        })

    except Exception as e:
        raise APIError(f"获取待同步记录失败: {e}", 500)


@sync_bp.route('/mark-pending', methods=['POST'])
@token_required
def mark_record_for_sync(current_user):
    """
    标记记录为待同步

    请求体:
        {
            "table": "capsules",
            "record_id": 123,
            "operation": "update"
        }

    需要认证

    响应:
        {
            "success": true,
            "message": "已标记为待同步"
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError('请求体不能为空', 400)

        # 兼容两种参数格式
        table_name = data.get('table') or data.get('table_name')
        record_id = data.get('record_id') or data.get('record_id')
        operation = data.get('operation', 'update')

        if not all([table_name, record_id]):
            raise APIError('缺少必要参数: table, record_id', 400)

        sync_service = get_sync_service()
        success = sync_service.mark_for_sync(table_name, record_id, operation)

        if success:
            return jsonify({
                'success': True,
                'message': '已标记为待同步'
            })
        else:
            raise APIError('标记失败', 500)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"标记待同步失败: {e}", 500)


# ============================================================
# Cloud Sync Routes
# ============================================================

@sync_bp.route('/upload', methods=['POST'])
@token_required
def upload_to_cloud(current_user):
    """
    上传数据到云端

    请求体:
        {
            "table": "capsules",
            "records": [...]
        }

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "uploaded": 5,
                "failed": 0
            }
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError('请求体不能为空', 400)

        table_name = data.get('table')
        records = data.get('records', [])

        if not table_name:
            raise APIError('缺少表名', 400)

        # 调试日志
        logger.info(f"\n{'='*60}")
        logger.info(f"[SYNC] 开始上传到云端")
        logger.info(f"[SYNC] 表名: {table_name}")
        logger.info(f"[SYNC] 记录数: {len(records)}")
        logger.info(f"[SYNC] 完整请求体: {data}")
        if records:
            logger.info(f"[SYNC] 第一条记录: {records[0]}")
        logger.info(f"{'='*60}\n")

        # 真实的云端上传逻辑
        try:
            from supabase_client import get_supabase_client
            from common import load_user_config  # Import helper function

            supabase = get_supabase_client()
            if not supabase:
                raise Exception("Supabase 客户端未初始化")

            # 获取用户 ID（优先使用 supabase_user_id，如果没有则使用本地 ID）
            user_id = current_user.get('supabase_user_id') or str(current_user.get('id', ''))

            uploaded = 0
            failed = 0
            cloud_id_mapping = {}  # 本地 ID -> 云端 ID 映射

            # 根据不同的表名处理
            if table_name == 'capsules':
                # 获取本地数据库连接
                db = get_database()
                db.connect()
                cursor = db.conn.cursor()

                try:
                    # 上传胶囊数据
                    for idx, pending_record in enumerate(records, 1):
                        logger.info(f"\n[SYNC] 处理第 {idx}/{len(records)} 条记录...")
                        try:
                            # 从 pending_record 中获取实际的 record_id
                            record_id = pending_record.get('record_id')
                            logger.info(f"[SYNC]   record_id: {record_id}")

                            # 从数据库获取完整的胶囊数据
                            cursor.execute("SELECT * FROM capsules WHERE id = ?", (record_id,))
                            row = cursor.fetchone()

                            if not row:
                                logger.warning(f"[SYNC]   ✗ 警告: 胶囊 ID {record_id} 不存在，跳过")
                                failed += 1
                                continue

                            # 将行数据转换为字典
                            columns = [desc[0] for desc in cursor.description]
                            capsule_data = dict(zip(columns, row))

                            # 获取技术元数据
                            cursor.execute("""SELECT bpm, duration, sample_rate, plugin_count, plugin_list,
                                                   has_sends, has_folder_bus, tracks_included
                                            FROM capsule_metadata WHERE capsule_id = ?""", (record_id,))
                            metadata_row = cursor.fetchone()
                            if metadata_row:
                                capsule_data['bpm'] = metadata_row[0]
                                capsule_data['duration'] = metadata_row[1]
                                capsule_data['sample_rate'] = metadata_row[2]
                                capsule_data['plugin_count'] = metadata_row[3]
                                capsule_data['plugin_list'] = metadata_row[4]
                                capsule_data['has_sends'] = metadata_row[5]
                                capsule_data['has_folder_bus'] = metadata_row[6]
                                capsule_data['tracks_included'] = metadata_row[7]

                            logger.info(f"[SYNC]   ✓ 胶囊名称: {capsule_data.get('name')}")

                            # 上传到云端（仅 keywords 更新）
                            logger.info(f"[SYNC]   → 正在上传到 Supabase...")
                            existing_cloud = supabase.get_cloud_capsule_by_local_id(user_id, record_id)
                            result = None
                            if existing_cloud:
                                remote_meta = existing_cloud.get('metadata') or {}
                                remote_keywords = remote_meta.get('keywords') if isinstance(remote_meta, dict) else None
                                local_keywords = capsule_data.get('keywords')
                                if local_keywords != remote_keywords:
                                    result = supabase.update_capsule_keywords(user_id, record_id, local_keywords)
                                else:
                                    result = existing_cloud
                            else:
                                result = supabase.upload_capsule(user_id, capsule_data)

                            if result:
                                uploaded += 1
                                cloud_id = result.get('id')
                                cloud_id_mapping[record_id] = cloud_id
                                logger.info(f"[SYNC]   ✓ 上传成功!")
                                logger.info(f"[SYNC]     - 本地ID: {record_id}")
                                logger.info(f"[SYNC]     - 云端ID: {cloud_id}")
                                logger.info(f"[SYNC]     - 版本: {result.get('version')}")
                                
                                # 🔧 立即更新 cloud_id（防止后续文件上传失败导致数据不一致）
                                cursor.execute("""
                                    UPDATE capsules
                                    SET cloud_id = ?,
                                        cloud_version = ?
                                    WHERE id = ?
                                """, (cloud_id, result.get('version', 1), record_id))
                                db.conn.commit()
                                logger.info(f"[SYNC]   ✓ 已设置 cloud_id")

                                # 🎯 上传 Audio 文件夹（仅缺失部分）
                                import os
                                capsule_dir = capsule_data.get('file_path', '')
                                if capsule_dir:
                                    from pathlib import Path
                                    import glob

                                    # 从路径管理器获取导出目录
                                    pm = PathManager.get_instance()
                                    full_capsule_dir = pm.export_dir / capsule_dir
                                    
                                    logger.info(f"[SYNC] 🔍 查找胶囊目录: {full_capsule_dir}")
                                    
                                    if not full_capsule_dir.exists():
                                        logger.warning(f"[SYNC] ⚠ 胶囊目录不存在: {full_capsule_dir}")
                                        full_capsule_dir = None

                                    if full_capsule_dir:
                                        # 🎵 上传预览音频文件（仅缺失）
                                        preview_audio = capsule_data.get('preview_audio')
                                        if preview_audio:
                                            preview_path = full_capsule_dir / preview_audio
                                            if preview_path.exists():
                                                if supabase.storage_file_exists(user_id, capsule_dir, preview_audio):
                                                    logger.info(f"[SYNC]   ✓ 预览音频已存在，跳过")
                                                else:
                                                    logger.info(f"[SYNC] → 上传预览音频: {preview_audio}")
                                                    preview_result = supabase.upload_file(
                                                        user_id=user_id,
                                                        capsule_folder_name=capsule_dir,
                                                        file_type='preview',
                                                        file_path=str(preview_path)
                                                    )
                                                    if preview_result:
                                                        logger.info(f"[SYNC]   ✓ 预览音频上传成功")
                                                        logger.info(f"[SYNC]     - 大小: {preview_result.get('size', 0):,} bytes")
                                                        logger.info(f"[SYNC]     - 路径: {preview_result.get('storage_path', 'N/A')}")
                                                    else:
                                                        logger.warning(f"[SYNC]   ⚠ 预览音频上传失败")
                                            else:
                                                logger.warning(f"[SYNC]   ⚠ 预览音频文件不存在: {preview_path}")

                                        # 📄 上传 RPP 项目文件（仅缺失）
                                        rpp_file = capsule_data.get('rpp_file')
                                        if rpp_file:
                                            rpp_path = full_capsule_dir / rpp_file
                                            if rpp_path.exists():
                                                if supabase.storage_file_exists(user_id, capsule_dir, rpp_file):
                                                    logger.info(f"[SYNC]   ✓ RPP 已存在，跳过")
                                                else:
                                                    logger.info(f"[SYNC] → 上传 RPP 文件: {rpp_file}")
                                                    rpp_result = supabase.upload_file(
                                                        user_id=user_id,
                                                        capsule_folder_name=capsule_dir,
                                                        file_type='rpp',
                                                        file_path=str(rpp_path)
                                                    )
                                                    if rpp_result:
                                                        logger.info(f"[SYNC]   ✓ RPP 文件上传成功")
                                                        logger.info(f"[SYNC]     - 大小: {rpp_result.get('size', 0):,} bytes")
                                                        logger.info(f"[SYNC]     - 路径: {rpp_result.get('storage_path', 'N/A')}")
                                                    else:
                                                        logger.warning(f"[SYNC]   ⚠ RPP 文件上传失败")
                                            else:
                                                logger.warning(f"[SYNC]   ⚠ RPP 文件不存在: {rpp_path}")

                                        # 📋 上传 metadata.json 文件（仅缺失）
                                        metadata_file = full_capsule_dir / "metadata.json"
                                        if metadata_file.exists():
                                            if supabase.storage_file_exists(user_id, capsule_dir, "metadata.json"):
                                                logger.info(f"[SYNC]   ✓ metadata.json 已存在，跳过")
                                            else:
                                                logger.info(f"[SYNC] → 上传 metadata.json...")
                                                metadata_result = supabase.upload_file(
                                                    user_id=user_id,
                                                    capsule_folder_name=capsule_dir,
                                                    file_type='metadata',
                                                    file_path=str(metadata_file)
                                                )
                                                if metadata_result:
                                                    logger.info(f"[SYNC]   ✓ metadata.json 上传成功")
                                                    logger.info(f"[SYNC]     - 大小: {metadata_result.get('size', 0):,} bytes")
                                                    logger.info(f"[SYNC]     - 路径: {metadata_result.get('storage_path', 'N/A')}")
                                                else:
                                                    logger.warning(f"[SYNC]   ⚠ metadata.json 上传失败")
                                        else:
                                            logger.warning(f"[SYNC]   ⚠ metadata.json 文件不存在: {metadata_file}")

                                        # 🎧 上传 Audio 文件夹（仅缺失）
                                        audio_folder = full_capsule_dir / "Audio"
                                        if audio_folder.exists():
                                            local_files = [
                                                entry for entry in audio_folder.iterdir()
                                                if entry.is_file() and not entry.name.startswith('.')
                                                and entry.suffix.lower() in ['.wav', '.mp3', '.ogg', '.flac', '.aiff']
                                            ]
                                            remote_files = set(supabase.list_audio_files(user_id, capsule_dir))
                                            missing_files = [f for f in local_files if f.name not in remote_files]
                                            if not missing_files:
                                                logger.info(f"[SYNC]   ✓ Audio 已完整存在，跳过")
                                            else:
                                                logger.info(f"[SYNC] → 上传 Audio 文件夹（缺失 {len(missing_files)} 个）...")
                                                audio_result = supabase.upload_audio_files(
                                                    user_id=user_id,
                                                    capsule_folder_name=capsule_dir,
                                                    audio_files=missing_files
                                                )
                                                if audio_result and audio_result.get('success', False):
                                                    logger.info(f"[SYNC]   ✓ Audio 文件夹上传成功")
                                                    logger.info(f"[SYNC]     - 文件数: {audio_result.get('files_uploaded', 0)}")
                                                    logger.info(f"[SYNC]     - 总大小: {audio_result.get('total_size', 0):,} bytes ({audio_result.get('total_size', 0) / 1024 / 1024:.2f} MB)")
                                                    if audio_result.get('errors'):
                                                        logger.warning(f"[SYNC]     - 失败: {len(audio_result.get('errors', []))} 个文件")
                                                else:
                                                    logger.warning(f"[SYNC]   ⚠ Audio 文件夹上传失败")
                                        else:
                                            logger.info(f"[SYNC]   ℹ 无 Audio 文件夹，跳过")
                                    else:
                                        logger.warning(f"[SYNC] ⚠ 无法找到胶囊目录: {capsule_dir}")

                                # 更新本地数据库的云同步状态（cloud_id 已在上传成功后立即设置）
                                cursor.execute("""
                                    UPDATE capsules
                                    SET cloud_status = 'synced',
                                        last_synced_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                """, (record_id,))
                                db.conn.commit()
                                logger.info(f"[SYNC]   ✓ 已更新本地同步状态为 'synced'")
                            else:
                                failed += 1
                                logger.error(f"[SYNC]   ✗ 上传失败: result is None")
                        except Exception as e:
                            failed += 1
                            logger.error(f"[SYNC]   ✗ 异常: {e}")
                            import traceback
                            logger.error(traceback.format_exc())

                    # 上传胶囊的标签和坐标（使用已有的 db 和 cursor）
                    if cloud_id_mapping:
                        logger.info(f"[SYNC] 📝 准备上传标签，cloud_id_mapping: {cloud_id_mapping}")
                        for local_id, cloud_id in cloud_id_mapping.items():
                            # 上传标签
                            cursor.execute("SELECT * FROM capsule_tags WHERE capsule_id = ?", (local_id,))
                            tags = []
                            for row in cursor.fetchall():
                                tags.append({
                                    'lens': row[2],         # 使用统一的 lens 命名
                                    'word_id': row[3],      # word_id
                                    'word_cn': row[4],      # word_cn
                                    'word_en': row[5],      # word_en
                                    'x': row[6],            # x
                                    'y': row[7],            # y
                                })
                            logger.info(f"[SYNC] 📝 本地胶囊 {local_id} 有 {len(tags)} 个标签")
                            if tags:
                                logger.info(f"[SYNC] → 上传标签到云端 (capsule_id={cloud_id})...")
                                supabase.upload_tags(user_id, cloud_id, tags)
                            else:
                                logger.warning(f"[SYNC] ⚠ 本地胶囊 {local_id} 没有标签")

                            # 上传坐标
                            cursor.execute("SELECT * FROM capsule_coordinates WHERE capsule_id = ?", (local_id,))
                            coords = []
                            for row in cursor.fetchall():
                                coords.append({
                                    'lens': row[2],
                                    'dimension': row[3],
                                    'value': row[4],
                                })
                            if coords:
                                supabase.upload_coordinates(user_id, cloud_id, coords)
                finally:
                    # 确保关闭数据库连接
                    db.close()

            elif table_name == 'capsule_tags':
                # 标签会随着胶囊一起上传
                uploaded = len(records)
            elif table_name == 'capsule_coordinates':
                # 坐标会随着胶囊一起上传
                uploaded = len(records)
            else:
                raise Exception(f"不支持的表名: {table_name}")

            # 标记为已同步（只标记成功上传的记录）
            sync_service = get_sync_service()
            synced_count = 0

            for pending_record in records:
                record_id = pending_record.get('record_id')
                if record_id and record_id in cloud_id_mapping:
                    # 只有成功上传到云端的记录才标记为已同步
                    sync_service.mark_as_synced(table_name, record_id, 1)
                    synced_count += 1
                    logger.info(f"[SYNC] 标记为已同步: {table_name} ID {record_id}")

            logger.info(f"[SYNC] 同步完成: 成功 {uploaded}, 失败 {failed}, 标记 {synced_count}")

            return jsonify({
                'success': True,
                'data': {
                    'uploaded': uploaded,
                    'failed': failed
                }
            })

        except ImportError:
            raise Exception("Supabase SDK 未安装")
        except Exception as e:
            raise Exception(f"云端上传失败: {str(e)}")

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"上传到云端失败: {e}", 500)


@sync_bp.route('/download', methods=['GET'])
@token_required
def download_from_cloud(current_user):
    """
    从云端下载数据

    Query Parameters:
        - table: 表名
        - since: ISO 8601 时间戳（可选）

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "records": [...],
                "deleted_ids": [...]
            }
        }
    """
    try:
        table_name = request.args.get('table')
        since = request.args.get('since')

        if not table_name:
            raise APIError('缺少表名', 400)

        # 真实的云端下载逻辑
        try:
            from supabase_client import get_supabase_client
            from common import load_user_config  # Import helper function

            supabase = get_supabase_client()
            if not supabase:
                raise Exception("Supabase 客户端未初始化")

            # 获取用户 ID（优先使用 supabase_user_id，如果没有则使用本地 ID）
            user_id = current_user.get('supabase_user_id') or str(current_user.get('id', ''))

            # 根据 table_name 下载对应的数据
            if table_name == 'capsules':
                records = supabase.download_capsules(user_id)

                # 保存到本地数据库
                if records:
                    db = get_database()
                    db.connect()
                    try:
                        for record in records:
                            # 检查是否已存在（按 cloud_id / uuid / name+file_path）
                            cursor = db.conn.cursor()
                            cursor.execute("SELECT id FROM capsules WHERE cloud_id = ?", (record.get('id'),))
                            existing = cursor.fetchone()
                            if not existing:
                                cursor.execute("SELECT id FROM capsules WHERE uuid = ?", (record.get('id'),))
                                existing = cursor.fetchone()

                            # 准备本地数据
                            capsule_folder_name = (record.get('metadata') or {}).get('file_path') or record.get('name', '')

                            local_data = {
                                'uuid': record.get('id'),
                                'name': record.get('name'),
                                'file_path': capsule_folder_name,
                                'preview_audio': record.get('metadata', {}).get('preview_audio'),
                                'rpp_file': record.get('metadata', {}).get('rpp_file'),
                                'capsule_type': record.get('metadata', {}).get('capsule_type', 'magic'),
                                'cloud_status': 'synced',
                                'cloud_id': record.get('id'),
                                'cloud_version': record.get('version', 1),
                            }

                            if existing:
                                # 更新现有记录
                                cursor.execute("""
                                    UPDATE capsules
                                    SET name = ?, file_path = ?, preview_audio = ?, rpp_file = ?,
                                        capsule_type = ?, cloud_status = ?, cloud_id = ?, cloud_version = ?,
                                        last_synced_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                """, (
                                    local_data['name'], local_data['file_path'], local_data['preview_audio'],
                                    local_data['rpp_file'], local_data['capsule_type'], local_data['cloud_status'],
                                    local_data['cloud_id'], local_data['cloud_version'], existing[0]
                                ))
                            else:
                                # 兜底再按 name + file_path 匹配，避免 UUID 冲突
                                cursor.execute("""
                                    SELECT id FROM capsules
                                    WHERE name = ? AND file_path = ?
                                """, (local_data['name'], local_data['file_path']))
                                existing_by_name = cursor.fetchone()
                                if existing_by_name:
                                    cursor.execute("""
                                        UPDATE capsules
                                        SET preview_audio = ?, rpp_file = ?,
                                            capsule_type = ?, cloud_status = ?, cloud_id = ?, cloud_version = ?,
                                            last_synced_at = CURRENT_TIMESTAMP
                                        WHERE id = ?
                                    """, (
                                        local_data['preview_audio'], local_data['rpp_file'], local_data['capsule_type'],
                                        local_data['cloud_status'], local_data['cloud_id'], local_data['cloud_version'],
                                        existing_by_name[0]
                                    ))
                                    continue
                                # 插入新记录
                                cursor.execute("""
                                    INSERT INTO capsules (uuid, name, file_path, preview_audio, rpp_file,
                                                         capsule_type, cloud_status, cloud_id, cloud_version)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    local_data['uuid'], local_data['name'], local_data['file_path'],
                                    local_data['preview_audio'], local_data['rpp_file'], local_data['capsule_type'],
                                    local_data['cloud_status'], local_data['cloud_id'], local_data['cloud_version']
                                ))

                                # 获取新插入的胶囊ID
                                capsule_id = cursor.lastrowid

                                # 从云端 metadata 恢复技术元数据
                                metadata = record.get('metadata', {})
                                if metadata.get('bpm') or metadata.get('plugin_count'):
                                    cursor.execute("""
                                        INSERT INTO capsule_metadata
                                        (capsule_id, bpm, duration, sample_rate, plugin_count, plugin_list,
                                         has_sends, has_folder_bus, tracks_included)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        capsule_id,
                                        metadata.get('bpm'),
                                        metadata.get('duration'),
                                        metadata.get('sample_rate'),
                                        metadata.get('plugin_count'),
                                        metadata.get('plugin_list'),
                                        metadata.get('has_sends'),
                                        metadata.get('has_folder_bus'),
                                        metadata.get('tracks_included')
                                    ))

                                # 从云端获取并恢复标签
                                cloud_tags = supabase.download_capsule_tags(record.get('id'))
                                if cloud_tags:
                                    for tag in cloud_tags:
                                        cursor.execute("""
                                            INSERT INTO capsule_tags
                                            (capsule_id, lens, word_id, word_cn, word_en, x, y)
                                            VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """, (
                                            capsule_id,
                                            tag.get('lens') or tag.get('lens_id'),
                                            tag.get('word_id'),
                                            tag.get('word_cn'),
                                            tag.get('word_en'),
                                            tag.get('x'),
                                            tag.get('y')
                                        ))

                                # 从云端获取并恢复坐标
                                try:
                                    cloud_coords_res = supabase.client.table('cloud_capsule_coordinates').select('*').eq('capsule_id', record.get('id')).execute()
                                    if cloud_coords_res.data:
                                        for coord in cloud_coords_res.data:
                                            cursor.execute("""
                                                INSERT INTO capsule_coordinates
                                                (capsule_id, lens, dimension, value)
                                                VALUES (?, ?, ?, ?)
                                            """, (
                                                capsule_id,
                                                coord.get('lens') or coord.get('lens_id'),
                                                coord.get('dimension'),
                                                coord.get('value')
                                            ))
                                except Exception as e:
                                    logger.warning(f"恢复坐标失败 (胶囊 {capsule_id}): {e}")

                                # 创建同步状态记录
                                cursor.execute("""
                                    INSERT OR REPLACE INTO sync_status
                                    (table_name, record_id, sync_state, local_version, cloud_version, created_at, updated_at)
                                    VALUES ('capsules', ?, 'synced', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """, (capsule_id, record.get('version', 1), record.get('version', 1)))

                                # 📥 下载文件（只对新下载的胶囊）
                                try:
                                    from pathlib import Path
                                    import os

                                    # 确定导出目录 - 从 PathManager 获取
                                    from common import PathManager
                                    pm = PathManager.get_instance()
                                    export_dir = pm.export_dir
                                    capsule_dir = Path(export_dir) / local_data['file_path']
                                    capsule_dir.mkdir(parents=True, exist_ok=True)

                                    logger.info(f"[SYNC] 📥 开始下载胶囊文件: {local_data['name']}")

                                    # 使用云端记录中的原作者 user_id
                                    owner_id = record.get('user_id')
                                    if not owner_id:
                                        owner_id = user_id

                                    # 1. 下载预览音频
                                    if local_data['preview_audio']:
                                        preview_path = capsule_dir / local_data['preview_audio']
                                        logger.info(f"[SYNC]   → 下载预览音频: {local_data['preview_audio']}")
                                        logger.info(f"[SYNC]     文件夹: {local_data['file_path']}, 作者: {owner_id}, 路径: {owner_id}/{local_data['file_path']}/preview")
                                        if supabase.download_file(owner_id, local_data['file_path'], 'preview', str(preview_path)):
                                            logger.info(f"[SYNC]   ✓ 预览音频下载成功")
                                        else:
                                            logger.warning(f"[SYNC]   ⚠ 预览音频下载失败")

                                    # 2. 下载 RPP 文件
                                    if local_data['rpp_file']:
                                        rpp_path = capsule_dir / local_data['rpp_file']
                                        logger.info(f"[SYNC]   → 下载 RPP 文件: {local_data['rpp_file']}")
                                        logger.info(f"[SYNC]     文件夹: {local_data['file_path']}, 作者: {owner_id}, 路径: {owner_id}/{local_data['file_path']}/project.rpp")
                                        if supabase.download_file(owner_id, local_data['file_path'], 'rpp', str(rpp_path)):
                                            logger.info(f"[SYNC]   ✓ RPP 文件下载成功")
                                        else:
                                            logger.warning(f"[SYNC]   ⚠ RPP 文件下载失败")

                                    logger.info(f"[SYNC] ✓ 胶囊文件下载完成: {local_data['name']}")

                                except Exception as e:
                                    logger.error(f"[SYNC] ✗ 下载文件失败: {e}")
                                    import traceback
                                    logger.error(traceback.format_exc())

                        db.conn.commit()
                    finally:
                        db.close()

            elif table_name == 'capsule_tags':
                records = supabase.download_tags(user_id)
            elif table_name == 'capsule_coordinates':
                records = supabase.download_coordinates(user_id)
            else:
                raise Exception(f"不支持的表名: {table_name}")

            return jsonify({
                'success': True,
                'data': {
                    'records': records,
                    'deleted_ids': []
                }
            })

        except ImportError:
            raise Exception("Supabase SDK 未安装")
        except Exception as e:
            raise Exception(f"云端下载失败: {str(e)}")

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"从云端下载失败: {e}", 500)


# ============================================================
# Conflict Resolution Routes
# ============================================================

@sync_bp.route('/conflicts', methods=['GET'])
def get_conflicts():
    """
    获取未解决的冲突列表

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "conflicts": [...]
            }
        }
    """
    try:
        conn = sqlite3.connect(os.getenv('DATABASE_PATH', 'database/capsules.db').replace('sqlite:///', ''))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, table_name, record_id, conflict_type, created_at
            FROM sync_conflicts
            WHERE resolved = 0
            ORDER BY created_at DESC
        """)

        conflicts = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'conflicts': conflicts,
                'count': len(conflicts)
            }
        })

    except Exception as e:
        raise APIError(f"获取冲突列表失败: {e}", 500)


@sync_bp.route('/resolve-conflict', methods=['POST'])
@token_required
def resolve_conflict_endpoint(current_user):
    """
    解决冲突

    请求体:
        {
            "conflict_id": 1,
            "resolution": "local"  // "local", "cloud", "merge"
        }

    需要认证

    响应:
        {
            "success": true,
            "message": "冲突已解决"
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError('请求体不能为空', 400)

        conflict_id = data.get('conflict_id')
        resolution = data.get('resolution')

        if not all([conflict_id, resolution]):
            raise APIError('缺少必要参数: conflict_id, resolution', 400)

        if resolution not in ['local', 'cloud', 'merge']:
            raise APIError('无效的解决方案', 400)

        sync_service = get_sync_service()
        success = sync_service.resolve_conflict(conflict_id, resolution)

        if success:
            return jsonify({
                'success': True,
                'message': '冲突已解决'
            })
        else:
            raise APIError('解决冲突失败', 500)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"解决冲突失败: {e}", 500)


# ============================================================
# Phase B.4: Lightweight Sync API
# ============================================================

@sync_bp.route('/lightweight', methods=['POST'])
@token_required
def sync_metadata_lightweight(current_user):
    """
    轻量级同步：仅同步元数据 + 预览音频（可选）

    Phase B.4 新增功能：分离元数据和资产同步

    请求体:
        {
            "include_previews": true,  // 是否自动下载预览音频
            "force": false              // 是否强制同步（忽略本地缓存）
        }

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "synced_count": 10,
                "preview_downloaded": 5,
                "duration_seconds": 2.5,
                "errors": []
            }
        }
    """
    try:
        data = request.get_json() or {}
        include_previews = data.get('include_previews', True)
        force = data.get('force', False)
        capsule_ids = data.get('capsule_ids')  # 获取指定的胶囊 ID 列表

        logger.info("\n" + "=" * 60)
        logger.info("🔄 轻量级同步请求")
        logger.info("=" * 60)
        logger.info(f"用户: {current_user.get('username')}")
        logger.info(f"包含预览音频: {include_previews}")
        logger.info(f"强制同步: {force}")
        if capsule_ids:
            logger.info(f"指定胶囊: {capsule_ids}")

        # 获取用户 ID
        user_id = current_user.get('supabase_user_id') or str(current_user.get('id', ''))

        if not user_id:
            raise APIError('用户 ID 不存在', 400)

        # 获取同步服务实例
        sync_service = get_sync_service()

        # 执行轻量级同步
        result = sync_service.sync_metadata_lightweight(
            user_id=user_id,
            include_previews=include_previews,
            capsule_ids=capsule_ids  # 传递指定的胶囊 ID 列表
        )

        # 同时也同步棱镜配置 (Phase C)
        try:
            sync_service.sync_prisms(user_id)
        except Exception as e:
            logger.warning(f"棱镜同步失败 (非阻断): {e}")

        if result['success']:
            logger.info(f"✅ 轻量级同步成功: {result['synced_count']} 个胶囊")
            return jsonify({
                'success': True,
                'data': {
                    'synced_count': result['synced_count'],
                    'preview_downloaded': result['preview_downloaded'],
                    'duration_seconds': result['duration_seconds'],
                    'errors': result['errors']
                }
            })
        else:
            logger.warning(f"⚠️  轻量级同步部分失败: {len(result['errors'])} 个错误")
            return jsonify({
                'success': False,
                'error': '同步过程中出现错误',
                'data': {
                    'synced_count': result['synced_count'],
                    'preview_downloaded': result['preview_downloaded'],
                    'duration_seconds': result['duration_seconds'],
                    'errors': result['errors']
                }
            }), 207  # 207 Multi-Status（部分成功）

    except APIError:
        raise
    except Exception as e:
        logger.error(f"轻量级同步失败: {e}")
        raise APIError(f"轻量级同步失败: {e}", 500)


@sync_bp.route('/upload-audio', methods=['POST'])
@token_required
def upload_audio_folders(current_user):
    """
    上传本地 Audio 文件夹（整体同步用）
    请求体:
        {
            "capsule_ids": [1,2,3]  // 可选，指定胶囊
        }
    """
    try:
        data = request.get_json() or {}
        capsule_ids = data.get('capsule_ids')

        user_id = current_user.get('supabase_user_id') or str(current_user.get('id', ''))
        if not user_id:
            raise APIError('用户 ID 不存在', 400)

        sync_service = get_sync_service()
        result = sync_service.upload_audio_folders(
            user_id=user_id,
            capsule_ids=capsule_ids
        )

        if result['success']:
            return jsonify({'success': True, 'data': result})
        return jsonify({'success': False, 'error': '音频上传失败', 'data': result}), 207
    except APIError:
        raise
    except Exception as e:
        logger.error(f"上传 Audio 文件夹失败: {e}")
        raise APIError(f"上传 Audio 文件夹失败: {e}", 500)


@sync_bp.route('/sync-tags', methods=['POST'])
@token_required
def sync_tags_only(current_user):
    """
    只同步关键词数据（capsule_tags）
    
    双向同步：
    1. 上传本地修改过的关键词到云端
    2. 下载云端更新的关键词到本地
    
    只同步有变化的数据，通过 updated_at 比对
    """
    try:
        sync_service = get_sync_service()
        user_id = current_user.get('supabase_user_id') or str(current_user.get('id', ''))
        if not user_id:
            raise APIError('用户 ID 不存在', 400)

        result = sync_service.sync_tags_only(user_id=user_id)

        if result['success']:
            logger.info(f"✅ 关键词同步成功: 上传 {result.get('uploaded', 0)}, 下载 {result.get('downloaded', 0)}")
            return jsonify({'success': True, 'data': result})
        return jsonify({'success': False, 'error': '关键词同步失败', 'data': result}), 207
    except APIError:
        raise
    except Exception as e:
        logger.error(f"关键词同步失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise APIError(f"关键词同步失败: {e}", 500)


@sync_bp.route('/upload-progress', methods=['GET'])
def get_upload_progress():
    """
    获取单个胶囊上传进度
    Query 参数:
        capsule_id: 胶囊 ID
    """
    try:
        capsule_id = request.args.get('capsule_id', type=int)
        if not capsule_id:
            raise APIError('缺少 capsule_id', 400)

        from sync_service import _get_upload_progress
        progress = _get_upload_progress(capsule_id)
        return jsonify({
            'success': True,
            'data': progress
        })
    except Exception as e:
        logger.error(f"获取上传进度失败: {e}")
        raise APIError(f"获取上传进度失败: {e}", 500)


@sync_bp.route('/download-only', methods=['POST'])
@token_required
def download_only(current_user):
    """
    仅下载模式：只从云端下载数据，不上传本地变更

    Phase G2 新增功能：启动同步专用

    请求体:
        {
            "include_previews": true  // 是否自动下载预览音频
        }

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "downloaded_count": 10,
                "preview_downloaded": 5,
                "duration_seconds": 2.5,
                "errors": []
            }
        }
    """
    try:
        data = request.get_json() or {}
        include_previews = data.get('include_previews', True)

        logger.info("\n" + "=" * 60)
        logger.info("🔄 仅下载模式（启动同步）")
        logger.info("=" * 60)
        logger.info(f"用户: {current_user.get('username')}")
        logger.info(f"包含预览音频: {include_previews}")
        logger.info("⚠️  跳过本地数据上传")

        # 获取用户 ID
        user_id = current_user.get('supabase_user_id') or str(current_user.get('id', ''))

        if not user_id:
            raise APIError('用户 ID 不存在', 400)

        # 获取同步服务实例
        sync_service = get_sync_service()

        # 执行仅下载同步
        result = sync_service.download_only(
            user_id=user_id,
            include_previews=include_previews
        )

        # 同时也同步棱镜配置 (Phase C)
        try:
            sync_service.sync_prisms(user_id)
        except Exception as e:
            logger.warning(f"棱镜同步失败 (非阻断): {e}")

        if result['success']:
            logger.info(f"✅ 仅下载成功: {result['downloaded_count']} 个胶囊")
            return jsonify({
                'success': True,
                'data': {
                    'downloaded_count': result['downloaded_count'],
                    'preview_downloaded': result['preview_downloaded'],
                    'duration_seconds': result['duration_seconds'],
                    'errors': result['errors']
                }
            })
        else:
            logger.warning(f"⚠️  仅下载部分失败: {len(result['errors'])} 个错误")
            return jsonify({
                'success': False,
                'error': '下载过程中出现错误',
                'data': {
                    'downloaded_count': result['downloaded_count'],
                    'preview_downloaded': result['preview_downloaded'],
                    'duration_seconds': result['duration_seconds'],
                    'errors': result['errors']
                }
            }), 207  # 207 Multi-Status（部分成功）

    except APIError:
        raise
    except Exception as e:
        logger.error(f"仅下载失败: {e}")
        raise APIError(f"仅下载失败: {e}", 500)
