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
import json
import base64
import time
import urllib.request
import urllib.parse
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


def _encode_cursor(offset: int) -> str:
    return base64.b64encode(json.dumps({'offset': offset}).encode('utf-8')).decode('utf-8')


def _decode_cursor(cursor: str) -> int:
    if not cursor:
        return 0
    try:
        payload = json.loads(base64.b64decode(cursor.encode('utf-8')).decode('utf-8'))
        return int(payload.get('offset', 0))
    except Exception:
        raise APIError('invalid_cursor', 400)


def _extract_supabase_sub_from_bearer() -> str:
    """
    从 Authorization Bearer JWT 中提取 supabase user id（sub）。

    设计说明：
    - 本地 sidecar 在“无 service_role/JWKS”模式下，不能依赖强校验。
    - 该函数只做 payload 解析用于路由分流，不用于权限提升。
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return ''

    token = auth_header.split(' ', 1)[1].strip()
    if not token:
        return ''

    parts = token.split('.')
    if len(parts) != 3:
        return ''

    payload_b64 = parts[1]
    padding = '=' * (-len(payload_b64) % 4)
    try:
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode('utf-8')
        payload = json.loads(payload_json)
        return str(payload.get('sub') or '').strip()
    except Exception:
        return ''


def _download_lightweight_assets_via_cloud(cloud_api_origin: str, include_previews: bool = True):
    """
    本地 sidecar 无 service_role 时，回退到云端 API 拉取轻量文件并落盘。
    """
    start = time.time()
    errors = []
    preview_downloaded = 0
    written_files = 0

    cloud_api_origin = (cloud_api_origin or '').rstrip('/')
    if not cloud_api_origin:
        raise APIError('缺少 cloud_api_origin，无法回退下载轻量文件', 400)

    db = get_database()
    db.connect()
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT cloud_id, file_path, name, preview_audio, rpp_file
        FROM capsules
        WHERE cloud_id IS NOT NULL
        ORDER BY id
    """)
    rows = cursor.fetchall()
    db.close()

    if not rows:
        return {
            'success': True,
            'downloaded_count': 0,
            'preview_downloaded': 0,
            'errors': [],
            'duration_seconds': time.time() - start,
        }

    req_capsules = []
    for r in rows:
        req_capsules.append({
            'cloud_id': r[0],
            'file_path': r[1],
            'name': r[2],
            'preview_audio': r[3],
            'rpp_file': r[4],
        })

    payload = json.dumps({
        'include_previews': include_previews,
        'capsules': req_capsules,
    }).encode('utf-8')

    auth_header = request.headers.get('Authorization', '')
    req = urllib.request.Request(
        url=f"{cloud_api_origin}/api/cloud/lightweight-assets",
        data=payload,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'Authorization': auth_header,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode('utf-8')
            result = json.loads(body) if body else {}
    except Exception as e:
        raise APIError(f'调用云端轻量文件接口失败: {e}', 502)

    items = ((result.get('data') or {}).get('items')) or []
    cloud_errors = ((result.get('data') or {}).get('errors')) or []
    errors.extend(cloud_errors)

    pm = PathManager.get_instance()
    export_dir = pm.export_dir

    for item in items:
        folder = item.get('folder') or ''
        files = item.get('files') or []
        if not folder:
            continue
        capsule_dir = Path(export_dir) / folder
        capsule_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            filename = f.get('filename')
            content_b64 = f.get('content_base64')
            file_type = f.get('type')
            if not filename or not content_b64:
                continue
            try:
                content = base64.b64decode(content_b64)
                with open(capsule_dir / filename, 'wb') as out:
                    out.write(content)
                written_files += 1
                if file_type == 'preview':
                    preview_downloaded += 1
            except Exception as e:
                errors.append(f"{folder}/{filename}: {e}")

    return {
        'success': len(errors) == 0,
        'downloaded_count': len(rows),
        'preview_downloaded': preview_downloaded,
        'errors': errors,
        'duration_seconds': time.time() - start,
        'written_files': written_files,
    }


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

    # 根据 payload 类型获取用户信息
    user = None
    
    # 优先使用 supabase_user_id（Supabase Auth）
    if 'supabase_user_id' in payload:
        user = auth_manager.get_user_by_supabase_id(payload['supabase_user_id'])
        
        # 如果本地没有缓存，直接返回 payload 中的信息
        if not user:
            user = {
                'id': payload['supabase_user_id'],
                'supabase_user_id': payload['supabase_user_id'],
                'username': payload.get('username'),
                'email': payload.get('email'),
                'display_name': payload.get('username')
            }
    
    # 降级到本地 user_id（本地认证）
    elif 'user_id' in payload:
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
                                                        _err = getattr(supabase, 'get_last_storage_error', lambda: '')()
                                                        logger.warning(f"[SYNC]   ⚠ 预览音频上传失败" + (f": {_err}" if _err else ""))
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
                                                        _err = getattr(supabase, 'get_last_storage_error', lambda: '')()
                                                        logger.warning(f"[SYNC]   ⚠ RPP 文件上传失败" + (f": {_err}" if _err else ""))
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
                                                    _err = getattr(supabase, 'get_last_storage_error', lambda: '')()
                                                    logger.warning(f"[SYNC]   ⚠ metadata.json 上传失败" + (f": {_err}" if _err else ""))
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
                                                    _err = getattr(supabase, 'get_last_storage_error', lambda: '')()
                                                    logger.warning(f"[SYNC]   ⚠ Audio 文件夹上传失败" + (f": {_err}" if _err else ""))
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
                            tag_embeddings = []
                            try:
                                cursor.execute(
                                    "SELECT name, keywords, description FROM capsules WHERE id = ?",
                                    (local_id,),
                                )
                                cap_row = cursor.fetchone()
                                if cap_row:
                                    from capsule_embedding_service import update_embedding_for_cloud_capsule
                                    ok, tag_embeddings = update_embedding_for_cloud_capsule(
                                        supabase,
                                        cloud_id,
                                        name=cap_row[0] or "",
                                        keywords=(cap_row[1] or ""),
                                        description=(cap_row[2] or ""),
                                        tags=tags,
                                    )
                                    if ok:
                                        logger.info(f"[SYNC]   ✓ 已更新胶囊主体 embedding (cloud_id={cloud_id})")
                            except Exception as emb_ex:
                                logger.warning(f"[SYNC] 更新胶囊 embedding 失败: {emb_ex}")

                            if tags:
                                logger.info(f"[SYNC] → 上传标签到云端 (capsule_id={cloud_id})...")
                                supabase.upload_tags(user_id, cloud_id, tags, tag_embeddings=tag_embeddings or [])
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
        data = request.get_json(silent=True) or {}
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

        # 同时也同步棱镜配置 (Phase C)，胶囊客户端只下载棱镜，不上传
        try:
            sync_service.sync_prisms(user_id, upload=False)
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


@sync_bp.route('/lightweight-page', methods=['POST'])
@token_required
def lightweight_page(current_user):
    """
    分页拉取轻量化数据（云端）
    """
    data = request.get_json(silent=True) or {}
    include_previews = bool(data.get('include_previews', True))
    include_signed_urls = bool(data.get('include_signed_urls', False))
    signed_url_expires_in = int(data.get('signed_url_expires_in', 900) or 900)
    signed_url_expires_in = max(60, min(3600, signed_url_expires_in))
    page_size = int(data.get('page_size', 200) or 200)
    if page_size <= 0:
        page_size = 200
    page_size = min(page_size, 500)
    offset = _decode_cursor(data.get('cursor'))

    supabase = __import__('supabase_client').get_supabase_client()
    if not supabase:
        raise APIError('Supabase 客户端未初始化', 500)

    user_id = current_user.get('supabase_user_id') or str(current_user.get('id', ''))
    if not user_id:
        raise APIError('用户 ID 不存在', 400)

    capsules = supabase.download_capsules(user_id=user_id) or []
    total = len(capsules)
    page_items = capsules[offset: offset + page_size]
    next_offset = offset + len(page_items)
    next_cursor = _encode_cursor(next_offset) if next_offset < total else None

    items = []
    errors = []
    for cap in page_items:
        cloud_id = cap.get('id')
        try:
            tags = supabase.download_capsule_tags(cloud_id) if cloud_id else []
            try:
                coord_res = supabase.client.table('cloud_capsule_coordinates').select('*').eq('capsule_id', cloud_id).execute()
                coordinates = coord_res.data or []
            except Exception:
                coordinates = []

            items.append({
                'capsule': cap,
                'tags': tags,
                'coordinates': coordinates,
                'preview': cap.get('metadata', {}).get('preview_audio') if include_previews else None,
            })
            if include_signed_urls:
                metadata = cap.get('metadata') or {}
                owner_id = cap.get('user_id')
                folder = metadata.get('file_path') or cap.get('name')
                signed_urls = {}

                if owner_id and folder:
                    def _try_signed(path: str):
                        # 兼容历史 bucket 命名差异：优先 capsule-files，失败后回退 capsules
                        first = supabase.create_signed_download_url(path, expires_in=signed_url_expires_in, bucket_name='capsule-files')
                        if first.get('signed_url'):
                            return first
                        second = supabase.create_signed_download_url(path, expires_in=signed_url_expires_in, bucket_name='capsules')
                        if second.get('signed_url'):
                            return second
                        return {'error': first.get('error') or second.get('error') or 'signed_url_failed'}

                    metadata_path = f"{owner_id}/{folder}/metadata.json"
                    meta_signed = _try_signed(metadata_path)
                    if meta_signed.get('signed_url'):
                        signed_urls['metadata'] = {
                            'url': meta_signed['signed_url'],
                            'filename': 'metadata.json',
                        }
                    else:
                        errors.append(f"{cloud_id}: metadata signed url failed: {meta_signed.get('error')}")

                    preview_name = metadata.get('preview_audio')
                    if include_previews and preview_name:
                        preview_path = f"{owner_id}/{folder}/{preview_name}"
                        preview_signed = _try_signed(preview_path)
                        if preview_signed.get('signed_url'):
                            signed_urls['preview'] = {
                                'url': preview_signed['signed_url'],
                                'filename': preview_name,
                            }
                        else:
                            errors.append(f"{cloud_id}: preview signed url failed: {preview_signed.get('error')}")

                    # 兼容历史 RPP 命名：先尝试常见命名，再回退到目录扫描 *.rpp
                    rpp_candidates = []
                    for candidate in (
                        metadata.get('rpp_file'),
                        metadata.get('project_file'),
                        metadata.get('rpp'),
                        f"{folder}.rpp",
                        f"{folder}.RPP",
                        "project.rpp",
                        "project.RPP",
                    ):
                        if candidate and candidate not in rpp_candidates:
                            rpp_candidates.append(candidate)

                    rpp_signed = None
                    for rpp_name in rpp_candidates:
                        rpp_path = f"{owner_id}/{folder}/{rpp_name}"
                        current = _try_signed(rpp_path)
                        if current.get('signed_url'):
                            rpp_signed = (rpp_name, current)
                            break

                    if rpp_signed:
                        rpp_name, rpp_data = rpp_signed
                        signed_urls['rpp'] = {
                            'url': rpp_data['signed_url'],
                            'filename': rpp_name,
                        }
                    else:
                        # 最后兜底：列目录自动找任意 .rpp（兼容不可预期命名）
                        discovered = None
                        for bucket_name in ('capsule-files', 'capsules'):
                            try:
                                obj_list = supabase.client.storage.from_(bucket_name).list(f"{owner_id}/{folder}") or []
                                for obj in obj_list:
                                    name = (obj or {}).get('name')
                                    if isinstance(name, str) and name.lower().endswith('.rpp'):
                                        path = f"{owner_id}/{folder}/{name}"
                                        signed = supabase.create_signed_download_url(
                                            path,
                                            expires_in=signed_url_expires_in,
                                            bucket_name=bucket_name,
                                        )
                                        if signed.get('signed_url'):
                                            discovered = (name, signed)
                                            break
                                if discovered:
                                    break
                            except Exception:
                                continue

                        if discovered:
                            name, signed = discovered
                            signed_urls['rpp'] = {
                                'url': signed['signed_url'],
                                'filename': name,
                            }
                        else:
                            errors.append(f"{cloud_id}: rpp signed url failed")
                else:
                    errors.append(f"{cloud_id}: missing owner_id/folder for signed urls")

                items[-1]['signed_urls'] = signed_urls
        except Exception as e:
            errors.append(str(e))

    return jsonify({
        'success': True,
        'data': {
            'items': items,
            'next_cursor': next_cursor,
            'total': total,
            'downloaded_count': len(items),
            'skipped_count': 0,
            'errors': errors,
        }
    })


@sync_bp.route('/apply-lightweight-page', methods=['POST'])
def apply_lightweight_page():
    """
    应用一页轻量化数据到本地（sidecar）

    设计约束：
    - 该端点仅做本地落库（纯本地写），不依赖 Supabase/service_role。
    - 云端拉取与鉴权由 /api/sync/lightweight-page 负责。
    """
    payload = request.get_json(silent=True) or {}
    items = payload.get('items') or []
    prefer_signed_url = bool(payload.get('prefer_signed_url', False))
    cloud_api_origin = (payload.get('cloud_api_origin') or '').strip()

    db = get_database()
    db.connect()
    cursor = db.conn.cursor()

    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    downloaded_files = 0
    preview_downloaded = 0
    rpp_downloaded = 0
    metadata_downloaded = 0
    errors = []

    try:
        for idx, item in enumerate(items):
            try:
                capsule = item.get('capsule') or {}
                tags = item.get('tags') or []
                coordinates = item.get('coordinates') or []
                signed_urls = item.get('signed_urls') or {}
                cloud_id = capsule.get('id')
                metadata = capsule.get('metadata') or {}
                file_path = metadata.get('file_path') or capsule.get('name') or ''
                owner_supabase_user_id = capsule.get('user_id') or None

                if not cloud_id:
                    skipped_count += 1
                    continue

                cursor.execute("SELECT id FROM capsules WHERE cloud_id = ?", (cloud_id,))
                existing = cursor.fetchone()

                if existing:
                    local_id = existing[0]
                    cursor.execute(
                        """
                        UPDATE capsules
                        SET name = ?, file_path = ?, preview_audio = ?, rpp_file = ?, capsule_type = ?,
                            keywords = ?, description = ?, cloud_status = 'synced', cloud_version = ?, last_synced_at = CURRENT_TIMESTAMP,
                            -- 关键修复：轻同步不能覆盖已下载状态。
                            -- 若本地已完整下载（files_downloaded=1 或 asset_status=synced），保持原状态；
                            -- 否则维持轻数据状态 cloud_only。
                            asset_status = CASE
                                WHEN files_downloaded = 1 OR asset_status = 'synced' THEN asset_status
                                ELSE 'cloud_only'
                            END,
                            files_downloaded = CASE
                                WHEN files_downloaded = 1 OR asset_status = 'synced' THEN 1
                                ELSE 0
                            END,
                            owner_supabase_user_id = COALESCE(?, owner_supabase_user_id)
                        WHERE id = ?
                        """,
                        (
                            capsule.get('name') or file_path,
                            file_path,
                            metadata.get('preview_audio'),
                            metadata.get('rpp_file'),
                            metadata.get('capsule_type', 'magic'),
                            metadata.get('keywords') or '',
                            capsule.get('description') or '',
                            capsule.get('version', 1),
                            owner_supabase_user_id,
                            local_id,
                        ),
                    )
                    updated_count += 1
                else:
                    cursor.execute(
                        """
                        INSERT INTO capsules
                        (uuid, name, file_path, preview_audio, rpp_file, capsule_type, keywords, description, cloud_status, cloud_id, cloud_version, asset_status, files_downloaded, owner_supabase_user_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?, ?, 'cloud_only', 0, ?)
                        """,
                        (
                            cloud_id,
                            capsule.get('name') or file_path,
                            file_path,
                            metadata.get('preview_audio'),
                            metadata.get('rpp_file'),
                            metadata.get('capsule_type', 'magic'),
                            metadata.get('keywords') or '',
                            capsule.get('description') or '',
                            cloud_id,
                            capsule.get('version', 1),
                            owner_supabase_user_id,
                        ),
                    )
                    local_id = cursor.lastrowid
                    inserted_count += 1

                # 替换 tags/coordinates
                cursor.execute("DELETE FROM capsule_tags WHERE capsule_id = ?", (local_id,))
                for tag in tags:
                    cursor.execute(
                        """
                        INSERT INTO capsule_tags (capsule_id, lens, word_id, word_cn, word_en, x, y)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            local_id,
                            tag.get('lens') or tag.get('lens_id'),
                            tag.get('word_id'),
                            tag.get('word_cn'),
                            tag.get('word_en'),
                            tag.get('x'),
                            tag.get('y'),
                        ),
                    )

                cursor.execute("DELETE FROM capsule_coordinates WHERE capsule_id = ?", (local_id,))
                for coord in coordinates:
                    cursor.execute(
                        """
                        INSERT INTO capsule_coordinates (capsule_id, lens, dimension, value)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            local_id,
                            coord.get('lens') or coord.get('lens_id'),
                            coord.get('dimension'),
                            coord.get('value'),
                        ),
                    )

                # 元数据回填（插件信息等）
                plugin_list = metadata.get('plugin_list')
                if plugin_list is None and isinstance(metadata.get('plugins'), dict):
                    plugin_list = metadata.get('plugins', {}).get('list')
                plugin_count = metadata.get('plugin_count')
                if plugin_count is None and isinstance(metadata.get('plugins'), dict):
                    plugin_count = metadata.get('plugins', {}).get('count')
                if plugin_count is None and isinstance(plugin_list, list):
                    plugin_count = len(plugin_list)

                if plugin_list is not None or plugin_count is not None:
                    if isinstance(plugin_list, list):
                        plugin_list = json.dumps(plugin_list, ensure_ascii=False)
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO capsule_metadata
                        (capsule_id, bpm, duration, sample_rate, plugin_count, plugin_list, has_sends, has_folder_bus, tracks_included)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            local_id,
                            metadata.get('bpm'),
                            metadata.get('duration'),
                            metadata.get('sample_rate'),
                            plugin_count or 0,
                            plugin_list or '[]',
                            metadata.get('has_sends'),
                            metadata.get('has_folder_bus'),
                            metadata.get('tracks_included'),
                        ),
                    )

                # 可选：优先使用云端签名 URL 下载轻量文件（无需本地 service_role）
                if prefer_signed_url:
                    # 兼容两种云端返回格式：
                    # 1) item.signed_urls.{metadata|preview|rpp}
                    # 2) item.preview.signed_url + capsule.metadata 内文件名（历史格式）
                    # 3) item.{preview|rpp|metadata_file}.{signed_url|path}（新格式）
                    effective_signed_urls = signed_urls if isinstance(signed_urls, dict) else {}
                    if not isinstance(effective_signed_urls, dict):
                        effective_signed_urls = {}

                    def _pick_url(asset_obj: dict):
                        if not isinstance(asset_obj, dict):
                            return None
                        direct = asset_obj.get('signed_url') or asset_obj.get('url') or asset_obj.get('download_url')
                        if direct:
                            return direct

                        signed = asset_obj.get('signed')
                        if isinstance(signed, dict):
                            nested = signed.get('signed_url') or signed.get('url')
                            if nested:
                                return nested

                        raw_path = asset_obj.get('path')
                        if isinstance(raw_path, str) and raw_path.startswith(('http://', 'https://')):
                            return raw_path
                        return None

                    def _guess_filename(asset_obj: dict, default_name: str):
                        if isinstance(asset_obj, dict):
                            for key in ('filename', 'file_name', 'name'):
                                val = asset_obj.get(key)
                                if isinstance(val, str) and val.strip():
                                    return val.strip()
                            for key in ('storage_path', 'path'):
                                val = asset_obj.get(key)
                                if isinstance(val, str) and val.strip():
                                    parsed = urllib.parse.urlparse(val)
                                    raw_path = (parsed.path or val).rstrip('/')
                                    base = raw_path.split('/')[-1] if raw_path else ''
                                    if base:
                                        return base
                        return default_name

                    def _pick_asset_obj(kind: str):
                        """
                        兼容多种云端 item 结构：
                        - item.{preview|rpp|metadata_file}
                        - item.files.{...} / item.assets.{...}
                        - item.files 数组（按 type 匹配）
                        - item.capsule.{preview|rpp|metadata_file}
                        """
                        aliases = [kind]
                        if kind == 'metadata':
                            aliases.extend(['metadata_file', 'metadata'])

                        # 1) 顶层对象
                        for k in aliases:
                            obj = item.get(k)
                            if isinstance(obj, dict) and obj:
                                return obj

                        # 2) item.files / item.assets 为 dict
                        for container_key in ('files', 'assets'):
                            container = item.get(container_key)
                            if isinstance(container, dict):
                                for k in aliases:
                                    obj = container.get(k)
                                    if isinstance(obj, dict) and obj:
                                        return obj

                        # 3) item.files / item.assets 为 list
                        for container_key in ('files', 'assets'):
                            container = item.get(container_key)
                            if isinstance(container, list):
                                target_types = set(aliases)
                                if kind == 'metadata':
                                    target_types.update({'meta', 'metadata_json'})
                                for obj in container:
                                    if not isinstance(obj, dict):
                                        continue
                                    t = str(obj.get('type') or '').strip().lower()
                                    if t in target_types:
                                        return obj

                        # 4) item.capsule 里内嵌对象
                        capsule_obj = item.get('capsule') or {}
                        if isinstance(capsule_obj, dict):
                            for k in aliases:
                                obj = capsule_obj.get(k)
                                if isinstance(obj, dict) and obj:
                                    return obj
                        return {}

                    # 新/旧格式融合，尽可能补全三类轻资产
                    preview_obj = _pick_asset_obj('preview')
                    if 'preview' not in effective_signed_urls:
                        preview_url = _pick_url(preview_obj)
                        preview_filename = _guess_filename(preview_obj, metadata.get('preview_audio') or 'preview.ogg')
                        if preview_url and preview_filename:
                            effective_signed_urls['preview'] = {'url': preview_url, 'filename': preview_filename}

                    rpp_obj = _pick_asset_obj('rpp')
                    if 'rpp' not in effective_signed_urls:
                        rpp_url = _pick_url(rpp_obj)
                        rpp_filename = _guess_filename(rpp_obj, metadata.get('rpp_file') or f"{file_path}.rpp")
                        if rpp_url and rpp_filename:
                            effective_signed_urls['rpp'] = {'url': rpp_url, 'filename': rpp_filename}
                        elif isinstance(rpp_obj, dict) and bool(rpp_obj.get('exists', False)):
                            errors.append(f"ASSET_DOWNLOAD_NO_SIGNED_URL:rpp:{file_path}")

                    metadata_obj = _pick_asset_obj('metadata')
                    if 'metadata' not in effective_signed_urls:
                        metadata_url = _pick_url(metadata_obj)
                        metadata_filename = _guess_filename(metadata_obj, 'metadata.json')
                        if metadata_url and metadata_filename:
                            effective_signed_urls['metadata'] = {'url': metadata_url, 'filename': metadata_filename}
                        elif isinstance(metadata_obj, dict) and bool(metadata_obj.get('exists', False)):
                            errors.append(f"ASSET_DOWNLOAD_NO_SIGNED_URL:metadata:{file_path}")

                    # 诊断日志：帮助定位云端 item 结构差异导致的静默未命中
                    if idx < 5:
                        top_keys = list(item.keys()) if isinstance(item, dict) else []
                        logger.info(
                            "[apply-lightweight-page][diag] file_path=%s top_keys=%s signed_keys=%s has_preview_obj=%s has_rpp_obj=%s has_metadata_obj=%s",
                            file_path,
                            top_keys,
                            list(effective_signed_urls.keys()),
                            bool(preview_obj),
                            bool(rpp_obj),
                            bool(metadata_obj),
                        )

                    if not effective_signed_urls:
                        errors.append(f"no signed urls provided for {file_path}")
                        continue

                    try:
                        pm = PathManager.get_instance()
                        capsule_dir = Path(pm.export_dir) / file_path
                        capsule_dir.mkdir(parents=True, exist_ok=True)
                        downloaded_for_capsule = 0
                        preview_downloaded_for_capsule = 0

                        for k in ('metadata', 'preview', 'rpp'):
                            item_signed = effective_signed_urls.get(k) or {}
                            signed_url = item_signed.get('url')
                            filename = item_signed.get('filename')
                            if not signed_url or not filename:
                                continue

                            try:
                                # 兼容云端返回 localhost/127.0.0.1 的签名 URL：
                                # 在跨机部署下，将 host 替换为 cloud_api_origin 的 host。
                                effective_url = signed_url
                                try:
                                    parsed = urllib.parse.urlparse(signed_url)
                                    if parsed.hostname in ('127.0.0.1', 'localhost') and cloud_api_origin:
                                        cloud_parsed = urllib.parse.urlparse(cloud_api_origin)
                                        target_host = cloud_parsed.hostname or parsed.hostname
                                        target_port = parsed.port or 8000
                                        target_scheme = parsed.scheme or cloud_parsed.scheme or 'http'
                                        netloc = f"{target_host}:{target_port}"
                                        effective_url = urllib.parse.urlunparse((
                                            target_scheme,
                                            netloc,
                                            parsed.path,
                                            parsed.params,
                                            parsed.query,
                                            parsed.fragment,
                                        ))
                                except Exception:
                                    effective_url = signed_url

                                with urllib.request.urlopen(effective_url, timeout=30) as resp:
                                    content = resp.read()
                                with open(capsule_dir / filename, 'wb') as f:
                                    f.write(content)
                                downloaded_files += 1
                                downloaded_for_capsule += 1
                                if k == 'preview':
                                    preview_downloaded += 1
                                    preview_downloaded_for_capsule += 1
                                elif k == 'rpp':
                                    rpp_downloaded += 1
                                elif k == 'metadata':
                                    metadata_downloaded += 1
                            except Exception as e:
                                errors.append(f"download {file_path}/{filename} failed: {e}")

                        # 兜底：若未拿到 metadata.json 签名，至少将云端 metadata 对象本地化为 metadata.json
                        metadata_file = capsule_dir / 'metadata.json'
                        if not metadata_file.exists() and isinstance(metadata, dict) and metadata:
                            try:
                                with open(metadata_file, 'w', encoding='utf-8') as f:
                                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                                downloaded_files += 1
                                downloaded_for_capsule += 1
                                metadata_downloaded += 1
                            except Exception as e:
                                errors.append(f"write fallback metadata.json failed for {file_path}: {e}")

                        if downloaded_for_capsule > 0:
                            cursor.execute(
                                """
                                UPDATE capsules
                                SET files_downloaded = 1,
                                    preview_downloaded = CASE WHEN ? > 0 THEN 1 ELSE preview_downloaded END
                                WHERE id = ?
                                """,
                                (preview_downloaded_for_capsule, local_id),
                            )
                    except Exception as e:
                        errors.append(f"prepare signed download failed: {e}")
            except Exception as e:
                errors.append(str(e))
                skipped_count += 1

        db.conn.commit()
    finally:
        db.close()

    status_code = 207 if errors else 200
    return jsonify({
        'success': len(errors) == 0,
        'data': {
            'downloaded_count': len(items),
            'inserted_count': inserted_count,
            'updated_count': updated_count,
            'skipped_count': skipped_count,
            'downloaded_files': downloaded_files,
            'preview_downloaded': preview_downloaded,
            'rpp_downloaded': rpp_downloaded,
            'metadata_downloaded': metadata_downloaded,
            'errors': errors,
        }
    }), status_code


