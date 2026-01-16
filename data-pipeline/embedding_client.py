"""
Phase C3.1: 云端 Embedding API 客户端

提供可靠的 HTTP 客户端，支持：
- 智能超时控制（3秒）
- 环境变量配置
- 请求重试
- 详细的错误处理
"""

import requests
import os
import logging
from typing import Optional, Dict, List
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """
    云端 Embedding API 客户端

    特性：
    - 智能超时（默认 3 秒）
    - 环境变量配置
    - 自动重试
    - 连接池管理
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 3,
        max_retries: int = 2
    ):
        """
        初始化客户端

        Args:
            base_url: API 基础 URL（默认从环境变量读取）
            timeout: 请求超时时间（秒），默认 3 秒
            max_retries: 最大重试次数，默认 2 次
        """
        # 优先级: 参数 > 环境变量 > 默认值
        self.base_url = base_url or os.getenv(
            "EMBEDDING_API_URL",
            "http://localhost:8000"
        )
        self.timeout = timeout

        # 创建带重试的 Session
        self.session = self._create_session(max_retries)

        logger.info(f"✅ EmbeddingClient 初始化")
        logger.info(f"   API URL: {self.base_url}")
        logger.info(f"   超时: {timeout}s")
        logger.info(f"   重试: {max_retries} 次")

    def _create_session(self, max_retries: int) -> requests.Session:
        """
        创建带重试策略的 Session

        Args:
            max_retries: 最大重试次数

        Returns:
            配置好的 Session 对象
        """
        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,  # 重试间隔：0.5s, 1s, 2s...
            status_forcelist=[500, 502, 503, 504],  # 这些状态码会重试
            allowed_methods=["POST"]  # 只对 POST 请求重试
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def health_check(self) -> Dict[str, any]:
        """
        健康检查

        Returns:
            健康状态字典
            {
                'healthy': bool,
                'model_loaded': bool,
                'cache_connected': bool,
                'latency_ms': float,
                'error': str or None
            }
        """
        start_time = __import__('time').time()

        try:
            response = self.session.get(
                f"{self.base_url}/api/health",
                timeout=2
            )

            latency = (__import__('time').time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                return {
                    'healthy': True,
                    'model_loaded': data.get('model_loaded', False),
                    'cache_connected': data.get('cache_connected', False),
                    'latency_ms': latency,
                    'error': None
                }
            else:
                return {
                    'healthy': False,
                    'model_loaded': False,
                    'cache_connected': False,
                    'latency_ms': latency,
                    'error': f"HTTP {response.status_code}"
                }

        except requests.exceptions.Timeout:
            return {
                'healthy': False,
                'model_loaded': False,
                'cache_connected': False,
                'latency_ms': 2000,  # 超时时间
                'error': 'Timeout'
            }
        except Exception as e:
            return {
                'healthy': False,
                'model_loaded': False,
                'cache_connected': False,
                'latency_ms': 0,
                'error': str(e)
            }

    def get_coordinate(
        self,
        text: str,
        prism_id: str,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, float]]:
        """
        获取文本的坐标

        Args:
            text: 输入文本
            prism_id: 棱镜 ID
            timeout: 超时时间（覆盖默认值）

        Returns:
            {'x': float, 'y': float} 或 None（失败时）
        """
        try:
            url = f"{self.base_url}/api/embed/coordinate"
            payload = {
                "text": text,
                "prism_id": prism_id
            }

            # 发送请求
            response = self.session.post(
                url,
                json=payload,
                timeout=timeout or self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                # 验证返回格式
                if "x" in data and "y" in data:
                    logger.debug(f"✅ 云端计算成功: {text[:30]}...")
                    return {
                        "x": float(data["x"]),
                        "y": float(data["y"])
                    }
                else:
                    logger.error(f"❌ 响应格式错误: {data}")
                    return None
            else:
                logger.warning(f"⚠️  API 返回非 200: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(
                f"⏱️  云端 API 超时 ({timeout or self.timeout}s)，"
                f"建议回退到本地模型"
            )
            return None

        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ 连接失败: {e}")
            logger.info(f"   检查服务是否启动: {self.base_url}")
            return None

        except Exception as e:
            logger.error(f"❌ 请求失败: {e}")
            return None

    def get_coordinates_batch(
        self,
        texts: List[str],
        prism_id: str,
        timeout: Optional[int] = None
    ) -> Optional[List[Dict[str, float]]]:
        """
        批量获取坐标

        Args:
            texts: 文本列表
            prism_id: 棱镜 ID
            timeout: 超时时间（批量请求给 3 倍时间）

        Returns:
            [{'x': float, 'y': float}, ...] 或 None
        """
        try:
            url = f"{self.base_url}/api/embed/batch"
            payload = {
                "texts": texts,
                "prism_id": prism_id
            }

            # 批量请求给 3 倍时间
            batch_timeout = timeout or (self.timeout * 3)

            response = self.session.post(
                url,
                json=payload,
                timeout=batch_timeout
            )

            if response.status_code == 200:
                data = response.json()

                if "coordinates" in data:
                    logger.info(f"✅ 批量计算成功: {len(texts)} 个文本")
                    return [
                        {"x": float(c["x"]), "y": float(c["y"])}
                        for c in data["coordinates"]
                    ]
                else:
                    logger.error(f"❌ 响应格式错误: {data}")
                    return None
            else:
                logger.warning(f"⚠️  批量 API 返回非 200: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"⏱️  批量请求超时 ({timeout}s)")
            return None

        except Exception as e:
            logger.error(f"❌ 批量请求失败: {e}")
            return None

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取文本的 Embedding 向量

        Args:
            text: 输入文本

        Returns:
            Embedding 向量或 None
        """
        try:
            url = f"{self.base_url}/api/embed"
            payload = {"text": text}

            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if "embedding" in data:
                    return data["embedding"]
                else:
                    logger.error(f"❌ 响应格式错误: {data}")
                    return None
            else:
                return None

        except Exception as e:
            logger.error(f"❌ 获取 embedding 失败: {e}")
            return None

    def close(self):
        """关闭 Session"""
        if self.session:
            self.session.close()
            logger.info("✅ EmbeddingClient 已关闭")

    def __enter__(self):
        """上下文管理器支持"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器支持"""
        self.close()


