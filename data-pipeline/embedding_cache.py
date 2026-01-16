"""
Phase C2: Embedding 缓存管理器

支持 Redis 和内存缓存两种模式
"""

import os
import json
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ============================================
# 内存缓存实现（fallback）
# ============================================

class MemoryCache:
    """简单的内存缓存实现"""

    def __init__(self):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl_cache: dict[str, datetime] = {}

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            value, expiry = self._cache[key]

            # 检查是否过期
            if expiry and datetime.now() > expiry:
                del self._cache[key]
                if key in self._ttl_cache:
                    del self._ttl_cache[key]
                return None

            return value

        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        expiry = None
        if ttl:
            expiry = datetime.now() + timedelta(seconds=ttl)

        self._cache[key] = (value, expiry)

    def delete(self, key: str):
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]
        if key in self._ttl_cache:
            del self._ttl_cache[key]

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._ttl_cache.clear()

    def stats(self) -> dict:
        """缓存统计"""
        return {
            "type": "memory",
            "keys": len(self._cache),
            "ttl_keys": len(self._ttl_cache)
        }

# ============================================
# Redis 缓存实现
# ============================================

class RedisCache:
    """Redis 缓存实现"""

    def __init__(self, url: str):
        try:
            import redis
            self.client = redis.from_url(url, decode_responses=False)
            # 测试连接
            self.client.ping()
            logger.info("✅ Redis 连接成功")
        except Exception as e:
            logger.error(f"❌ Redis 连接失败: {e}")
            raise

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            data = self.client.get(key)
            if data:
                # 尝试反序列化
                try:
                    return json.loads(data)
                except:
                    return data
            return None
        except Exception as e:
            logger.warning(f"Redis GET 失败: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        try:
            # 序列化
            if isinstance(value, (list, dict)):
                data = json.dumps(value)
            else:
                data = value

            # 存储并设置 TTL
            if ttl:
                self.client.setex(key, ttl, data)
            else:
                self.client.set(key, data)

        except Exception as e:
            logger.warning(f"Redis SET 失败: {e}")

    def delete(self, key: str):
        """删除缓存"""
        try:
            self.client.delete(key)
        except Exception as e:
            logger.warning(f"Redis DELETE 失败: {e}")

    def clear(self):
        """清空缓存"""
        try:
            # 注意：这会清空所有缓存，慎用
            self.client.flushdb()
        except Exception as e:
            logger.warning(f"Redis CLEAR 失败: {e}")

    def stats(self) -> dict:
        """缓存统计"""
        try:
            info = self.client.info('stats')
            return {
                "type": "redis",
                "keys": info.get('keyspace_hits', 0),
                "hits": info.get('keyspace_hits', 0),
                "misses": info.get('keyspace_misses', 0)
            }
        except Exception as e:
            logger.warning(f"Redis STATS 失败: {e}")
            return {"type": "redis", "error": str(e)}

# ============================================
# 缓存管理器（统一接口）
# ============================================

class CacheManager:
    """缓存管理器"""

    def __init__(self, backend):
        self.backend = backend

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        return self.backend.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        self.backend.set(key, value, ttl)

    def delete(self, key: str):
        """删除缓存"""
        self.backend.delete(key)

    def clear(self):
        """清空缓存"""
        self.backend.clear()

    def stats(self) -> dict:
        """获取统计信息"""
        return self.backend.stats()

# ============================================
# 全局实例
# ============================================

_cache_manager: Optional[CacheManager] = None

def get_cache_manager() -> CacheManager:
    """获取缓存管理器实例（单例）"""
    global _cache_manager

    if _cache_manager is not None:
        return _cache_manager

    # 尝试连接 Redis
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    try:
        logger.info(f"尝试连接 Redis: {redis_url}")
        redis_backend = RedisCache(redis_url)
        _cache_manager = CacheManager(redis_backend)
        logger.info("✅ 使用 Redis 缓存")
        return _cache_manager

    except Exception as e:
        logger.warning(f"⚠️  Redis 不可用，使用内存缓存: {e}")
        memory_backend = MemoryCache()
        _cache_manager = CacheManager(memory_backend)
        logger.info("✅ 使用内存缓存")
        return _cache_manager

# ============================================
# 测试代码
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 缓存管理器测试")
    print("=" * 60)

    # 测试内存缓存
    print("\n1️⃣ 测试内存缓存...")
    cache = get_cache_manager()

    cache.set("test_key", {"value": 123}, ttl=60)
    print(f"   设置缓存: test_key")

    value = cache.get("test_key")
    print(f"   读取缓存: {value}")

    stats = cache.stats()
    print(f"   缓存统计: {stats}")

    # 测试过期
    print("\n2️⃣ 测试批量操作...")
    for i in range(5):
        cache.set(f"key_{i}", f"value_{i}", ttl=3600)

    for i in range(5):
        value = cache.get(f"key_{i}")
        print(f"   key_{i}: {value}")

    stats = cache.stats()
    print(f"\n   最终统计: {stats}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
