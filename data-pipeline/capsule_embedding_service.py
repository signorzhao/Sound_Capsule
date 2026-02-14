"""
语义搜索：胶囊 embedding 构建与云端更新

- 主体向量：name + description + keywords（cloud_capsules.embedding）
- 标签向量：每个 tag 的 word_cn + word_en 单独向量（cloud_capsule_tags.embedding）
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 模型维度（paraphrase-multilingual-MiniLM-L12-v2）
EMBEDDING_DIM = 384


def get_embedding_for_body(name: str = "", description: str = "", keywords: str = "") -> Optional[List[float]]:
    """为主体（name + description + keywords）生成 embedding，不含 tags"""
    parts = []
    if name:
        parts.append(str(name).strip())
    if description:
        parts.append(str(description).strip())
    if keywords:
        parts.append(str(keywords).strip())
    text = " ".join(parts)
    if not text:
        return None
    return _get_embedding(text)


def get_embedding_for_tag(word_cn: str = "", word_en: str = "") -> Optional[List[float]]:
    """为单个标签（word_cn + word_en）生成 embedding"""
    parts = []
    if word_cn:
        parts.append(str(word_cn).strip())
    if word_en and str(word_en).strip() != str(word_cn or "").strip():
        parts.append(str(word_en).strip())
    text = " ".join(parts)
    if not text:
        return None
    return _get_embedding(text)


def _get_embedding(text: str) -> Optional[List[float]]:
    try:
        from hybrid_embedding_service import get_hybrid_service
        service = get_hybrid_service()
        emb = service.get_embedding(text)
        if emb and len(emb) == EMBEDDING_DIM:
            return emb
        return None
    except Exception as e:
        logger.error(f"生成 embedding 失败: {e}")
        return None


def compute_tag_level_embeddings(
    name: str = "",
    description: str = "",
    keywords: str = "",
    tags: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[List[float]], List[Optional[List[float]]]]:
    """
    计算主体向量和每个标签的向量。

    Returns:
        (body_embedding, [tag_embedding_1, tag_embedding_2, ...])
    """
    body_emb = get_embedding_for_body(name=name, description=description, keywords=keywords)
    tag_embs = []
    if tags:
        for t in tags:
            tag_emb = get_embedding_for_tag(
                word_cn=t.get("word_cn") or "",
                word_en=t.get("word_en") or "",
            )
            tag_embs.append(tag_emb)
    return body_emb, tag_embs


def build_search_text(
    name: str = "",
    description: str = "",
    keywords: str = "",
    tags: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    构建用于 embedding 的搜索文本（中英混合，便于语义搜索）

    Args:
        name: 胶囊名称
        description: 描述
        keywords: 聚合关键词（逗号分隔）
        tags: 标签列表，每项含 word_cn, word_en

    Returns:
        拼接后的文本，空格分隔
    """
    parts = []
    if name:
        parts.append(str(name).strip())
    if description:
        parts.append(str(description).strip())
    if keywords:
        parts.append(str(keywords).strip())
    if tags:
        for t in tags:
            w_cn = (t.get("word_cn") or "").strip()
            w_en = (t.get("word_en") or "").strip()
            if w_cn:
                parts.append(w_cn)
            if w_en and w_en != w_cn:
                parts.append(w_en)
    return " ".join(p for p in parts if p)


def get_embedding_for_capsule(
    name: str = "",
    description: str = "",
    keywords: str = "",
    tags: Optional[List[Dict[str, Any]]] = None,
) -> Optional[List[float]]:
    """
    为胶囊内容生成 embedding 向量

    Args:
        name, description, keywords, tags: 同 build_search_text

    Returns:
        384 维向量或 None
    """
    text = build_search_text(name=name, description=description, keywords=keywords, tags=tags)
    if not text:
        logger.debug("胶囊搜索文本为空，跳过 embedding")
        return None
    try:
        from hybrid_embedding_service import get_hybrid_service
        service = get_hybrid_service()
        emb = service.get_embedding(text)
        if emb is not None and len(emb) != EMBEDDING_DIM:
            logger.warning(f"embedding 维度异常: {len(emb)} != {EMBEDDING_DIM}")
            return None
        return emb
    except Exception as e:
        logger.error(f"生成胶囊 embedding 失败: {e}")
        return None


def update_embedding_for_cloud_capsule(
    supabase_client,
    cloud_capsule_id: str,
    name: str = "",
    description: str = "",
    keywords: str = "",
    tags: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, List[Optional[List[float]]]]:
    """
    标签级向量化：计算主体向量 + 标签向量。

    - 主体向量写入 cloud_capsules.embedding
    - 返回 tag_embeddings 供调用方传入 upload_tags（调用方需在 upload_tags 前调用本函数）

    Returns:
        (是否成功, tag_embeddings)
    """
    body_emb, tag_embs = compute_tag_level_embeddings(
        name=name, description=description, keywords=keywords, tags=tags
    )
    try:
        if body_emb:
            supabase_client.update_capsule_embedding(cloud_capsule_id, body_emb)
        return True, tag_embs
    except Exception as e:
        logger.error(f"更新云端主体 embedding 失败 {cloud_capsule_id}: {e}")
        return False, tag_embs


def get_tag_embeddings_for_upload(
    name: str = "",
    description: str = "",
    keywords: str = "",
    tags: Optional[List[Dict[str, Any]]] = None,
) -> List[Optional[List[float]]]:
    """
    计算标签向量列表，供 upload_tags 使用。
    调用方应在 upload_tags 时传入 tag_embeddings=result。
    """
    _, tag_embs = compute_tag_level_embeddings(
        name=name, description=description, keywords=keywords, tags=tags
    )
    return tag_embs
