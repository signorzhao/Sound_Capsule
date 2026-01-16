"""
Phase C3.2: 混合 Embedding 服务

实现云端优先 + 本地降级的智能策略
"""

import logging
from typing import Optional, Dict, List
import numpy as np

from embedding_client import EmbeddingClient
from coordinate_calculator import get_coordinate_calculator, load_anchors_from_prism
from prism_version_manager import PrismVersionManager

logger = logging.getLogger(__name__)


class HybridEmbeddingService:
    """
    混合 Embedding 服务

    策略：
    1. 云端优先（快速，~100ms）
    2. 本地降级（可靠，~500ms）
    3. 懒加载本地模型（节省内存）

    特性：
    - 智能超时控制（3秒）
    - 自动降级
    - 统计信息
    """

    def __init__(
        self,
        cloud_timeout: int = 3,
        prefer_cloud: bool = True,
        lazy_load_local: bool = True
    ):
        """
        初始化混合服务

        Args:
            cloud_timeout: 云端请求超时时间（秒）
            prefer_cloud: 是否优先使用云端
            lazy_load_local: 是否懒加载本地模型
        """
        self.cloud_client = EmbeddingClient(timeout=cloud_timeout)
        self.prefer_cloud = prefer_cloud
        self.lazy_load_local = lazy_load_local

        # 本地模型（懒加载）
        self._local_model = None
        self._local_model_loaded = False

        # 统计信息
        self.stats = {
            'cloud_requests': 0,
            'cloud_success': 0,
            'cloud_timeout': 0,
            'local_fallback': 0,
            'local_success': 0,
            'total_failures': 0
        }

        logger.info("✅ HybridEmbeddingService 初始化")
        logger.info(f"   云端超时: {cloud_timeout}s")
        logger.info(f"   优先云端: {prefer_cloud}")
        logger.info(f"   懒加载: {lazy_load_local}")

    @property
    def local_model_available(self) -> bool:
        """本地模型是否可用"""
        return self._local_model is not None

    def load_local_model(self, force: bool = False):
        """
        加载本地模型（懒加载）

        Args:
            force: 是否强制重新加载
        """
        if self._local_model_loaded and not force:
            logger.debug("本地模型已加载")
            return

        logger.info("🔄 加载本地模型...")

        try:
            from sentence_transformers import SentenceTransformer

            model_name = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
            self._local_model = SentenceTransformer(model_name)
            self._local_model_loaded = True

            logger.info("✅ 本地模型加载成功")
            logger.info(f"   模型: {model_name}")
            logger.info(f"   维度: {self._local_model.get_sentence_embedding_dimension()}")

        except Exception as e:
            logger.error(f"❌ 本地模型加载失败: {e}")
            self._local_model = None
            self._local_model_loaded = False

    def get_coordinate(
        self,
        text: str,
        prism_id: str,
        use_cloud: Optional[bool] = None
    ) -> Optional[Dict[str, float]]:
        """
        获取文本坐标（云端优先 + 本地降级）

        Args:
            text: 输入文本
            prism_id: 棱镜 ID
            use_cloud: 是否使用云端（None 表示自动判断）

        Returns:
            {'x': float, 'y': float} 或 None
        """
        # 决策：是否尝试云端
        try_cloud = use_cloud if use_cloud is not None else self.prefer_cloud

        # 策略 1: 云端优先
        if try_cloud:
            self.stats['cloud_requests'] += 1

            logger.debug(f"🌐 尝试云端计算: {text[:30]}...")
            result = self._try_cloud(text, prism_id)

            if result:
                self.stats['cloud_success'] += 1
                return result
            else:
                # 云端失败，记录原因
                health = self.cloud_client.health_check()
                if health['error'] == 'Timeout':
                    self.stats['cloud_timeout'] += 1
                    logger.info("⏱️  云端超时，降级到本地")
                else:
                    logger.info("⚠️  云端失败，降级到本地")

        # 策略 2: 本地降级
        self.stats['local_fallback'] += 1

        logger.debug(f"💻 使用本地计算: {text[:30]}...")
        result = self._try_local(text, prism_id)

        if result:
            self.stats['local_success'] += 1
            return result
        else:
            self.stats['total_failures'] += 1
            logger.error("❌ 本地计算也失败了")
            return None

    def _try_cloud(
        self,
        text: str,
        prism_id: str
    ) -> Optional[Dict[str, float]]:
        """
        尝试使用云端 API

        Args:
            text: 输入文本
            prism_id: 棱镜 ID

        Returns:
            {'x': float, 'y': float} 或 None
        """
        return self.cloud_client.get_coordinate(text, prism_id)

    def _try_local(
        self,
        text: str,
        prism_id: str
    ) -> Optional[Dict[str, float]]:
        """
        尝试使用本地模型

        Args:
            text: 输入文本
            prism_id: 棱镜 ID

        Returns:
            {'x': float, 'y': float} 或 None
        """
        # 懒加载本地模型
        if not self.local_model_available:
            if self.lazy_load_local:
                self.load_local_model()
            else:
                logger.error("❌ 本地模型未启用")
                return None

        if not self.local_model_available:
            return None

        try:
            # 1. 计算 embedding
            word_embedding = self._local_model.encode(text)

            # 2. 获取 prism 配置
            prism_manager = PrismVersionManager()
            prism_config_dict = prism_manager.get_prism(prism_id)

            if not prism_config_dict:
                logger.error(f"❌ 棱镜 '{prism_id}' 不存在")
                return None

            # 3. 加载锚点数据
            import json
            prism_config = {
                'anchors': json.loads(prism_config_dict['anchors'])
            }

            anchor_embeddings, anchor_coords = load_anchors_from_prism(prism_config)

            # 4. 计算坐标
            calculator = get_coordinate_calculator()
            x, y = calculator.calculate_single_word(
                word_embedding,
                anchor_embeddings,
                anchor_coords,
                stretch=True
            )

            return {'x': x, 'y': y}

        except Exception as e:
            logger.error(f"❌ 本地计算失败: {e}")
            return None

    def get_coordinates_batch(
        self,
        texts: List[str],
        prism_id: str,
        use_cloud: Optional[bool] = None
    ) -> List[Optional[Dict[str, float]]]:
        """
        批量获取坐标

        Args:
            texts: 文本列表
            prism_id: 棱镜 ID
            use_cloud: 是否使用云端

        Returns:
            [Optional[Dict], ...]
        """
        results = []

        for text in texts:
            result = self.get_coordinate(text, prism_id, use_cloud)
            results.append(result)

        return results

    def get_stats(self) -> Dict[str, any]:
        """
        获取统计信息

        Returns:
            统计字典
        """
        total = self.stats['cloud_requests']

        if total > 0:
            cloud_success_rate = self.stats['cloud_success'] / total
            local_fallback_rate = self.stats['local_fallback'] / total
        else:
            cloud_success_rate = 0
            local_fallback_rate = 0

        return {
            'cloud_requests': total,
            'cloud_success': self.stats['cloud_success'],
            'cloud_timeout': self.stats['cloud_timeout'],
            'local_fallback': self.stats['local_fallback'],
            'local_success': self.stats['local_success'],
            'total_failures': self.stats['total_failures'],
            'cloud_success_rate': f"{cloud_success_rate:.1%}",
            'local_fallback_rate': f"{local_fallback_rate:.1%}",
            'local_model_loaded': self._local_model_loaded
        }

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()

        print("\n" + "=" * 60)
        print("📊 混合服务统计")
        print("=" * 60)
        print(f"云端请求总数: {stats['cloud_requests']}")
        print(f"云端成功: {stats['cloud_success']}")
        print(f"云端超时: {stats['cloud_timeout']}")
        print(f"本地降级: {stats['local_fallback']}")
        print(f"本地成功: {stats['local_success']}")
        print(f"完全失败: {stats['total_failures']}")
        print(f"\n云端成功率: {stats['cloud_success_rate']}")
        print(f"本地降级率: {stats['local_fallback_rate']}")
        print(f"本地模型: {'已加载' if stats['local_model_loaded'] else '未加载'}")
        print("=" * 60)


