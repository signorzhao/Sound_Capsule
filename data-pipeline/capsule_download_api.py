"""
胶囊下载 API (JIT 决策流)

简化实现，直接使用 Supabase 客户端下载
"""

from flask import request, jsonify
from auth import get_auth_manager
from capsule_db import get_database
from supabase_client import get_supabase_client
import logging
import threading
import time
from typing import Dict, Any, Optional
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)


class APIError(Exception):
    """API 错误基类"""
    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.status_code = status_code


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
                # 如果没有 token，允许匿名访问（用于测试）
                user_id = None
            else:
                token = auth_header.split(' ')[1]
                auth_manager = get_auth_manager()
                payload = auth_manager.verify_access_token(token)
                if not payload:
                    raise APIError('Token 无效或已过期', 401)
                user_id = payload.get('user_id')
            
            # 安全获取 JSON 数据
            try:
                data = request.get_json(silent=True) or {}
            except Exception:
                data = {}
            
            force = data.get('force', False)
            priority = data.get('priority', 5)
            
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
                                # 如果本地没有这个用户，直接使用云端 UUID（可能其他用户的胶囊）
                                target_user_id = owner_supabase_uuid
                                logger.info(f"[DOWNLOAD] ⚠️ 本地未找到所有者用户，使用云端 UUID: {target_user_id}")
                        finally:
                            db.close()
                    else:
                        logger.warning(f"[DOWNLOAD] ⚠️ 云端未找到胶囊记录 (cloud_id: {cloud_id})")
                except Exception as e:
                    logger.warning(f"[DOWNLOAD] ⚠️ 无法查询云端所有者: {e}，将尝试使用当前用户")
            
            # 回退方案 1: 如果没有 cloud_id 或查询失败，使用当前登录用户
            if not target_user_id:
                if user_id:
                    user = db.get_user_by_id(user_id)
                    if user:
                        target_user_id = user.get('supabase_user_id')
                        logger.info(f"[DOWNLOAD] 📌 使用当前登录用户的 Supabase User ID: {target_user_id}")
            
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
                    db.close()
            
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
            
            # 使用 threading 在后台下载，避免阻塞 API
            def download_in_thread():
                try:
                    logger.info(f"[DOWNLOAD] 开始下载 Audio 文件夹: 胶囊 {capsule_id}")
                    logger.info(f"[DOWNLOAD] 云端文件夹: {target_user_id}/{capsule_dir_name}")
                    logger.info(f"[DOWNLOAD] 本地目标: {local_capsule_path}")
                    
                    # 下载 Audio 文件夹 - 使用胶囊所有者的 Supabase User ID
                    success = supabase.download_file(
                        user_id=target_user_id,  # ✅ 关键修复：使用胶囊所有者的 ID
                        capsule_folder_name=capsule_dir_name,
                        file_type='audio_folder',
                        local_path=str(local_capsule_path)  # 使用完整路径
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
                        # 不抛出异常，让线程正常结束
                        return
                        
                except Exception as e:
                    logger.error(f"[DOWNLOAD] 下载异常: {e}")
                    raise Exception(str(e))
            
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
