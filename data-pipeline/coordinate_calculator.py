"""
Phase C2: 坐标计算器（云端和本地共享）

确保云端 API 和本地客户端使用完全相同的坐标计算算法
避免因为算法差异导致的位置不一致
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from scipy.stats import rankdata
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CoordinateCalculator:
    """坐标计算器 - 实现 v2 算法"""

    def __init__(self):
        """初始化计算器"""
        pass

    def calculate_coordinates(
        self,
        word_embeddings: np.ndarray,
        anchor_embeddings: np.ndarray,
        anchor_coords: np.ndarray,
        stretch: bool = True
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        计算单词的 2D 坐标

        算法流程：
        1. 计算与所有锚点的余弦相似度
        2. 使用 8 次方加权（强调相似度高的锚点）
        3. 加权平均得到初始坐标
        4. 可选：空间均匀化变换

        Args:
            word_embeddings: 单词的 embedding 向量 (n_words, dim)
            anchor_embeddings: 锚点的 embedding 向量 (n_anchors, dim)
            anchor_coords: 锚点的 2D 坐标 (n_anchors, 2)
            stretch: 是否进行空间均匀化变换

        Returns:
            (x_coords, y_coords): 单词的 2D 坐标
        """
        n_words = word_embeddings.shape[0]

        # 计算与所有锚点的相似度
        sims = cosine_similarity(word_embeddings, anchor_embeddings)  # (n_words, n_anchors)

        # 8 次方加权（强调高相似度）
        weights = np.power((sims + 1) / 2, 8)  # (n_words, n_anchors)

        # 加权平均计算初始坐标
        total_weight = np.sum(weights, axis=1, keepdims=True)  # (n_words, 1)

        # 避免除零
        total_weight = np.where(total_weight < 1e-9, 1.0, total_weight)

        # 加权求和
        weighted_coords = np.dot(weights, anchor_coords)  # (n_words, 2)

        # 归一化
        raw_x = weighted_coords[:, 0] / total_weight[:, 0]
        raw_y = weighted_coords[:, 1] / total_weight[:, 0]

        # 空间均匀化变换
        if stretch:
            x_coords = self._smooth_stretch(raw_x)
            y_coords = self._smooth_stretch(raw_y)
        else:
            x_coords = raw_x
            y_coords = raw_y

        # 限制在 [0, 100] 范围
        x_coords = np.clip(x_coords, 0, 100)
        y_coords = np.clip(y_coords, 0, 100)

        return x_coords, y_coords

    def _smooth_stretch(
        self,
        vals: np.ndarray,
        target_min: float = 5.0,
        target_max: float = 95.0
    ) -> np.ndarray:
        """
        空间均匀化变换

        使用排名将数据均匀分布到目标范围

        Args:
            vals: 原始值
            target_min: 目标最小值
            target_max: 目标最大值

        Returns:
            变换后的值
        """
        if len(vals) < 2:
            return np.full_like(vals, 50.0)

        # 计算排名（处理并列）
        ranks = rankdata(vals, method='average')

        # 归一化到 [0, 1]
        norm = (ranks - np.min(ranks)) / (np.max(ranks) - np.min(ranks) + 1e-9)

        # 映射到目标范围
        return norm * (target_max - target_min) + target_min

    def calculate_single_word(
        self,
        word_embedding: np.ndarray,
        anchor_embeddings: np.ndarray,
        anchor_coords: np.ndarray,
        stretch: bool = True
    ) -> tuple[float, float]:
        """
        计算单个单词的坐标

        Args:
            word_embedding: 单词的 embedding 向量 (dim,)
            anchor_embeddings: 锚点的 embedding 向量 (n_anchors, dim)
            anchor_coords: 锚点的 2D 坐标 (n_anchors, 2)
            stretch: 是否进行空间均匀化变换

        Returns:
            (x, y): 单词的 2D 坐标
        """
        # 转换为 2D 数组
        word_embeddings = word_embedding.reshape(1, -1)

        # 计算坐标
        x_coords, y_coords = self.calculate_coordinates(
            word_embeddings,
            anchor_embeddings,
            anchor_coords,
            stretch=stretch
        )

        return float(x_coords[0]), float(y_coords[0])


# ============================================
# 从 Prism 配置加载锚点
# ============================================

def load_anchors_from_prism(prism_config: Dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """
    从棱镜配置加载锚点数据

    Args:
        prism_config: 棱镜配置（来自 Phase C1 的 prisms 表）

    Returns:
        (anchor_embeddings, anchor_coords): 锚点数据
    """
    # TODO: 这里需要实际的 embedding 计算
    # 目前返回占位符

    anchors = prism_config.get('anchors', [])

    if not anchors:
        # 默认锚点（如果没有配置）
        anchor_coords = np.array([
            [10, 50],   # 左
            [90, 50],   # 右
            [50, 10],   # 上
            [50, 90],   # 下
        ])
        # TODO: 计算 anchor_embeddings
        anchor_embeddings = np.random.rand(4, 384)  # MiniLM-L12 是 384 维
    else:
        # 从配置加载锚点
        anchor_coords = np.array([[a['x'], a['y']] for a in anchors])
        # TODO: 计算 anchor_embeddings（需要 embedding 模型）
        anchor_embeddings = np.random.rand(len(anchors), 384)

    return anchor_embeddings, anchor_coords


# ============================================
# 全局实例
# ============================================

_calculator: Optional[CoordinateCalculator] = None


def get_coordinate_calculator() -> CoordinateCalculator:
    """获取坐标计算器实例（单例）"""
    global _calculator

    if _calculator is None:
        _calculator = CoordinateCalculator()

    return _calculator


# ============================================
# 测试代码
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 坐标计算器测试")
    print("=" * 60)

    # 创建测试数据
    np.random.seed(42)

    # 模拟 3 个锚点
    anchor_embeddings = np.random.rand(3, 384)
    anchor_coords = np.array([
        [10, 10],   # 左上
        [90, 10],   # 右上
        [50, 90],   # 底部中间
    ])

    # 模拟 5 个单词
    word_embeddings = np.random.rand(5, 384)

    print(f"\n锚点数量: {len(anchor_coords)}")
    print(f"单词数量: {len(word_embeddings)}")

    # 计算坐标
    calculator = get_coordinate_calculator()

    print("\n1️⃣ 计算坐标（无拉伸）...")
    x_coords, y_coords = calculator.calculate_coordinates(
        word_embeddings,
        anchor_embeddings,
        anchor_coords,
        stretch=False
    )

    for i, (x, y) in enumerate(zip(x_coords, y_coords)):
        print(f"   Word {i+1}: ({x:.2f}, {y:.2f})")

    print("\n2️⃣ 计算坐标（有拉伸）...")
    x_coords_stretched, y_coords_stretched = calculator.calculate_coordinates(
        word_embeddings,
        anchor_embeddings,
        anchor_coords,
        stretch=True
    )

    for i, (x, y) in enumerate(zip(x_coords_stretched, y_coords_stretched)):
        print(f"   Word {i+1}: ({x:.2f}, {y:.2f})")

    print("\n3️⃣ 测试单个单词...")
    single_word_embedding = word_embeddings[0]
    x, y = calculator.calculate_single_word(
        single_word_embedding,
        anchor_embeddings,
        anchor_coords,
        stretch=True
    )
    print(f"   单词 1: ({x:.2f}, {y:.2f})")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