# ============================================
# 全局实例（单例模式）
# ============================================

_hybrid_service: Optional[HybridEmbeddingService] = None


def get_hybrid_service() -> HybridEmbeddingService:
    """
    获取混合服务实例（单例）

    Returns:
        HybridEmbeddingService 实例
    """
    global _hybrid_service

    if _hybrid_service is None:
        _hybrid_service = HybridEmbeddingService()

    return _hybrid_service


# ============================================
# 测试代码
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 混合 Embedding 服务测试")
    print("=" * 60)

    # 测试 1: 云端优先模式
    print("\n1️⃣ 测试云端优先模式...")
    service = HybridEmbeddingService(prefer_cloud=True)

    result = service.get_coordinate("粗糙的声音", "texture")
    if result:
        print(f"   ✅ 成功: ({result['x']:.2f}, {result['y']:.2f})")
    else:
        print(f"   ❌ 失败")

    # 测试 2: 本地优先模式
    print("\n2️⃣ 测试本地优先模式...")
    service_local = HybridEmbeddingService(prefer_cloud=False)

    result = service_local.get_coordinate("粗糙的声音", "texture")
    if result:
        print(f"   ✅ 成功: ({result['x']:.2f}, {result['y']:.2f})")
    else:
        print(f"   ❌ 失败")

    # 测试 3: 批量处理
    print("\n3️⃣ 测试批量处理...")
    texts = ["粗糙", "光滑", "明亮", "温暖"]

    results = service.get_coordinates_batch(texts, "texture")
    for i, (text, result) in enumerate(zip(texts, results)):
        if result:
            print(f"   {i+1}. {text}: ({result['x']:.2f}, {result['y']:.2f})")
        else:
            print(f"   {i+1}. {text}: 失败")

    # 测试 4: 打印统计
    service.print_stats()

    print("\n✅ 测试完成")
    print("=" * 60)
