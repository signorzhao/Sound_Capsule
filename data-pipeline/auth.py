"""
用户认证模块

提供用户注册、登录、Token 管理等认证功能

认证模式：
- 优先使用 Supabase Auth（云端统一认证，跨设备一致）
- 如果 Supabase 不可用，降级到本地 SQLite 认证
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import sqlite3
from pathlib import Path

# JWT and bcrypt imports with fallback
try:
    import jwt
except ImportError:
    # PyJWT package uses this import in newer versions
    import jwt as jwt_module
    jwt = jwt_module

try:
    import bcrypt
except ImportError:
    bcrypt = None


# JWT 配置（用于本地模式的降级）
SECRET_KEY = "synesth-secret-key-change-in-production"  # TODO: 从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Supabase 客户端（延迟导入避免循环依赖）
_supabase_client = None

def _get_supabase():
    """获取 Supabase 客户端（延迟初始化）"""
    global _supabase_client
    if _supabase_client is None:
        try:
            from supabase_client import get_supabase_client
            _supabase_client = get_supabase_client()
        except Exception as e:
            print(f"⚠️ [Auth] Supabase 不可用: {e}")
            _supabase_client = False  # 标记为不可用
    return _supabase_client if _supabase_client else None


class AuthManager:
    """认证管理器"""

    def __init__(self, db_path: str):
        """
        初始化认证管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path

    def _get_connection(self):
        """获取数据库连接（统一使用 WAL 模式，与 capsule_db 保持一致）"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,  # 增加超时时间，避免并发锁等待
            check_same_thread=False  # 允许多线程访问
        )
        conn.row_factory = sqlite3.Row
        # 启用 WAL 模式，降低读写并发锁冲突
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def hash_password(self, password: str) -> str:
        """
        哈希密码

        Args:
            password: 明文密码

        Returns:
            哈希后的密码
        """
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        验证密码

        Args:
            password: 明文密码
            password_hash: 哈希密码

        Returns:
            是否匹配
        """
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def create_access_token(self, user_id: int, username: str) -> str:
        """
        创建 Access Token

        Args:
            user_id: 用户 ID
            username: 用户名

        Returns:
            JWT Token 字符串
        """
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {
            "user_id": user_id,
            "username": username,
            "exp": expire,
            "iat": datetime.utcnow()
        }

        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def create_refresh_token(self) -> str:
        """
        创建 Refresh Token

        Returns:
            UUID 格式的 Token 字符串
        """
        return str(uuid.uuid4())

    def register_user(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """
        注册新用户
        
        优先使用 Supabase Auth（云端统一认证），如果不可用则降级到本地认证

        Args:
            username: 用户名
            email: 邮箱
            password: 密码

        Returns:
            包含成功状态和用户信息的字典

        Raises:
            ValueError: 如果用户名或邮箱已存在
        """
        # 验证用户名格式
        if not self._validate_username(username):
            raise ValueError("用户名格式不正确（3-30字符，仅字母数字下划线）")

        # 验证邮箱格式
        if not self._validate_email(email):
            raise ValueError("邮箱格式不正确")

        # 验证密码强度
        if not self._validate_password(password):
            raise ValueError("密码强度不足（最少8字符，必须包含字母和数字）")

        # ========================================
        # 尝试使用 Supabase Auth（优先）
        # ========================================
        supabase = _get_supabase()
        if supabase:
            try:
                result = supabase.auth_sign_up(email, password, username)
                
                if result.get('success'):
                    supabase_user_id = result['user']['id']
                    
                    # 在本地数据库中缓存用户信息
                    self._cache_supabase_user(
                        supabase_user_id=supabase_user_id,
                        username=username,
                        email=email
                    )
                    
                    return {
                        "success": True,
                        "user": {
                            "id": supabase_user_id,
                            "username": username,
                            "email": email,
                            "display_name": username,
                            "supabase_user_id": supabase_user_id
                        },
                        "tokens": {
                            "access_token": result['session']['access_token'] if result.get('session') else None,
                            "refresh_token": result['session']['refresh_token'] if result.get('session') else None,
                            "expires_in": result['session']['expires_in'] if result.get('session') else 3600
                        }
                    }
                else:
                    err = result.get('error', '注册失败')
                    # 自建 Supabase 未配 SMTP：signup 会创建用户但返回 500（发信失败），用户处于未确认状态
                    # 用 Admin API 将该邮箱用户设为已确认，再尝试登录
                    if 'confirmation email' in err.lower():
                        if supabase.auth_admin_confirm_user_by_email(email):
                            signin = supabase.auth_sign_in(email, password)
                            if signin.get('success') and signin.get('user'):
                                self._cache_supabase_user(
                                    supabase_user_id=signin['user']['id'],
                                    username=username,
                                    email=email
                                )
                                return {
                                    "success": True,
                                    "user": {
                                        "id": signin['user']['id'],
                                        "username": username,
                                        "email": email,
                                        "display_name": username,
                                        "supabase_user_id": signin['user']['id']
                                    },
                                    "tokens": {
                                        "access_token": signin.get('session', {}).get('access_token'),
                                        "refresh_token": signin.get('session', {}).get('refresh_token'),
                                        "expires_in": signin.get('session', {}).get('expires_in', 3600)
                                    }
                                }
                        else:
                            err = "注册暂不可用。请让管理员在 Supabase Dashboard → Authentication → Users → Add user 添加账号后，用该邮箱和密码直接登录。"
                    raise ValueError(err)
            except ValueError:
                raise
            except Exception as e:
                print(f"⚠️ [Auth] Supabase 注册失败，降级到本地模式: {e}")
        
        # ========================================
        # 降级到本地 SQLite 认证
        # ========================================
        print("📝 [Auth] 使用本地认证模式")
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                raise ValueError("用户名已存在")

            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                raise ValueError("邮箱已被注册")

            # 哈希密码
            password_hash = self.hash_password(password)

            # 生成本地 UUID（本地模式无法跨设备）
            supabase_user_id = str(uuid.uuid4())

            # 插入用户
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, display_name, supabase_user_id)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, password_hash, username, supabase_user_id))

            user_id = cursor.lastrowid

            # 创建 tokens
            access_token = self.create_access_token(user_id, username)
            refresh_token = self.create_refresh_token()

            # 存储 refresh token
            expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            cursor.execute("""
                INSERT INTO refresh_tokens (user_id, token, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, refresh_token, expires_at.strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()

            # 获取用户信息
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user_row = cursor.fetchone()

            return {
                "success": True,
                "user": dict(user_row),
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
                }
            }

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _cache_supabase_user(self, supabase_user_id: str, username: str, email: str):
        """
        在本地数据库中缓存 Supabase 用户信息
        
        这样即使离线也能识别用户身份
        
        修复：使用 WAL checkpoint 确保数据立即可见，避免注册后首次上传失败
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM users WHERE supabase_user_id = ?", 
                (supabase_user_id,)
            )
            
            existing = cursor.fetchone()
            
            if not existing:
                # 使用占位符密码哈希（Supabase 用户不使用本地密码）
                # 这是为了兼容旧数据库 schema（password_hash 可能是 NOT NULL）
                placeholder_hash = "SUPABASE_AUTH_USER"
                
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, display_name, supabase_user_id, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (username, email, placeholder_hash, username, supabase_user_id))
                conn.commit()
                print(f"✓ [Auth] 已缓存用户: {username} ({supabase_user_id[:8]}...)")
            else:
                # 用户已存在，更新信息（以防之前缓存不完整）
                cursor.execute("""
                    UPDATE users SET username = ?, email = ?, display_name = ?, is_active = 1
                    WHERE supabase_user_id = ?
                """, (username, email, username, supabase_user_id))
                conn.commit()
                print(f"✓ [Auth] 已更新用户缓存: {username} ({supabase_user_id[:8]}...)")
            
            # 🔑 关键修复：执行 WAL checkpoint，确保数据立即对其他连接可见
            # 这解决了注册/登录后首次上传失败的问题
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            print(f"✓ [Auth] WAL checkpoint 完成，用户数据已同步")
            
        except Exception as e:
            print(f"⚠️ [Auth] 缓存用户失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

    def login_user(self, login: str, password: str) -> Dict[str, Any]:
        """
        用户登录
        
        优先使用 Supabase Auth（云端统一认证），如果不可用则降级到本地认证

        Args:
            login: 用户名或邮箱
            password: 密码

        Returns:
            包含成功状态和用户信息的字典

        Raises:
            ValueError: 如果登录失败
        """
        # ========================================
        # 尝试使用 Supabase Auth（优先）
        # ========================================
        supabase = _get_supabase()
        
        # 判断 login 是邮箱还是用户名
        is_email = '@' in login
        
        if supabase and is_email:
            # Supabase Auth 只支持邮箱登录
            try:
                result = supabase.auth_sign_in(login, password)
                
                if result.get('success'):
                    user_info = result['user']
                    session = result['session']
                    
                    # 在本地数据库中缓存用户信息
                    self._cache_supabase_user(
                        supabase_user_id=user_info['id'],
                        username=user_info.get('username', login.split('@')[0]),
                        email=login
                    )
                    
                    print(f"✓ [Auth] Supabase 登录成功: {user_info.get('username')}")
                    
                    return {
                        "success": True,
                        "user": {
                            "id": user_info['id'],
                            "username": user_info.get('username', login.split('@')[0]),
                            "email": user_info.get('email', login),
                            "display_name": user_info.get('display_name', user_info.get('username')),
                            "supabase_user_id": user_info['id']
                        },
                        "tokens": {
                            "access_token": session['access_token'],
                            "refresh_token": session['refresh_token'],
                            "expires_in": session.get('expires_in', 3600)
                        }
                    }
                else:
                    raise ValueError(result.get('error', '登录失败'))
            except ValueError:
                raise
            except Exception as e:
                print(f"⚠️ [Auth] Supabase 登录失败，降级到本地模式: {e}")
        
        # ========================================
        # 降级到本地 SQLite 认证
        # ========================================
        if not is_email and supabase:
            print("📝 [Auth] 用户名登录，使用本地认证模式")
        elif not supabase:
            print("📝 [Auth] Supabase 不可用，使用本地认证模式")
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 查找用户（支持用户名或邮箱登录）
            cursor.execute("""
                SELECT * FROM users
                WHERE (username = ? OR email = ?)
                AND is_active = 1
            """, (login, login))

            user = cursor.fetchone()

            if not user:
                raise ValueError("用户名或密码错误")

            # 验证密码（本地模式需要 password_hash）
            if not user['password_hash']:
                raise ValueError("该账号使用云端认证，请使用邮箱登录")
            
            if not self.verify_password(password, user['password_hash']):
                raise ValueError("用户名或密码错误")

            # 更新最后登录时间
            cursor.execute("""
                UPDATE users
                SET last_login = ?
                WHERE id = ?
            """, (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), user['id']))

            # 创建 tokens
            access_token = self.create_access_token(user['id'], user['username'])
            refresh_token = self.create_refresh_token()

            # 存储 refresh token
            expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            cursor.execute("""
                INSERT INTO refresh_tokens (user_id, token, expires_at)
                VALUES (?, ?, ?)
            """, (user['id'], refresh_token, expires_at.strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()

            return {
                "success": True,
                "user": dict(user),
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
                }
            }

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        刷新 Access Token
        
        优先使用 Supabase 刷新，如果失败则尝试本地刷新

        Args:
            refresh_token: Refresh Token 字符串

        Returns:
            包含新 Access Token 的字典

        Raises:
            ValueError: 如果 Refresh Token 无效
        """
        # ========================================
        # 尝试使用 Supabase 刷新（优先）
        # ========================================
        supabase = _get_supabase()
        if supabase:
            try:
                result = supabase.auth_refresh_token(refresh_token)
                if result.get('success'):
                    return {
                        "success": True,
                        "access_token": result['access_token'],
                        "refresh_token": result.get('refresh_token', refresh_token),
                        "expires_in": result.get('expires_in', 3600)
                    }
            except Exception as e:
                print(f"⚠️ [Auth] Supabase 刷新失败，尝试本地刷新: {e}")
        
        # ========================================
        # 降级到本地刷新
        # ========================================
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 查找 refresh token
            cursor.execute("""
                SELECT rt.*, u.id, u.username
                FROM refresh_tokens rt
                JOIN users u ON rt.user_id = u.id
                WHERE rt.token = ?
                AND rt.expires_at > datetime('now')
                AND u.is_active = 1
            """, (refresh_token,))

            token_data = cursor.fetchone()

            if not token_data:
                raise ValueError("Refresh token 无效或已过期")

            # 创建新的 access token
            access_token = self.create_access_token(
                token_data['id'],
                token_data['username']
            )

            return {
                "success": True,
                "access_token": access_token,
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }

        finally:
            conn.close()

    def logout_user(self, refresh_token: str) -> bool:
        """
        用户注销

        Args:
            refresh_token: Refresh Token 字符串

        Returns:
            是否成功
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 删除 refresh token
            cursor.execute("""
                DELETE FROM refresh_tokens
                WHERE token = ?
            """, (refresh_token,))

            conn.commit()
            return True

        finally:
            conn.close()

    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        验证 Access Token
        
        优先使用 Supabase 验证，如果失败则尝试本地验证

        Args:
            token: JWT Token 字符串

        Returns:
            Token Payload 或 None（包含 user_id 或 supabase_user_id）
        """
        # ========================================
        # 尝试使用 Supabase 验证（优先）
        # ========================================
        supabase = _get_supabase()
        if supabase:
            try:
                user = supabase.auth_get_user(token)
                if user:
                    return {
                        'user_id': user['id'],
                        'supabase_user_id': user['id'],
                        'username': user.get('username'),
                        'email': user.get('email')
                    }
            except Exception as e:
                # Supabase 验证失败，尝试本地验证
                pass
        
        # ========================================
        # 降级到本地 JWT 验证
        # ========================================
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取用户信息

        Args:
            user_id: 用户 ID

        Returns:
            用户信息字典或 None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, email, display_name, avatar_url, bio,
                       created_at, last_login, preferences, supabase_user_id
                FROM users
                WHERE id = ? AND is_active = 1
            """, (user_id,))

            user = cursor.fetchone()
            return dict(user) if user else None

        finally:
            conn.close()

    def get_user_by_supabase_id(self, supabase_user_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 Supabase User ID 获取用户信息
        
        用于 Supabase Auth 认证后查找本地缓存的用户

        Args:
            supabase_user_id: Supabase User UUID

        Returns:
            用户信息字典或 None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, email, display_name, avatar_url, bio,
                       created_at, last_login, preferences, supabase_user_id
                FROM users
                WHERE supabase_user_id = ? AND is_active = 1
            """, (supabase_user_id,))

            user = cursor.fetchone()
            return dict(user) if user else None

        finally:
            conn.close()

    def update_user_profile(self, user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新用户资料

        Args:
            user_id: 用户 ID
            updates: 更新的字段字典

        Returns:
            更新后的用户信息
        """
        allowed_fields = ['display_name', 'bio', 'avatar_url', 'preferences']

        # 过滤允许的字段
        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not valid_updates:
            raise ValueError("没有有效的更新字段")

        # 构建更新 SQL
        set_clause = ", ".join([f"{k} = ?" for k in valid_updates.keys()])
        values = list(valid_updates.values())

        # 如果 preferences 是字典，转换为 JSON 字符串
        if 'preferences' in valid_updates and isinstance(valid_updates['preferences'], dict):
            import json
            values[values.index(valid_updates['preferences'])] = json.dumps(valid_updates['preferences'])

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE users
                SET {set_clause}
                WHERE id = ?
            """, values + [user_id])

            conn.commit()

            # 返回更新后的用户信息
            return self.get_user_by_id(user_id)

        finally:
            conn.close()

    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """
        修改密码

        Args:
            user_id: 用户 ID
            old_password: 旧密码
            new_password: 新密码

        Returns:
            是否成功

        Raises:
            ValueError: 如果旧密码错误或新密码强度不足
        """
        # 验证新密码强度
        if not self._validate_password(new_password):
            raise ValueError("新密码强度不足")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 获取当前密码
            cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()

            if not result:
                raise ValueError("用户不存在")

            # 验证旧密码
            if not self.verify_password(old_password, result['password_hash']):
                raise ValueError("旧密码错误")

            # 哈希新密码
            new_hash = self.hash_password(new_password)

            # 更新密码
            cursor.execute("""
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
            """, (new_hash, user_id))

            conn.commit()
            return True

        finally:
            conn.close()

    def _validate_username(self, username: str) -> bool:
        """验证用户名格式"""
        import re
        return bool(re.match(r'^[a-zA-Z0-9_]{3,30}$', username))

    def _validate_email(self, email: str) -> bool:
        """验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _validate_password(self, password: str) -> bool:
        """验证密码强度"""
        if len(password) < 8:
            return False
        has_letter = any(c.isalpha() for c in password)
        has_digit = any(c.isdigit() for c in password)
        return has_letter and has_digit


# 便捷函数
def get_auth_manager(db_path: str = None) -> AuthManager:
    """
    获取认证管理器实例

    Args:
        db_path: 数据库路径（可选，默认从 PathManager 获取）

    Returns:
        AuthManager 实例
    """
    if db_path is None:
        # 🔴 架构规范：优先从 PathManager 获取数据库路径
        # 这确保所有模块使用同一个数据库文件
        try:
            from common import PathManager
            pm = PathManager.get_instance()
            db_path = pm.db_path
        except (RuntimeError, ImportError):
            # 兜底：如果 PathManager 未初始化（如独立脚本运行），使用项目目录
            current_dir = Path(__file__).parent
            db_path = current_dir / "database" / "capsules.db"
            print(f"⚠️ [AuthManager] PathManager 未初始化，使用兜底路径: {db_path}")

    return AuthManager(str(db_path))
