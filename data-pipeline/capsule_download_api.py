"""
胶囊下载 API (JIT 决策流)

简化实现，直接使用 Supabase 客户端下载
"""

from flask import request, jsonify
from auth import get_auth_manager
from capsule_db import get_database
from supabase_client import get_supabase_client
from common import APIError
import logging
import threading
import time
import os
import json
import base64
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)


def _extract_supabase_sub_from_bearer(auth_header: str) -> str:
    """
    从 Bearer JWT 提取 payload.sub（不验签）。
    仅用于本地 sidecar 的路由分流，不用于权限提升。
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return ""
    token = auth_header.split(" ", 1)[1].strip()
    parts = token.split(".")
    if len(parts) != 3:
        return ""
    payload_b64 = parts[1]
    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        payload = json.loads(payload_json)
        return str(payload.get("sub") or "").strip()
    except Exception:
        return ""


def _download_audio_via_cloud_signed(
    cloud_api_origin: str,
    auth_header: str,
    cloud_id: str,
    local_capsule_path: Path
) -> bool:
    cloud_api_origin = (cloud_api_origin or "").rstrip("/")
    if not cloud_api_origin:
        raise APIError("缺少 cloud_api_origin，无法下载 WAV", 400)

    req_body = json.dumps({
        "cloud_id": cloud_id,
        "signed_url_expires_in": 900,
    }).encode("utf-8")
    req = urllib.request.Request(
        url=f"{cloud_api_origin}/api/cloud/audio-signed-urls",
        data=req_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": auth_header or "",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8") or "{}")
    files = ((payload.get("data") or {}).get("files")) or []
    if not files:
        return False

    audio_dir = local_capsule_path / "Audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    for item in files:
        signed_url = (item or {}).get("url")
        filename = (item or {}).get("filename")
        if not signed_url or not filename or not str(filename).lower().endswith(".wav"):
            continue
        with urllib.request.urlopen(signed_url, timeout=120) as file_resp:
            content = file_resp.read()
        with open(audio_dir / filename, "wb") as f:
            f.write(content)
        downloaded += 1

    return downloaded > 0


def register_download_routes(app):
    """注册下载相关路由"""
    
    # 获取 Supabase 客户端
    supabase = get_supabase_client()
    
    @app.route('/api/capsules/<int:capsule_id>/download-assets', methods=['POST'])
    def download_capsule_assets(capsule_id):
        """
        按需下载胶囊资产（JIT 决策流）
        
        请求体:
            {
                "force": false,  // 是否强制重新下载
                "priority": 5     // 优先级 (0-10)
            }
        
        需要认证
        
        响应:
            {
                "success": true,
                "task_id": 123,
                "status": "pending",  // pending, downloading, completed
                "progress": 0,
                "file_size": 104857600
            }
        """
        try:
            # 验证用户已登录（从 Authorization header 获取 token）
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                raise APIError('缺少认证令牌', 401)
            token = auth_header.split(' ')[1]
            auth_manager = get_auth_manager()
            payload = None
            try:
                payload = auth_manager.verify_access_token(token)
            except Exception:
                payload = None

            if payload:
                user_id = payload.get('supabase_user_id') or payload.get('user_id') or payload.get('sub')
            else:
                # 本地未配置 JWT_SECRET/SUPABASE_JWT_SECRET 时，回退提取 sub
                sub = _extract_supabase_sub_from_bearer(auth_header)
                if not sub:
                    raise APIError('Token 无效或已过期', 401)
                user_id = sub
            
            # 安全获取 JSON 数据
            try:
                data = request.get_json(silent=True) or {}
            except Exception:
                data = {}
            
            force = data.get('force', False)
            priority = data.get('priority', 5)
            cloud_api_origin = (
                data.get('cloud_api_origin')
                or os.getenv('CLOUD_API_ORIGIN')
                or os.getenv('VITE_CLOUD_API_ORIGIN')
                or ''
            ).strip()
            
            db = get_database()
            
            # 获取胶囊信息
            capsule = db.get_capsule(capsule_id)
            if not capsule:
                raise APIError('胶囊不存在', 404)
            
            # 检查资产状态
            asset_status = capsule.get('asset_status', 'local')
            
            if asset_status == 'synced' and not force:
                # 已经完整下载
                logger.info(f"[DOWNLOAD] 胶囊 {capsule_id} 已完整下载，跳过")
                return jsonify({
                    'success': True,
                    'already_downloaded': True,
                    'task_id': None,
                    'message': '资产已完整下载'
                })
            
            # 获取文件路径
            file_path = capsule.get('file_path')
            capsule_dir_name = Path(file_path).name if file_path else None
            
            if not capsule_dir_name:
                logger.error(f"[DOWNLOAD] 无法确定胶囊目录名: {file_path}")
                raise APIError('无法确定下载目标', 400)
            
            # ==========================================
            # 🔑 关键修复：确定正确的文件所有者 ID (Owner ID)
            # ==========================================
            # 不能盲目使用"当前用户 ID"，必须使用"胶囊所有者 ID"
            target_user_id = None
            cloud_id = capsule.get('cloud_id')
            
            # 方案 A: 如果有 cloud_id，从 Supabase 查询胶囊的所有者
            if cloud_id:
                try:
                    logger.info(f"[DOWNLOAD] 🔍 查询胶囊 {capsule_id} 的所有者 (cloud_id: {cloud_id})")
                    supabase_client = get_supabase_client()
                    response = supabase_client.client.table('cloud_capsules')\
                        .select('user_id')\
                        .eq('id', cloud_id)\
                        .single()\
                        .execute()
                    
                    if response.data:
                        owner_supabase_uuid = response.data.get('user_id')
                        logger.info(f"[DOWNLOAD] ✅ 胶囊 {capsule_id} 的所有者是: {owner_supabase_uuid}")
                        
                        # 查询本地 users 表，找到对应的 supabase_user_id
                        # 注意：owner_supabase_uuid 是 Supabase Auth 的 UUID，需要匹配本地 users 表的 supabase_user_id
                        conn = db.connect()
                        try:
                            cursor = conn.cursor()
                            cursor.execute("SELECT supabase_user_id FROM users WHERE supabase_user_id = ? LIMIT 1", (owner_supabase_uuid,))
                            users = cursor.fetchall()
                            if users and users[0][0]:
                                target_user_id = users[0][0]
                                logger.info(f"[DOWNLOAD] ✅ 找到所有者的 Supabase User ID: {target_user_id}")
                            else:
                                # 本地 users 表可不存在该用户，直接使用云端 UUID 即可
                                target_user_id = owner_supabase_uuid
                                logger.info(f"[DOWNLOAD] ⚠️ 本地未找到所有者用户，使用云端 UUID: {target_user_id}")
                        finally:
                            conn.close()
                    else:
                        logger.warning(f"[DOWNLOAD] ⚠️ 云端未找到胶囊记录 (cloud_id: {cloud_id})")
                except Exception as e:
                    logger.warning(f"[DOWNLOAD] ⚠️ 无法查询云端所有者: {e}，将尝试使用当前用户")
            
            # 回退方案 1: 如果没有 cloud_id 或查询失败，使用当前登录用户
            if not target_user_id:
                if user_id:
                    # user_id 可能已是 Supabase UUID（推荐），直接使用
                    if isinstance(user_id, str) and user_id.strip():
                        target_user_id = user_id.strip()
                        logger.info(f"[DOWNLOAD] 📌 使用当前登录用户 ID: {target_user_id}")
            
            # 回退方案 2: 最后的保底 - 开发环境默认用户
            if not target_user_id:
                logger.warning(f"[DOWNLOAD] ⚠️ 未找到用户的 Supabase User ID，使用默认用户")
                conn = db.connect()
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT supabase_user_id FROM users LIMIT 1")
                    users = cursor.fetchall()
                    if users and users[0][0]:  # 确保值不为NULL
                        target_user_id = users[0][0]  # 第一行第一列
                        logger.info(f"[DOWNLOAD] 📌 使用默认 Supabase User ID: {target_user_id}")
                finally:
                    conn.close()
            
            if not target_user_id:
                logger.error(f"[DOWNLOAD] ❌ 无法获取 Supabase User ID")
                raise APIError('无法确定云端用户身份', 400)
            
            logger.info(f"[DOWNLOAD] 🚀 最终使用的 Target User ID: {target_user_id}")
            
            # 从 PathManager 获取导出目录
            from common import PathManager
            pm = PathManager.get_instance()
            export_dir = pm.export_dir
            local_capsule_path = Path(export_dir) / file_path
            
            logger.info(f"[DOWNLOAD] PathManager 导出目录: {export_dir}")
            logger.info(f"[DOWNLOAD] 本地胶囊路径: {local_capsule_path}")
            
            # 标记开始下载，供前端轮询状态
            db.update_asset_status(
                capsule_id=capsule_id,
                asset_status='downloading'
            )

            # 使用 threading 在后台下载，避免阻塞 API
            def download_in_thread():
                try:
                    logger.info(f"[DOWNLOAD] 开始下载 Audio 文件夹: 胶囊 {capsule_id}")
                    logger.info(f"[DOWNLOAD] 云端文件夹: {target_user_id}/{capsule_dir_name}")
                    logger.info(f"[DOWNLOAD] 本地目标: {local_capsule_path}")
                    
                    # 优先本地存储客户端下载；无本地存储客户端时回退到云端签名 URL 下载 WAV
                    if supabase:
                        success = supabase.download_file(
                            user_id=target_user_id,  # ✅ 使用胶囊所有者 ID
                            capsule_folder_name=capsule_dir_name,
                            file_type='audio_folder',
                            local_path=str(local_capsule_path)
                        )
                    else:
                        if not cloud_id:
                            success = False
                        else:
                            success = _download_audio_via_cloud_signed(
                                cloud_api_origin=cloud_api_origin,
                                auth_header=auth_header,
                                cloud_id=str(cloud_id),
                                local_capsule_path=local_capsule_path,
                            )
                    
                    if success:
                        logger.info(f"[DOWNLOAD] ✅ Audio 文件夹下载成功")
                        
                        # 更新胶囊状态
                        db.update_asset_status(
                            capsule_id=capsule_id,
                            asset_status='synced'
                        )
                        
                        logger.info(f"[DOWNLOAD] ✅ 胶囊 {capsule_id} 资产状态更新为 synced")
                    else:
                        logger.error(f"[DOWNLOAD] ❌ Audio 文件夹下载失败 (supabase.download_file 返回 False)")
                        logger.error(f"[DOWNLOAD] ❌ 请检查: 1) 云端是否有文件 2) 网络连接 3) 权限")
                        db.update_asset_status(
                            capsule_id=capsule_id,
                            asset_status='download_failed'
                        )
                        return
                        
                except Exception as e:
                    logger.error(f"[DOWNLOAD] 下载异常: {e}")
                    db.update_asset_status(
                        capsule_id=capsule_id,
                        asset_status='download_failed'
                    )
                    return
            
            # 启动后台线程
            thread = threading.Thread(target=download_in_thread)
            thread.start()
            
            return jsonify({
                'success': True,
                'task_id': None,  # 简化版本，不追踪任务 ID
                'status': 'downloading',
                'message': '开始下载'
            })
            
        except APIError:
            raise
        except Exception as e:
            logger.error(f"[DOWNLOAD] 创建下载任务失败: {e}")
            raise APIError(f"创建下载任务失败: {e}", 500)

    @app.route('/api/cloud/capsules/<capsule_ref>/download-manifest', methods=['POST', 'OPTIONS'])
    def download_manifest(capsule_ref):
        """
        生成完整资产下载清单（每个文件一个 signed_url）。
        """
        if request.method == 'OPTIONS':
            return jsonify({'success': True}), 200

        try:
            # 统一鉴权：必须 Bearer token
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                raise APIError('缺少认证令牌', 401)
            token = auth_header.split(' ')[1]
            auth_manager = get_auth_manager()
            payload = None
            try:
                payload = auth_manager.verify_access_token(token)
            except Exception:
                payload = None
            if not payload and not _extract_supabase_sub_from_bearer(auth_header):
                raise APIError('Token 无效或已过期', 401)

            supabase = get_supabase_client()
            if not supabase:
                raise APIError('云端存储客户端未初始化', 503)

            data = request.get_json(silent=True) or {}
            include_preview = bool(data.get('include_preview', True))
            include_rpp = bool(data.get('include_rpp', True))
            include_metadata = bool(data.get('include_metadata', True))
            include_audio = bool(data.get('include_audio', True))
            expires_in = int(data.get('signed_url_expires_in', 900) or 900)
            expires_in = max(60, min(3600, expires_in))

            # capsule_ref 既可传 cloud_id，也可传本地 capsule_id（数字）
            cloud_id = str(capsule_ref)
            if str(capsule_ref).isdigit():
                try:
                    db = get_database()
                    local_capsule = db.get_capsule(int(capsule_ref))
                    if local_capsule and local_capsule.get('cloud_id'):
                        cloud_id = str(local_capsule['cloud_id'])
                except Exception:
                    pass

            cap_resp = (
                supabase.client
                .table('cloud_capsules')
                .select('id,user_id,name,metadata')
                .eq('id', cloud_id)
                .single()
                .execute()
            )
            cap = cap_resp.data or {}
            owner_id = cap.get('user_id')
            metadata = cap.get('metadata') or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            folder = metadata.get('file_path') or cap.get('name')
            if not owner_id or not folder:
                raise APIError('未找到云端胶囊或缺少 owner/folder', 404)

            files = []
            errors = []

            def _sign(storage_path: str):
                for bucket_name in ('capsule-files', 'capsules'):
                    try:
                        signed = supabase.create_signed_download_url(
                            storage_path,
                            expires_in=expires_in,
                            bucket_name=bucket_name,
                        )
                        if signed.get('signed_url'):
                            return bucket_name, signed['signed_url']
                    except Exception:
                        continue
                return None, None

            def _append_one(relative_path: str, size=None):
                storage_path = f"{owner_id}/{folder}/{relative_path}"
                bucket, signed_url = _sign(storage_path)
                if not signed_url:
                    errors.append(f"signed_url_failed:{relative_path}")
                    return
                files.append({
                    'relative_path': relative_path,
                    'storage_path': storage_path,
                    'signed_url': signed_url,
                    'expires_in': expires_in,
                    'size': size if isinstance(size, int) else None,
                    'bucket': bucket,
                })

            if include_metadata:
                _append_one('metadata.json')

            if include_preview:
                preview_name = metadata.get('preview_audio')
                if preview_name:
                    _append_one(preview_name)

            if include_rpp:
                rpp_name = metadata.get('rpp_file') or f"{folder}.rpp"
                _append_one(rpp_name)

            if include_audio:
                seen = set()
                for audio_dir in ('Audio', 'audio'):
                    prefix = f"{owner_id}/{folder}/{audio_dir}"
                    for bucket_name in ('capsule-files', 'capsules'):
                        try:
                            rows = supabase.client.storage.from_(bucket_name).list(prefix) or []
                        except Exception:
                            continue
                        for row in rows:
                            name = (row or {}).get('name')
                            if not isinstance(name, str):
                                continue
                            if not name.lower().endswith('.wav'):
                                continue
                            relative_path = f"{audio_dir}/{name}"
                            dedup = f"{bucket_name}:{relative_path}"
                            if dedup in seen:
                                continue
                            seen.add(dedup)
                            storage_path = f"{owner_id}/{folder}/{relative_path}"
                            signed = supabase.create_signed_download_url(
                                storage_path,
                                expires_in=expires_in,
                                bucket_name=bucket_name,
                            )
                            signed_url = signed.get('signed_url')
                            if not signed_url:
                                errors.append(f"signed_url_failed:{relative_path}")
                                continue
                            files.append({
                                'relative_path': relative_path,
                                'storage_path': storage_path,
                                'signed_url': signed_url,
                                'expires_in': expires_in,
                                'size': (row or {}).get('metadata', {}).get('size') if isinstance((row or {}).get('metadata'), dict) else None,
                                'bucket': bucket_name,
                            })

            return jsonify({
                'success': True,
                'data': {
                    'files': files,
                    'errors': errors,
                }
            })
        except APIError:
            raise
        except Exception as e:
            logger.error(f"[MANIFEST] 生成下载清单失败: {e}")
            raise APIError(f"生成下载清单失败: {e}", 500)

    @app.route('/api/capsules/<int:capsule_id>/apply-download-manifest', methods=['POST', 'OPTIONS'])
    def apply_download_manifest(capsule_id):
        """
        按清单下载并落盘到本地导出目录。
        """
        if request.method == 'OPTIONS':
            return jsonify({'success': True}), 200

        try:
            # 统一鉴权：必须 Bearer token
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                raise APIError('缺少认证令牌', 401)
            token = auth_header.split(' ')[1]
            auth_manager = get_auth_manager()
            payload = None
            try:
                payload = auth_manager.verify_access_token(token)
            except Exception:
                payload = None
            if not payload and not _extract_supabase_sub_from_bearer(auth_header):
                raise APIError('Token 无效或已过期', 401)

            data = request.get_json(silent=True) or {}
            files = data.get('files') or []
            cloud_api_origin = (data.get('cloud_api_origin') or '').strip()
            if not isinstance(files, list):
                raise APIError('files 必须为数组', 400)

            db = get_database()
            capsule = db.get_capsule(capsule_id)
            if not capsule:
                raise APIError('胶囊不存在', 404)

            file_path = capsule.get('file_path')
            if not file_path:
                raise APIError('胶囊 file_path 缺失', 400)
            capsule_folder_name = Path(file_path).name

            from common import PathManager
            pm = PathManager.get_instance()
            capsule_dir = Path(pm.export_dir) / file_path
            capsule_dir.mkdir(parents=True, exist_ok=True)
            capsule_dir_resolved = capsule_dir.resolve()

            downloaded_files = 0
            skipped_files = 0
            errors = []

            for item in files:
                signed_url = (item or {}).get('signed_url') or (item or {}).get('url')
                relative_path = (item or {}).get('relative_path')
                storage_path = (item or {}).get('storage_path')

                if not signed_url:
                    skipped_files += 1
                    errors.append('missing_signed_url')
                    continue

                if not relative_path:
                    if isinstance(storage_path, str) and '/' in storage_path:
                        parts = storage_path.split('/')
                        # owner/folder/...
                        relative_path = '/'.join(parts[2:]) if len(parts) > 2 else parts[-1]
                    else:
                        skipped_files += 1
                        errors.append('missing_relative_path')
                        continue

                # 兼容云端清单把胶囊根目录也放进 relative_path 的情况：
                # e.g. "impact_xxx/Audio/a.wav" -> "Audio/a.wav"
                if isinstance(relative_path, str):
                    rel_norm = relative_path.lstrip('/').replace('\\', '/')
                    folder_prefix = f"{capsule_folder_name}/"
                    if rel_norm.startswith(folder_prefix):
                        rel_norm = rel_norm[len(folder_prefix):]
                    relative_path = rel_norm

                target = (capsule_dir / relative_path).resolve()
                if not str(target).startswith(str(capsule_dir_resolved)):
                    skipped_files += 1
                    errors.append(f'invalid_relative_path:{relative_path}')
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    skipped_files += 1
                    continue

                try:
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

                    with urllib.request.urlopen(effective_url, timeout=120) as resp:
                        content = resp.read()
                    with open(target, 'wb') as f:
                        f.write(content)
                    downloaded_files += 1
                except Exception as e:
                    errors.append(f"download_failed:{relative_path}:{e}")

            # 只要没有错误且有文件被下载/已存在（跳过），都应视为完整可用
            # 否则刷新后 UI 会回到“可下载”状态。
            if not errors and (downloaded_files > 0 or skipped_files > 0):
                conn = db.connect()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE capsules
                        SET asset_status = 'synced',
                            files_downloaded = 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (capsule_id,),
                    )
                    conn.commit()
                finally:
                    conn.close()

            return jsonify({
                'success': len(errors) == 0,
                'data': {
                    'downloaded_files': downloaded_files,
                    'skipped_files': skipped_files,
                    'errors': errors,
                }
            }), (200 if not errors else 207)
        except APIError:
            raise
        except Exception as e:
            logger.error(f"[MANIFEST] 应用下载清单失败: {e}")
            raise APIError(f"应用下载清单失败: {e}", 500)
    
    @app.route('/api/downloads/status/<int:capsule_id>', methods=['GET'])
    def get_download_status_jit(capsule_id):
        """
        查询胶囊下载状态
        
        响应:
            {
                "status": "downloading" | "completed" | "not_started",
                "progress": 0-100,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "speed": 0,
                "eta_seconds": null
            }
        """
        try:
            db = get_database()
            capsule = db.get_capsule(capsule_id)
            
            if not capsule:
                raise APIError('胶囊不存在', 404)
            
            asset_status = capsule.get('asset_status', 'local')
            
            # 简化实现：基于 asset_status 返回状态
            if asset_status == 'synced':
                return jsonify({
                    'status': 'completed',
                    'progress': 100,
                    'downloaded_bytes': 0,
                    'total_bytes': 0,
                    'speed': 0,
                    'eta_seconds': None
                })
            elif asset_status == 'download_failed':
                return jsonify({
                    'status': 'failed',
                    'progress': 0,
                    'downloaded_bytes': 0,
                    'total_bytes': 0,
                    'speed': 0,
                    'eta_seconds': None,
                    'error_message': 'WAV 下载失败，请检查云端文件与权限'
                })
            elif asset_status == 'downloading':
                return jsonify({
                    'status': 'downloading',
                    'progress': 50,  # 简化：假设进度 50%
                    'downloaded_bytes': 0,
                    'total_bytes': 0,
                    'speed': 0,
                    'eta_seconds': None
                })
            else:
                return jsonify({
                    'status': 'not_started',
                    'progress': 0,
                    'downloaded_bytes': 0,
                    'total_bytes': 0,
                    'speed': 0,
                    'eta_seconds': None
                })
                
        except APIError:
            raise
        except Exception as e:
            logger.error(f"[DOWNLOAD] 查询下载状态失败: {e}")
            raise APIError(f"查询下载状态失败: {e}", 500)
    
    @app.route('/api/capsules/<int:capsule_id>/pause-download', methods=['POST'])
    def pause_download(capsule_id):
        """暂停下载（简化版：暂不支持）"""
        return jsonify({
            'success': False,
            'error': '简化版本暂不支持暂停下载'
        }), 501
    
    @app.route('/api/capsules/<int:capsule_id>/resume-download', methods=['POST'])
    def resume_download(capsule_id):
        """恢复下载（简化版：暂不支持）"""
        return jsonify({
            'success': False,
            'error': '简化版本暂不支持恢复下载'
        }), 501
    
    @app.route('/api/capsules/<int:capsule_id>/cancel-download', methods=['POST'])
    def cancel_download(capsule_id):
        """取消下载（简化版：暂不支持）"""
        return jsonify({
            'success': False,
            'error': '简化版本暂不支持取消下载'
        }), 501
