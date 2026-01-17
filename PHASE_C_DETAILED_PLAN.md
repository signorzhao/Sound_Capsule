# Phase C: 数据一致性优化 - 详细实施计划

**日期**: 2026-01-11
**状态**: 📋 规划中
**预计耗时**: 2-3 周
**依赖**: Phase B 已完成 ✅

---

## 📋 项目未完成内容总览

### 1. Phase C: 数据一致性优化（本次规划）⏳

**目标**: 确保多设备间数据的一致性和冲突解决

**核心内容**:
- C1: 棱镜版本号机制
- C2: 云端 Embedding API
- C3: 客户端缓存策略

### 2. Supabase 集成测试（Phase B 遗留）⏳

**需要完成的测试**:
- 真实 Supabase 连接测试
- 轻量级同步端到端测试
- 按需下载流程测试
- 文件上传/下载测试

### 3. 前端 UI 完整集成（Phase B 遗留）⏳

**需要完成的集成**:
- CapsuleLibrary 组件与后端 API 对接
- DownloadProgressDialog 实时更新
- CacheManager 智能清理按钮

### 4. 文档和用户手册（所有 Phase）⏳

**需要编写的文档**:
- API 文档
- 用户使用手册
- 部署指南
- 故障排查指南

---

## 🎯 Phase C 详细规划

### C1: 棱镜版本号机制

**目标**: 解决棱镜配置的版本冲突

#### 当前问题分析

**场景**:
```
设备 A 修改棱镜 → 上传到云端 (v2)
设备 B 也在修改同一棱镜 → 上传到云端 (v2)
→ 冲突！哪个版本是正确的？
```

**需要的机制**:
1. 版本号字段
2. 版本比较算法
3. 冲突检测和解决

#### 实施计划

**C1.1 数据库改造**

```sql
-- prisms 表添加版本字段
ALTER TABLE prisms ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE prisms ADD COLUMN parent_version INTEGER;  -- 父版本号

-- 创建版本历史表
CREATE TABLE prism_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prism_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    config_data TEXT NOT NULL,  -- JSON 配置
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,  -- user_id
    change_description TEXT,

    FOREIGN KEY (prism_id) REFERENCES prisms(id) ON DELETE CASCADE
);

CREATE INDEX idx_prism_versions_prism_version
ON prism_versions(prism_id, version);
```

**文件**: `data-pipeline/database/prism_versioning.sql`

---

**C1.2 版本管理服务**

**新文件**: `data-pipeline/prism_version_manager.py`

```python
class PrismVersionManager:
    """棱镜版本管理器"""

    def create_version(self, prism_id: int, config: Dict, user_id: str) -> int:
        """
        创建新版本

        Args:
            prism_id: 棱镜 ID
            config: 配置数据
            user_id: 用户 ID

        Returns:
            新版本号
        """

    def get_version_history(self, prism_id: int) -> List[Dict]:
        """获取版本历史"""

    def detect_conflict(self, local_version: int, cloud_version: int) -> bool:
        """检测版本冲突"""

    def resolve_conflict(
        self,
        prism_id: int,
        local_config: Dict,
        cloud_config: Dict,
        strategy: str = "latest"  # latest, local, cloud, manual
    ) -> Dict:
        """
        解决冲突

        策略:
        - latest: 使用最新修改时间
        - local: 保留本地版本
        - cloud: 使用云端版本
        - manual: 需要用户手动选择
        """
```

---

**C1.3 同步服务增强**

**修改**: `data-pipeline/sync_service.py`

```python
def sync_prisms_with_versioning(self, user_id: str) -> Dict[str, Any]:
    """
    带版本控制的棱镜同步

    流程:
    1. 检查本地和云端版本号
    2. 检测冲突
    3. 根据策略解决冲突
    4. 更新版本历史
    """
```

---

**C1.4 REST API 端点**

**修改**: `data-pipeline/capsule_api.py`

```python
# 获取版本历史
@app.route('/api/prisms/<int:prism_id>/versions', methods=['GET'])
@token_required
def get_prism_versions(current_user, prism_id):
    """获取棱镜版本历史"""

# 回滚到指定版本
@app.route('/api/prisms/<int:prism_id>/versions/<int:version>', methods=['POST'])
@token_required
def restore_prism_version(current_user, prism_id, version):
    """回滚棱镜到指定版本"""

# 比较两个版本的差异
@app.route('/api/prisms/<int:prism_id>/versions/compare', methods=['POST'])
@token_required
def compare_prism_versions(current_user, prism_id):
    """
    比较版本差异

    请求体: {"version1": 1, "version2": 2}
    响应: {"differences": [...]}
    """
```

---

### C2: 云端 Embedding API

**目标**: 集中化 Embedding 计算，避免客户端重复计算

