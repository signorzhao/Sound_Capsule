"""
Supabase 客户端配置

提供云端数据库连接和操作
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import hashlib

# 加载 .env.supabase 文件
def _load_supabase_env():
    """从 .env.supabase 文件加载环境变量"""
    env_file = Path(__file__).parent / '.env.supabase'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# 加载环境变量
_load_supabase_env()

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("警告: supabase 包未安装，云端同步功能将不可用")
    print("请运行: pip install supabase")


class SupabaseClient:
    """Supabase 客户端单例"""

    _instance: Optional['SupabaseClient'] = None
    _client: Optional[Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is not None:
            return

        if not SUPABASE_AVAILABLE:
            raise Exception("Supabase 包未安装")

        # 从环境变量读取配置
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # 后端使用 service role key

        if not self.url or not self.key:
            raise Exception("Supabase 配置缺失：请设置 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY")

        # 创建客户端
        self._client = create_client(self.url, self.key)
        print(f"✓ Supabase 客户端已初始化: {self.url}")

    @property
    def client(self) -> Client:
        """获取 Supabase 客户端"""
        if self._client is None:
            raise Exception("Supabase 客户端未初始化")
        return self._client

    def table(self, table_name: str):
        """
        代理方法：允许外部直接访问 Supabase 的 table 对象

        Args:
            table_name: 表名

        Returns:
            Supabase Table API 对象
        """
        if self._client is None:
            raise Exception("Supabase 客户端未初始化")
        return self._client.table(table_name)

    # ==========================================
    # 用户认证 (Supabase Auth)
    # ==========================================

    def auth_sign_up(self, email: str, password: str, username: str = None) -> Dict[str, Any]:
        """
        使用 Supabase Auth 注册用户
        
        Args:
            email: 用户邮箱
            password: 密码
            username: 用户名（可选，存入 user_metadata）
            
        Returns:
            包含用户信息和 session 的字典
        """
        try:
            user_metadata = {}
            if username:
                user_metadata['username'] = username
                user_metadata['display_name'] = username
            
            response = self._client.auth.sign_up({
                'email': email,
                'password': password,
                'options': {
                    'data': user_metadata
                }
            })
            
            if response.user:
                return {
                    'success': True,
                    'user': {
                        'id': response.user.id,
                        'email': response.user.email,
                        'username': username or email.split('@')[0],
                        'created_at': str(response.user.created_at) if response.user.created_at else None
                    },
                    'session': {
                        'access_token': response.session.access_token if response.session else None,
                        'refresh_token': response.session.refresh_token if response.session else None,
                        'expires_in': response.session.expires_in if response.session else None
                    } if response.session else None
                }
            else:
                return {'success': False, 'error': '注册失败'}
        except Exception as e:
            error_msg = str(e)
            if 'already registered' in error_msg.lower():
                return {'success': False, 'error': '该邮箱已被注册'}
            return {'success': False, 'error': f'注册失败: {error_msg}'}

    def auth_admin_confirm_user_by_email(self, email: str) -> bool:
        """
        使用 Service Role 按邮箱找到未确认用户并设为已确认（不发邮件）。
        用于自建 Supabase 未配 SMTP 时，注册虽创建用户但返回 500 的场景。

        Returns:
            True 表示已找到并确认，False 表示未找到或操作失败
        """
        try:
            # list_users 返回分页，先取一页按邮箱过滤
            r = self._client.auth.admin.list_users(per_page=1000)
            if not getattr(r, 'users', None):
                return False
            for u in r.users:
                if getattr(u, 'email', None) and u.email.lower() == email.lower():
                    self._client.auth.admin.update_user_by_id(u.id, {"email_confirm": True})
                    return True
            return False
        except Exception as e:
            print(f"[Supabase] auth_admin_confirm_user_by_email 失败: {e}")
            return False

    def auth_sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        使用 Supabase Auth 登录用户
        
        Args:
            email: 用户邮箱
            password: 密码
            
        Returns:
            包含用户信息和 session 的字典
        """
        try:
            response = self._client.auth.sign_in_with_password({
                'email': email,
                'password': password
            })
            
            if response.user and response.session:
                user_metadata = response.user.user_metadata or {}
                return {
                    'success': True,
                    'user': {
                        'id': response.user.id,
                        'email': response.user.email,
                        'username': user_metadata.get('username', email.split('@')[0]),
                        'display_name': user_metadata.get('display_name', user_metadata.get('username', email.split('@')[0])),
                        'created_at': str(response.user.created_at) if response.user.created_at else None
                    },
                    'session': {
                        'access_token': response.session.access_token,
                        'refresh_token': response.session.refresh_token,
                        'expires_in': response.session.expires_in
                    }
                }
            else:
                return {'success': False, 'error': '登录失败'}
        except Exception as e:
            error_msg = str(e)
            if 'invalid' in error_msg.lower() or 'credentials' in error_msg.lower():
                return {'success': False, 'error': '邮箱或密码错误'}
            return {'success': False, 'error': f'登录失败: {error_msg}'}

    def auth_sign_out(self) -> Dict[str, Any]:
        """登出当前用户"""
        try:
            self._client.auth.sign_out()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def auth_get_user(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        通过 access token 获取用户信息
        
        Args:
            access_token: JWT access token
            
        Returns:
            用户信息字典，如果无效则返回 None
        """
        try:
            response = self._client.auth.get_user(access_token)
            if response.user:
                user_metadata = response.user.user_metadata or {}
                return {
                    'id': response.user.id,
                    'email': response.user.email,
                    'username': user_metadata.get('username', response.user.email.split('@')[0] if response.user.email else None),
                    'display_name': user_metadata.get('display_name'),
                    'supabase_user_id': response.user.id
                }
            return None
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return None

    def auth_refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        刷新 access token
        
        Args:
            refresh_token: refresh token
            
        Returns:
            新的 session 信息
        """
        try:
            response = self._client.auth.refresh_session(refresh_token)
            if response.session:
                return {
                    'success': True,
                    'access_token': response.session.access_token,
                    'refresh_token': response.session.refresh_token,
                    'expires_in': response.session.expires_in
                }
            return {'success': False, 'error': 'Token 刷新失败'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==========================================
    # 胶囊操作
    # ==========================================

    def get_cloud_capsule_by_local_id(self, user_id: str, local_id: int, capsule_name: str = None) -> Optional[Dict[str, Any]]:
        """
        根据本地 ID 或胶囊名称获取云端胶囊记录
        
        优先使用 local_id 匹配，如果失败则尝试使用 name 匹配（防止切换文件夹后 ID 变化）
        """
        try:
            # 1. 优先使用 local_id 匹配
            result = self.client.table('cloud_capsules').select('id, version, metadata, local_id').eq('user_id', user_id).eq('local_id', local_id).execute()
            if result.data:
                return result.data[0]
            
            # 2. 如果 local_id 匹配失败，尝试使用 name 匹配（更稳定）
            if capsule_name:
                result = self.client.table('cloud_capsules').select('id, version, metadata, local_id').eq('user_id', user_id).eq('name', capsule_name).execute()
                if result.data:
                    print(f"   ℹ️ 通过名称匹配到云端胶囊: {capsule_name}")
                    return result.data[0]
            
            return None
        except Exception as e:
            print(f"✗ 获取云端胶囊失败: {e}")
            return None

    def update_capsule_keywords(self, user_id: str, local_id: int, keywords: Optional[str]) -> Optional[Dict[str, Any]]:
        """仅更新云端胶囊的 keywords（metadata 内）"""
        try:
            existing = self.get_cloud_capsule_by_local_id(user_id, local_id)
            if not existing:
                return None

            metadata = existing.get('metadata') or {}
            if not isinstance(metadata, dict):
                metadata = {}
            metadata['keywords'] = keywords

            version = existing.get('version', 0) + 1
            result = self.client.table('cloud_capsules').update({
                'metadata': metadata,
                'version': version,
                'last_write_at': datetime.utcnow().isoformat()
            }).eq('id', existing['id']).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"✗ 更新 keywords 失败: {e}")
            return None

    def upload_capsule(self, user_id: str, capsule_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        上传胶囊到云端

        Args:
            user_id: 用户 ID
            capsule_data: 胶囊数据

        Returns:
            上传的记录，失败返回 None
        """
        try:
            # 计算数据哈希
            data_json = json.dumps(capsule_data, sort_keys=True)
            data_hash = hashlib.sha256(data_json.encode()).hexdigest()

            # 准备云端记录
            cloud_record = {
                'user_id': user_id,
                'local_id': capsule_data.get('id'),
                'name': capsule_data.get('name'),
                'description': capsule_data.get('description'),
                'capsule_type_id': capsule_data.get('capsule_type_id'),
                'reaper_project_path': capsule_data.get('reaper_project_path'),
                'version': capsule_data.get('version', 1),
                'data_hash': data_hash,
                'metadata': capsule_data,
                'last_write_at': capsule_data.get('last_write_at', datetime.utcnow().isoformat()),
            }

            # 检查是否已存在（使用多级匹配：local_id -> name）
            capsule_name = capsule_data.get('name')
            existing = None
            
            # 1. 优先使用 local_id 匹配
            result_by_id = self.client.table('cloud_capsules').select('id, version').eq('user_id', user_id).eq('local_id', capsule_data.get('id')).execute()
            if result_by_id.data:
                existing = result_by_id.data[0]
            
            # 2. 如果 local_id 匹配失败，尝试使用 name 匹配（更稳定）
            if not existing and capsule_name:
                result_by_name = self.client.table('cloud_capsules').select('id, version').eq('user_id', user_id).eq('name', capsule_name).execute()
                if result_by_name.data:
                    existing = result_by_name.data[0]
                    print(f"   ℹ️ 通过名称匹配到已有胶囊: {capsule_name}")

            if existing:
                # 更新现有记录
                cloud_record['version'] = existing['version'] + 1
                # 同时更新 local_id 以保持同步
                cloud_record['local_id'] = capsule_data.get('id')
                result = self.client.table('cloud_capsules').update(cloud_record).eq('id', existing['id']).execute()
                print(f"✓ 更新胶囊 {capsule_name} (版本 {cloud_record['version']})")
            else:
                # 插入新记录
                result = self.client.table('cloud_capsules').insert(cloud_record).execute()
                print(f"✓ 上传胶囊 {capsule_name}")

            return result.data[0] if result.data else None

        except Exception as e:
            print(f"✗ 上传胶囊失败: {e}")
            return None

    # ==========================================
    # Storage 文件检查
    # ==========================================

    def storage_file_exists(self, user_id: str, capsule_folder_name: str, filename: str) -> bool:
        """检查 Storage 中指定文件是否存在"""
        try:
            bucket_name = 'capsule-files'
            storage_path = f"{user_id}/{capsule_folder_name}/{filename}"
            self.client.storage.from_(bucket_name).get_metadata(storage_path)
            return True
        except Exception:
            return False

    def list_audio_files(self, user_id: str, capsule_folder_name: str) -> List[str]:
        """列出云端 Audio 文件夹内的文件名"""
        try:
            bucket_name = 'capsule-files'
            cloud_folder = f"{user_id}/{capsule_folder_name}/Audio"
            files = self.client.storage.from_(bucket_name).list(cloud_folder)
            return [f['name'] for f in files] if files else []
        except Exception:
            return []

    def upload_audio_files(self, user_id: str, capsule_folder_name: str, audio_files: List[Path], progress_callback=None) -> Dict[str, Any]:
        """仅上传指定的音频文件列表"""
        try:
            bucket_name = 'capsule-files'
            files_uploaded = 0
            total_size = 0
            errors = []
            total_files = len(audio_files)

            for audio_file in audio_files:
                try:
                    with open(audio_file, 'rb') as f:
                        file_content = f.read()
                    storage_path = f"{user_id}/{capsule_folder_name}/Audio/{audio_file.name}"
                    self.client.storage.from_(bucket_name).upload(
                        path=storage_path,
                        file=file_content,
                        file_options={"upsert": "true"}
                    )
                    file_size = len(file_content)
                    total_size += file_size
                    files_uploaded += 1
                    if progress_callback:
                        progress_callback(files_uploaded, total_files, audio_file.name)
                except Exception as e:
                    self._last_storage_error = str(e)
                    errors.append(f"{audio_file.name}: {e}")

            return {
                'success': len(errors) == 0,
                'files_uploaded': files_uploaded,
                'total_size': total_size,
                'errors': errors
            }
        except Exception as e:
            self._last_storage_error = str(e)
            print(f"✗ 上传音频文件失败: {e}")
            return {'success': False, 'files_uploaded': 0}

    def download_capsules(self, user_id: str, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        从云端下载胶囊

        Args:
            user_id: 用户 ID
            since: 可选，只下载此时间之后更新的记录

        Returns:
            胶囊列表
        """
        try:
            # 修改：获取所有用户的胶囊 (Shared/Public Mode)
            query = self.client.table('cloud_capsules').select('*')

            # 过滤已删除的记录
            query = query.is_('deleted_at', None)

            # 时间过滤
            if since:
                query = query.gt('updated_at', since.isoformat())

            result = query.execute()
            print(f"✓ 下载 {len(result.data)} 个胶囊")

            return result.data

        except Exception as e:
            print(f"✗ 下载胶囊失败: {e}")
            return []

    def delete_capsule(self, user_id: str, local_id: int) -> bool:
        """
        软删除胶囊（标记为已删除）

        Args:
            user_id: 用户 ID
            local_id: 本地 ID

        Returns:
            是否成功
        """
        try:
            result = self.client.table('cloud_capsules').update({
                'deleted_at': datetime.utcnow().isoformat()
            }).eq('user_id', user_id).eq('local_id', local_id).execute()

            print(f"✓ 标记删除胶囊 {local_id}")
            return True

        except Exception as e:
            print(f"✗ 删除胶囊失败: {e}")
            return False

    def get_capsule_count(self, user_id: str) -> Optional[int]:
        """
        获取云端胶囊总数

        Args:
            user_id: 用户 ID

        Returns:
            胶囊总数，失败返回 None
        """
        try:
            # 修改：统计所有用户的胶囊
            result = self.client.table('cloud_capsules').select('id', count='exact').execute()
            return result.count
        except Exception as e:
            print(f"✗ 获取云端胶囊数量失败: {e}")
            return None

    # ==========================================
    # 标签操作
    # ==========================================

    def upload_tags(self, user_id: str, capsule_cloud_id: str, tags: List[Dict[str, Any]]) -> bool:
        """
        上传标签到云端（先删除旧标签，再插入新标签）

        Args:
            user_id: 用户 ID
            capsule_cloud_id: 胶囊云端 ID
            tags: 标签列表，包含 lens, word_id, word_cn, word_en, x, y

        Returns:
            是否成功
        """
        try:
            # 先删除该胶囊的所有旧标签（不限制 user_id，避免跨设备同步时重复）
            self.client.table('cloud_capsule_tags').delete().eq(
                'capsule_id', capsule_cloud_id
            ).execute()

            # 再插入新标签
            if tags:
                tag_records = []
                for tag in tags:
                    tag_records.append({
                        'user_id': user_id,
                        'capsule_id': capsule_cloud_id,
                        'lens_id': tag.get('lens') or tag.get('lens_id'),
                        'word_id': tag.get('word_id'),
                        'word_cn': tag.get('word_cn'),
                        'word_en': tag.get('word_en'),
                        'x': tag.get('x'),
                        'y': tag.get('y'),
                    })

                # 批量插入
                self.client.table('cloud_capsule_tags').insert(tag_records).execute()

            print(f"✓ 上传 {len(tags)} 个标签")
            return True

        except Exception as e:
            import traceback
            print(f"✗ 上传标签失败: {e}")
            traceback.print_exc()
            return False

    def download_tags(self, user_id: str) -> List[Dict[str, Any]]:
        """
        从云端下载标签

        Args:
            user_id: 用户 ID

        Returns:
            标签列表
        """
        try:
            # 修改：下载所有用户的标签
            result = self.client.table('cloud_capsule_tags').select('*').execute()
            print(f"✓ 下载 {len(result.data)} 个标签")
            return result.data

        except Exception as e:
            print(f"✗ 下载标签失败: {e}")
            return []

    def download_capsule_tags(self, capsule_cloud_id: str) -> List[Dict[str, Any]]:
        """
        下载指定胶囊的标签

        Args:
            capsule_cloud_id: 胶囊云端 ID

        Returns:
            标签列表
        """
        try:
            result = self.client.table('cloud_capsule_tags').select('*').eq('capsule_id', capsule_cloud_id).execute()
            return result.data if result.data else []

        except Exception as e:
            print(f"✗ 下载胶囊标签失败: {e}")
            return []

    # ==========================================
    # 坐标操作
    # ==========================================

    def upload_coordinates(self, user_id: str, capsule_cloud_id: str, coordinates: List[Dict[str, Any]]) -> bool:
        """
        上传坐标到云端

        Args:
            user_id: 用户 ID
            capsule_cloud_id: 胶囊云端 ID
            coordinates: 坐标列表

        Returns:
            是否成功
        """
        try:
            for coord in coordinates:
                coord_record = {
                    'user_id': user_id,
                    'capsule_id': capsule_cloud_id,
                    'lens_id': coord.get('lens') or coord.get('lens_id'),
                    'dimension': coord.get('dimension'),
                    'value': coord.get('value'),
                }

                # 插入或更新
                self.client.table('cloud_capsule_coordinates').upsert(coord_record).execute()

            print(f"✓ 上传 {len(coordinates)} 个坐标")
            return True

        except Exception as e:
            print(f"✗ 上传坐标失败: {e}")
            return False

    def download_coordinates(self, user_id: str) -> List[Dict[str, Any]]:
        """
        从云端下载坐标

        Args:
            user_id: 用户 ID

        Returns:
            坐标列表
        """
        try:
            # 修改：下载所有用户的坐标
            result = self.client.table('cloud_capsule_coordinates').select('*').execute()
            print(f"✓ 下载 {len(result.data)} 个坐标")
            return result.data

        except Exception as e:
            print(f"✗ 下载坐标失败: {e}")
            return []

    # ==========================================
    # 同步日志操作
    # ==========================================

    def log_sync(self, user_id: str, table_name: str, operation: str,
                 record_id: str, direction: str, status: str, metadata: Optional[Dict] = None) -> bool:
        """
        记录同步日志

        Args:
            user_id: 用户 ID
            table_name: 表名
            operation: 操作类型
            record_id: 记录 ID
            direction: 方向 ('to_cloud' 或 'from_cloud')
            status: 状态 ('success', 'failed', 'conflict')
            metadata: 可选的元数据

        Returns:
            是否成功
        """
        try:
            log_record = {
                'user_id': user_id,
                'table_name': table_name,
                'operation': operation,
                'record_id': record_id,
                'direction': direction,
                'status': status,
                'metadata': metadata or {},
            }

            self.client.table('sync_log_cloud').insert(log_record).execute()
            return True

        except Exception as e:
            print(f"✗ 记录同步日志失败: {e}")
            return False

    def get_last_sync_time(self, user_id: str) -> Optional[datetime]:
        """
        获取最后同步时间

        Args:
            user_id: 用户 ID

        Returns:
            最后同步时间，如果没有则返回 None
        """
        try:
            result = self.client.table('sync_log_cloud').select('created_at').eq('user_id', user_id).eq('direction', 'to_cloud').eq('status', 'success').order('created_at', desc=True).limit(1).execute()

            if result.data:
                return datetime.fromisoformat(result.data[0]['created_at'].replace('Z', '+00:00'))
            return None

        except Exception as e:
            print(f"✗ 获取最后同步时间失败: {e}")
            return None

    # ==========================================
    # 文件存储操作
    # ==========================================

    def upload_file(self, user_id: str, capsule_folder_name: str, file_type: str,
                   file_path: str, progress_callback=None) -> Optional[Dict[str, Any]]:
        """
        上传文件到 Supabase Storage

        Args:
            user_id: 用户 ID (Supabase UUID)
            capsule_folder_name: 胶囊文件夹名（如：magic_ianzhao_20260111_213145）
            file_type: 文件类型 ('preview', 'rpp', 'capsule', 或 'audio_folder')
            file_path: 本地文件路径

        Returns:
            上传结果，包含路径等信息
        """
        self._last_storage_error = None
        try:
            import os
            from pathlib import Path

            # 检查文件/文件夹是否存在
            path_obj = Path(file_path)
            if not path_obj.exists():
                print(f"✗ 路径不存在: {file_path}")
                return None

            # 上传整个 Audio 文件夹
            if file_type == 'audio_folder':
                return self._upload_audio_folder(user_id, capsule_folder_name, file_path, progress_callback)

            # 单个文件上传
            if not path_obj.is_file():
                print(f"✗ 不是文件: {file_path}")
                return None

            # 确定文件扩展名
            file_ext = path_obj.suffix
            if file_type == 'preview':
                # 使用胶囊文件夹名作为预览音频文件名（而非硬编码的 preview.ogg）
                storage_path = f"{user_id}/{capsule_folder_name}/{capsule_folder_name}{file_ext}"
            elif file_type == 'rpp':
                # 使用胶囊文件夹名作为 RPP 文件名（而非硬编码的 project.rpp）
                storage_path = f"{user_id}/{capsule_folder_name}/{capsule_folder_name}.rpp"
            elif file_type == 'metadata':
                storage_path = f"{user_id}/{capsule_folder_name}/metadata.json"
            elif file_type == 'capsule':
                storage_path = f"{user_id}/{capsule_folder_name}/capsule.capsule"
            else:
                print(f"✗ 不支持的文件类型: {file_type}")
                return None

            # 读取文件内容
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # 上传到 Storage（使用 upsert 覆盖已存在的文件）
            bucket_name = 'capsule-files'
            result = self.client.storage.from_(bucket_name).upload(
                path=storage_path,
                file=file_content,
                file_options={"upsert": "true"}  # 覆盖已存在的文件
            )

            # 获取公开 URL（如果 bucket 是私有的，需要生成签名 URL）
            file_url = f"{self.url}/storage/v1/object/{bucket_name}/{storage_path}"

            print(f"✓ 上传文件成功: {storage_path}")
            print(f"  大小: {len(file_content)} bytes")
            print(f"  URL: {file_url}")

            return {
                'storage_path': storage_path,
                'file_url': file_url,
                'size': len(file_content),
                'file_type': file_type
            }

        except Exception as e:
            self._last_storage_error = str(e)
            import logging
            import traceback
            logging.getLogger(__name__).error("Storage 上传文件失败: %s\n%s", e, traceback.format_exc())
            print(f"✗ 上传文件失败: {e}")
            traceback.print_exc()
            return None

    def get_last_storage_error(self) -> str:
        """返回最近一次 Storage 操作失败时的错误信息，便于同步流程上报"""
        return getattr(self, '_last_storage_error', None) or ''

    def _upload_audio_folder(self, user_id: str, capsule_folder_name: str, audio_folder_path: str, progress_callback=None) -> Dict[str, Any]:
        """
        上传整个 Audio 文件夹到云端

        Args:
            user_id: 用户 ID (Supabase UUID)
            capsule_folder_name: 胶囊文件夹名（如：magic_ianzhao_20260111_213145）
            audio_folder_path: Audio 文件夹路径

        Returns:
            上传结果统计
        """
        try:
            from pathlib import Path
            import os

            audio_folder = Path(audio_folder_path)
            if not audio_folder.exists() or not audio_folder.is_dir():
                print(f"✗ Audio 文件夹不存在: {audio_folder_path}")
                return {'success': False, 'files_uploaded': 0}

            bucket_name = 'capsule-files'
            files_uploaded = 0
            total_size = 0
            errors = []

            audio_files = [
                audio_file for audio_file in audio_folder.iterdir()
                if audio_file.is_file()
                and audio_file.suffix.lower() in ['.wav', '.mp3', '.ogg', '.flac', '.aiff']
            ]
            total_files = len(audio_files)

            # 遍历 Audio 文件夹中的所有音频文件
            for audio_file in audio_files:

                try:
                    # 读取文件
                    with open(audio_file, 'rb') as f:
                        file_content = f.read()

                    # 云端路径: {user_id}/{capsule_folder_name}/Audio/{filename}
                    storage_path = f"{user_id}/{capsule_folder_name}/Audio/{audio_file.name}"

                    # 先删除已存在的文件（避免 400 错误）
                    try:
                        self.client.storage.from_(bucket_name).remove(storage_path)
                    except:
                        pass  # 文件不存在，继续上传

                    # 上传
                    self.client.storage.from_(bucket_name).upload(
                        path=storage_path,
                        file=file_content
                    )

                    file_size = len(file_content)
                    total_size += file_size
                    files_uploaded += 1

                    if progress_callback:
                        progress_callback(files_uploaded, total_files, audio_file.name)

                    print(f"  ✓ {audio_file.name} ({file_size:,} bytes)")

                except Exception as e:
                    error_msg = f"{audio_file.name}: {str(e)}"
                    errors.append(error_msg)
                    print(f"  ✗ {error_msg}")

            print(f"\n✓ Audio 文件夹上传完成:")
            print(f"  成功: {files_uploaded} 个文件")
            print(f"  总大小: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
            if errors:
                print(f"  失败: {len(errors)} 个文件")
                for error in errors:
                    print(f"    - {error}")

            return {
                'success': True,
                'files_uploaded': files_uploaded,
                'total_size': total_size,
                'errors': errors
            }

        except Exception as e:
            self._last_storage_error = str(e)
            print(f"✗ 上传 Audio 文件夹失败: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'files_uploaded': 0}

    def download_file(self, user_id: str, capsule_folder_name: str, file_type: str,
                     local_path: str) -> bool:
        """
        从 Supabase Storage 下载文件

        Args:
            user_id: 用户 ID (Supabase UUID)
            capsule_folder_name: 胶囊文件夹名（如：magic_ianzhao_20260111_213145）
            file_type: 文件类型 ('preview', 'rpp', 'capsule', 或 'audio_folder')
            local_path: 本地保存路径

        Returns:
            是否成功
        """
        try:
            from pathlib import Path

            # 下载整个 Audio 文件夹
            if file_type == 'audio_folder':
                return self._download_audio_folder(user_id, capsule_folder_name, local_path)

            # 确定存储路径
            if file_type == 'preview':
                # 优先尝试动态文件名（新格式），然后回退到 preview.ogg（旧格式）
                possible_paths = []
                for ext in ['.ogg', '.mp3', '.wav']:
                    # 新格式：使用胶囊文件夹名
                    possible_paths.append(f"{user_id}/{capsule_folder_name}/{capsule_folder_name}{ext}")
                    # 旧格式：固定 preview 文件名（向后兼容）
                    possible_paths.append(f"{user_id}/{capsule_folder_name}/preview{ext}")
                
                for storage_path in possible_paths:
                    try:
                        result = self.client.storage.from_('capsule-files').download(storage_path)
                        print(f"✓ 下载预览音频: {storage_path}")
                        break
                    except:
                        continue
                else:
                    print(f"✗ 预览音频不存在: {user_id}/{capsule_folder_name}/ (尝试了所有格式)")
                    return False
            elif file_type == 'rpp':
                # 使用胶囊文件夹名作为 RPP 文件名（而非硬编码的 project.rpp）
                storage_path = f"{user_id}/{capsule_folder_name}/{capsule_folder_name}.rpp"
                try:
                    result = self.client.storage.from_('capsule-files').download(storage_path)
                except Exception as e:
                    # 兼容旧数据：如果新路径不存在，尝试旧的 project.rpp
                    print(f"⚠️ 尝试新路径失败，尝试旧路径 project.rpp: {e}")
                    storage_path = f"{user_id}/{capsule_folder_name}/project.rpp"
                    result = self.client.storage.from_('capsule-files').download(storage_path)
            elif file_type == 'metadata':
                storage_path = f"{user_id}/{capsule_folder_name}/metadata.json"
                try:
                    result = self.client.storage.from_('capsule-files').download(storage_path)
                except Exception as e:
                    # metadata 可能不存在（旧胶囊），不应阻断流程
                    print(f"⚠️ metadata.json 不存在（可能是旧胶囊）: {e}")
                    return False
            elif file_type == 'capsule':
                storage_path = f"{user_id}/{capsule_folder_name}/capsule.capsule"
                result = self.client.storage.from_('capsule-files').download(storage_path)
            else:
                print(f"✗ 不支持的文件类型: {file_type}")
                return False

            # 创建本地目录
            local_file = Path(local_path)
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # 保存文件
            with open(local_path, 'wb') as f:
                f.write(result)

            print(f"✓ 下载文件成功: {storage_path} -> {local_path}")
            return True

        except Exception as e:
            print(f"✗ 下载文件失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _download_audio_folder(self, user_id: str, capsule_folder_name: str, local_capsule_dir: str) -> bool:
        """
        从云端下载 Audio 文件夹到本地

        Args:
            user_id: 用户 ID (Supabase UUID)
            capsule_folder_name: 胶囊文件夹名（如：magic_ianzhao_20260111_213145）
            local_capsule_dir: 本地胶囊目录（会自动创建 Audio 子目录）

        Returns:
            是否成功
        """
        try:
            from pathlib import Path

            bucket_name = 'capsule-files'
            cloud_folder = f"{user_id}/{capsule_folder_name}/Audio/"
            local_audio_dir = Path(local_capsule_dir) / "Audio"

            # 创建本地 Audio 目录
            local_audio_dir.mkdir(parents=True, exist_ok=True)

            # 列出云端 Audio 文件夹中的所有文件
            try:
                files = self.client.storage.from_(bucket_name).list(cloud_folder)
            except Exception as e:
                print(f"✗ 无法列出云端文件: {e}")
                return False

            if not files:
                print(f"✗云端 Audio 文件夹为空")
                return False

            files_downloaded = 0
            total_size = 0
            errors = []

            # 下载每个音频文件
            for file_info in files:
                try:
                    filename = file_info['name']
                    storage_path = f"{cloud_folder}{filename}"
                    local_path = local_audio_dir / filename

                    # 下载文件
                    file_content = self.client.storage.from_(bucket_name).download(storage_path)

                    # 保存到本地
                    with open(local_path, 'wb') as f:
                        f.write(file_content)

                    file_size = len(file_content)
                    total_size += file_size
                    files_downloaded += 1

                    print(f"  ✓ {filename} ({file_size:,} bytes)")

                except Exception as e:
                    error_msg = f"{filename}: {str(e)}"
                    errors.append(error_msg)
                    print(f"  ✗ {error_msg}")

            print(f"\n✓ Audio 文件夹下载完成:")
            print(f"  成功: {files_downloaded} 个文件")
            print(f"  总大小: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
            print(f"  本地路径: {local_audio_dir}")
            if errors:
                print(f"  失败: {len(errors)} 个文件")
                for error in errors:
                    print(f"    - {error}")

            return files_downloaded > 0

        except Exception as e:
            print(f"✗ 下载 Audio 文件夹失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def delete_file(self, user_id: str, capsule_local_id: int) -> bool:
        """
        删除胶囊的所有文件

        Args:
            user_id: 用户 ID (Supabase UUID)
            capsule_local_id: 胶囊本地 ID

        Returns:
            是否成功
        """
        try:
            bucket_name = 'capsule-files'
            folder_path = f"{user_id}/{capsule_local_id}/"

            # 删除文件夹中的所有文件
            files = self.client.storage.from_(bucket_name).list(folder_path)

            for file in files:
                file_path = f"{folder_path}{file['name']}"
                self.client.storage.from_(bucket_name).remove(file_path)

            print(f"✓ 删除文件成功: {folder_path} ({len(files)} 个文件)")
            return True

        except Exception as e:
            print(f"✗ 删除文件失败: {e}")
            return False

    def get_file_url(self, user_id: str, capsule_local_id: int, file_type: str) -> Optional[str]:
        """
        获取文件的访问 URL

        Args:
            user_id: 用户 ID (Supabase UUID)
            capsule_local_id: 胶囊本地 ID
            file_type: 文件类型

        Returns:
            文件 URL，如果文件不存在返回 None
        """
        try:
            bucket_name = 'capsule-files'

            if file_type == 'preview':
                # 尝试不同的扩展名
                for ext in ['.ogg', '.mp3', '.wav']:
                    storage_path = f"{user_id}/{capsule_local_id}/preview{ext}"
                    url = self.client.storage.from_(bucket_name).get_public_url(storage_path)
                    # 这里假设 bucket 是私有的，需要生成签名 URL
                    # 或者使用临时 URL
                    return f"{self.url}/storage/v1/object/{bucket_name}/{storage_path}"
            elif file_type == 'rpp':
                storage_path = f"{user_id}/{capsule_local_id}/project.rpp"
            elif file_type == 'capsule':
                storage_path = f"{user_id}/{capsule_local_id}/capsule.capsule"
            else:
                return None

            return f"{self.url}/storage/v1/object/{bucket_name}/{storage_path}"

        except Exception as e:
            print(f"✗ 获取文件 URL 失败: {e}")
            return None

    def check_file_exists(self, user_id: str, capsule_local_id: int, file_type: str) -> bool:
        """
        检查文件是否存在于云端

        Args:
            user_id: 用户 ID (Supabase UUID)
            capsule_local_id: 胶囊本地 ID
            file_type: 文件类型

        Returns:
            文件是否存在
        """
        try:
            bucket_name = 'capsule-files'

            if file_type == 'preview':
                folder_path = f"{user_id}/{capsule_local_id}/"
                files = self.client.storage.from_(bucket_name).list(folder_path)
                # 检查是否有 preview 文件
                return any(f['name'].startswith('preview') for f in files)
            else:
                storage_path = f"{user_id}/{capsule_local_id}/{'project.rpp' if file_type == 'rpp' else 'capsule.capsule'}"
                # 尝试获取文件信息
                self.client.storage.from_(bucket_name).get_metadata(storage_path)
                return True

        except Exception as e:
            return False


# ==========================================
# 全局实例
# ==========================================

_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> Optional[SupabaseClient]:
    """
    获取 Supabase 客户端实例

    Returns:
        SupabaseClient 实例，如果未配置则返回 None
    """
    global _supabase_client

    if _supabase_client is None:
        try:
            _supabase_client = SupabaseClient()
        except Exception as e:
            print(f"无法初始化 Supabase 客户端: {e}")
            return None

    return _supabase_client
