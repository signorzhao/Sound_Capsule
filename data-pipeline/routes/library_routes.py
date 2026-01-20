"""
Flask Blueprint for Library Routes

This module contains all capsule library-related routes for the Sound Capsule API.
Migrated from capsule_api.py as part of the API modularization effort (Phase G).

Core Routes:
- GET /api/capsules - Get capsule list
- GET /api/capsules/:id - Get single capsule
- POST /api/capsules - Create capsule (export)
- DELETE /api/capsules/:id - Delete capsule
- GET /api/capsules/:id/tags - Get capsule tags
- POST /api/capsules/:id/tags - Update capsule tags
"""

import logging
from flask import Blueprint, request, jsonify
from pathlib import Path

# 创建 logger
logger = logging.getLogger(__name__)

# Import dependencies from parent modules
from capsule_db import get_database
from common import load_user_config, APIError, PathManager

logger = logging.getLogger(__name__)

# Define Blueprint
library_bp = Blueprint('library_bp', __name__)


# ============================================================
# Core Capsule CRUD Routes
# ============================================================

@library_bp.route('/', methods=['GET'])
def get_capsules():
    """
    获取胶囊列表

    Phase G: 添加用户所有权支持（is_mine 字段）和过滤器

    Query Parameters:
        - filter: 过滤器类型 (all, mine, downloaded) - 默认 all
        - lens: 语义棱镜类型（可选）
        - x, y: 中心点坐标（可选）
        - radius: 搜索半径（默认 20）
        - limit: 返回数量限制（默认 50）
        - offset: 偏移量（默认 0）
    """
    try:
        filter_type = request.args.get('filter', 'all')  # Phase G: 新增
        lens = request.args.get('lens')
        x = request.args.get('x', type=float)
        y = request.args.get('y', type=float)
        radius = request.args.get('radius', 20, type=float)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        db = get_database()
        capsules = db.get_capsules(
            lens=lens,
            x=x,
            y=y,
            radius=radius,
            limit=limit,
            offset=offset
        )

        # Phase G: 获取当前用户 ID 以判断所有权
        current_user_id = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                from auth import get_auth_manager
                auth_manager = get_auth_manager()
                token = auth_header.split(' ')[1]
                payload = auth_manager.verify_access_token(token)
                if payload:
                    # 优先使用 payload 中的 supabase_user_id
                    if 'supabase_user_id' in payload:
                        current_user_id = payload['supabase_user_id']
                    elif 'user_id' in payload:
                        # 如果是本地用户，尝试从 auth_manager 获取
                        user = auth_manager.get_user_by_id(payload['user_id'])
                        if user:
                            current_user_id = user.get('supabase_user_id') or str(user.get('id'))
                    logger.info(f"[CAPSULES] 当前用户 ID: {current_user_id}")
            except Exception as e:
                logger.warning(f"[CAPSULES] Token 验证失败: {e}")
                pass  # 允许匿名访问

        # 为每个胶囊添加完整的 RPP 路径（绝对路径）
        # 使用 PathManager 获取导出目录
        pm = PathManager.get_instance()
        export_base = pm.export_dir

        for capsule in capsules:
            # 添加 RPP 路径
            if capsule.get('file_path') and capsule.get('rpp_file'):
                rpp_path = export_base / capsule['file_path'] / capsule['rpp_file']
                capsule['local_rpp_path'] = str(rpp_path.resolve())

            # Phase G: 添加所有权标识
            capsule['is_mine'] = (
                current_user_id and
                capsule.get('owner_supabase_user_id') == current_user_id
            )

        # Phase G: 应用过滤器
        if filter_type == 'mine':
            capsules = [c for c in capsules if c.get('is_mine', False)]
        elif filter_type == 'downloaded':
            capsules = [c for c in capsules if c.get('files_downloaded', False)]

        return jsonify({
            'success': True,
            'capsules': capsules,
            'count': len(capsules),
            'filter': filter_type  # Phase G: 返回当前过滤器
        })

    except Exception as e:
        import traceback
        logger.error(f"❌ 获取胶囊列表失败: {e}")
        traceback.print_exc()
        raise APIError(f"获取胶囊列表失败: {e}", 500)


