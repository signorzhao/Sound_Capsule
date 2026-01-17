"""
Synesth 胶囊系统 Flask API 服务器

提供胶囊管理的 RESTful API 接口
"""

import os
import sys
import json
import uuid
import subprocess
import argparse
import logging
import sqlite3
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

from capsule_db import get_database
from auth import get_auth_manager
from sync_service import get_sync_service
from prism_version_manager import PrismVersionManager
import capsule_scanner
from supabase_client import get_supabase_client
from capsule_download_api import register_download_routes

# ML 功能可选导入（需要 numpy, sklearn, sentence-transformers）
try:
    from hybrid_embedding_service import get_hybrid_service
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    logging.warning(f"ML 功能不可用（缺少依赖）: {e}")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

# ============================================
# 命令行参数解析
# ============================================

def parse_arguments():
    """
    解析命令行参数

    支持的参数:
        --config-dir: 配置目录路径（由 Rust 传递）
        --export-dir: 导出目录路径（由 Rust 传递）
        --resource-dir: 资源目录路径（打包后使用）
        --port: API 端口（默认 5002）

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='Sound Capsule API Server')

    parser.add_argument('--config-dir', type=str,
                        help='配置目录路径')
    parser.add_argument('--export-dir', type=str,
                        help='导出目录路径')
    parser.add_argument('--resource-dir', type=str,
                        help='资源目录路径（打包后）')
    parser.add_argument('--port', type=int, default=5002,
                        help='API 服务器端口（默认 5002）')

    return parser.parse_args()

# 解析命令行参数
ARGS = parse_arguments()

# ============================================
# 路径初始化 - 🔴 架构铁律：禁止路径猜测
# ============================================

# 强制检查必需参数
if not ARGS.config_dir or not ARGS.export_dir:
    print("\n" + "=" * 60)
    print("❌ 错误：缺少必需的命令行参数")
    print("=" * 60)
    print("Sound Capsule 必须由 Tauri 启动并传递以下参数：")
    print("  --config-dir  : 配置目录路径")
    print("  --export-dir  : 导出目录路径")
    print("  --resource-dir: 资源目录路径（可选，开发环境可省略）")
    print("\n这是架构铁律：Python 后端严禁自行猜测路径。")
    print("如果你在开发环境中直接运行此脚本，请使用：")
    print("  python capsule_api.py --config-dir <path> --export-dir <path>")
    print("=" * 60 + "\n")
    sys.exit(1)

# 资源目录：打包环境由 Tauri 传递，开发环境使用脚本所在目录
RESOURCE_DIR = Path(ARGS.resource_dir) if ARGS.resource_dir else Path(__file__).parent

# ============================================
# 初始化统一路径管理器（必须在任何其他模块导入之前）
# ============================================
from common import PathManager

PathManager.initialize(
    config_dir=str(ARGS.config_dir),
    export_dir=str(ARGS.export_dir),
    resource_dir=str(RESOURCE_DIR)
)

# 获取路径管理器实例
pm = PathManager.get_instance()

# 向后兼容：设置旧的全局变量（新代码应该使用 pm）
CONFIG_DIR = pm.config_dir
EXPORT_DIR = pm.export_dir

# 设置日志文件
LOG_FILE = pm.get_config_file('export_debug.log')

def log_to_file(message):
    """写入日志到文件"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)  # 同时输出到控制台

# 加载环境变量
load_dotenv()

# 打印路径配置信息
print("\n" + "=" * 60)
print("📂 路径配置（由 PathManager 管理）")
print("=" * 60)
print(f"  CONFIG_DIR: {pm.config_dir}")
print(f"  EXPORT_DIR: {pm.export_dir}")
print(f"  RESOURCE_DIR: {pm.resource_dir}")
print(f"  DB_PATH: {pm.db_path}")
print(f"  SCHEMA_PATH: {pm.schema_path}")
print(f"  LUA_SCRIPTS_DIR: {pm.lua_scripts_dir}")
print(f"  LOG_FILE: {LOG_FILE}")
print("=" * 60 + "\n")

# load_user_config 已在 common.py 中定义，这里不需要重复定义

def setup_export_environment():
    """
    设置导出环境变量

    使用路径管理器的导出目录，并设置环境变量供 Lua 脚本使用
    """
    pm = PathManager.get_instance()
    export_dir = str(pm.export_dir)

    os.environ['SYNESTH_CAPSULE_OUTPUT'] = export_dir
    log_to_file(f"✅ 设置导出目录环境变量: {export_dir}")
    print(f"✅ 设置导出目录环境变量: {export_dir}")

    return export_dir

app = Flask(__name__)
# 允许前端 (3000, 3002, 5173) 和 REAPER Web UI (9000) 访问
default_origins = 'http://localhost:3000,http://localhost:3002,http://localhost:5173,http://localhost:9000,http://198.18.0.1:9000'
cors_origins = os.getenv('CORS_ORIGINS', default_origins).split(',')

# 允许所有本地开发端口访问
CORS(app, resources={r"/api/*": {
    "origins": "*",  # 开发环境允许所有源
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "max_age": 3600,
    "supports_credentials": False  # 不使用凭证时可以放宽限制
}})

# 注册下载相关路由 (JIT 决策流)
register_download_routes(app)

# 配置（使用路径管理器）
DB_PATH = str(pm.db_path)  # 数据库路径从路径管理器获取
REAPER_CAPSULE_PATH = Path(os.getenv('REAPER_SONIC_CAPSULE_PATH', '../Reaper_Sonic_Capsule'))

# ============================================
# 🚀 Blueprint 注册 (API Modularization - Phase G, Step 0)
# ============================================
logger.info("正在注册 API Blueprint 模块...")

# 导入 Blueprint 模块
from routes.sync_routes import sync_bp
from routes.library_routes import library_bp

# 注册同步模块，所有路由前缀为 /api/sync
app.register_blueprint(sync_bp, url_prefix='/api/sync')
logger.info("✅ Sync Routes 注册: /api/sync/*")

# 注册库模块，所有路由前缀为 /api/capsules
app.register_blueprint(library_bp, url_prefix='/api/capsules')
logger.info("✅ Library Routes 注册: /api/capsules/*")

# ============================================
# Phase C1: 棱镜版本管理器初始化
# ============================================
# 使用 PathManager 获取正确的数据库路径
from common import PathManager
pm = PathManager.get_instance()
prism_manager = PrismVersionManager(db_path=str(pm.db_path))
try:
    prism_manager.init_tables()
    logger.info("✅ 棱镜版本管理器初始化成功")
except Exception as e:
    logger.error(f"❌ 棱镜版本管理器初始化失败: {e}")

# 配置信息已在上方的 PathManager 初始化时打印
# 不再需要重复打印


# ============================================
# 错误处理
# ============================================

# 从 common 模块导入 APIError 和 init_paths
from common import APIError, init_paths

# 为向后兼容，同步全局路径变量（PathManager 已在上方初始化）
init_paths(str(CONFIG_DIR), str(EXPORT_DIR), str(RESOURCE_DIR))

@app.errorhandler(APIError)
def handle_api_error(error):
    """处理 API 错误"""
    import traceback
    logger.error(f"API Error: {error.message}")
    logger.error(traceback.format_exc())
    response = jsonify({
        'success': False,
        'error': error.message
    })
    response.status_code = error.status_code
    return response


@app.errorhandler(Exception)
def handle_generic_error(error):
    """处理通用错误"""
    import traceback
    logger.error(f"Internal Server Error: {error}")
    logger.error(traceback.format_exc())
    print(f"服务器错误: {error}")
    response = jsonify({
        'success': False,
        'error': '内部服务器错误'
    })
    response.status_code = 500
    return response


# ============================================
# 工具函数
# ============================================

def find_reaper_executable():
    """
    查找 REAPER 可执行文件（跨平台）
    
    优先使用用户配置的路径

    Returns:
        Path 或 None
    """
    import platform
    import shutil
    import json

    # 1. 优先读取用户配置的 REAPER 路径
    try:
        system = platform.system()
        if system == "Darwin":
            config_path = Path.home() / "Library/Application Support/com.soundcapsule.app/config.json"
        elif system == "Windows":
            config_path = Path.home() / "AppData/Roaming/com.soundcapsule.app/config.json"
        else:
            config_path = Path.home() / ".config/com.soundcapsule.app/config.json"
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                reaper_path = config.get('reaper_path')
                if reaper_path:
                    reaper_exe = Path(reaper_path)
                    if reaper_exe.exists():
                        print(f"✓ 使用用户配置的 REAPER 路径: {reaper_exe}")
                        return reaper_exe
                    else:
                        print(f"⚠️ 用户配置的 REAPER 路径不存在: {reaper_path}")
    except Exception as e:
        print(f"⚠️ 读取 REAPER 配置失败: {e}")

    # 2. 降级到默认路径
    system = platform.system()

    if system == "Darwin":  # macOS
        paths = [
            Path("/Applications/REAPER.app/Contents/MacOS/REAPER"),
            Path("/Applications/REAPER64.app/Contents/MacOS/REAPER"),
            Path.home() / "Applications/REAPER.app/Contents/MacOS/REAPER"
        ]
    elif system == "Windows":
        paths = [
            Path("C:/Program Files/REAPER (x64)/reaper.exe"),
            Path("C:/Program Files/REAPER/reaper.exe"),
            Path("C:/Program Files (x86)/REAPER/reaper.exe"),
            Path.home() / "AppData/Local/Programs/REAPER/reaper.exe"
        ]
    else:  # Linux
        reaper_in_path = shutil.which("reaper")
        if reaper_in_path:
            return Path(reaper_in_path)
        paths = [Path("/usr/bin/reaper")]

    for path in paths:
        if path.exists():
            print(f"✓ 找到 REAPER: {path}")
            return path

    return None


# ============================================
# 认证中间件
# ============================================

