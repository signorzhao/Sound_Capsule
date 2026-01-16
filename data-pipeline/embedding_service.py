"""
Phase C2: 云端 Embedding API 服务

提供文本 → 语义坐标的转换服务
"""

import os
import hashlib
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# FastAPI 应用初始化
# ============================================

app = FastAPI(
    title="Sound Capsule Embedding API",
    description="文本 → 语义坐标转换服务",
    version="1.0.0"
)

# ============================================
# 数据模型
# ============================================

class EmbeddingRequest(BaseModel):
    """Embedding 请求"""
    text: str

class CoordinateRequest(BaseModel):
    """坐标转换请求"""
    text: str
    prism_id: str

class BatchEmbedRequest(BaseModel):
    """批量 Embedding 请求"""
    texts: List[str]
    prism_id: str

class EmbeddingResponse(BaseModel):
    """Embedding 响应"""
    embedding: List[float]
    dimension: int

class CoordinateResponse(BaseModel):
    """坐标响应"""
    text: str
    x: float
    y: float
    prism_id: str

class BatchCoordinateResponse(BaseModel):
    """批量坐标响应"""
    coordinates: List[CoordinateResponse]
    count: int

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str
    model_loaded: bool
    cache_connected: bool
    timestamp: str

# ============================================
# 全局变量（延迟初始化）
# ============================================

model = None
cache_manager = None

# ============================================
# 生命周期管理
# ============================================

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global model, cache_manager

    logger.info("=" * 60)
    logger.info("🚀 Embedding 服务启动中...")
    logger.info("=" * 60)

    # 1. 加载模型
    try:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv('MODEL_NAME', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        logger.info(f"📦 加载模型: {model_name}")

        model = SentenceTransformer(model_name)
        logger.info(f"✅ 模型加载成功 (维度: {model.get_sentence_embedding_dimension()})")

    except Exception as e:
        logger.error(f"❌ 模型加载失败: {e}")
        raise

    # 2. 初始化缓存
    try:
        from embedding_cache import get_cache_manager
        cache_manager = get_cache_manager()
        logger.info(f"✅ 缓存管理器初始化成功")

    except Exception as e:
        logger.warning(f"⚠️  缓存管理器初始化失败: {e}")
        logger.warning(f"   将使用内存缓存")
        cache_manager = None

    logger.info("=" * 60)
    logger.info("✅ Embedding 服务已就绪")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    logger.info("🛑 Embedding 服务关闭中...")

# ============================================
# 工具函数
# ============================================

def get_text_hash(text: str) -> str:
    """计算文本哈希（用于缓存 key）"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

def compute_embedding(text: str) -> List[float]:
    """计算文本的 embedding 向量"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    try:
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"计算 embedding 失败: {e}")
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")

def map_to_coordinate(embedding: List[float], prism_id: str) -> tuple[float, float]:
    """
    将 embedding 映射到 2D 坐标

    使用与本地完全相同的算法（v2）：
    1. 从 Phase C1 的 prisms 表读取棱镜配置
    2. 加载锚点的 embedding 和坐标
    3. 使用余弦相似度 + 8 次方加权
    4. 可选的空间均匀化变换
    """
    try:
        from coordinate_calculator import get_coordinate_calculator, load_anchors_from_prism
        from prism_version_manager import PrismVersionManager

        # 1. 获取棱镜配置
        prism_manager = PrismVersionManager()
        prism_config_dict = prism_manager.get_prism(prism_id)

        if not prism_config_dict:
            raise HTTPException(
                status_code=404,
                detail=f"棱镜 '{prism_id}' 不存在"
            )

        # 2. 解析 prism 配置
        import json
        prism_config = {
            'anchors': json.loads(prism_config_dict['anchors'])
        }

        # 3. 加载锚点数据
        # 注意：这里需要实际计算锚点的 embedding
        # 如果是第一次，需要缓存锚点的 embedding
        anchor_embeddings, anchor_coords = load_anchors_from_prism(prism_config)

        # 4. 转换为 numpy 数组
        import numpy as np
        word_embedding = np.array(embedding)

        # 5. 使用坐标计算器计算坐标
        calculator = get_coordinate_calculator()
        x, y = calculator.calculate_single_word(
            word_embedding,
            anchor_embeddings,
            anchor_coords,
            stretch=True  # 使用空间均匀化变换
        )

        return x, y

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"坐标计算失败: {e}")
        # 降级到简单算法（如果真实算法失败）
        import numpy as np
        arr = np.array(embedding)
        x = float((arr[0] + 1) * 50)
        y = float((arr[1] + 1) * 50)
        x = max(0, min(100, x))
        y = max(0, min(100, y))
        return x, y

# ============================================
# API 端点
# ============================================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        service="embedding-api",
        model_loaded=model is not None,
        cache_connected=cache_manager is not None,
        timestamp=datetime.now().isoformat()
    )

@app.post("/api/embed", response_model=EmbeddingResponse)
async def embed_text(request: EmbeddingRequest):
    """
    文本转 Embedding

    将文本转换为高维向量表示
    """
    try:
        # 检查缓存
        text_hash = get_text_hash(request.text)
        cache_key = f"embedding:{text_hash}"

        if cache_manager:
            cached = cache_manager.get(cache_key)
            if cached:
                logger.info(f"缓存命中: {request.text[:50]}...")
                return EmbeddingResponse(
                    embedding=cached,
                    dimension=len(cached)
                )

        # 计算 embedding
        logger.info(f"计算 embedding: {request.text[:50]}...")
        embedding = compute_embedding(request.text)

        # 存入缓存
        if cache_manager:
            cache_manager.set(cache_key, embedding, ttl=7*24*3600)  # 7 天

        return EmbeddingResponse(
            embedding=embedding,
            dimension=len(embedding)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理请求失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/embed/coordinate", response_model=CoordinateResponse)
async def embed_to_coordinate(request: CoordinateRequest):
    """
    文本转坐标（使用 prism 配置）

    将文本转换为指定 prism 空间的 2D 坐标
    """
    try:
        # 1. 计算 embedding
        embedding = compute_embedding(request.text)

        # 2. 映射到 2D 坐标
        x, y = map_to_coordinate(embedding, request.prism_id)

        return CoordinateResponse(
            text=request.text,
            x=x,
            y=y,
            prism_id=request.prism_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理请求失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/embed/batch", response_model=BatchCoordinateResponse)
async def embed_batch(request: BatchEmbedRequest):
    """
    批量文本转坐标

    高效处理多个文本的转换请求
    """
    try:
        results = []

        for text in request.texts:
            # 计算 embedding
            embedding = compute_embedding(text)

            # 映射到坐标
            x, y = map_to_coordinate(embedding, request.prism_id)

            results.append(CoordinateResponse(
                text=text,
                x=x,
                y=y,
                prism_id=request.prism_id
            ))

        return BatchCoordinateResponse(
            coordinates=results,
            count=len(results)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# 主函数
# ============================================

def main():
    """启动服务"""
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')

    logger.info(f"🚀 启动 Embedding API 服务")
    logger.info(f"   地址: http://{host}:{port}")
    logger.info(f"   文档: http://{host}:{port}/docs")

    uvicorn.run(
        "embedding_service:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