@library_bp.route('/<int:capsule_id>', methods=['GET'])
def get_capsule(capsule_id):
    """获取单个胶囊详情"""
    try:
        db = get_database()
        capsule = db.get_capsule(capsule_id)

        if not capsule:
            raise APIError(f"胶囊不存在: {capsule_id}", 404)

        # 添加完整的 RPP 路径（绝对路径）
        # 使用 PathManager 获取导出目录
        pm = PathManager.get_instance()
        export_base = pm.export_dir

        if capsule.get('file_path') and capsule.get('rpp_file'):
            rpp_path = export_base / capsule['file_path'] / capsule['rpp_file']
            capsule['local_rpp_path'] = str(rpp_path.resolve())

        return jsonify({
            'success': True,
            'capsule': capsule
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"获取胶囊失败: {e}", 500)


@library_bp.route('/<int:capsule_id>', methods=['DELETE'])
def delete_capsule_api(capsule_id):
    """删除胶囊（只删除数据库记录，不删除文件）"""
    try:
        db = get_database()

        # 检查胶囊是否存在
        capsule = db.get_capsule(capsule_id)
        if not capsule:
            raise APIError(f"胶囊不存在: {capsule_id}", 404)

        # 使用封装的方法删除
        if db.delete_capsule(capsule_id):
            return jsonify({
                'success': True,
                'message': f'已删除胶囊 {capsule_id} 数据库记录'
            })
        else:
            raise APIError("删除失败", 500)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"删除胶囊失败: {e}", 500)


# ============================================================
# Capsule Tags Routes
# ============================================================

