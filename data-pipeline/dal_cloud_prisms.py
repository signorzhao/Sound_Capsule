"""
数据访问层 (DAL): 云端 Prisms 操作

封装所有与 Supabase cloud_prisms 表的交互
保持业务逻辑层与数据访问层的分离
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CloudPrismDAL:
    """
    云端棱镜数据访问层

    封装所有与 cloud_prisms 表的操作
    """

    def __init__(self):
        """初始化 DAL"""
        from supabase_client import get_supabase_client
        self.client = get_supabase_client()
        logger.info("✅ CloudPrismDAL 初始化")

    # 🔐 管理员用户 ID - 只有这个用户可以上传棱镜
    # ian@ian.com 是唯一的棱镜管理员
    ADMIN_USER_ID = 'cd272ab9-0855-4edd-9b64-9be46952d97e'

    def upload_prism(
        self,
        user_id: str,
        prism_id: str,
        prism_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        上传单个棱镜到云端（仅管理员可用）

        🔐 全局共享模式：只有管理员（ian@ian.com）可以上传棱镜
        普通用户的上传请求会被静默忽略

        Args:
            user_id: 用户 ID
            prism_id: 棱镜 ID
            prism_data: 棱镜数据（来自本地 prisms 表）

        Returns:
            上传的记录，失败返回 None
        """
        # 🔐 检查是否是管理员
        if user_id != self.ADMIN_USER_ID:
            logger.info(f"ℹ️  跳过棱镜上传：用户 {user_id[:8]}... 不是管理员")
            return None

        try:
            # 准备云端记录
            # 注意：不包含 field_data，因为云端 schema 中没有此字段
            cloud_record = {
                'user_id': user_id,
                'prism_id': prism_id,
                'name': prism_data.get('name'),
                'description': prism_data.get('description'),
                'axis_config': prism_data.get('axis_config'),  # JSON 字符串
                'anchors': prism_data.get('anchors'),  # JSON 字符串
                # 'field_data' 已从云端 schema 移除，不再上传
                'version': prism_data.get('version', 1),
                'updated_at': prism_data.get('updated_at'),
                'updated_by': prism_data.get('updated_by')
            }

            # 使用 upsert（插入或更新）
            result = self.client.table('cloud_prisms').upsert(
                cloud_record,
                on_conflict='user_id,prism_id'
            ).execute()

            if result.data:
                logger.info(f"✅ 上传棱镜 '{prism_id}' (v{cloud_record['version']})")
                return result.data[0]
            else:
                logger.warning(f"⚠️  上传棱镜 '{prism_id}' 无返回数据")
                return None

        except Exception as e:
            logger.error(f"❌ 上传棱镜 '{prism_id}' 失败: {e}")
            return None

    def download_prisms(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        下载官方棱镜（全局共享模式）

        🔐 所有用户都下载管理员（ian@ian.com）的棱镜
        普通用户无法修改棱镜，只有管理员可以通过锚点编辑器更新

        Args:
            user_id: 用户 ID（忽略，始终下载管理员的棱镜）

        Returns:
            棱镜列表
        """
        try:
            # 🔐 始终下载管理员的棱镜，实现全局共享
            result = self.client.table('cloud_prisms').select('*').eq('user_id', self.ADMIN_USER_ID).execute()

            if result.data:
                logger.info(f"✅ 下载 {len(result.data)} 个官方棱镜 (来自管理员)")
                return result.data
            else:
                logger.info("ℹ️  无官方棱镜")
                return []

        except Exception as e:
            logger.error(f"❌ 下载官方棱镜失败: {e}")
            return []

    def get_prism(
        self,
        user_id: str,
        prism_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取单个云端棱镜

        Args:
            user_id: 用户 ID
            prism_id: 棱镜 ID

        Returns:
            棱镜数据或 None
        """
        try:
            result = self.client.table('cloud_prisms').select('*').eq('user_id', user_id).eq('prism_id', prism_id).execute()

            if result.data:
                return result.data[0]
            else:
                return None

        except Exception as e:
            logger.error(f"❌ 获取云端棱镜 '{prism_id}' 失败: {e}")
            return None

    def delete_prism(
        self,
        user_id: str,
        prism_id: str
    ) -> bool:
        """
        删除云端棱镜

        Args:
            user_id: 用户 ID
            prism_id: 棱镜 ID

        Returns:
            是否成功
        """
        try:
            result = self.client.table('cloud_prisms').delete().eq('user_id', user_id).eq('prism_id', prism_id).execute()

            logger.info(f"✅ 删除云端棱镜 '{prism_id}'")
            return True

        except Exception as e:
            logger.error(f"❌ 删除云端棱镜 '{prism_id}' 失败: {e}")
            return False

    def get_prisms_by_version(
        self,
        user_id: str,
        min_version: int = 1
    ) -> List[Dict[str, Any]]:
        """
        获取版本大于等于指定值的所有棱镜

        用于增量同步

        Args:
            user_id: 用户 ID
            min_version: 最小版本号

        Returns:
            棱镜列表
        """
        try:
            # Supabase 不直接支持 >= 查询，需要在服务端过滤
            result = self.client.table('cloud_prisms').select('*').eq('user_id', user_id).gte('version', min_version).execute()

            if result.data:
                return result.data
            else:
                return []

        except Exception as e:
            logger.error(f"❌ 获取云端棱镜（版本 >= {min_version}）失败: {e}")
            return []

    def batch_upload_prisms(
        self,
        user_id: str,
        prisms: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        批量上传棱镜

        Args:
            user_id: 用户 ID
            prisms: 棱镜列表（每个包含 prism_id 和 prism_data）

        Returns:
            {
                'success': bool,
                'uploaded': int,
                'failed': int,
                'errors': List[str]
            }
        """
        success_count = 0
        failed_count = 0
        errors = []

        for prism in prisms:
            prism_id = prism.get('id')
            prism_data = prism

            result = self.upload_prism(user_id, prism_id, prism_data)

            if result:
                success_count += 1
            else:
                failed_count += 1
                errors.append(f"上传棱镜 '{prism_id}' 失败")

        return {
            'success': failed_count == 0,
            'uploaded': success_count,
            'failed': failed_count,
            'errors': errors
        }

    def sync_prism(
        self,
        user_id: str,
        local_prism: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        同步单个棱镜（智能版本比较）

        Args:
            user_id: 用户 ID
            local_prism: 本地棱镜数据

        Returns:
            {
                'action': 'upload' | 'download' | 'skip',
                'version': int,
                'success': bool
            }
        """
        prism_id = local_prism.get('id')
        local_version = local_prism.get('version', 1)

        # 获取云端版本
        cloud_prism = self.get_prism(user_id, prism_id)

        if not cloud_prism:
            # 云端不存在，上传
            result = self.upload_prism(user_id, prism_id, local_prism)
            return {
                'action': 'upload',
                'version': local_version,
                'success': result is not None
            }

        cloud_version = cloud_prism.get('version', 1)

        # 版本比较
        if local_version > cloud_version:
            # 本地版本更新，上传
            result = self.upload_prism(user_id, prism_id, local_prism)
            return {
                'action': 'upload',
                'version': local_version,
                'success': result is not None
            }
        elif cloud_version > local_version:
            # 云端版本更新，下载
            return {
                'action': 'download',
                'version': cloud_version,
                'success': True,
                'data': cloud_prism
            }
        else:
            # 版本相同，跳过
            return {
                'action': 'skip',
                'version': local_version,
                'success': True
            }


# ==========================================
# 便捷函数
# ==========================================

_dal_instance: Optional[CloudPrismDAL] = None


def get_cloud_prism_dal() -> CloudPrismDAL:
    """
    获取 CloudPrismDAL 实例（单例）

    Returns:
        CloudPrismDAL 实例
    """
    global _dal_instance

    if _dal_instance is None:
        _dal_instance = CloudPrismDAL()

    return _dal_instance
