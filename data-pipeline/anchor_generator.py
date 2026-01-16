#!/usr/bin/env python3
"""
智能锚点生成器 - Anchor Generator
====================================
基于语义模型和轴标签，自动生成锚点建议
"""

import random
import re
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

# 尝试导入语义模型
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    ANCHOR_ML_AVAILABLE = True
except ImportError:
    ANCHOR_ML_AVAILABLE = False
    print("Warning: ML libraries not available. Anchor generation will use template method.")

# 路径配置
BASE_DIR = Path(__file__).parent
MASTER_LEXICON = BASE_DIR / "master_lexicon_v3.csv"


class AnchorGenerator:
    """智能锚点生成器"""

    def __init__(self):
        """初始化生成器"""
        self.model = None
        self.word_embeddings = None
        self.word_list = []

        if ANCHOR_ML_AVAILABLE:
            try:
                print("Loading semantic model...")
                self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
                self.load_lexicon()
                print(f"✓ AnchorGenerator ready: {len(self.word_list)} words loaded")
            except Exception as e:
                print(f"Warning: Failed to load model: {e}")
                # 设置实例标志，不修改全局变量
                self.model = None

    def load_lexicon(self):
        """加载主词库"""
        if not MASTER_LEXICON.exists():
            print(f"Warning: Master lexicon not found at {MASTER_LEXICON}")
            return

        import csv
        with open(MASTER_LEXICON, 'r', encoding='utf-8-sig') as f:  # utf-8-sig to handle BOM
            reader = csv.DictReader(f)
            for row in reader:
                # CSV 列名: word_cn, word_en, semantic_hint, category
                word = row.get('word_en', '').strip()
                if word:
                    self.word_list.append({
                        'en': word,
                        'cn': row.get('word_cn', word),
                        'pos': row.get('category', '')
                    })

        # 预计算词嵌入
        if self.model and self.word_list:
            texts = [w['en'] for w in self.word_list]
            self.word_embeddings = self.model.encode(texts, show_progress_bar=False)

    def extract_keywords(self, label: str) -> List[str]:
        """
        从轴标签中提取关键词

        Args:
            label: 轴标签，例如 "Dark / 黑暗恐惧" 或 "Light / 光明"

        Returns:
            关键词列表
        """
        # 移除括号内容，提取主要关键词
        # "Dark / 黑暗恐惧" -> ["Dark", "黑暗恐惧"]
        # "Dark / (黑暗)" -> ["Dark", "黑暗"]

        # 分割英文和中文
        parts = label.split(' / ')
        keywords = []

        for part in parts:
            part = part.strip()
            # 移除括号
            part = re.sub(r'^[\(\[]+|[\)\]]+$', '', part)
            if part:
                keywords.append(part)

        return keywords

    def find_similar_words(
        self,
        keywords: List[str],
        top_k: int = 5,
        pos_filter: List[str] = None,
        exclude_words: List[str] = None
    ) -> List[Dict]:
        """
        从词库中找到最相似的词

        Args:
            keywords: 关键词列表
            top_k: 返回前 K 个最相似的词
            pos_filter: 词性过滤列表，如 ['noun', 'verb', 'adjective']
            exclude_words: 要排除的词汇列表（用于避免重复）

        Returns:
            相似词列表
        """
        if not ANCHOR_ML_AVAILABLE or not self.model or not self.word_list:
            return []

        # 初始化排除词汇列表
        if exclude_words is None:
            exclude_words = []

        # 编码关键词
        keyword_embeddings = self.model.encode(keywords, show_progress_bar=False)

        # 计算与词库中所有词的相似度
        similarities = cosine_similarity(keyword_embeddings, self.word_embeddings)

        # 取平均相似度
        avg_similarities = similarities.mean(axis=0)

        # 过滤候选词
        candidate_indices = []
        for idx, word_obj in enumerate(self.word_list):
            word = word_obj['en']

            # 避免与关键词完全相同
            if word.lower() in [k.lower() for k in keywords]:
                continue

            # 避免与排除词汇重复
            if word.lower() in [w.lower() for w in exclude_words]:
                continue

            # 词性过滤
            if pos_filter and word_obj.get('pos'):
                # 标准化词性名称
                pos = word_obj.get('pos', '').lower().strip()
                if pos not in [p.lower() for p in pos_filter]:
                    continue

            candidate_indices.append(idx)

        # 按相似度排序候选词
        candidate_indices = sorted(
            candidate_indices,
            key=lambda idx: avg_similarities[idx],
            reverse=True
        )

        # 返回 top-k 结果
        results = []
        for idx in candidate_indices:
            if len(results) >= top_k:
                break
            word_obj = self.word_list[idx]
            results.append({
                'word': word_obj['en'],
                'zh': word_obj['cn'],
                'pos': word_obj.get('pos', ''),
                'similarity': float(avg_similarities[idx])
            })

        return results

    def generate_anchors_for_quadrant(
        self,
        x_label: str,
        y_label: str,
        x_direction: str,  # 'neg' or 'pos'
        y_direction: str,  # 'neg' or 'pos'
        count: int = 5,
        pos_filter: List[str] = None,
        exclude_words: List[str] = None
    ) -> List[Dict]:
        """
        为某个象限生成锚点

        Args:
            x_label: X轴标签
            y_label: Y轴标签
            x_direction: X方向 ('neg' or 'pos')
            y_direction: Y方向 ('neg' or 'pos')
            count: 生成锚点数量
            pos_filter: 词性过滤列表
            exclude_words: 要排除的词汇列表（避免重复）

        Returns:
            锚点列表
        """
        # 提取关键词
        x_keywords = self.extract_keywords(x_label)
        y_keywords = self.extract_keywords(y_label)

        # 组合关键词
        combined_keywords = x_keywords + y_keywords

        # 查找相似词（传入词性过滤和排除词汇）
        similar_words = self.find_similar_words(
            combined_keywords,
            top_k=count*3,
            pos_filter=pos_filter,
            exclude_words=exclude_words
        )

        # 确定象限位置
        x_center = 10 if x_direction == 'neg' else 90
        y_center = 10 if y_direction == 'neg' else 90

        # 生成锚点
        anchors = []
        for i, word_obj in enumerate(similar_words[:count]):
            # 在中心点周围添加随机偏移
            offset_x = random.gauss(0, 8)
            offset_y = random.gauss(0, 8)

            # 限制在 0-100 范围内
            x = max(5, min(95, x_center + offset_x))
            y = max(5, min(95, y_center + offset_y))

            anchors.append({
                'word': word_obj['word'],
                'x': round(x, 2),
                'y': round(y, 2),
                'zh': word_obj['zh'],
                'pos': word_obj.get('pos', '')
            })

        return anchors

    def generate_all_anchors(
        self,
        axes: Dict,
        count_per_quadrant: int = 5,
        pos_filter: List[str] = None
    ) -> List[Dict]:
        """
        为整个棱镜生成锚点（保证全局唯一性）

        Args:
            axes: 轴配置
                {
                    "x_label": {"neg": "...", "pos": "..."},
                    "y_label": {"neg": "...", "pos": "..."}
                }
            count_per_quadrant: 每个象限生成的锚点数量
            pos_filter: 词性过滤列表，如 ['noun', 'verb', 'adjective']

        Returns:
            锚点列表（总共 4 * count_per_quadrant 个，保证不重复）
        """
        all_anchors = []
        used_words = []  # 全局已使用的词汇列表

        x_neg = axes.get('x_label', {}).get('neg', 'Left')
        x_pos = axes.get('x_label', {}).get('pos', 'Right')
        y_neg = axes.get('y_label', {}).get('neg', 'Bottom')
        y_pos = axes.get('y_label', {}).get('pos', 'Top')

        # 四个象限
        quadrants = [
            (x_neg, y_neg, 'neg', 'neg'),  # 左下
            (x_pos, y_neg, 'pos', 'neg'),  # 右下
            (x_neg, y_pos, 'neg', 'pos'),  # 左上
            (x_pos, y_pos, 'pos', 'pos'),  # 右上
        ]

        for x_label, y_label, x_dir, y_dir in quadrants:
            # 为当前象限生成锚点，传入已使用的词汇以避免重复
            anchors = self.generate_anchors_for_quadrant(
                x_label, y_label, x_dir, y_dir, count_per_quadrant,
                pos_filter=pos_filter,
                exclude_words=used_words
            )
            all_anchors.extend(anchors)

            # 更新已使用词汇列表
            for anchor in anchors:
                used_words.append(anchor['word'])

        return all_anchors


# 全局实例
_generator_instance = None

def get_generator():
    """获取全局生成器实例"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = AnchorGenerator()
    return _generator_instance


if __name__ == '__main__':
    # 测试代码
    print("Anchor Generator Test")
    print("=" * 50)

    generator = get_generator()

    test_axes = {
        "x_label": {"neg": "Dark / 黑暗", "pos": "Light / 光明"},
        "y_label": {"neg": "Cold / 寒冷", "pos": "Warm / 温暖"}
    }

    print("\n测试生成锚点...")
    anchors = generator.generate_all_anchors(test_axes, count_per_quadrant=5)

    print(f"\n生成了 {len(anchors)} 个锚点:")
    for anchor in anchors:
        print(f"  - {anchor['word']} ({anchor['zh']}) at ({anchor['x']}, {anchor['y']})")