@library_bp.route('/<int:capsule_id>/tags', methods=['GET'])
def get_capsule_tags_api(capsule_id):
    """获取胶囊的所有标签（按棱镜分组）"""
    try:
        db = get_database()
        capsule = db.get_capsule(capsule_id)

        if not capsule:
            raise APIError(f"胶囊不存在: {capsule_id}", 404)

        tags = db.get_capsule_tags(capsule_id)

        return jsonify({
            'success': True,
            'tags': tags,
            'capsule': capsule
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"获取标签失败: {e}", 500)


@library_bp.route('/<int:capsule_id>/tags', methods=['POST'])
def update_capsule_tags_api(capsule_id):
    """
    更新胶囊标签

    🔐 Phase G: 添加所有权检查，只有胶囊所有者才能编辑标签
    - 对于有 owner_supabase_user_id 的胶囊：只有所有者可以编辑
    - 对于没有 owner 的旧胶囊：允许所有已认证用户编辑

    请求体:
        {
            "tags": {
                "texture": [...],
                "source": [...],
                "materiality": [...],
                "temperament": [...]
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            raise APIError('请求体不能为空', 400)

        # 数据本身就是 tags 对象（前端直接发送 {texture: [], source: [], ...}）
        tags = data if isinstance(data, dict) else {}
        db = get_database()

        import json
        print(f"[DEBUG] POST /api/capsules/{capsule_id}/tags")
        print(f"[DEBUG] 原始 JSON: {json.dumps(data, ensure_ascii=False, indent=2)}")
        print(f"[DEBUG] 接收到的数据: {tags}")
        print(f"[DEBUG] tags.keys(): {list(tags.keys())}")

        # 验证胶囊是否存在
        capsule = db.get_capsule(capsule_id)
        if not capsule:
            raise APIError(f"胶囊不存在: {capsule_id}", 404)

        # 🔐 所有权检查：只有胶囊所有者才能编辑标签
        current_user_id = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                from auth import get_auth_manager
                auth_manager = get_auth_manager()
                token = auth_header.split(' ')[1]
                payload = auth_manager.verify_access_token(token)
                if payload:
                    # 优先使用 payload 中的 supabase_user_id
                    if 'supabase_user_id' in payload:
                        current_user_id = payload['supabase_user_id']
                    elif 'user_id' in payload:
                        # 如果是本地用户，尝试从 auth_manager 获取
                        user = auth_manager.get_user_by_id(payload['user_id'])
                        if user:
                            current_user_id = user.get('supabase_user_id') or str(user.get('id'))
                    logger.info(f"[TAGS] ✓ Token 验证成功: 用户 {current_user_id}")
            except Exception as e:
                logger.warning(f"[TAGS] Token 验证失败: {e}")
                pass

        owner_id = capsule.get('owner_supabase_user_id')
        
        # 检查权限：
        # 1. 如果胶囊有所有者，必须是所有者才能编辑
        # 2. 如果胶囊没有所有者（旧数据），允许任何已认证用户编辑
        if owner_id:
            if not current_user_id:
                raise APIError('需要登录才能编辑此胶囊', 401)
            if current_user_id != owner_id:
                raise APIError('无权编辑此胶囊：您不是胶囊所有者', 403)
            logger.info(f"[TAGS] ✓ 所有权验证通过: 用户 {current_user_id} 编辑胶囊 {capsule_id}")
        else:
            # 旧胶囊（没有 owner），记录日志但允许编辑
            logger.info(f"[TAGS] ℹ️ 胶囊 {capsule_id} 没有所有者（旧数据），允许编辑")

        print(f"[DEBUG] 胶囊存在: {capsule['name']}")

        # 删除旧标签
        db.delete_capsule_tags(capsule_id)
        print(f"[DEBUG] 已删除旧标签")

        # 收集所有标签到一个列表
        all_tags = []
        logger.info(f"[TAGS] 接收到的原始 tags 数据: {tags}")
        logger.info(f"[TAGS] tags.keys(): {list(tags.keys())}")

        for lens, tag_list in tags.items():
            logger.info(f"[TAGS] 处理棱镜 {lens}, 标签数量: {len(tag_list) if tag_list else 0}")
            # 🔥 移除硬编码白名单，允许所有棱镜（包括 mechanics、force_field_test 等）
            # 遵循架构规范：严禁硬编码棱镜 ID

            if not tag_list or len(tag_list) == 0:
                continue

            for tag in tag_list:
                # 🔥 字段兼容：支持多种字段名称
                word_id = tag.get('word_id') or tag.get('id') or tag.get('word')
                word_cn = tag.get('word_cn') or tag.get('zh') or tag.get('word_cn')
                word_en = tag.get('word_en') or tag.get('en') or tag.get('word')
                x = tag.get('x')
                y = tag.get('y')

                all_tags.append({
                    'lens': lens,
                    'word_id': word_id,
                    'word_cn': word_cn,
                    'word_en': word_en,
                    'x': x,
                    'y': y
                })

        logger.info(f"[TAGS] 收集到的 all_tags 数量: {len(all_tags)}")
        print(f"[DEBUG] 收集到的 all_tags 数量: {len(all_tags)}")
        print(f"[DEBUG] all_tags 内容: {all_tags[:3] if all_tags else []}")

        # 批量插入所有标签
        if all_tags:
            print(f"[DEBUG] 开始插入 {len(all_tags)} 个标签...")
            db.add_capsule_tags(capsule_id, all_tags)
            print(f"[DEBUG] 插入完成")
            logger.info(f"✓ 插入 {len(all_tags)} 个标签到胶囊 {capsule_id}")

            # 🔥 关键：聚合关键词到 capsules.keywords 字段
            print(f"[DEBUG] 开始聚合关键词...")
            db.aggregate_and_update_keywords(capsule_id)
            print(f"[DEBUG] 关键词聚合完成")
            
            # 🌐 标记关键词为待同步状态（等待用户点击顶部同步按钮时同步）
            try:
                from sync_service import get_sync_service
                sync_service = get_sync_service()
                sync_service.mark_for_sync('capsule_tags', capsule_id, 'update')
                logger.info(f"[TAGS] ✓ 已标记关键词待同步: 胶囊 {capsule_id}")
            except Exception as e:
                logger.warning(f"[TAGS] 标记待同步失败: {e}")
            
            # 🔑 关键修复：执行 WAL checkpoint，确保标签数据立即对其他连接可见
            # 这解决了编辑关键词后数据不更新的问题
            try:
                db.wal_checkpoint()
                logger.info(f"[TAGS] ✓ WAL checkpoint 完成，标签数据已同步")
            except Exception as e:
                logger.warning(f"[TAGS] WAL checkpoint 失败: {e}")
        else:
            logger.warning(f"⚠️ 胶囊 {capsule_id} 没有标签需要插入")

        return jsonify({
            'success': True,
            'message': '标签已更新',
            'capsule_id': capsule_id,
            'tags_count': len(all_tags),
            'pending_sync': True  # 标签已标记为待同步
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"更新标签失败: {e}", 500)


@library_bp.route('/<int:capsule_id>/tags', methods=['PUT'])
def replace_capsule_tags_api(capsule_id):
    """
    替换胶囊标签（与 POST 功能相同，保留用于兼容）

    请求体:
        {
            "tags": {
                "texture": [...],
                "source": [...],
                "materiality": [...],
                "temperament": [...]
            }
        }
    """
    # 直接调用 POST 方法的实现
    return update_capsule_tags_api(capsule_id)
