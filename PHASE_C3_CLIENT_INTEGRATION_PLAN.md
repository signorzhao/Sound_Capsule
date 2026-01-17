# Phase C3: 客户端集成与缓存策略

**目标**: 将云端 Embedding API 集成到客户端，实现智能缓存和降级策略

---

## 📋 当前状态

### Phase C1: ✅ 100% 完成
- 棱镜版本控制系统
- 云端同步功能
- REST API 集成

### Phase C2: ✅ 70% 完成
- 云端 Embedding API 服务（核心代码完成）
- 坐标计算算法（与本地一致）
- Redis 缓存系统
- ⏳ 待部署测试
- ⏳ 待客户端集成

---

## 🎯 Phase C3 任务分解

### C3.1: 客户端 HTTP 客户端（1-2小时）

**任务**: 创建一个简单的 HTTP 客户端，用于调用云端 API

**文件**: `embedding_client.py`

```python
import requests
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class EmbeddingClient:
    """云端 Embedding API 客户端"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.timeout = 10  # 10 秒超时

    def health_check(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(
                f"{self.base_url}/api/health",
                timeout=2
            )
            return response.status_code == 200
        except:
            return False

    def get_coordinate(
        self,
        text: str,
        prism_id: str,
        timeout: Optional[int] = None
    ) -> Optional[tuple[float, float]]:
        """
        获取文本的坐标

        Args:
            text: 输入文本
            prism_id: 棱镜 ID
            timeout: 超时时间（秒）

        Returns:
            (x, y) 坐标，失败返回 None
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embed/coordinate",
                json={"text": text, "prism_id": prism_id},
                timeout=timeout or self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return data['x'], data['y']
            else:
                logger.error(f"API 错误: {response.status_code}")
                return None

        except requests.Timeout:
            logger.warning(f"请求超时: {text[:20]}...")
            return None
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return None

    def get_coordinates_batch(
        self,
        texts: List[str],
        prism_id: str,
        timeout: Optional[int] = None
    ) -> Optional[List[tuple[float, float]]]:
        """
        批量获取坐标

        Args:
            texts: 文本列表
            prism_id: 棱镜 ID
            timeout: 超时时间

        Returns:
            坐标列表
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embed/batch",
                json={"texts": texts, "prism_id": prism_id},
                timeout=timeout or self.timeout * 3  # 批量请求给 3 倍时间
            )

            if response.status_code == 200:
                data = response.json()
                return [(c['x'], c['y']) for c in data['coordinates']]
            else:
                return None

        except Exception as e:
            logger.error(f"批量请求失败: {e}")
            return None
```

### C3.2: 混合模式：云端优先 + 本地降级（2-3小时）

**任务**: 修改 `anchor_editor_v2.py`，实现智能降级策略

**策略**:
```
1. 尝试云端 API（快速，~100ms）
2. 如果失败/超时，降级到本地模型（慢，~500ms）
3. 如果本地模型未下载，提示错误
```

**实现**:

```python
class HybridEmbeddingService:
    """混合 Embedding 服务"""

    def __init__(self):
        self.cloud_client = EmbeddingClient()
        self.local_model = None
        self.prefer_cloud = True

    def load_local_model(self):
        """加载本地模型（降级方案）"""
        try:
            from sentence_transformers import SentenceTransformer
            self.local_model = SentenceTransformer('...')
            logger.info("✅ 本地模型加载成功")
        except Exception as e:
            logger.warning(f"⚠️  本地模型加载失败: {e}")
            self.local_model = None

    def get_coordinate(self, text: str, prism_id: str) -> tuple[float, float]:
        """
        获取坐标（云端优先 + 本地降级）

        优先级:
        1. 云端 API（快）
        2. 本地模型（慢但可靠）
        3. 抛出异常
        """
        # 策略 1: 云端优先
        if self.prefer_cloud:
            result = self.cloud_client.get_coordinate(text, prism_id)

            if result is not None:
                logger.debug(f"✅ 云端计算: {text[:20]}...")
                return result
            else:
                logger.warning("⚠️  云端失败，降级到本地")

        # 策略 2: 本地降级
        if self.local_model is not None:
            logger.debug(f"🔄 本地计算: {text[:20]}...")
            # 使用本地算法
            from coordinate_calculator import get_coordinate_calculator
            calculator = get_coordinate_calculator()
            # ... 本地计算逻辑
            return x, y

        # 策略 3: 无可用服务
        raise Exception("云端和本地都不可用")

# 在 anchor_editor_v2.py 中替换
# embedding_service = HybridEmbeddingService()
```

### C3.3: 客户端缓存策略（2-3小时）

**任务**: 实现多层缓存，避免重复计算

