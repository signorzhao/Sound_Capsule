"""
Phase C3.3: 三层 Embedding 缓存管理器

实现高性能的多级缓存策略：
- L1: 内存缓存（LRU，< 0.1ms）
- L2: SQLite 持久化缓存（~5ms）
- L3: 混合计算服务（100-500ms）
"""

import sqlite3
import json
import logging
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


class EmbeddingCacheManager:
    """
    三层 Embedding 缓存管理器

    缓存策略：
    - L1: 内存 LRU 缓存（最快，容量最小）
    - L2: SQLite 持久化缓存（快，容量大）
    - L3: 混合计算服务（慢，但可靠）

    特性：
    - 自动缓存写入
    - 统计信息追踪
    - TTL 支持
    - 缓存预热
    """

    def __init__(
        self,
        db_path: str = None,
        l1_capacity: int = 1000,
        l2_ttl_days: int = 30,
        enable_stats: bool = True
    ):
        """
        初始化缓存管理器

        Args:
            db_path: SQLite 数据库路径
            l1_capacity: L1 缓存容量（条目数）
            l2_ttl_days: L2 缓存过期时间（天）
            enable_stats: 是否启用统计
        """
        # 数据库路径
        if db_path is None:
            current_dir = Path(__file__).parent
            db_path = current_dir / "database" / "capsules.db"

        self.db_path = str(db_path)
        self.l1_capacity = l1_capacity
        self.l2_ttl_days = l2_ttl_days
        self.enable_stats = enable_stats

        # 统计信息
        self.stats = {
            'l1_hits': 0,
            'l1_misses': 0,
            'l2_hits': 0,
            'l2_misses': 0,
            'l3_calls': 0,
            'total_requests': 0,
            'cache_writes': 0
        }

        # 初始化 L2 数据库
        self._init_l2_database()

        # 初始化 L3 服务
        from hybrid_embedding_service import get_hybrid_service
        self.l3_service = get_hybrid_service()

        logger.info("✅ EmbeddingCacheManager 初始化")
        logger.info(f"   L1 容量: {l1_capacity} 条")
        logger.info(f"   L2 TTL: {l2_ttl_days} 天")
        logger.info(f"   数据库: {self.db_path}")

    def _init_l2_database(self):
        """初始化 L2 SQLite 数据库"""
        try:
            conn = sqlite3.connect(self.db_path)

            # 创建缓存表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    text TEXT NOT NULL,
                    prism_id TEXT NOT NULL,
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1,
                    last_access TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (text, prism_id)
                )
            """)

            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embedding_cache_prism
                ON embedding_cache(prism_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embedding_cache_access
                ON embedding_cache(last_access DESC)
            """)

            conn.commit()
            conn.close()

            logger.info("✅ L2 数据库初始化成功")

        except Exception as e:
            logger.error(f"❌ L2 数据库初始化失败: {e}")
            raise

    # L1 缓存：使用 lru_cache 装饰器
    def _l1_cache_key(self, text: str, prism_id: str) -> str:
        """生成 L1 缓存键"""
        return f"{prism_id}:{text}"

    # 手动管理 L1 缓存（使用字典 + LRU 淘汰）
    def __init_l1_cache(self):
        """初始化 L1 内存缓存"""
        self._l1_cache: Dict[str, Dict[str, float]] = {}
        self._l1_access_order: List[str] = []

    def _l1_get(self, key: str) -> Optional[Dict[str, float]]:
        """从 L1 获取"""
        if key in self._l1_cache:
            # 更新访问顺序
            if key in self._l1_access_order:
                self._l1_access_order.remove(key)
            self._l1_access_order.append(key)

            return self._l1_cache[key]
        return None

    def _l1_set(self, key: str, value: Dict[str, float]):
        """写入 L1"""
        # 检查容量
        if len(self._l1_cache) >= self.l1_capacity:
            # 淘汰最旧的
            oldest = self._l1_access_order.pop(0)
            del self._l1_cache[oldest]
            logger.debug(f"L1 淘汰: {oldest}")

        # 写入
        self._l1_cache[key] = value
        self._l1_access_order.append(key)

        if self.enable_stats:
            self.stats['cache_writes'] += 1

    def _l2_get(self, text: str, prism_id: str) -> Optional[Dict[str, float]]:
        """从 L2（SQLite）获取"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("""
                SELECT x, y FROM embedding_cache
                WHERE text = ? AND prism_id = ?
                LIMIT 1
            """, (text, prism_id))

            row = cursor.fetchone()

            if row:
                x, y = row
                # 更新访问统计
                conn.execute("""
                    UPDATE embedding_cache
                    SET access_count = access_count + 1,
                        last_access = CURRENT_TIMESTAMP
                    WHERE text = ? AND prism_id = ?
                """, (text, prism_id))
                conn.commit()

                conn.close()
                return {'x': x, 'y': y}

            conn.close()
            return None

        except Exception as e:
            logger.error(f"L2 读取失败: {e}")
            return None

    def _l2_set(self, text: str, prism_id: str, x: float, y: float):
        """写入 L2"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO embedding_cache
                (text, prism_id, x, y, cached_at, access_count, last_access)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP)
            """, (text, prism_id, x, y))

            conn.commit()
            conn.close()

            if self.enable_stats:
                self.stats['cache_writes'] += 1

        except Exception as e:
            logger.error(f"L2 写入失败: {e}")

    def get_coordinate(self, text: str, prism_id: str) -> Optional[Dict[str, float]]:
        """
        获取文本坐标（三层缓存）

        查询顺序：L1 -> L2 -> L3
        写回策略：L3 -> L2 -> L1

        Args:
            text: 输入文本
            prism_id: 棱镜 ID

        Returns:
            {'x': float, 'y': float} 或 None
        """
        if self.enable_stats:
            self.stats['total_requests'] += 1

        # 生成缓存键
        cache_key = self._l1_cache_key(text, prism_id)

        # L1: 内存缓存
        result = self._l1_get(cache_key)
        if result:
            if self.enable_stats:
                self.stats['l1_hits'] += 1
            logger.debug(f"✅ L1 命中: {text[:30]}...")
            return result

        if self.enable_stats:
            self.stats['l1_misses'] += 1

        # L2: SQLite 缓存
        result = self._l2_get(text, prism_id)
        if result:
            if self.enable_stats:
                self.stats['l2_hits'] += 1

            # 提升到 L1
            self._l1_set(cache_key, result)
            logger.debug(f"✅ L2 命中: {text[:30]}...")
            return result

        if self.enable_stats:
            self.stats['l2_misses'] += 1

        # L3: 混合计算服务
        if self.enable_stats:
            self.stats['l3_calls'] += 1

        logger.debug(f"🔄 L3 计算: {text[:30]}...")
        result = self.l3_service.get_coordinate(text, prism_id)

        if result:
            x, y = result['x'], result['y']

            # 写回 L2 和 L1
            self._l2_set(text, prism_id, x, y)
            self._l1_set(cache_key, result)

            return result

        return None

    def get_coordinates_batch(
        self,
        texts: List[str],
        prism_id: str
    ) -> List[Optional[Dict[str, float]]]:
        """
        批量获取坐标

        Args:
            texts: 文本列表
            prism_id: 棱镜 ID

        Returns:
            [Optional[Dict], ...]
        """
        results = []

        for text in texts:
            result = self.get_coordinate(text, prism_id)
            results.append(result)

        return results

    def warm_up(self, texts: List[str], prism_id: str):
        """
        缓存预热

        Args:
            texts: 要预热的文本列表
            prism_id: 棱镜 ID
        """
        logger.info(f"🔥 缓存预热: {len(texts)} 个文本")

        start_time = time.time()

        for text in texts:
            self.get_coordinate(text, prism_id)

        duration = time.time() - start_time

        logger.info(f"✅ 预热完成: {duration:.2f} 秒")
        logger.info(f"   平均: {duration/len(texts)*1000:.1f} ms/个")

    def clear_l1(self):
        """清空 L1 缓存"""
        self._l1_cache.clear()
        self._l1_access_order.clear()
        logger.info("✅ L1 缓存已清空")

    def clear_l2(self, prism_id: Optional[str] = None):
        """
        清空 L2 缓存

        Args:
            prism_id: 如果指定，只清空该棱镜的缓存
        """
        try:
            conn = sqlite3.connect(self.db_path)

            if prism_id:
                conn.execute(
                    "DELETE FROM embedding_cache WHERE prism_id = ?",
                    (prism_id,)
                )
                logger.info(f"✅ L2 缓存已清空（棱镜: {prism_id}）")
            else:
                conn.execute("DELETE FROM embedding_cache")
                logger.info("✅ L2 缓存已全部清空")

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"❌ 清空 L2 失败: {e}")

    def cleanup_l2(self, max_age_days: int = None):
        """
        清理 L2 过期缓存

        Args:
            max_age_days: 最大保留天数（None 使用初始化时的 TTL）
        """
        if max_age_days is None:
            max_age_days = self.l2_ttl_days

        try:
            conn = sqlite3.connect(self.db_path)

            cursor = conn.execute("""
                DELETE FROM embedding_cache
                WHERE cached_at < datetime('now', '-' || ? || ' day')
            """, (max_age_days,))

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"✅ L2 清理完成: 删除 {deleted} 条过期记录")

        except Exception as e:
            logger.error(f"❌ L2 清理失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计字典
        """
        total = self.stats['total_requests']

        if total > 0:
            l1_hit_rate = self.stats['l1_hits'] / total
            l2_hit_rate = self.stats['l2_hits'] / total
            l3_call_rate = self.stats['l3_calls'] / total
            overall_hit_rate = (self.stats['l1_hits'] + self.stats['l2_hits']) / total
        else:
            l1_hit_rate = 0
            l2_hit_rate = 0
            l3_call_rate = 0
            overall_hit_rate = 0

        # L1 缓存大小
        l1_size = len(self._l1_cache)

        # L2 缓存大小
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM embedding_cache")
            l2_size = cursor.fetchone()[0]
            conn.close()
        except:
            l2_size = 0

        return {
            'total_requests': total,
            'l1_hits': self.stats['l1_hits'],
            'l1_misses': self.stats['l1_misses'],
            'l1_size': l1_size,
            'l1_capacity': self.l1_capacity,
            'l1_hit_rate': f"{l1_hit_rate:.1%}",
            'l2_hits': self.stats['l2_hits'],
            'l2_misses': self.stats['l2_misses'],
            'l2_size': l2_size,
            'l2_hit_rate': f"{l2_hit_rate:.1%}",
            'l3_calls': self.stats['l3_calls'],
            'l3_call_rate': f"{l3_call_rate:.1%}",
            'overall_hit_rate': f"{overall_hit_rate:.1%}",
            'cache_writes': self.stats['cache_writes']
        }

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()

        print("\n" + "=" * 70)
        print("📊 三层缓存统计")
        print("=" * 70)

        print(f"\n总请求数: {stats['total_requests']}")

        print(f"\nL1 (内存缓存):")
        print(f"  命中: {stats['l1_hits']}")
        print(f"  未命中: {stats['l1_misses']}")
        print(f"  容量: {stats['l1_size']}/{stats['l1_capacity']}")
        print(f"  命中率: {stats['l1_hit_rate']}")

        print(f"\nL2 (SQLite缓存):")
        print(f"  命中: {stats['l2_hits']}")
        print(f"  未命中: {stats['l2_misses']}")
        print(f"  大小: {stats['l2_size']} 条")
        print(f"  命中率: {stats['l2_hit_rate']}")

        print(f"\nL3 (计算服务):")
        print(f"  调用: {stats['l3_calls']}")
        print(f"  调用率: {stats['l3_call_rate']}")

        print(f"\n总体:")
        print(f"  总体命中率: {stats['overall_hit_rate']}")
        print(f"  缓存写入: {stats['cache_writes']}")

        print("=" * 70)