@sync_bp.route('/download-only', methods=['POST'])
def download_only():
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
        data = request.get_json(silent=True) or {}
        include_previews = data.get('include_previews', True)
        cloud_api_origin = (
            data.get('cloud_api_origin')
            or os.getenv('CLOUD_API_ORIGIN')
            or 'http://127.0.0.1:5002'
        ).strip()

        logger.info("\n" + "=" * 60)
        logger.info("🔄 仅下载模式（启动同步）")
        logger.info("=" * 60)
        logger.info("用户: sidecar-local")
        logger.info(f"包含预览音频: {include_previews}")
        logger.info(f"云端 API: {cloud_api_origin}")
        logger.info("⚠️  跳过本地数据上传")

        # 获取用户 ID（优先从 Bearer token 的 sub 提取，避免依赖 service_role 校验）
        user_id = _extract_supabase_sub_from_bearer()

        if not user_id:
            raise APIError('缺少用户身份（Bearer token.sub）', 401)

        # 获取同步服务实例
        sync_service = get_sync_service()
        from supabase_client import get_supabase_client
        local_supabase = get_supabase_client()

        # 执行仅下载同步：
        # - 本地有 service_role：沿用历史 download_only 逻辑
        # - 本地无 service_role：回退到云端 API 拉取轻量文件并落盘
        if local_supabase:
            result = sync_service.download_only(
                user_id=user_id,
                include_previews=include_previews
            )
        else:
            result = _download_lightweight_assets_via_cloud(
                cloud_api_origin=cloud_api_origin,
                include_previews=include_previews
            )

        # 同时也同步棱镜配置 (Phase C)，胶囊客户端只下载棱镜，不上传
        try:
            sync_service.sync_prisms(user_id, upload=False)
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
