"""
用户认证模块

提供用户注册、登录、Token 管理等认证功能
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


# JWT 配置
SECRET_KEY = "synesth-secret-key-change-in-production"  # TODO: 从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30


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
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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

        # 检查用户名是否已存在
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

            # 生成 Supabase UUID
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

    def login_user(self, login: str, password: str) -> Dict[str, Any]:
        """
        用户登录

        Args:
            login: 用户名或邮箱
            password: 密码

        Returns:
            包含成功状态和用户信息的字典

        Raises:
            ValueError: 如果登录失败
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 查找用户（支持用户名或邮箱登录）
            cursor.execute("""
                SELECT * FROM users
                WHERE username = ? OR email = ?
                AND is_active = 1
            """, (login, login))

            user = cursor.fetchone()

            if not user:
                raise ValueError("用户名或密码错误")

            # 验证密码
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

        Args:
            refresh_token: Refresh Token 字符串

        Returns:
            包含新 Access Token 的字典

        Raises:
            ValueError: 如果 Refresh Token 无效
        """
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

        Args:
            token: JWT Token 字符串

        Returns:
            Token Payload 或 None
        """
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