#### 当前架构分析

**现状**:
```python
# 客户端计算 Embedding
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode(text)  # 耗时 ~500ms
```

**问题**:
- 每个客户端都需要下载模型（~500MB）
- 重复计算相同文本的 embedding
- 客户端性能压力大

#### 解决方案：云端 Embedding 服务

**架构**:
```
客户端                     云端 API
  |                           |
  |-- 1. 发送文本 -------->   |
  |                           |-- 2. 计算 embedding
  |                           |     (模型已在内存)
  |<--- 3. 返回 embedding ----|
```

**优点**:
- 客户端不需要下载模型
- 相同文本缓存结果
- 统一的 embedding 版本

#### 实施计划

**C2.1 云端 Embedding 服务**

**方案 A: FastAPI（推荐）**

**新文件**: `cloud-embedding-service/main.py`

```python
from fastapi import FastAPI, HTTPException
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel
import redis
import hashlib

app = FastAPI(title="Sound Capsule Embedding Service")

# 加载模型（启动时）
model = SentenceTransformer('all-MiniLM-L6-v2')

# Redis 缓存
redis_client = redis.Redis(host='localhost', port=6379, db=0)

class EmbeddingRequest(BaseModel):
    text: str
    model: str = "all-MiniLM-L6-v2"

class EmbeddingResponse(BaseModel):
    embedding: List[float]
    dimension: int
    cached: bool

@app.post("/embed", response_model=EmbeddingResponse)
async def compute_embedding(request: EmbeddingRequest):
    """
    计算文本 embedding

    流程:
    1. 计算文本哈希
    2. 检查 Redis 缓存
    3. 如果缓存命中，返回缓存结果
    4. 如果缓存未命中，计算并缓存
    """
    # 1. 计算哈希
    text_hash = hashlib.md5(request.text.encode()).hexdigest()

    # 2. 检查缓存
    cached = redis_client.get(f"embed:{text_hash}")
    if cached:
        embedding = json.loads(cached)
        return EmbeddingResponse(
            embedding=embedding,
            dimension=len(embedding),
            cached=True
        )

    # 3. 计算 embedding
    embedding = model.encode(request.text).tolist()

    # 4. 缓存结果（TTL 30 天）
    redis_client.setex(
        f"embed:{text_hash}",
        30 * 24 * 3600,
        json.dumps(embedding)
    )

    return EmbeddingResponse(
        embedding=embedding,
        dimension=len(embedding),
        cached=False
    )

@app.post("/embed/batch")
async def compute_batch_embedding(requests: List[EmbeddingRequest]):
    """批量计算 embedding"""
    texts = [r.text for r in requests]
    embeddings = model.encode(texts).tolist()

    return {
        "embeddings": embeddings,
        "dimension": len(embeddings[0]) if embeddings else 0
    }
```

**部署方案**:
- Docker 容器部署
- 2GB 内存
- GPU 可选（加速）
- Redis 缓存

---

**C2.2 客户端集成**

**修改**: `data-pipeline/capsule_scanner.py`

```python
class EmbeddingClient:
    """Embedding 客户端"""

    def __init__(self, api_url: str):
        self.api_url = api_url
        self.cache = {}  # 本地内存缓存

    async def get_embedding(self, text: str) -> List[float]:
        """
        获取文本 embedding

        优先级:
        1. 本地内存缓存
        2. 云端 API
        """

        # 1. 检查本地缓存
        if text in self.cache:
            return self.cache[text]

        # 2. 调用云端 API
        try:
            response = requests.post(
                f"{self.api_url}/embed",
                json={"text": text},
                timeout=5
            )
            response.raise_for_status()

            data = response.json()
            embedding = data["embedding"]

            # 更新本地缓存
            self.cache[text] = embedding

            return embedding

        except Exception as e:
            print(f"❌ 获取 embedding 失败: {e}")
            # 回退到本地计算
            return self._compute_local(text)

    def _compute_local(self, text: str) -> List[float]:
        """本地计算 embedding（回退方案）"""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        return model.encode(text).tolist()
```

**使用**:
```python
# 在 capsule_scanner.py 中
embedding_client = EmbeddingClient(
    api_url=os.getenv("EMBEDDING_API_URL", "http://localhost:8000")
)

# 替换原来的 model.encode()
embedding = await embedding_client.get_embedding(keywords)
```

---

**C2.3 REST API 包装**

**新文件**: `data-pipeline/embedding_api.py`