# ============================================
# 初始化 L1 缓存
# ============================================

EmbeddingCacheManager.__init_l1_cache = EmbeddingCacheManager._init_l1_cache


# ============================================
# 全局实例（单例模式）
# ============================================

_cache_manager: Optional[EmbeddingCacheManager] = None


def get_cache_manager() -> EmbeddingCacheManager:
    """
    获取缓存管理器实例（单例）

    Returns:
        EmbeddingCacheManager 实例
    """
    global _cache_manager

    if _cache_manager is None:
        _cache_manager = EmbeddingCacheManager()

    return _cache_manager


# ============================================
# 测试代码
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 三层缓存测试")
    print("=" * 70)

    # 测试 1: 基本功能
    print("\n1️⃣ 测试基本缓存功能...")
    cache_mgr = EmbeddingCacheManager()

    # 第一次请求（L3 计算）
    print("   第一次请求（应该走 L3）...")
    result1 = cache_mgr.get_coordinate("测试文本1", "texture")
    if result1:
        print(f"   ✅ 成功: ({result1['x']:.2f}, {result1['y']:.2f})")

    # 第二次请求（应该命中 L1）
    print("   第二次请求（应该命中 L1）...")
    result2 = cache_mgr.get_coordinate("测试文本1", "texture")
    if result2:
        print(f"   ✅ 成功: ({result2['x']:.2f}, {result2['y']:.2f})")

    # 验证一致性
    if result1 and result2:
        assert abs(result1['x'] - result2['x']) < 1e-5
        assert abs(result1['y'] - result2['y']) < 1e-5
        print(f"   ✅ 结果一致")

    # 测试 2: 批量请求
    print("\n2️⃣ 测试批量请求...")
    texts = ["文本1", "文本2", "文本3", "文本1"]  # 文本1 重复
    results = cache_mgr.get_coordinates_batch(texts, "texture")

    for i, (text, result) in enumerate(zip(texts, results)):
        if result:
            print(f"   {i+1}. {text}: ({result['x']:.2f}, {result['y']:.2f})")
        else:
            print(f"   {i+1}. {text}: 失败")

    # 测试 3: 缓存预热
    print("\n3️⃣ 测试缓存预热...")
    cache_mgr.clear_l1()
    warmup_texts = ["预热1", "预热2", "预热3"]
    cache_mgr.warm_up(warmup_texts, "texture")

    # 验证预热后的缓存
    stats = cache_mgr.get_stats()
    print(f"   L1 缓存大小: {stats['l1_size']}")
    print(f"   L2 缓存大小: {stats['l2_size']}")

    # 测试 4: 打印统计
    cache_mgr.print_stats()

    print("\n✅ 测试完成")
    print("=" * 70)