def get_current_user():
    """
    从请求中获取当前用户
    
    支持两种认证方式：
    1. Supabase Auth：token 验证后返回 supabase_user_id
    2. 本地认证：token 验证后返回 user_id（整数）

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
    def decorated(*args, **kwargs):
        user = get_current_user()

        if not user:
            raise APIError('需要认证', 401)

        # 将用户信息传递给视图函数
        return f(current_user=user, *args, **kwargs)

    # 保留原始函数的名称
    decorated.__name__ = f.__name__
    return decorated


# ============================================
# 认证 API 端点
# ============================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """
    用户注册

    请求体:
        {
            "username": "用户名",
            "email": "邮箱",
            "password": "密码"
        }

    响应:
        {
            "success": true,
            "message": "注册成功",
            "data": {
                "user": {...},
                "tokens": {
                    "access_token": "...",
                    "refresh_token": "...",
                    "expires_in": 1800
                }
            }
        }
    """
    try:
        data = request.get_json()

        # 验证必填字段
        if not data:
            raise APIError('请求体不能为空', 400)

        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not all([username, email, password]):
            raise APIError('用户名、邮箱和密码不能为空', 400)

        # 注册用户
        auth_manager = get_auth_manager()
        result = auth_manager.register_user(username, email, password)

        # 移除敏感信息
        if 'user' in result and 'password_hash' in result['user']:
            del result['user']['password_hash']

        return jsonify({
            'success': True,
            'message': '注册成功',
            'data': result
        }), 201

    except ValueError as e:
        raise APIError(str(e), 400)
    except Exception as e:
        raise APIError(f'注册失败: {e}', 500)


@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    用户登录

    请求体:
        {
            "login": "用户名或邮箱",
            "password": "密码"
        }

    响应:
        {
            "success": true,
            "message": "登录成功",
            "data": {
                "user": {...},
                "tokens": {...}
            }
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError('请求体不能为空', 400)

        login = data.get('login')
        password = data.get('password')

        if not all([login, password]):
            raise APIError('登录凭证不能为空', 400)

        # 登录
        auth_manager = get_auth_manager()
        result = auth_manager.login_user(login, password)

        # 移除敏感信息
        if 'user' in result and 'password_hash' in result['user']:
            del result['user']['password_hash']

        return jsonify({
            'success': True,
            'message': '登录成功',
            'data': result
        })

    except ValueError as e:
        raise APIError(str(e), 401)
    except Exception as e:
        raise APIError(f'登录失败: {e}', 500)


@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """
    刷新 Access Token

    请求体:
        {
            "refresh_token": "..."
        }

    响应:
        {
            "success": true,
            "data": {
                "access_token": "...",
                "expires_in": 1800
            }
        }
    """
    try:
        data = request.get_json()

        if not data or not data.get('refresh_token'):
            raise APIError('refresh_token 不能为空', 400)

        refresh_token = data['refresh_token']
        auth_manager = get_auth_manager()

        result = auth_manager.refresh_token(refresh_token)

        return jsonify({
            'success': True,
            'data': result
        })

    except ValueError as e:
        raise APIError(str(e), 401)
    except Exception as e:
        raise APIError(f'Token 刷新失败: {e}', 500)


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """
    用户注销

    请求体:
        {
            "refresh_token": "..."
        }

    响应:
        {
            "success": True,
            "message": "注销成功"
        }
    """
    try:
        data = request.get_json()

        if not data or not data.get('refresh_token'):
            raise APIError('refresh_token 不能为空', 400)

        refresh_token = data['refresh_token']
        auth_manager = get_auth_manager()

        auth_manager.logout_user(refresh_token)

        return jsonify({
            'success': True,
            'message': '注销成功'
        })

    except Exception as e:
        raise APIError(f'注销失败: {e}', 500)


@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user_info(current_user):
    """
    获取当前用户信息

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "user": {...}
            }
        }
    """
    return jsonify({
        'success': True,
        'data': {
            'user': current_user
        }
    })


@app.route('/api/auth/me', methods=['PUT'])
@token_required
def update_current_user_info(current_user):
    """
    更新当前用户信息

    需要认证

    请求体:
        {
            "display_name": "显示名称",
            "bio": "个人简介",
            "avatar_url": "头像 URL",
            "preferences": {...}
        }

    响应:
        {
            "success": True,
            "message": "用户信息更新成功",
            "data": {
                "user": {...}
            }
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError('请求体不能为空', 400)

        auth_manager = get_auth_manager()
        user = auth_manager.update_user_profile(current_user['id'], data)

        return jsonify({
            'success': True,
            'message': '用户信息更新成功',
            'data': {
                'user': user
            }
        })

    except ValueError as e:
        raise APIError(str(e), 400)
    except Exception as e:
        raise APIError(f'更新用户信息失败: {e}', 500)


@app.route('/api/auth/password', methods=['PUT'])
@token_required
def change_password(current_user):
    """
    修改密码

    需要认证

    请求体:
        {
            "old_password": "旧密码",
            "new_password": "新密码"
        }

    响应:
        {
            "success": True,
            "message": "密码修改成功"
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError('请求体不能为空', 400)

        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if not all([old_password, new_password]):
            raise APIError('旧密码和新密码不能为空', 400)

        auth_manager = get_auth_manager()
        auth_manager.change_password(current_user['id'], old_password, new_password)

        return jsonify({
            'success': True,
            'message': '密码修改成功'
        })

    except ValueError as e:
        raise APIError(str(e), 400)
    except Exception as e:
        raise APIError(f'修改密码失败: {e}', 500)


# ============================================
# 其他 API 端点
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'success': True,
        'service': 'Synesth Capsule API',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/debug-log', methods=['POST'])
def debug_log():
    """调试日志端点（用于追踪应用重启问题）"""
    try:
        data = request.get_json()
        message = data.get('message', 'NO MESSAGE')
        
        # 写入日志文件
        import os
        from pathlib import Path
        
        log_dir = Path.home() / 'Library/Application Support/com.soundcapsule.app'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'debug.log'
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_entry = f"[{timestamp}] {message}\n"
        
        # 追加日志（如果文件太大则清空）
        if log_file.exists() and log_file.stat().st_size > 1024 * 1024:  # 1MB
            log_file.write_text(log_entry)
        else:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        
        # 同时输出到控制台
        logger.info(f"[DEBUG] {message}")
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"写入调试日志失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/capsules', methods=['POST'])
def create_capsule():
    """
    创建新胶囊 (手动创建)
    
    请求体:
        {
            "title": "胶囊名称",
            "description": "描述",
            "type": "magic",
            "file_path": "路径/到/文件",
            ...
        }
    """
    try:
        data = request.get_json()
        logger.info(f"Received request to create capsule: {data}")
        
        if not data:
            raise APIError("Request body is empty", 400)
            
        uuid_str = data.get('uuid', str(uuid.uuid4()))
        name = data.get('title') or data.get('name', 'Untitled')
        
        # 构造符合数据库要求的字典
        capsule_data = {
            'uuid': uuid_str,
            'name': name,
            'project_name': data.get('project_name', name),
            'theme_name': data.get('theme_name', 'default'),
            'capsule_type': data.get('type', 'magic'),
            'file_path': data.get('file_path', ''),
            'preview_audio': data.get('preview_audio', ''),
            'rpp_file': data.get('rpp_file', ''),
            'metadata': data.get('metadata', {})
        }
        
        db = get_database()
        logger.info(f"Inserting capsule into database: {capsule_data}")
        capsule_id = db.insert_capsule(capsule_data)
        logger.info(f"Capsule created with ID: {capsule_id}")
        
        # 如果有标签数据，也尝试添加
        if 'tags' in data:
            tags = data['tags']
            # 将简单字符串标签转换为数据库格式 (简化处理)
            formatted_tags = []
            for t in tags:
                if isinstance(t, str):
                    formatted_tags.append({
                        'lens': 'texture', # 默认 lens
                        'word_id': f"tag_{uuid.uuid4().hex[:8]}", 
                        'word_cn': t
                    })
                elif isinstance(t, dict):
                    formatted_tags.append(t)
            
            if formatted_tags:
                db.add_capsule_tags(capsule_id, formatted_tags)
                
        # 返回创建的胶囊数据
        return jsonify({
            'success': True,
            'message': 'Capsule created successfully',
            'capsule': {
                'id': capsule_id,
                **capsule_data
            }
        }), 201
        
    except Exception as e:
        import traceback
        logger.error(f"Failed to create capsule: {e}")
        logger.error(traceback.format_exc())
        raise APIError(f"Failed to create capsule: {str(e)}", 500)


# ============================================================
# ⚠️  以下路由已迁移到 routes/library_routes.py Blueprint
# ============================================================
# GET /api/capsules - get_capsules (已迁移)
# GET /api/capsules/<int:capsule_id> - get_capsule (已迁移)
# DELETE /api/capsules/<int:capsule_id> - delete_capsule_api (已迁移)
# GET /api/capsules/<int:capsule_id>/tags - get_capsule_tags_api (已迁移)
# POST /api/capsules/<int:capsule_id>/tags - add_capsule_tags (已迁移)
# PUT /api/capsules/<int:capsule_id>/tags - replace_capsule_tags (已迁移)
# ============================================================

@app.route('/api/capsules/export', methods=['POST'])
def export_capsule():
    """
    导出胶囊

    Request Body:
        {
            "project_name": "项目名",
            "theme_name": "主题名",
            "render_preview": true
        }

    Returns:
        {
            "success": true,
            "capsule_id": 123,
            "capsule_path": "/path/to/capsule"
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError("请求体不能为空")

        project_name = data.get('project_name', '').strip()
        theme_name = data.get('theme_name', '').strip()
        render_preview = data.get('render_preview', True)

        if not project_name:
            raise APIError("项目名不能为空")

        if not theme_name:
            raise APIError("主题名不能为空")

        # 调用 REAPER 桥接器导出胶囊
        from exporters.reaper_bridge import ReaperBridge

        bridge = ReaperBridge(REAPER_CAPSULE_PATH, use_headless=True)

        result = bridge.export_capsule(
            project_name=project_name,
            theme_name=theme_name,
            render_preview=render_preview,
            output_dir=capsule_scanner.get_output_dir()  # 使用用户配置的导出目录
        )

        if not result.get('success'):
            raise APIError(result.get('error', '导出失败'), 500)

        # 读取导出的元数据
        capsule_path = Path(result.get('capsule_path'))
        metadata_file = capsule_path / "metadata.json"

        if not metadata_file.exists():
            raise APIError("导出成功但未找到元数据文件", 500)

        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # 插入数据库
        # 使用相对于导出目录的路径
        capsule_data = {
            'uuid': metadata.get('id', str(uuid.uuid4())),
            'name': metadata.get('name', f"{project_name}_{theme_name}"),
            'project_name': project_name,
            'theme_name': theme_name,
            'capsule_type': 'magic',  # 默认为 magic
            'file_path': str(capsule_path.relative_to(capsule_scanner.get_output_dir())),
            'preview_audio': metadata.get('preview_audio'),
            'rpp_file': metadata.get('files', {}).get('project', 'source.rpp'),
            'metadata': {
                'bpm': metadata.get('info', {}).get('bpm'),
                'duration': metadata.get('info', {}).get('length'),
                'sample_rate': metadata.get('info', {}).get('sample_rate'),
                'plugin_count': metadata.get('plugins', {}).get('count'),
                'plugin_list': metadata.get('plugins', {}).get('list', []),
                'has_sends': metadata.get('routing_info', {}).get('has_sends'),
                'has_folder_bus': metadata.get('routing_info', {}).get('has_folder_bus'),
                'tracks_included': metadata.get('routing_info', {}).get('tracks_included')
            }
        }

        db = get_database()
        capsule_id = db.insert_capsule(capsule_data)

        # 检测本地 WAV 文件并更新 asset_status
        audio_folder = capsule_path / "Audio"
        if audio_folder.exists():
            wav_files = list(audio_folder.glob("*.wav"))
            if wav_files:
                # 有 WAV 文件，更新为 local 状态
                total_size = sum(f.stat().st_size for f in wav_files)
                db.connect()
                try:
                    cursor = db.conn.cursor()
                    cursor.execute("""
                        UPDATE capsules
                        SET asset_status = 'local',
                            local_wav_path = ?,
                            local_wav_size = ?
                        WHERE id = ?
                    """, (str(audio_folder), total_size, capsule_id))
                    db.conn.commit()
                    print(f"✓ 胶囊 {capsule_id} 设置为 local 状态（{len(wav_files)} 个 WAV 文件）")
                finally:
                    db.close()

        return jsonify({
            'success': True,
            'capsule_id': capsule_id,
            'capsule_path': str(capsule_path),
            'metadata': metadata
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"导出失败: {e}", 500)


# POST 和 PUT /api/capsules/<int:capsule_id>/tags 已迁移到 routes/library_routes.py

@app.route('/api/capsules/<int:capsule_id>/preview', methods=['GET'])
@app.route('/api/capsules/<int:capsule_id>/preview/<path:filename>', methods=['GET'])
def stream_preview(capsule_id, filename=None):
    """
    流式传输预览音频

    支持两种格式:
    - /api/capsules/{id}/preview (使用数据库中的文件名)
    - /api/capsules/{id}/preview/{filename} (直接指定文件名)

    支持 Range 请求（可拖动进度条）
    """
    try:
        # 导入 scanner 模块以获取 OUTPUT_DIR
        import capsule_scanner

        db = get_database()
        capsule = db.get_capsule(capsule_id)

        if not capsule:
            raise APIError(f"胶囊不存在: {capsule_id}", 404)

        # 如果提供了文件名参数，使用它；否则使用数据库中的
        preview_audio = filename or capsule.get('preview_audio')

        if not preview_audio:
            raise APIError("预览音频文件不存在", 404)

        # 使用 get_output_dir()（用户配置的导出目录）而不是 CAPSULE_ROOT
        # capsule['file_path'] 是相对于 output_dir 的路径
        output_dir = capsule_scanner.get_output_dir()
        preview_file = output_dir / capsule['file_path'] / preview_audio

        # 调试日志
        print(f"🔍 [预览音频] 调试信息:")
        print(f"  - output_dir: {output_dir}")
        print(f"  - output_dir (absolute): {output_dir.resolve()}")
        print(f"  - capsule['file_path']: {capsule['file_path']}")
        print(f"  - preview_audio: {preview_audio}")
        print(f"  - 拼接后的路径: {preview_file}")
        print(f"  - 绝对路径: {preview_file.resolve()}")
        print(f"  - 文件存在: {preview_file.exists()}")

        if not preview_file.exists():
            raise APIError(f"预览音频文件不存在: {preview_audio}", 404)

        # 转换为绝对路径
        preview_file = preview_file.resolve()

        return send_file(
            preview_file,
            mimetype='audio/ogg',
            as_attachment=False,
            conditional=True  # 支持 Range 请求
        )

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"获取预览失败: {e}", 500)


@app.route('/api/capsules/<int:capsule_id>/metadata', methods=['GET'])
def get_capsule_metadata(capsule_id):
    """
    获取胶囊的 metadata.json 内容

    Returns:
        metadata 对象
    """
    try:
        # 导入 scanner 模块以获取 OUTPUT_DIR
        import capsule_scanner

        db = get_database()
        capsule = db.get_capsule(capsule_id)

        if not capsule:
            raise APIError(f"胶囊不存在: {capsule_id}", 404)

        # 使用 OUTPUT_DIR（用户配置的导出目录）而不是 CAPSULE_ROOT
        metadata_file = capsule_scanner.get_output_dir() / capsule['file_path'] / 'metadata.json'

        # 如果文件不存在，尝试从数据库获取 metadata
        if not metadata_file.exists():
            logger.info(f"[Metadata] metadata.json 文件不存在，从数据库获取 metadata (胶囊 ID: {capsule_id})")

            # 从 capsule.get_capsule() 已经包含了 metadata
            if capsule.get('metadata'):
                return jsonify({
                    'success': True,
                    'metadata': capsule['metadata']
                })
            else:
                raise APIError("metadata.json 文件不存在且数据库中无 metadata", 404)

        # 转换为绝对路径
        metadata_file = metadata_file.resolve()

        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        return jsonify({
            'success': True,
            'metadata': metadata
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"获取 metadata 失败: {e}", 500)


@app.route('/api/capsules/<int:capsule_id>/open', methods=['POST'])
def open_in_reaper(capsule_id):
    """
    在 REAPER 中打开胶囊

    Returns:
        {
            "success": true,
            "message": "已在 REAPER 中打开"
        }
    """
    try:
        # 导入 scanner 模块以获取 OUTPUT_DIR
        import capsule_scanner

        db = get_database()
        capsule = db.get_capsule(capsule_id)

        if not capsule:
            raise APIError(f"胶囊不存在: {capsule_id}", 404)

        # 获取文件路径，处理可能为 None 的情况
        file_path = capsule.get('file_path') or capsule.get('name')
        rpp_filename = capsule.get('rpp_file')
        
        # 如果 rpp_file 为空，尝试使用胶囊名称构建默认文件名
        if not rpp_filename:
            # 尝试查找目录中的 .rpp 文件
            capsule_dir = capsule_scanner.get_output_dir() / file_path
            if capsule_dir.exists():
                rpp_files = list(capsule_dir.glob("*.rpp"))
                if rpp_files:
                    rpp_filename = rpp_files[0].name
                else:
                    # 使用默认命名规则
                    rpp_filename = f"{capsule['name']}.rpp"
            else:
                rpp_filename = f"{capsule['name']}.rpp"
        
        if not file_path:
            raise APIError("胶囊路径信息缺失", 400)

        # 使用 OUTPUT_DIR（用户配置的导出目录）而不是 CAPSULE_ROOT
        rpp_file = capsule_scanner.get_output_dir() / file_path / rpp_filename

        if not rpp_file.exists():
            raise APIError(f"RPP 文件不存在: {rpp_file}", 404)

        # 转换为绝对路径
        rpp_file = rpp_file.resolve()

        # 查找 REAPER 可执行文件
        reaper_exe = find_reaper_executable()

        if not reaper_exe:
            raise APIError("找不到 REAPER 可执行文件", 500)

        # 启动 REAPER（新实例）
        import platform

        if platform.system() == "Darwin":  # macOS
            cmd = ["open", "-a", str(reaper_exe), str(rpp_file)]
            subprocess.run(cmd, check=True, capture_output=True)
        elif platform.system() == "Windows":
            # Windows 上直接用 REAPER 可执行文件打开项目
            subprocess.Popen([str(reaper_exe), str(rpp_file)], 
                           creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:  # Linux
            cmd = ["xdg-open", str(rpp_file)]
            subprocess.run(cmd, check=True, capture_output=True)

        return jsonify({
            'success': True,
            'message': f"已在 REAPER 中打开: {capsule['name']}"
        })

    except APIError:
        raise
    except subprocess.CalledProcessError as e:
        raise APIError(f"启动 REAPER 失败: {e}", 500)
    except Exception as e:
        raise APIError(f"打开失败: {e}", 500)


# ============================================
# 真正的一键导出 (后台执行 REAPER)
# ============================================

@app.route('/api/capsules/auto-export', methods=['POST'])
def auto_export_api():
    """
    一键导出: 在后台启动 REAPER 执行导出,无需用户手动操作

    请求体:
        {
            "project_name": "项目名",
            "theme_name": "主题名",
            "render_preview": true
        }

    响应:
        {
            "success": true,
            "capsule_name": "项目名_主题名",
            "message": "导出成功"
        }
    """
    try:
        from exporters.reaper_headless_export import quick_export

        data = request.get_json()

        project_name = data.get('project_name', '').strip()
        theme_name = data.get('theme_name', '').strip()
        render_preview = data.get('render_preview', True)

        if not project_name:
            raise APIError("项目名不能为空")

        if not theme_name:
            raise APIError("主题名不能为空")

        # 执行导出
        print(f"\n{'='*50}")
        print(f"开始自动导出: {project_name}_{theme_name}")
        print(f"{'='*50}\n")

        result = quick_export(
            project_name=project_name,
            theme_name=theme_name,
            render_preview=render_preview
        )

        print(f"\n{'='*50}")
        print(f"导出结果: {result}")
        print(f"{'='*50}\n")

        if not result['success']:
            raise APIError(result.get('error', '导出失败'))

        # 导出成功后,自动扫描并导入
        from capsule_scanner import scan_and_import_all
        imported = scan_and_import_all()

        return jsonify({
            'success': True,
            'capsule_name': result.get('capsule_name'),
            'message': '导出成功',
            'imported_count': len(imported),
            'auto_imported': imported
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"自动导出失败: {e}", 500)


# ============================================
# REAPER Web UI 远程触发导出 (推荐!)
# ============================================

@app.route('/api/capsules/webui-export', methods=['OPTIONS', 'POST'])
def webui_export_api():
    """
    REAPER Web UI 远程触发导出

    使用 REAPER 7.0+ 的 Web UI 功能进行远程控制

    请求体:
        {
            "project_name": "项目名",
            "theme_name": "主题名",
            "render_preview": true,
            "webui_port": 9000  # 可选,默认 9000
        }

    响应:
        {
            "success": true,
            "capsule_name": "项目名_主题名",
            "message": "导出成功"
        }
    """
    # 处理 OPTIONS 预检请求
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Max-Age', '3600')
        return response

    try:
        from exporters.reaper_webui_export import quick_webui_export

        data = request.get_json()

        # 获取 capsule_type (可能是 ID 数字或名称字符串)
        capsule_type_input = data.get('capsule_type', 'magic')
        render_preview = data.get('render_preview', True)
        webui_port = data.get('webui_port', 9000)

        # 如果 capsule_type 是数字 ID，转换为名称
        if isinstance(capsule_type_input, int):
            db = get_database()
            capsule_type_obj = db.get_capsule_type(capsule_type_input)
            if capsule_type_obj:
                capsule_type = capsule_type_obj.get('name', 'magic')
            else:
                capsule_type = 'magic'
        else:
            capsule_type = capsule_type_input

        # 使用 capsule_type 作为 project_name 和 theme_name
        project_name = capsule_type
        theme_name = capsule_type

        # 记录到日志文件
        log_to_file("=" * 80)
        log_to_file("🚀 收到导出请求")
        log_to_file(f"胶囊类型: {capsule_type}")
        log_to_file(f"渲染预览: {render_preview}")
        log_to_file(f"接收到的完整数据: {data}")
        log_to_file("=" * 80)

        # 获取导出目录
        # 优先使用前端传递的 export_dir，否则使用 setup_export_environment()
        export_dir = data.get('export_dir')
        if export_dir:
            log_to_file(f"✅ 使用前端传递的导出目录: {export_dir}")
            # 设置环境变量供 Lua 脚本使用
            os.environ['SYNESTH_CAPSULE_OUTPUT'] = export_dir

            # 同时更新配置文件，确保下次下载时使用正确的目录
            try:
                from pathlib import Path

                # 使用与 capsule_scanner.py 相同的配置文件路径
                home = Path.home()
                system = os.uname().sysname.lower() if hasattr(os, 'uname') else 'unknown'

                if 'darwin' in system:
                    # macOS
                    config_dir = home / 'Library/Application Support/com.soundcapsule.app'
                elif 'windows' in system or os.name == 'nt':
                    # Windows
                    appdata = os.environ.get('APPDATA', home / 'AppData/Roaming')
                    config_dir = Path(appdata) / 'com.soundcapsule.app'
                else:
                    # Linux
                    config_dir = home / '.config/com.soundcapsule.app'

                config_file = config_dir / 'config.json'

                # 读取现有配置
                existing_config = {}
                if config_file.exists():
                    with open(config_file, 'r', encoding='utf-8') as f:
                        existing_config = json.load(f)

                # 更新导出目录
                existing_config['export_dir'] = export_dir

                # 保存配置
                config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_config, f, indent=2, ensure_ascii=False)

                logger.info(f"[CONFIG] ✅ 已更新配置文件: {export_dir}")
            except Exception as e:
                logger.warning(f"[CONFIG] ⚠ 更新配置文件失败: {e}")
        else:
            log_to_file(f"⚠️  前端未传递 export_dir，使用配置文件")
            export_dir = setup_export_environment()

        # 执行 Web UI 导出
        print(f"\n{'='*50}")
        print(f"开始 REAPER Web UI 远程导出")
        print(f"胶囊类型: {capsule_type}")
        print(f"Web UI 端口: {webui_port}")
        print(f"渲染预览: {render_preview}")
        print(f"导出目录: {export_dir}")
        print(f"接收到的数据: {data}")
        print(f"{'='*50}\n")

        result = quick_webui_export(
            project_name=project_name,
            theme_name=theme_name,
            render_preview=render_preview,
            webui_port=webui_port,
            capsule_type=capsule_type,
            export_dir=export_dir  # 传递导出目录
        )

        print(f"\n{'='*50}")
        print(f"Web UI 导出结果: {result}")
        print(f"{'='*50}\n")

        log_to_file(f"✅ REAPER 导出完成")
        log_to_file(f"返回的 capsule_name: {result.get('capsule_name')}")
        log_to_file(f"导出成功: {result.get('success')}")

        if not result['success']:
            raise APIError(result.get('error', '导出失败'))

        # 获取导出的胶囊名称
        expected_capsule_name = result.get('capsule_name')
        print(f"🎯 期望的胶囊名称: {expected_capsule_name}")
        print(f"⏳ 等待文件完全写入...")

        # 从 PathManager 获取导出目录
        from common import PathManager
        pm = PathManager.get_instance()
        output_dir = pm.export_dir
        print(f"📁 使用导出目录: {output_dir}")
        log_to_file(f"📁 使用导出目录: {output_dir}")

        # 等待文件完全写入（最多等待 5 秒）
        import time
        max_wait = 5  # 最多等待 5 秒
        wait_interval = 0.5  # 每次检查间隔 0.5 秒
        waited = 0

        capsule_dir = output_dir / expected_capsule_name
        metadata_file = capsule_dir / 'metadata.json'

        while waited < max_wait:
            if metadata_file.exists():
                # 文件存在，再等待一小段时间确保写入完成
                time.sleep(0.5)
                print(f"✅ 文件已创建: {metadata_file}")
                break
            print(f"   ⏳ 等待文件创建... ({waited}s)")
            time.sleep(wait_interval)
            waited += wait_interval

        if not metadata_file.exists():
            print(f"⚠️ 警告: 等待 {max_wait}s 后文件仍未存在，继续尝试扫描")

        # 导出成功后,自动扫描并导入
        print("=" * 80)
        print("🔄 开始扫描和导入流程")
        print("=" * 80)

        # 重新加载 capsule_scanner 模块以获取最新的 OUTPUT_DIR
        import sys
        if 'capsule_scanner' in sys.modules:
            del sys.modules['capsule_scanner']
            print("♻️  重新加载 capsule_scanner 模块")

        from capsule_scanner import import_specific_capsule

        # 直接导入指定的胶囊
        print(f"\n🎯 [步骤 1] 导出请求的胶囊名称: {expected_capsule_name}")
        print(f"   用户选择的胶囊类型: {capsule_type}")
        print(f"   当前使用的导出目录: {os.getenv('SYNESTH_CAPSULE_OUTPUT', '未设置')}")

        # 尝试导入指定的胶囊
        imported_capsule = import_specific_capsule(expected_capsule_name)

        if not imported_capsule:
            print(f"\n❌ [步骤 2] 导入胶囊失败！")
            print(f"   期望名称: {expected_capsule_name}")
            response = jsonify({
                'success': False,
                'error': f'导出成功但无法导入胶囊: {expected_capsule_name}'
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response

        print(f"\n✅ [步骤 2] 成功导入胶囊:")
        print(f"   - ID: {imported_capsule.get('id')}")
        print(f"   - name: {imported_capsule.get('name')}")
        print(f"   - capsule_type: {imported_capsule.get('capsule_type')}")
        print(f"   - preview_audio: {imported_capsule.get('preview_audio')}")

        capsule_id = imported_capsule['id']

        # 打印匹配的数据
        print(f"\n📦 [步骤 3] 准备更新的胶囊数据:")
        print(f"   - id: {imported_capsule.get('id')}")
        print(f"   - name: {imported_capsule.get('name')}")
        print(f"   - capsule_type: {imported_capsule.get('capsule_type')}")
        print(f"   - preview_audio: {imported_capsule.get('preview_audio')}")
        print(f"   - file_path: {imported_capsule.get('file_path')}")

        try:
            # 使用新方法：更新胶囊类型并立即返回完整数据
            print(f"\n🔧 [步骤 4] 调用 update_capsule_type_and_get()")
            print(f"   - capsule_id: {capsule_id}")
            print(f"   - 新 capsule_type: {capsule_type}")

            db = get_database()
            updated_capsule = db.update_capsule_type_and_get(capsule_id, capsule_type)
            if updated_capsule:
                # 使用更新后的数据
                final_capsule = updated_capsule
                print(f"\n✅ [步骤 5] 更新成功，最终返回给前端的数据:")
                print(f"   - id: {updated_capsule.get('id')}")
                print(f"   - name: {updated_capsule.get('name')}")
                print(f"   - capsule_type: {updated_capsule.get('capsule_type')}")
                print(f"   - preview_audio: {updated_capsule.get('preview_audio')}")
                print(f"   - file_path: {updated_capsule.get('file_path')}")
                print("=" * 80)

                # 记录到日志文件
                log_to_file("✅ 最终返回给前端的数据:")
                log_to_file(f"  - id: {updated_capsule.get('id')}")
                log_to_file(f"  - name: {updated_capsule.get('name')}")
                log_to_file(f"  - capsule_type: {updated_capsule.get('capsule_type')}")
                log_to_file(f"  - preview_audio: {updated_capsule.get('preview_audio')}")
                log_to_file(f"  - file_path: {updated_capsule.get('file_path')}")
                log_to_file("=" * 80)
            else:
                print(f"\n⚠️ [步骤 5] 更新失败，使用原数据")
                final_capsule = imported_capsule
        except Exception as e:
            print(f"\n⚠️ 更新胶囊类型失败: {e}")
            import traceback
            traceback.print_exc()
            final_capsule = imported_capsule

        # 返回建议的棱镜
        lens_map = {
            'magic': 'texture',
            'impact': 'temperament',
            'atmosphere': 'materiality'
        }
        suggested_lens = lens_map.get(capsule_type, 'texture')

        response = jsonify({
            'success': True,
            'capsule_id': final_capsule['id'],
            'capsule_name': result.get('capsule_name'),
            'capsule_type': capsule_type,
            'suggested_lens': suggested_lens,
            'message': 'REAPER Web UI 远程导出成功',
            'imported_count': 1,
            'auto_imported': [final_capsule]
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')

        # 记录最终响应
        log_to_file("📤 返回给前端的完整响应:")
        log_to_file(f"  - success: True")
        log_to_file(f"  - capsule_id: {final_capsule['id']}")
        log_to_file(f"  - capsule_name: {result.get('capsule_name')}")
        log_to_file(f"  - capsule_type: {capsule_type}")
        log_to_file(f"  - auto_imported 数量: 1")
        log_to_file(f"  - auto_imported[0].name: {final_capsule.get('name')}")
        log_to_file(f"  - auto_imported[0].id: {final_capsule.get('id')}")
        log_to_file("=" * 80)

        return response

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"Web UI 导出失败: {e}", 500)


# ============================================
# OSC 远程触发导出 (备用方案)
# ============================================

@app.route('/api/capsules/osc-export', methods=['POST'])
def osc_export_api():
    """
    OSC 远程触发导出: 通过 OSC 协议远程控制 REAPER 执行导出

    请求体:
        {
            "project_name": "项目名",
            "theme_name": "主题名",
            "render_preview": true,
            "osc_port": 9000  # 可选,默认 9000
        }

    响应:
        {
            "success": true,
            "capsule_name": "项目名_主题名",
            "message": "导出成功"
        }
    """
    try:
        from exporters.reaper_osc_export import quick_osc_export

        data = request.get_json()

        project_name = data.get('project_name', '').strip()
        theme_name = data.get('theme_name', '').strip()
        render_preview = data.get('render_preview', True)
        osc_port = data.get('osc_port', 9000)

        if not project_name:
            raise APIError("项目名不能为空")

        if not theme_name:
            raise APIError("主题名不能为空")

        # 执行 OSC 导出
        print(f"\n{'='*50}")
        print(f"开始 OSC 远程导出: {project_name}_{theme_name}")
        print(f"OSC 端口: {osc_port}")
        print(f"{'='*50}\n")

        result = quick_osc_export(
            project_name=project_name,
            theme_name=theme_name,
            render_preview=render_preview,
            osc_port=osc_port
        )

        print(f"\n{'='*50}")
        print(f"OSC 导出结果: {result}")
        print(f"{'='*50}\n")

        if not result['success']:
            raise APIError(result.get('error', '导出失败'))

        # 导出成功后,自动扫描并导入
        from capsule_scanner import scan_and_import_all
        imported = scan_and_import_all()

        return jsonify({
            'success': True,
            'capsule_name': result.get('capsule_name'),
            'message': 'OSC 远程导出成功',
            'imported_count': len(imported),
            'auto_imported': imported
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"OSC 导出失败: {e}", 500)


# ============================================
# 检查 REAPER 触发状态
# ============================================

@app.route('/api/capsules/check-reaper-trigger', methods=['GET'])
def check_reaper_trigger():
    """
    检查是否有来自 REAPER 的触发信号

    当用户在 REAPER 中按快捷键时,会生成触发文件

    响应:
        {
            "success": true,
            "has_trigger": true,
            "project_name": "项目名",
            "item_count": 3
        }
    """
    try:
        from exporters.reaper_trigger_export import read_reaper_trigger

        trigger_config = read_reaper_trigger()

        if trigger_config:
            return jsonify({
                'success': True,
                'has_trigger': True,
                'project_name': trigger_config.get('project_name'),
                'item_count': trigger_config.get('item_count'),
                'timestamp': trigger_config.get('timestamp')
            })
        else:
            return jsonify({
                'success': True,
                'has_trigger': False
            })

    except Exception as e:
        raise APIError(f"检查触发状态失败: {e}", 500)


# ============================================
# 扫描并导入新胶囊
# ============================================

@app.route('/api/capsules/scan-and-import', methods=['POST'])
def scan_and_import_capsules():
    """
    扫描 output 目录并导入新发现的胶囊

    请求体:
        {}

    响应:
        {
            "success": true,
            "imported": [
                {"id": 1, "name": "项目_主题"},
                {"id": 2, "name": "项目2_主题2"}
            ],
            "count": 2
        }
    """
    try:
        from capsule_scanner import scan_and_import_all

        imported = scan_and_import_all()

        return jsonify({
            'success': True,
            'imported': imported,
            'count': len(imported)
        })

    except Exception as e:
        raise APIError(f"扫描失败: {e}", 500)


# ============================================
# 胶囊类型管理
# ============================================

@app.route('/api/capsule-types', methods=['GET'])
def get_capsule_types():
    """获取所有胶囊类型"""
    try:
        db = get_database()
        types = db.get_all_capsule_types()

        return jsonify({
            'success': True,
            'types': types
        })

    except Exception as e:
        raise APIError(f"获取胶囊类型失败: {e}", 500)


@app.route('/api/capsule-types/<type_id>', methods=['GET'])
def get_capsule_type(type_id):
    """获取单个胶囊类型"""
    try:
        db = get_database()
        capsule_type = db.get_capsule_type(type_id)

        if not capsule_type:
            raise APIError(f"胶囊类型不存在: {type_id}", 404)

        return jsonify({
            'success': True,
            'type': capsule_type
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"获取胶囊类型失败: {e}", 500)


@app.route('/api/capsule-types', methods=['POST'])
def create_capsule_type():
    """创建新的胶囊类型"""
    try:
        data = request.get_json()

        # 验证必填字段
        required_fields = ['id', 'name', 'name_cn', 'color', 'gradient']
        for field in required_fields:
            if field not in data:
                raise APIError(f"缺少必填字段: {field}", 400)

        # 验证ID格式（只允许字母、数字、下划线）
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', data['id']):
            raise APIError("ID只能包含字母、数字和下划线", 400)

        db = get_database()
        success = db.create_capsule_type(data)

        if success:
            return jsonify({
                'success': True,
                'message': f"成功创建胶囊类型: {data['name_cn']}"
            })
        else:
            raise APIError("创建失败，可能是ID已存在", 400)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"创建胶囊类型失败: {e}", 500)


@app.route('/api/capsule-types/<type_id>', methods=['PUT'])
def update_capsule_type(type_id):
    """更新胶囊类型"""
    try:
        data = request.get_json()

        db = get_database()
        # 检查类型是否存在
        existing = db.get_capsule_type(type_id)
        if not existing:
            raise APIError(f"胶囊类型不存在: {type_id}", 404)

        success = db.update_capsule_type(type_id, data)

        if success:
            return jsonify({
                'success': True,
                'message': f"成功更新胶囊类型: {type_id}"
            })
        else:
            raise APIError("更新失败，没有提供要更新的字段", 400)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"更新胶囊类型失败: {e}", 500)


@app.route('/api/capsule-types/<type_id>', methods=['DELETE'])
def delete_capsule_type(type_id):
    """删除胶囊类型"""
    try:
        db = get_database()

        # 检查类型是否存在
        existing = db.get_capsule_type(type_id)
        if not existing:
            raise APIError(f"胶囊类型不存在: {type_id}", 404)

        # 检查是否有胶囊使用此类型
        capsules = db.get_all_capsules()
        in_use = any(c['capsule_type'] == type_id for c in capsules)

        if in_use:
            raise APIError(f"无法删除：仍有胶囊正在使用此类型", 400)

        success = db.delete_capsule_type(type_id)

        if success:
            return jsonify({
                'success': True,
                'message': f"成功删除胶囊类型: {type_id}"
            })
        else:
            raise APIError("删除失败", 500)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"删除胶囊类型失败: {e}", 500)


# ============================================
# 云端同步 API 端点
# ============================================

@app.route('/api/sync/status', methods=['GET'])
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


@app.route('/api/sync/pending', methods=['GET'])
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


@app.route('/api/sync/mark-pending', methods=['POST'])
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


@app.route('/api/sync/upload', methods=['POST'])
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

                            # 上传到云端
                            logger.info(f"[SYNC]   → 正在上传到 Supabase...")
                            result = supabase.upload_capsule(user_id, capsule_data)

                            if result:
                                uploaded += 1
                                cloud_id = result.get('id')
                                cloud_id_mapping[record_id] = cloud_id
                                logger.info(f"[SYNC]   ✓ 上传成功!")
                                logger.info(f"[SYNC]     - 本地ID: {record_id}")
                                logger.info(f"[SYNC]     - 云端ID: {cloud_id}")
                                logger.info(f"[SYNC]     - 版本: {result.get('version')}")

                                # 🎯 上传 Audio 文件夹（REAPER 项目所需）
                                import os
                                capsule_dir = capsule_data.get('file_path', '')
                                if capsule_dir:
                                    from pathlib import Path
                                    import glob

                                    # 搜索多个可能的导出目录
                                    possible_dirs = []
                                    base_dir = Path(__file__).parent

                                    # 1. output 目录（默认）
                                    possible_dirs.append(base_dir / 'output' / capsule_dir)

                                    # 2. 从环境变量读取导出目录（前端设置）
                                    export_dir_env = os.getenv('SYNESTH_CAPSULE_OUTPUT')
                                    if export_dir_env:
                                        possible_dirs.append(Path(export_dir_env) / capsule_dir)
                                        logger.info(f"[SYNC] 使用环境变量导出目录: {export_dir_env}")

                                    # 3. 从 PathManager 获取导出目录
                                    from common import PathManager
                                    pm = PathManager.get_instance()
                                    export_dir = pm.export_dir
                                    possible_dirs.append(Path(export_dir) / capsule_dir)
                                    logger.info(f"[SYNC] 使用 PathManager 导出目录: {export_dir}")

                                    # 4. 直接在 base_dir 下搜索
                                    possible_dirs.append(base_dir / capsule_dir)

                                    # 找到第一个存在的目录
                                    full_capsule_dir = None
                                    logger.info(f"[SYNC] 🔍 搜索胶囊目录: {capsule_dir}")
                                    for idx, dir_path in enumerate(possible_dirs, 1):
                                        logger.info(f"[SYNC]   [{idx}] 检查: {dir_path} - {'✓ 存在' if dir_path.exists() else '✗ 不存在'}")
                                        if dir_path.exists():
                                            full_capsule_dir = dir_path
                                            logger.info(f"[SYNC] ✓ 找到胶囊目录: {full_capsule_dir}")
                                            break

                                    if full_capsule_dir:
                                        # 🎵 上传预览音频文件
                                        preview_audio = capsule_data.get('preview_audio')
                                        if preview_audio:
                                            preview_path = full_capsule_dir / preview_audio
                                            if preview_path.exists():
                                                logger.info(f"[SYNC] → 上传预览音频: {preview_audio}")
                                                preview_result = supabase.upload_file(
                                                    user_id=user_id,
                                                    capsule_folder_name=capsule_dir,  # 使用文件夹名
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

                                        # 📄 上传 RPP 项目文件
                                        rpp_file = capsule_data.get('rpp_file')
                                        if rpp_file:
                                            rpp_path = full_capsule_dir / rpp_file
                                            if rpp_path.exists():
                                                logger.info(f"[SYNC] → 上传 RPP 文件: {rpp_file}")
                                                rpp_result = supabase.upload_file(
                                                    user_id=user_id,
                                                    capsule_folder_name=capsule_dir,  # 使用文件夹名
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

                                        # 🎧 上传 Audio 文件夹（REAPER 项目所需）
                                        audio_folder = full_capsule_dir / "Audio"
                                        if audio_folder.exists():
                                            logger.info(f"[SYNC] → 上传 Audio 文件夹...")
                                            audio_result = supabase.upload_file(
                                                user_id=user_id,
                                                capsule_folder_name=capsule_dir,  # 使用文件夹名
                                                file_type='audio_folder',
                                                file_path=str(audio_folder)
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

                                # 更新本地数据库的云同步状态
                                cursor.execute("""
                                    UPDATE capsules
                                    SET cloud_status = 'synced',
                                        cloud_id = ?,
                                        cloud_version = ?,
                                        last_synced_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                """, (cloud_id, result.get('version', 1), record_id))
                                db.conn.commit()
                                logger.info(f"[SYNC]   ✓ 已更新本地同步状态")
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


@app.route('/api/sync/download', methods=['GET'])
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
                            # 检查是否已存在
                            cursor = db.conn.cursor()
                            cursor.execute("SELECT id FROM capsules WHERE cloud_id = ?", (record.get('id'),))
                            existing = cursor.fetchone()

                            # 准备本地数据
                            # 云端的 name 字段就是文件夹名（如 template_ianzhao_20260111_215759）
                            # 本地的 file_path 字段存储文件夹名
                            capsule_folder_name = record.get('name', '')

                            local_data = {
                                'uuid': record.get('id'),
                                'name': record.get('name'),
                                'file_path': capsule_folder_name,  # 直接使用 name 字段作为文件夹路径
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
                                    # 这里直接查询 cloud_capsule_coordinates 表
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

                                    # 重要：使用云端记录中的原作者 user_id (Shared Mode 下 user_id 可能不是当前登录用户)
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

                                    # 3. 下载 Audio 文件夹 (元数据同步时跳过，避免长时间阻塞导致超时)
                                    # logger.info(f"[SYNC]   → 下载 Audio 文件夹...")
                                    # if supabase.download_file(owner_id, local_data['file_path'], 'audio_folder', str(capsule_dir)):
                                    #     logger.info(f"[SYNC]   ✓ Audio 文件夹下载成功")
                                    # else:
                                    #     logger.warning(f"[SYNC]   ⚠ Audio 文件夹下载失败")

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


@app.route('/api/sync/conflicts', methods=['GET'])
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


@app.route('/api/sync/resolve-conflict', methods=['POST'])
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


# ============================================
# Phase B.4: 轻量级同步 API（元数据 + 预览音频）
# ============================================

@app.route('/api/sync/lightweight', methods=['POST'])
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

        logger.info("\n" + "=" * 60)
        logger.info("🔄 轻量级同步请求")
        logger.info("=" * 60)
        logger.info(f"用户: {current_user.get('username')}")
        logger.info(f"包含预览音频: {include_previews}")
        logger.info(f"强制同步: {force}")
        logger.info()

        # 获取用户 ID
        user_id = current_user.get('supabase_user_id') or str(current_user.get('id', ''))

        if not user_id:
            raise APIError('用户 ID 不存在', 400)

        # 获取同步服务实例
        sync_service = get_sync_service()

        # 执行轻量级同步
        result = sync_service.sync_metadata_lightweight(
            user_id=user_id,
            include_previews=include_previews
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


# ============================================
# Phase B: 混合存储策略 - 下载管理 API
# ============================================

@app.route('/api/capsules/<int:capsule_id>/download-wav', methods=['POST'])
def download_wav(capsule_id):
    """
    按需下载 WAV 源文件（Phase B）

    请求体:
        {
            "force": false,  // 是否强制重新下载
            "priority": 5    // 优先级 (0-10)
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
        # 验证用户已登录
        auth_manager = get_auth_manager()
        user_id = auth_manager.verify_token(request)

        if not user_id:
            raise APIError('未授权访问', 401)

        data = request.get_json() or {}
        force = data.get('force', False)
        priority = data.get('priority', 5)

        db = get_database()

        # 获取胶囊信息
        capsule = db.get_capsule(capsule_id)
        if not capsule:
            raise APIError('胶囊不存在', 404)

        # 检查是否已缓存
        if not force:
            cache_entry = db.get_cache_entry(capsule_id, 'wav')
            if cache_entry and Path(cache_entry['file_path']).exists():
                return jsonify({
                    'success': True,
                    'already_cached': True,
                    'file_path': cache_entry['file_path'],
                    'file_size': cache_entry['file_size']
                })

        # 从 Supabase 获取下载 URL
        # TODO: 这里需要集成 Supabase Storage API
        # 暂时返回占位响应
        raise APIError('WAV 下载功能待集成 Supabase Storage', 501)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"创建下载任务失败: {e}", 500)


@app.route('/api/capsules/<int:capsule_id>/download-status', methods=['GET'])
def get_download_status(capsule_id):
    """
    获取胶囊下载状态（Phase B）

    响应:
        {
            "status": "downloading",  // pending, downloading, completed, failed
            "progress": 45,
            "downloaded_bytes": 47185920,
            "speed": 2621440,  // bytes/second
            "eta": "23s"
        }
    """
    try:
        # 验证用户已登录
        auth_manager = get_auth_manager()
        user_id = auth_manager.verify_token(request)

        if not user_id:
            raise APIError('未授权访问', 401)

        db = get_database()

        # 获取下载任务
        tasks = db.get_download_tasks_by_capsule(capsule_id)

        if not tasks:
            return jsonify({
                'status': 'not_started',
                'progress': 0
            })

        # 获取最新的下载任务
        task = tasks[0]

        # 格式化响应
        response = {
            'task_id': task['id'],
            'status': task['status'],
            'progress': task['progress'],
            'downloaded_bytes': task['downloaded_bytes'],
            'remote_size': task['remote_size']
        }

        if task['speed']:
            response['speed'] = task['speed']
            response['speed_mb_s'] = f"{task['speed'] / 1024 / 1024:.2f} MB/s"

        if task['eta_seconds']:
            response['eta'] = f"{task['eta_seconds']}s"
            response['eta_seconds'] = task['eta_seconds']

        if task['error_message']:
            response['error'] = task['error_message']

        return jsonify(response)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"获取下载状态失败: {e}", 500)


@app.route('/api/download-tasks/<int:task_id>/pause', methods=['POST'])
def pause_download_task(task_id):
    """
    暂停下载任务（Phase B）

    需要认证

    响应:
        {
            "success": true,
            "message": "下载已暂停"
        }
    """
    try:
        # 验证用户已登录
        auth_manager = get_auth_manager()
        user_id = auth_manager.verify_token(request)

        if not user_id:
            raise APIError('未授权访问', 401)

        db = get_database()

        # 更新任务状态为暂停
        success = db.update_download_task_status(task_id, 'paused')

        if success:
            return jsonify({
                'success': True,
                'message': '下载已暂停'
            })
        else:
            raise APIError('暂停下载失败', 500)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"暂停下载失败: {e}", 500)


@app.route('/api/download-tasks/<int:task_id>/resume', methods=['POST'])
def resume_download_task(task_id):
    """
    恢复下载任务（支持断点续传）（Phase B）

    需要认证

    响应:
        {
            "success": true,
            "message": "下载已恢复"
        }
    """
    try:
        # 验证用户已登录
        auth_manager = get_auth_manager()
        user_id = auth_manager.verify_token(request)

        if not user_id:
            raise APIError('未授权访问', 401)

        db = get_database()

        # 获取任务信息
        task = db.get_download_task(task_id)
        if not task:
            raise APIError('任务不存在', 404)

        # 检查任务状态
        if task['status'] not in ['paused', 'failed']:
            raise APIError(f'任务状态为 {task["status"]}，无法恢复', 400)

        # 更新任务状态为 pending
        success = db.update_download_task_status(task_id, 'pending')

        if success:
            # TODO: 这里需要通知 DownloadQueue 重新处理任务
            return jsonify({
                'success': True,
                'message': '下载已恢复'
            })
        else:
            raise APIError('恢复下载失败', 500)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"恢复下载失败: {e}", 500)


@app.route('/api/download-tasks/<int:task_id>/cancel', methods=['POST'])
def cancel_download_task(task_id):
    """
    取消下载任务（Phase B）

    需要认证

    响应:
        {
            "success": true,
            "message": "下载已取消"
        }
    """
    try:
        # 验证用户已登录
        auth_manager = get_auth_manager()
        user_id = auth_manager.verify_token(request)

        if not user_id:
            raise APIError('未授权访问', 401)

        db = get_database()

        # 获取任务信息
        task = db.get_download_task(task_id)
        if not task:
            raise APIError('任务不存在', 404)

        # 取消任务
        success = db.update_download_task_status(task_id, 'cancelled')

        if success:
            # TODO: 如果任务正在下载，需要通知 DownloadWorker 停止
            # 删除部分下载的文件
            if task['local_path'] and Path(task['local_path']).exists():
                try:
                    os.remove(task['local_path'])
                    logger.info(f"已删除部分下载文件: {task['local_path']}")
                except Exception as e:
                    logger.warning(f"删除部分下载文件失败: {e}")

            return jsonify({
                'success': True,
                'message': '下载已取消'
            })
        else:
            raise APIError('取消下载失败', 500)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"取消下载失败: {e}", 500)


@app.route('/api/cache/stats', methods=['GET'])
def get_cache_stats():
    """
    获取缓存统计信息（Phase B）

    响应:
        {
            "total_cached_files": 50,
            "total_cache_size": 1073741824,
            "max_cache_size": 5368709120,
            "usage_percent": 20.0,
            "available_space": 4294967296,
            "needs_purge": false,
            "pinned_files_count": 5,
            "pinned_files_size": 104857600,
            "by_type": {
                "preview": {"count": 50, "size": 52428800},
                "wav": {"count": 20, "size": 1024*1024*100}
            }
        }
    """
    try:
        # 验证用户已登录
        auth_manager = get_auth_manager()
        user_id = auth_manager.verify_token(request)

        if not user_id:
            raise APIError('未授权访问', 401)

        from cache_manager import create_cache_manager

        # 创建缓存管理器
        max_cache_size = int(os.getenv('MAX_CACHE_SIZE', 5 * 1024 * 1024 * 1024))  # 5GB
        manager = create_cache_manager(
            db_path=get_database().db_path.replace('sqlite:///', ''),
            max_cache_size=max_cache_size
        )

        # 获取缓存状态
        status = manager.get_cache_status()

        return jsonify(status)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"获取缓存统计失败: {e}", 500)


@app.route('/api/cache/purge', methods=['POST'])
def purge_cache():
    """
    清理缓存（Phase B）

    请求体:
        {
            "keep_pinned": true,
            "max_size_to_free": 536870912  // 可选，释放的最大空间
        }

    需要认证

    响应:
        {
            "success": true,
            "files_deleted": 10,
            "space_freed": 104857600,
            "files_skipped": 5,
            "errors": []
        }
    """
    try:
        # 验证用户已登录
        auth_manager = get_auth_manager()
        user_id = auth_manager.verify_token(request)

        if not user_id:
            raise APIError('未授权访问', 401)

        data = request.get_json() or {}
        keep_pinned = data.get('keep_pinned', True)
        max_size_to_free = data.get('max_size_to_free')

        from cache_manager import create_cache_manager

        # 创建缓存管理器
        max_cache_size = int(os.getenv('MAX_CACHE_SIZE', 5 * 1024 * 1024 * 1024))  # 5GB
        manager = create_cache_manager(
            db_path=get_database().db_path.replace('sqlite:///', ''),
            max_cache_size=max_cache_size
        )

        # 执行清理
        result = manager.purge_old_cache(
            keep_pinned=keep_pinned,
            max_size_to_free=max_size_to_free
        )

        return jsonify({
            'success': True,
            **result
        })

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"清理缓存失败: {e}", 500)


@app.route('/api/capsules/<int:capsule_id>/cache-pin', methods=['PUT'])
def set_cache_pinned(capsule_id):
    """
    设置缓存固定状态（Phase B）

    请求体:
        {
            "pinned": true  // true = 固定, false = 取消固定
        }

    需要认证

    响应:
        {
            "success": true,
            "message": "缓存已固定"
        }
    """
    try:
        # 验证用户已登录
        auth_manager = get_auth_manager()
        user_id = auth_manager.verify_token(request)

        if not user_id:
            raise APIError('未授权访问', 401)

        data = request.get_json()
        if not data:
            raise APIError('请求体不能为空', 400)

        pinned = data.get('pinned')
        if pinned is None:
            raise APIError('缺少参数: pinned', 400)

        db = get_database()
        success = db.set_cache_pinned(capsule_id, pinned)

        if success:
            action = '固定' if pinned else '取消固定'
            return jsonify({
                'success': True,
                'message': f'缓存已{action}'
            })
        else:
            raise APIError('设置失败', 500)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"设置缓存固定状态失败: {e}", 500)


@app.route('/api/capsules/<int:capsule_id>/asset-status', methods=['GET'])
@token_required
def get_asset_status(current_user, capsule_id):
    """
    获取胶囊资产状态（Phase B）

    响应:
        {
            "capsule_id": 1,
            "asset_status": "local",  // local, cloud_only, downloading, cached
            "cloud_status": "synced",
            "local_wav_path": "/path/to/file.wav",
            "local_wav_size": 1330486,
            "download_progress": 0,
            "is_cache_pinned": false
        }
    """
    try:
        db = get_database()
        asset_status = db.get_capsule_asset_status(capsule_id)

        if not asset_status:
            raise APIError('胶囊不存在', 404)

        return jsonify(asset_status)

    except APIError:
        raise
    except Exception as e:
        raise APIError(f"获取资产状态失败: {e}", 500)


# ============================================
# Phase B.5: 智能缓存管理 API
# ============================================

@app.route('/api/cache/smart-purge', methods=['POST'])
@token_required
def smart_cache_purge(current_user):
    """
    智能缓存清理（Phase B.5）

    综合考虑 LRU、访问频率、文件大小、固定状态等因素

    请求体:
        {
            "target_usage_percent": 80.0,  // 目标使用率（默认 80%）
            "keep_frequent": true,          // 是否保留高频访问文件
            "min_access_count": 3            // 最小访问次数阈值
        }

    需要认证

    响应:
        {
            "success": true,
            "data": {
                "files_deleted": 5,
                "space_freed": 52428800,
                "files_skipped": 2,
                "errors": []
            }
        }
    """
    try:
        data = request.get_json() or {}
        target_usage_percent = data.get('target_usage_percent', 80.0)
        keep_frequent = data.get('keep_frequent', True)
        min_access_count = data.get('min_access_count', 3)

        logger.info("\n" + "=" * 60)
        logger.info("🧠 智能缓存清理请求")
        logger.info("=" * 60)
        logger.info(f"用户: {current_user.get('username')}")
        logger.info(f"目标使用率: {target_usage_percent}%")
        logger.info(f"保留高频文件: {keep_frequent}")
        logger.info(f"最小访问次数: {min_access_count}")
        logger.info()

        # 导入 CacheManager
        from cache_manager import create_cache_manager

        # 创建缓存管理器
        cache_manager = create_cache_manager()

        # 执行智能清理
        result = cache_manager.smart_cache_cleanup(
            target_usage_percent=target_usage_percent,
            keep_frequent=keep_frequent,
            min_access_count=min_access_count
        )

        logger.info(f"✅ 智能清理完成: 删除 {result['files_deleted']} 个文件, 释放 {cache_manager._format_size(result['space_freed'])}")

        return jsonify({
            'success': True,
            'data': {
                'files_deleted': result['files_deleted'],
                'space_freed': result['space_freed'],
                'files_skipped': result['files_skipped'],
                'errors': result['errors']
            }
        })

    except APIError:
        raise
    except Exception as e:
        logger.error(f"智能缓存清理失败: {e}")
        raise APIError(f"智能缓存清理失败: {e}", 500)


# ============================================
# Phase C1: 棱镜配置管理 API
# ============================================

@app.route('/api/prisms', methods=['GET'])
def get_prisms():
    """
    获取所有活跃棱镜配置

    Phase C1: 棱镜版本控制

    无需认证

    响应:
        [
            {
                "id": "texture",
                "name": "Texture / Timbre (质感)",
                "description": "...",
                "axis_config": {...},
                "anchors": [...],
                "version": 1,
                "updated_at": "2026-01-11 10:00:00",
                "updated_by": "alice"
            },
            ...
        ]
    """
    try:
        prisms = prism_manager.get_all_prisms()

        # 解析 JSON 字段
        for p in prisms:
            try:
                p['axis_config'] = json.loads(p['axis_config'])
                p['anchors'] = json.loads(p['anchors'])
                p['field_data'] = json.loads(p.get('field_data', '[]'))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"棱镜 {p.get('id')} 的 JSON 字段解析失败: {e}")
                p['axis_config'] = {}
                p['anchors'] = []
                p['field_data'] = []

        return jsonify(prisms)

    except Exception as e:
        logger.error(f"获取棱镜列表失败: {e}")
        # 这里假设 APIError 已在上下文定义，如果没有定义则直接抛出或返回 500
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/prisms/field', methods=['GET'])
def get_prisms_field():
    """
    获取所有棱镜的预计算力场坐标 (WebApp 核心加载接口)
    
    格式兼容 sonic_vectors.json
    """
    try:
        prisms = prism_manager.get_all_prisms()
        output = {}
        for p in prisms:
            try:
                output[p['id']] = {
                    "name": p['name'],
                    "description": p['description'],
                    "axes": json.loads(p.get('axis_config', '{}')),
                    "points": json.loads(p.get('field_data', '[]'))
                }
            except Exception as e:
                logger.warning(f"解析棱镜 {p.get('id')} 字段失败: {e}")
                
        return jsonify(output)
    except Exception as e:
        logger.error(f"获取力场数据失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/prisms/<prism_id>', methods=['GET'])
def get_prism_detail(prism_id):
    """
    获取单个棱镜详情

    Phase C1: 棱镜版本控制

    Args:
        prism_id: 棱镜 ID (如 'texture', 'source')

    无需认证

    响应:
        {
            "id": "texture",
            "name": "Texture / Timbre (质感)",
            "description": "...",
            "axis_config": {
                "x_label_pos": "Rough",
                "x_label_neg": "Smooth",
                ...
            },
            "anchors": [
                {"word": "粗糙", "x": 80, "y": 50},
                ...
            ],
            "version": 5,
            "updated_at": "2026-01-11 10:00:00",
            "updated_by": "alice"
        }
    """
    try:
        prism = prism_manager.get_prism(prism_id)

        if not prism:
            raise APIError(f"棱镜 '{prism_id}' 不存在", 404)

        # 解析 JSON 字段
        try:
            prism['axis_config'] = json.loads(prism['axis_config'])
            prism['anchors'] = json.loads(prism['anchors'])
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"棱镜 {prism_id} 的 JSON 字段解析失败: {e}")
            prism['axis_config'] = {}
            prism['anchors'] = []

        return jsonify(prism)

    except APIError:
        raise
    except Exception as e:
        logger.error(f"获取棱镜详情失败: {e}")
        raise APIError(f"获取棱镜详情失败: {e}", 500)


@app.route('/api/prisms/<prism_id>', methods=['POST', 'PUT'])
@token_required
def update_prism(current_user, prism_id):
    """
    更新棱镜配置（自动版本控制）

    Phase C1: 棱镜版本控制

    策略: Last Write Wins
    - 每次更新自动递增版本号
    - 保存完整快照到 prism_versions 表
    - 记录更新者和时间戳

    Args:
        prism_id: 棱镜 ID (如 'texture', 'source')

    请求体:
        {
            "name": "Texture / Timbre (质感)",
            "description": "描述声音的质感特征",
            "axis_config": {
                "x_label_pos": "Rough",
                "x_label_neg": "Smooth",
                "y_label_pos": "Bright",
                "y_label_neg": "Dark"
            },
            "anchors": [
                {"word": "粗糙", "x": 80, "y": 50},
                {"word": "光滑", "x": -80, "y": 50}
            ]
        }

    需要认证

    响应:
        {
            "success": true,
            "message": "Prism updated successfully",
            "data": {
                "id": "texture",
                "version": 6,
                "updated_at": "2026-01-11 10:05:00"
            }
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError("请求体不能为空", 400)

        # 验证必要字段
        if 'name' not in data:
            raise APIError("缺少必要字段: name", 400)

        # 获取用户 ID
        user_id = current_user.get('username') or current_user.get('user_id', 'unknown')

        logger.info(f"用户 {user_id} 更新棱镜 {prism_id}")

        # 更新棱镜（自动版本控制）
        new_version = prism_manager.create_or_update_prism(
            prism_id,
            data,
            user_id=user_id
        )

        return jsonify({
            'success': True,
            'message': f"棱镜 '{prism_id}' 更新成功",
            'data': {
                'id': prism_id,
                'version': new_version,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })

    except APIError:
        raise
    except Exception as e:
        logger.error(f"更新棱镜失败: {e}")
        raise APIError(f"更新棱镜失败: {e}", 500)


@app.route('/api/prisms/<prism_id>/history', methods=['GET'])
@token_required
def get_prism_history(current_user, prism_id):
    """
    获取棱镜版本历史

    Phase C1: 棱镜版本控制

    Args:
        prism_id: 棱镜 ID (如 'texture')

    查询参数:
        limit: 返回的最大版本数（默认 10）

    需要认证

    响应:
        [
            {
                "version": 5,
                "created_at": "2026-01-11 10:00:00",
                "created_by": "alice",
                "change_reason": "update"
            },
            {
                "version": 4,
                "created_at": "2026-01-11 09:55:00",
                "created_by": "bob",
                "change_reason": "update"
            },
            ...
        ]
    """
    try:
        # 检查棱镜是否存在
        prism = prism_manager.get_prism(prism_id)
        if not prism:
            raise APIError(f"棱镜 '{prism_id}' 不存在", 404)

        # 获取版本历史
        history = prism_manager.get_version_history(prism_id)

        # 应用 limit
        limit = request.args.get('limit', type=int, default=10)
        if limit > 0:
            history = history[:limit]

        return jsonify(history)

    except APIError:
        raise
    except Exception as e:
        logger.error(f"获取版本历史失败: {e}")
        raise APIError(f"获取版本历史失败: {e}", 500)


@app.route('/api/prisms/<prism_id>/rollback', methods=['POST'])
@token_required
def rollback_prism(current_user, prism_id):
    """
    回滚棱镜到指定版本

    Phase C1: 棱镜版本控制

    注意：回滚会创建一个新版本，而非覆盖历史
    例如：当前 v5，回滚到 v3 → 创建 v6（内容等于 v3）

    Args:
        prism_id: 棱镜 ID (如 'texture')

    请求体:
        {
            "version": 3  // 目标版本号
        }

    需要认证

    响应:
        {
            "success": true,
            "message": "已回滚到 v3",
            "data": {
                "id": "texture",
                "target_version": 3,
                "new_version": 6,
                "rolled_back_at": "2026-01-11 10:10:00"
            }
        }
    """
    try:
        data = request.get_json()

        if not data:
            raise APIError("请求体不能为空", 400)

        target_version = data.get('version')

        if target_version is None:
            raise APIError("缺少目标版本号: version", 400)

        # 检查棱镜是否存在
        prism = prism_manager.get_prism(prism_id)
        if not prism:
            raise APIError(f"棱镜 '{prism_id}' 不存在", 404)

        # 获取用户 ID
        user_id = current_user.get('username') or current_user.get('user_id', 'unknown')

        logger.info(f"用户 {user_id} 回滚棱镜 {prism_id} 到 v{target_version}")

        # 执行回滚
        success, message = prism_manager.restore_version(prism_id, target_version)

        if not success:
            raise APIError(message, 400)

        # 获取新版本号
        updated_prism = prism_manager.get_prism(prism_id)

        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'id': prism_id,
                'target_version': target_version,
                'new_version': updated_prism['version'],
                'rolled_back_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })

    except APIError:
        raise
    except Exception as e:
        logger.error(f"回滚棱镜失败: {e}")
        raise APIError(f"回滚棱镜失败: {e}", 500)


@app.route('/api/embed/coordinate', methods=['POST'])
def calculate_coordinate_api():
    """
    计算文本坐标 (Phase C3: Hybrid Embedding)
    
    请求体:
        {
            "text": "明亮的声音",
            "prism_id": "texture"
        }
    """
    try:
        # 检查 ML 功能是否可用
        if not ML_AVAILABLE:
            raise APIError("ML 功能不可用（缺少 numpy/sklearn/sentence-transformers 依赖）", 503)
        
        data = request.get_json()
        if not data or 'text' not in data or 'prism_id' not in data:
            raise APIError("缺少必要参数: text, prism_id", 400)
            
        text = data['text']
        prism_id = data['prism_id']
        
        service = get_hybrid_service()
        result = service.get_coordinate(text, prism_id)
        
        if result:
            return jsonify({
                "success": True,
                "text": text,
                "prism_id": prism_id,
                "x": result['x'],
                "y": result['y']
            })
        else:
            raise APIError("坐标计算失败", 500)
            
    except APIError:
        raise
    except Exception as e:
        logger.error(f"Embedding 计算失败: {e}")
        raise APIError(f"Embedding 计算失败: {e}", 500)

# ============================================
# 配置管理端点
# ============================================

@app.route('/api/config/save', methods=['POST'])
def save_config():
    """
    保存用户配置（无需认证）

    用于前端保存 Tauri 配置时同步到 Python 后端

    请求体:
        {
            "export_dir": "/path/to/export/dir",
            "reaper_path": "/path/to/reaper"
        }

    响应:
        {
            "success": true,
            "message": "配置已保存"
        }
    """
    logger.info("[DEBUG] /api/config/save 端点被调用")
    try:
        data = request.get_json()
        logger.info(f"[DEBUG] 接收到的数据: {data}")

        if not data:
            raise APIError('请求体不能为空', 400)

        export_dir = data.get('export_dir')
        reaper_path = data.get('reaper_path')

        # 保存配置到系统配置目录（与 capsule_scanner.py 相同的路径）
        from pathlib import Path
        import os

        home = Path.home()
        system = os.uname().sysname.lower() if hasattr(os, 'uname') else 'unknown'

        if 'darwin' in system:
            # macOS
            config_dir = home / 'Library/Application Support/com.soundcapsule.app'
        elif 'windows' in system or os.name == 'nt':
            # Windows
            appdata = os.environ.get('APPDATA', home / 'AppData/Roaming')
            config_dir = Path(appdata) / 'com.soundcapsule.app'
        else:
            # Linux
            config_dir = home / '.config/com.soundcapsule.app'

        config_file = config_dir / 'config.json'

        # 读取现有配置
        existing_config = {}
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)

        # 检测导出目录是否变更（在更新之前）
        export_dir_changed = False
        old_export_dir = existing_config.get('export_dir')

        # 更新配置
        if export_dir:
            existing_config['export_dir'] = export_dir
            # 同时更新环境变量，确保 get_output_dir() 能立即获取最新值
            os.environ['SYNESTH_CAPSULE_OUTPUT'] = export_dir
            logger.info(f"[CONFIG] 保存导出目录并更新环境变量: {export_dir}")

        if reaper_path:
            existing_config['reaper_path'] = reaper_path
            logger.info(f"[CONFIG] 保存 REAPER 路径: {reaper_path}")

        if export_dir and old_export_dir and export_dir != old_export_dir:
            export_dir_changed = True
            logger.warning(f"[CONFIG] 导出目录已变更: '{old_export_dir}' -> '{export_dir}'")
            logger.info(f"[DEBUG] 路径变更检测完成")
            
            # ⚠️ 临时禁用文件复制功能，避免触发应用重启
            logger.info(f"[CONFIG] 跳过文件复制（已禁用）")

        # 保存配置
        logger.info(f"[DEBUG] 准备写入配置文件: {config_file}")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)

        logger.info(f"[CONFIG] 配置已保存到: {config_file}")
        logger.info(f"[DEBUG] /api/config/save 即将返回响应")

        return jsonify({
            'success': True,
            'message': '配置已保存' + ('，旧目录文件已复制到新目录' if export_dir_changed else ''),
            'directory_changed': export_dir_changed
        })

    except APIError:
        raise
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        raise APIError(f"保存配置失败: {e}", 500)


@app.route('/api/config/reset-local-db', methods=['POST'])
def reset_local_db():
    """
    清空本地数据库（保留用户认证信息）
    
    用于路径变更时清空本地缓存，之后需要重新同步
    
    响应:
        {
            "success": true,
            "message": "本地数据库已清空",
            "deleted": {
                "capsules": 10,
                "tags": 25,
                "coordinates": 20,
                "sync_status": 10
            }
        }
    """
    try:
        logger.info("[CONFIG] 开始清空本地数据库...")
        
        db = get_database()
        deleted_counts = db.clear_all_capsules()
        
        logger.info(f"[CONFIG] 本地数据库已清空: {deleted_counts}")
        
        return jsonify({
            'success': True,
            'message': '本地数据库已清空，下次启动时将重新同步',
            'deleted': deleted_counts
        })
        
    except Exception as e:
        logger.error(f"清空数据库失败: {e}")
        raise APIError(f"清空数据库失败: {e}", 500)


# ============================================
# 主函数
# ============================================

if __name__ == '__main__':
    # 初始化数据库
    db = get_database()
    db_path = db.db_path.replace('sqlite:///', '')

    if not Path(db_path).exists():
        print("数据库不存在，正在初始化...")
        db.initialize()
    else:
        # Phase G: 数据库健康检查（生产环境适用）
        print("检查数据库完整性...")
        health = db.verify_schema()
        
        if not health['valid']:
            print(f"⚠️  数据库 schema 不完整:")
            print(f"   当前字段: {health['current_fields_count']}")
            print(f"   需要字段: {health['required_fields_count']}")
            
            if health['missing_fields']:
                print(f"   缺失字段: {', '.join(health['missing_fields'])}")
            if health['missing_tables']:
                print(f"   缺失表: {', '.join(health['missing_tables'])}")
            
            if health.get('invalid_tables'):
                print(f"   结构错误的表: {', '.join(health['invalid_tables'])}")
            
            print("\n🔧 正在自动修复...")
            
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 修复结构错误的表（删除并重建）
            invalid_tables = health.get('invalid_tables', [])
            for table in invalid_tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    print(f"   ✓ 删除旧表: {table}")
                except Exception as e:
                    print(f"   ✗ 删除表 {table} 失败: {e}")
            
            # 创建缺失的表（包括刚删除的无效表）
            tables_to_create = set(health.get('missing_tables', [])) | set(invalid_tables)
            
            # 表定义
            table_definitions = {
                'sync_status': """
                    CREATE TABLE IF NOT EXISTS sync_status (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        table_name TEXT NOT NULL,
                        record_id INTEGER NOT NULL,
                        sync_state TEXT DEFAULT 'pending',
                        local_version INTEGER DEFAULT 1,
                        cloud_version INTEGER DEFAULT 0,
                        last_sync_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(table_name, record_id)
                    )
                """,
                'prisms': """
                    CREATE TABLE IF NOT EXISTS prisms (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        axis_config TEXT DEFAULT '{}',
                        anchors TEXT DEFAULT '[]',
                        field_data TEXT DEFAULT '[]',
                        version INTEGER DEFAULT 1,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_by TEXT,
                        is_deleted BOOLEAN DEFAULT 0
                    )
                """,
                'prism_versions': """
                    CREATE TABLE IF NOT EXISTS prism_versions (
                        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prism_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        snapshot_data TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        change_reason TEXT,
                        FOREIGN KEY (prism_id) REFERENCES prisms (id)
                    )
                """,
                'capsule_types': """
                    CREATE TABLE IF NOT EXISTS capsule_types (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        name_cn TEXT NOT NULL,
                        description TEXT,
                        icon TEXT,
                        color TEXT NOT NULL,
                        gradient TEXT NOT NULL,
                        examples TEXT,
                        priority_lens TEXT,
                        sort_order INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            }
            
            for table in tables_to_create:
                if table in table_definitions:
                    try:
                        cursor.execute(table_definitions[table])
                        print(f"   ✓ 创建表: {table}")
                    except Exception as e:
                        print(f"   ✗ 创建表 {table} 失败: {e}")
            
            # 插入默认胶囊类型（如果是新创建的）
            if 'capsule_types' in tables_to_create:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO capsule_types (id, name, name_cn, description, icon, color, gradient, examples, priority_lens, sort_order)
                        VALUES 
                            ('magic', 'MAGIC', '魔法', '神秘、梦幻、超自然', 'Sparkles', '#8B5CF6', 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)', '["粒子合成", "调制噪声", "演变音色"]', 'texture', 1),
                            ('impact', 'IMPACT', '打击', '强力、冲击、震撼', 'Flame', '#EF4444', 'linear-gradient(135deg, #EF4444 0%, #F59E0B 100%)', '["鼓点", "打击乐", "贝斯拨奏"]', 'texture', 2),
                            ('atmosphere', 'ATMOSPHERE', '环境', '空间、氛围、场景', 'Music', '#10B981', 'linear-gradient(135deg, #10B981 0%, #06B6D4 100%)', '["Pad", "氛围纹理", "音景"]', 'atmosphere', 3)
                    """)
                    print(f"   ✓ 插入默认胶囊类型")
                except Exception as e:
                    print(f"   ✗ 插入默认胶囊类型失败: {e}")
            
            # 插入默认棱镜数据（如果是新创建的）
            if 'prisms' in tables_to_create:
                try:
                    default_prisms = [
                        ('texture', 'Texture / Timbre', '描述声音的质感特征', 
                         '{"x_label": {"pos": "Light / 光明治愈", "neg": "Dark / 黑暗恐惧"}, "y_label": {"pos": "Playful / 趣味活跃", "neg": "Serious / 写实严肃"}}',
                         '[]', '[]', 1),
                        ('source', 'Source & Physics', '描述声音的来源和物理特性',
                         '{"x_label": {"pos": "Transient / 瞬态冲击", "neg": "Static / 静态铺底"}, "y_label": {"pos": "Sci-Fi / 科幻合成", "neg": "Organic / 有机自然"}}',
                         '[]', '[]', 1),
                        ('materiality', 'Materiality / Room', '描述声音的材质和空间感',
                         '{"x_label": {"pos": "Distant / 遥远湿润", "neg": "Close / 贴耳干涩"}, "y_label": {"pos": "Warm / 暖软吸音", "neg": "Cold / 冷硬反射"}}',
                         '[]', '[]', 1),
                        ('temperament', 'Temperament', '描述声音的情绪和性格',
                         '{"x_label": {"pos": "Calm / 平静", "neg": "Intense / 激烈"}, "y_label": {"pos": "Positive / 积极", "neg": "Negative / 消极"}}',
                         '[]', '[]', 1),
                        ('spectral', 'Spectral', '描述声音的频谱特征',
                         '{"x_label": {"pos": "Bright / 明亮", "neg": "Dark / 暗淡"}, "y_label": {"pos": "Thin / 纤细", "neg": "Thick / 厚重"}}',
                         '[]', '[]', 1)
                    ]
                    for prism in default_prisms:
                        cursor.execute("""
                            INSERT OR IGNORE INTO prisms (id, name, description, axis_config, anchors, field_data, version)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, prism)
                    print(f"   ✓ 插入默认棱镜数据 ({len(default_prisms)} 个)")
                except Exception as e:
                    print(f"   ✗ 插入默认棱镜数据失败: {e}")
            
            # 自动添加缺失的字段
            if health['missing_fields']:
                # 字段类型映射（根据用途推断）
                field_types = {
                    'description': 'TEXT',
                    'keywords': 'TEXT',
                    'asset_status': "TEXT DEFAULT 'local'",
                    'cloud_status': "TEXT DEFAULT 'local'",
                    'cloud_id': 'TEXT',
                    'cloud_version': 'INTEGER DEFAULT 1',
                    'files_downloaded': 'BOOLEAN DEFAULT 1',
                    'last_synced_at': 'TIMESTAMP',
                    'local_wav_path': 'TEXT',
                    'local_wav_size': 'INTEGER',
                    'local_wav_hash': 'TEXT',
                    'download_progress': 'INTEGER DEFAULT 0',
                    'download_started_at': 'TIMESTAMP',
                    'preview_downloaded': 'BOOLEAN DEFAULT 0',
                    'asset_last_accessed_at': 'TIMESTAMP',
                    'asset_access_count': 'INTEGER DEFAULT 0',
                    'is_cache_pinned': 'BOOLEAN DEFAULT 0',
                    'audio_uploaded': 'BOOLEAN DEFAULT 0',
                    'owner_supabase_user_id': 'TEXT',
                    'created_by': 'INTEGER',
                }
                
                for field in health['missing_fields']:
                    field_def = field_types.get(field, 'TEXT')
                    try:
                        cursor.execute(f"ALTER TABLE capsules ADD COLUMN {field} {field_def}")
                        print(f"   ✓ 添加字段: {field}")
                    except Exception as e:
                        print(f"   ✗ 添加字段 {field} 失败: {e}")
            
            conn.commit()
            conn.close()
            print("✅ 数据库修复完成！")
        else:
            print("✅ 数据库 schema 完整")
        
        # 检查 prisms 表是否为空，如果为空则插入默认数据
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prisms")
        prisms_count = cursor.fetchone()[0]
        if prisms_count == 0:
            print("⚠️  prisms 表为空，插入默认棱镜数据...")
            default_prisms = [
                ('texture', 'Texture / Timbre', '描述声音的质感特征', 
                 '{"x_label": {"pos": "Light / 光明治愈", "neg": "Dark / 黑暗恐惧"}, "y_label": {"pos": "Playful / 趣味活跃", "neg": "Serious / 写实严肃"}}',
                 '[]', '[]', 1),
                ('source', 'Source & Physics', '描述声音的来源和物理特性',
                 '{"x_label": {"pos": "Transient / 瞬态冲击", "neg": "Static / 静态铺底"}, "y_label": {"pos": "Sci-Fi / 科幻合成", "neg": "Organic / 有机自然"}}',
                 '[]', '[]', 1),
                ('materiality', 'Materiality / Room', '描述声音的材质和空间感',
                 '{"x_label": {"pos": "Distant / 遥远湿润", "neg": "Close / 贴耳干涩"}, "y_label": {"pos": "Warm / 暖软吸音", "neg": "Cold / 冷硬反射"}}',
                 '[]', '[]', 1),
                ('temperament', 'Temperament', '描述声音的情绪和性格',
                 '{"x_label": {"pos": "Calm / 平静", "neg": "Intense / 激烈"}, "y_label": {"pos": "Positive / 积极", "neg": "Negative / 消极"}}',
                 '[]', '[]', 1),
                ('spectral', 'Spectral', '描述声音的频谱特征',
                 '{"x_label": {"pos": "Bright / 明亮", "neg": "Dark / 暗淡"}, "y_label": {"pos": "Thin / 纤细", "neg": "Thick / 厚重"}}',
                 '[]', '[]', 1)
            ]
            for prism in default_prisms:
                cursor.execute("""
                    INSERT OR IGNORE INTO prisms (id, name, description, axis_config, anchors, field_data, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, prism)
            conn.commit()
            print(f"   ✓ 已插入 {len(default_prisms)} 个默认棱镜")
        conn.close()

    # 启动服务器（使用命令行参数中的端口）
    port = ARGS.port
    host = os.getenv('API_HOST', 'localhost')

    print(f"\n{'='*60}")
    print(f"🚀 Synesth 胶囊 API 服务器")
    print(f"{'='*60}")
    print(f"监听地址: http://{host}:{port}")
    print(f"数据库: {db_path}")
    print(f"导出目录: {EXPORT_DIR}")
    print(f"资源目录: {RESOURCE_DIR}")
    print(f"{'='*60}\n")

    app.run(host=host, port=port, debug=False)