# ============================================
# 全局实例（单例模式）
# ============================================

_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    """
    获取 EmbeddingClient 实例（单例）

    Returns:
        EmbeddingClient 实例
    """
    global _client

    if _client is None:
        _client = EmbeddingClient()

    return _client


# ============================================
# 测试代码
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 EmbeddingClient 测试")
    print("=" * 60)

    # 测试 1: 健康检查
    print("\n1️⃣ 测试健康检查...")
    client = EmbeddingClient()

    health = client.health_check()
    print(f"   健康状态: {health['healthy']}")
    print(f"   模型已加载: {health['model_loaded']}")
    print(f"   缓存已连接: {health['cache_connected']}")
    print(f"   延迟: {health['latency_ms']:.1f}ms")

    if not health['healthy']:
        print(f"\n❌ 服务不可用: {health['error']}")
        print("💡 请先启动服务: python embedding_service.py")
        exit(1)

    # 测试 2: 单个文本转坐标
    print("\n2️⃣ 测试单个文本转坐标...")
    result = client.get_coordinate("粗糙的声音", "texture")

    if result:
        print(f"   ✅ 成功")
        print(f"   坐标: ({result['x']:.2f}, {result['y']:.2f})")
    else:
        print(f"   ❌ 失败")

    # 测试 3: 批量转换
    print("\n3️⃣ 测试批量转换...")
    results = client.get_coordinates_batch(
        ["粗糙", "光滑", "明亮"],
        "texture"
    )

    if results:
        print(f"   ✅ 成功")
        for i, r in enumerate(results):
            print(f"      {i+1}. ({r['x']:.2f}, {r['y']:.2f})")
    else:
        print(f"   ❌ 失败")

    # 测试 4: 超时测试
    print("\n4️⃣ 测试超时控制...")
    import time

    client_with_timeout = EmbeddingClient(timeout=1)  # 1 秒超时
    start = time.time()
    result = client_with_timeout.get_coordinate("测试超时", "texture")
    duration = (time.time() - start) * 1000

    print(f"   请求耗时: {duration:.1f}ms")
    if result:
        print(f"   ✅ 成功: ({result['x']:.2f}, {result['y']:.2f})")
    else:
        print(f"   ⚠️  失败（可能是超时）")

    client_with_timeout.close()

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