**缓存层级**:

```
L1: 内存缓存（运行时）
   - 最快：< 1ms
   - 容量：~1000 个坐标
   - 生命周期：应用运行期间

L2: SQLite 持久化缓存
   - 快：~5ms
   - 容量：~100,000 个坐标
   - 生命周期：永久

L3: 云端 API
   - 慢：~100ms
   - 容量：无限
   - 缓存：7 天 TTL
```

**实现**:

```python
class EmbeddingCache:
    """Embedding 坐标缓存"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.memory_cache: Dict[str, tuple[float, float]] = {}
        self.memory_cache_size = 1000

    def get(self, text: str, prism_id: str) -> Optional[tuple[float, float]]:
        """
        获取缓存的坐标

        优先级: 内存 -> SQLite -> None
        """
        # L1: 内存缓存
        cache_key = f"{prism_id}:{text}"
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]

        # L2: SQLite 缓存
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT x, y FROM embedding_cache WHERE text = ? AND prism_id = ?",
            (text, prism_id)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            x, y = row
            # 提升到内存缓存
            self.memory_cache[cache_key] = (x, y)
            return x, y

        return None

    def set(self, text: str, prism_id: str, x: float, y: float):
        """设置缓存"""
        cache_key = f"{prism_id}:{text}"

        # 存入内存
        if len(self.memory_cache) < self.memory_cache_size:
            self.memory_cache[cache_key] = (x, y)

        # 存入 SQLite
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO embedding_cache (text, prism_id, x, y, cached_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (text, prism_id, x, y)
        )
        conn.commit()
        conn.close()
```

**数据库表**:

```sql
CREATE TABLE IF NOT EXISTS embedding_cache (
    text TEXT NOT NULL,
    prism_id TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (text, prism_id)
);

CREATE INDEX IF NOT EXISTS idx_embedding_cache_prism ON embedding_cache(prism_id);
```

### C3.4: 一致性验证测试（1小时）

**任务**: 确保云端和本地计算结果一致

**测试脚本**: `test_coordinate_consistency.py`

```python
def test_consistency():
    """
    一致性测试：对比云端和本地计算结果

    目标：误差 < 1e-5
    """
    test_texts = [
        "粗糙的声音",
        "明亮的音色",
        "合成器低音",
        # ... 更多测试用例
    ]

    for text in test_texts:
        # 云端计算
        cloud_client = EmbeddingClient()
        cloud_x, cloud_y = cloud_client.get_coordinate(text, "texture")

        # 本地计算
        local_x, local_y = calculate_local(text, "texture")

        # 对比
        diff_x = abs(cloud_x - local_x)
        diff_y = abs(cloud_y - local_y)

        print(f"{text}:")
        print(f"   云端: ({cloud_x:.4f}, {cloud_y:.4f})")
        print(f"   本地: ({local_x:.4f}, {local_y:.4f})")
        print(f"   差异: ({diff_x:.4e}, {diff_y:.4e})")

        assert diff_x < 1e-5, f"x 坐标不一致: {diff_x}"
        assert diff_y < 1e-5, f"y 坐标不一致: {diff_y}"

    print("✅ 一致性测试通过")
```

---

## 📊 Phase C3 时间估算

```
C3.1: HTTP 客户端          - 1-2 小时
C3.2: 混合模式 + 降级     - 2-3 小时
C3.3: 客户端缓存策略      - 2-3 小时
C3.4: 一致性验证测试      - 1 小时

总计: 6-9 小时
```

---

## 🎯 成功标准

- [ ] HTTP 客户端正常工作
- [ ] 云端 API 调用成功
- [ ] 降级到本地模型正常
- [ ] 三层缓存正常工作
- [ ] 一致性测试通过（误差 < 1e-5）
- [ ] 性能测试通过（缓存命中 < 10ms）

---

## 🚀 下一步行动

### 立即可做

1. **启动 Embedding API 服务**
   ```bash
   cd data-pipeline
   python embedding_service.py
   ```

2. **运行快速测试**
   ```bash
   python quick_test_embedding.py
   ```

3. **创建 HTTP 客户端**
   - 实现 `EmbeddingClient` 类
   - 测试基本功能

### 后续工作

4. **修改 anchor_editor_v2.py**
   - 集成 `HybridEmbeddingService`
   - 实现降级策略

5. **实现客户端缓存**
   - 创建 `EmbeddingCache` 类
   - 添加数据库表

6. **一致性验证**
   - 对比云端和本地结果
   - 确保误差 < 1e-5

---

**Phase C3 预计完成时间**: 6-9 小时
**Phase C2 + C3 总体完成度**: 70% → 100%