```python
from flask import Blueprint, request, jsonify
import requests

embedding_bp = Blueprint('embedding', __name__)

@embedding_bp.route('/api/embedding', methods=['POST'])
@token_required
def get_embedding(current_user):
    """
    代理到云端 Embedding 服务

    请求体: {"text": "some text"}
    响应: {"embedding": [...], "cached": true}
    """
    text = request.json.get('text')

    # 调用云端服务
    response = requests.post(
        f"{EMBEDDING_SERVICE_URL}/embed",
        json={"text": text},
        timeout=5
    )

    return jsonify(response.json())
```

---

### C3: 客户端缓存策略

**目标**: 优化 Embedding 和棱镜配置的本地缓存

#### C3.1 Embedding 缓存

**新文件**: `data-pipeline/cache/embedding_cache.py`

```python
class EmbeddingCache:
    """Embedding 缓存管理器"""

    def __init__(self, db_path: str, max_size: int = 10000):
        """
        Args:
            max_size: 最大缓存条目数
        """
        self.db = sqlite3.connect(db_path)
        self.max_size = max_size
        self._init_db()

    def _init_db(self):
        """初始化缓存表"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS embedding_cache (
                text_hash TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL,  -- numpy array 序列化
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_embedding_cache_accessed
            ON embedding_cache(last_accessed);
        """)

    def get(self, text: str) -> Optional[np.ndarray]:
        """获取缓存的 embedding"""
        text_hash = hashlib.md5(text.encode()).hexdigest()

        cursor = self.db.execute("""
            SELECT embedding, access_count
            FROM embedding_cache
            WHERE text_hash = ?
        """, (text_hash,))

        row = cursor.fetchone()
        if row:
            # 更新访问记录
            self.db.execute("""
                UPDATE embedding_cache
                SET access_count = access_count + 1,
                    last_accessed = CURRENT_TIMESTAMP
                WHERE text_hash = ?
            """, (text_hash,))
            self.db.commit()

            # 反序列化
            embedding = np.frombuffer(row[0], dtype=np.float32)
            return embedding

        return None

    def put(self, text: str, embedding: np.ndarray):
        """缓存 embedding"""
        text_hash = hashlib.md5(text.encode()).hexdigest()

        # LRU 清理
        self._evict_if_needed()

        # 序列化
        embedding_blob = embedding.astype(np.float32).tobytes()

        # 插入
        self.db.execute("""
            INSERT OR REPLACE INTO embedding_cache
            (text_hash, text, embedding)
            VALUES (?, ?, ?)
        """, (text_hash, text, embedding_blob))

        self.db.commit()

    def _evict_if_needed(self):
        """LRU 清理"""
        cursor = self.db.execute("""
            SELECT COUNT(*) FROM embedding_cache
        """)
        count = cursor.fetchone()[0]

        if count >= self.max_size:
            # 删除最旧的 10%
            delete_count = int(self.max_size * 0.1)
            self.db.execute(f"""
                DELETE FROM embedding_cache
                ORDER BY last_accessed ASC
                LIMIT {delete_count}
            """)
            self.db.commit()
```

---

**C3.2 棱镜配置缓存**

**新文件**: `data-pipeline/cache/prism_cache.py`

```python
class PrismCache:
    """棱镜配置缓存"""

    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self._init_db()

    def get(self, prism_id: int) -> Optional[Dict]:
        """获取缓存的棱镜配置"""
        cursor = self.db.execute("""
            SELECT config_data, version
            FROM prism_cache
            WHERE prism_id = ?
        """, (prism_id,))

        row = cursor.fetchone()
        if row:
            return {
                "config": json.loads(row[0]),
                "version": row[1]
            }
        return None

    def put(self, prism_id: int, config: Dict, version: int):
        """缓存棱镜配置"""
        config_json = json.dumps(config)

        self.db.execute("""
            INSERT OR REPLACE INTO prism_cache
            (prism_id, config_data, version, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (prism_id, config_json, version))

        self.db.commit()

    def invalidate(self, prism_id: int):
        """失效缓存"""
        self.db.execute("""
            DELETE FROM prism_cache WHERE prism_id = ?
        """, (prism_id,))
        self.db.commit()
```

---

## 🔧 需要了解的技术细节

### 1. Supabase 配置

**需要的信息**:
```bash
# .env.supabase 文件
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Supabase 表结构
# - cloud_capsules (云端胶囊表)
# - cloud_prisms (云端棱镜表)
# - capsules (本地胶囊表)
# - prisms (本地棱镜表)
```

**问题**:
- ✅ Supabase 项目是否已创建？
- ✅ 表结构是否已同步？
- ✅ Storage bucket 是否已配置？
- ⏳ Row Level Security (RLS) 策略是否已设置？

### 2. Embedding 模型选择

**当前使用**: `all-MiniLM-L6-v2`
- 维度: 384
- 大小: ~80MB
- 速度: 快（~500ms per text）

**备选方案**:
- `all-mpnet-base-v2` (768 维，更准确但慢)
- `multilingual-e5-base` (多语言支持)

