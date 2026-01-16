这是一份完整的、可直接执行的**API 模块化重构代码包**。

此操作将 `capsule_api.py` 中的同步逻辑剥离到新的 `routes/sync_routes.py` 中，并建立 Flask Blueprint 架构，为接下来的 Global Sync 做好准备。

### 📂 1. 新建文件 `data-pipeline/routes/__init__.py`

_(保持为空文件，用于标记 Python 包)_

---

### 📂 2. 新建文件 `data-pipeline/routes/sync_routes.py`

_(这是新的同步逻辑中心，包含了原有的轻量级同步和为 Phase G 预留的接口)_

Python

```
from flask import Blueprint, request, jsonify
from auth import token_required
from capsule_db import CapsuleDB
from sync_service import SyncService
import logging

# 定义蓝图
sync_bp = Blueprint('sync_bp', __name__)

# 初始化依赖
# 注意：在生产环境中，建议使用 current_app 或依赖注入，这里为了保持与原架构兼容，直接实例化
db = CapsuleDB()
sync_service = SyncService()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
#  原有同步路由 (迁移自 capsule_api.py)
# ---------------------------------------------------------

@sync_bp.route('/lightweight', methods=['POST'])
@token_required
def sync_lightweight(current_user):
    """
    轻量级同步：只同步元数据，不自动下载大文件
    """
    try:
        user_id = current_user['id']
        supabase_uid = current_user['supabase_user_id']
        
        logger.info(f"[SYNC] 用户 {user_id} ({supabase_uid}) 开始轻量级同步...")
        
        # 1. 执行元数据同步 (Push My Changes + Pull My Updates)
        stats = sync_service.sync_metadata_lightweight(user_id)
        
        return jsonify({
            "success": True,
            "message": "Lightweight sync completed",
            "stats": stats
        })
    except Exception as e:
        logger.error(f"[SYNC ERROR] {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@sync_bp.route('/status', methods=['GET'])
@token_required
def get_sync_status(current_user):
    """
    获取当前的同步状态概览
    """
    try:
        user_id = current_user['id']
        
        # 获取待上传数量
        pending_uploads = db.get_pending_uploads_count(user_id)
        
        # 获取待下载数量 (需要在 sync_service 中实现更精确的统计，这里暂时返回本地状态)
        # 实际逻辑通常是比较 local_version 和 cloud_version
        
        return jsonify({
            "success": True,
            "status": {
                "pending_uploads": pending_uploads,
                "is_syncing": False, # 暂时硬编码，未来可接入 Redis 状态
                "last_sync": "Recently" # TODO: 从数据库读取最后同步时间
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@sync_bp.route('/mark-pending', methods=['POST'])
@token_required
def mark_for_sync(current_user):
    """
    手动标记所有本地胶囊为'待同步' (Debug用途)
    """
    try:
        user_id = current_user['id']
        count = db.mark_all_as_pending(user_id)
        return jsonify({"success": True, "marked_count": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------------------------------------------------
#  Global Sync (Phase G) 预留接口
# ---------------------------------------------------------

@sync_bp.route('/world', methods=['GET'])
@token_required
def sync_world_metadata(current_user):
    """
    [Phase G 新增] 拉取世界胶囊数据 (只读模式)
    该接口将触发 'Pull Global' 逻辑，获取其他用户的公开胶囊元数据
    """
    try:
        user_id = current_user['id']
        logger.info(f"[GLOBAL SYNC] 用户 {user_id} 请求拉取世界数据...")
        
        # 这里的具体逻辑将在下一步实现
        # stats = sync_service.pull_global_metadata(user_id)
        
        return jsonify({
            "success": True, 
            "msg": "Global sync logic ready to be implemented",
            "stats": {"new_global_capsules": 0}
        })
    except Exception as e:
        logger.error(f"[GLOBAL SYNC ERROR] {e}")
        return jsonify({"error": str(e)}), 500
```

---

### 📂 3. 修改文件 `data-pipeline/capsule_api.py`

_(这是瘦身后的入口文件，删除了旧的 sync 路由，注册了新的 Blueprint)_

**请将你的 `capsule_api.py` 替换或修改为以下结构：**

Python

```
import sys
import os
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pathlib import Path

# 添加当前目录到 sys.path，确保能导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入配置和依赖
from utils import get_resource_path
from auth import AuthManager, token_required, hash_password
from capsule_db import CapsuleDB
# 注意：SyncService 不再需要在这里直接导入，除非有其他用途

# 👇 1. 导入新的 Blueprint
from routes.sync_routes import sync_bp
# 如果你已经创建了下载模块，也可以在这里导入
# from capsule_download_api import download_bp 

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # 允许跨域

# 配置常量
PORT = 5002

# 初始化核心服务
db = CapsuleDB()
auth_manager = AuthManager()

# ==========================================
# 🚀 蓝图注册 (Blueprint Registration)
# ==========================================

# 注册同步模块，所有路由前缀为 /api/sync
# 例如: /api/sync/lightweight
app.register_blueprint(sync_bp, url_prefix='/api/sync')

# 如果有下载模块，也可以这样注册
# app.register_blueprint(download_bp, url_prefix='/api/download')

# ==========================================
# 🏠 核心 API 路由 (暂未拆分的部分)
# ==========================================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "Sound Capsule API"})

# ... (此处保留 Auth, Library, Tags, Export 等现有路由代码) ...
# ... (请确保不要删除非 Sync 相关的代码) ...

# ---------------------------------------------------------
# 注意：以下原来的 Sync 路由应该被删除了，因为它们现在在 routes/sync_routes.py 中
# @app.route('/api/sync/lightweight', methods=['POST']) -> 删除
# @app.route('/api/sync/status', methods=['GET']) -> 删除
# ---------------------------------------------------------

if __name__ == '__main__':
    print(f"🚀 Sound Capsule API is running on port {PORT}")
    print(f"📂 Sync Routes registered at /api/sync/*")
    app.run(host='0.0.0.0', port=PORT, debug=True)
```