**需要决定**:
- 是否支持多语言？
- 是否需要更高的准确度？
- 云端服务的硬件配置？

### 3. 缓存策略配置

**Embedding 缓存**:
```python
# 配置参数
EMBEDDING_CACHE_SIZE = 10000  # 最大条目数
EMBEDDING_CACHE_TTL = 30 * 24 * 3600  # 30 天

# Redis 配置（云端）
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = None
```

**棱镜缓存**:
```python
# 配置参数
PRISM_CACHE_SIZE = 100  # 最大棱镜数
PRISM_CACHE_TTL = 7 * 24 * 3600  # 7 天
```

**需要决定**:
- 缓存大小限制？
- 缓存过期时间？
- 是否支持 Redis？

### 4. 版本冲突策略

**冲突解决策略**:

```python
CONFLICT_RESOLUTION_STRATEGIES = {
    "latest": "使用最新修改时间的版本",
    "local": "始终保留本地版本",
    "cloud": "始终使用云端版本",
    "manual": "需要用户手动选择"
}
```

**需要决定**:
- 默认使用哪种策略？
- 是否提供用户选择界面？
- 如何记录冲突历史？

---

## 📊 Phase C 实施步骤

### 第 1 周：C1 棱镜版本号机制

**Day 1-2**: 数据库改造
- 创建 `prism_versioning.sql`
- 执行迁移
- 单元测试

**Day 3-4**: 版本管理服务
- 实现 `PrismVersionManager`
- 修改 `sync_service.py`
- REST API 端点

**Day 5**: 测试和文档
- 版本冲突测试
- 回滚功能测试
- API 文档

### 第 2 周：C2 云端 Embedding API

**Day 1-2**: 云端服务开发
- FastAPI 服务
- Redis 缓存集成
- Docker 容器化

**Day 3-4**: 客户端集成
- 实现 `EmbeddingClient`
- 修改 `capsule_scanner.py`
- 回退机制

**Day 5**: 测试和优化
- 性能测试
- 缓存命中率测试
- 负载测试

### 第 3 周：C3 客户端缓存策略 + 集成测试

**Day 1-2**: 缓存实现
- `EmbeddingCache`
- `PrismCache`
- LRU 清理策略

**Day 3-4**: 端到端测试
- Supabase 集成测试
- 前端 UI 集成测试
- 完整流程测试

**Day 5**: 文档和部署
- API 文档
- 部署指南
- 用户手册

---

## ❓ 需要你的决策

### 1. 技术选型

**Q1**: Embedding 云端服务部署方式？
- A. Docker 容器（自托管）
- B. AWS Lambda（无服务器）
- C. Supabase Edge Functions

**Q2**: 缓存方案？
- A. 仅本地 SQLite
- B. Redis + 本地 SQLite
- C. Supabase Database + 本地 SQLite

**Q3**: 版本冲突默认策略？
- A. latest（最新时间）
- B. local（保留本地）
- C. cloud（使用云端）

### 2. 优先级

**Q4**: 是否优先实现？
- A. C1 → C2 → C3（顺序）
- B. C2 → C1 → C3（Embedding 优先）
- C. C3 → C1 → C2（缓存优先）

**Q5**: 是否需要完整测试每个功能？
- A. 是，每个功能都完整测试
- B. 否，先实现核心功能，测试后续进行

### 3. 资源配置

**Q6**: 云端服务器配置？
- A. 2 核 4GB（基础）
- B. 4 核 8GB（标准）
- C. 8 核 16GB（高性能）

**Q7**: 是否需要 GPU？
- A. 是（加速 Embedding 计算）
- B. 否（CPU 够用）

---

## 📝 总结

### 未完成内容清单

1. **Phase C: 数据一致性优化** ⏳
   - C1: 棱镜版本号机制
   - C2: 云端 Embedding API
   - C3: 客户端缓存策略

2. **Supabase 集成测试** ⏳
   - 真实云端连接测试
   - 轻量级同步测试
   - 文件上传下载测试

3. **前端 UI 集成** ⏳
   - CapsuleLibrary 完整对接
   - DownloadProgressDialog 实时更新
   - CacheManager 智能清理

4. **文档编写** ⏳
   - API 文档
   - 用户手册
   - 部署指南

### 下一步行动

请回答上述 7 个问题（Q1-Q7），我会据此制定更详细的实施方案。

或者，如果你希望我使用推荐的配置直接开始，请告诉我：
- **"开始 Phase C"** - 我会使用推荐配置开始实施
- **"先测试 Supabase"** - 先完成 Supabase 集成测试
- **"具体规划某一项"** - 告诉我你想深入哪一个（C1/C2/C3）

你想要怎么进行？
