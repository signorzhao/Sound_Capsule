import pandas as pd
import numpy as np
import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

def refined_categorize():
    print("🚀 启动高级语义词性分类器...")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # 1. 强化的原型词库
    prototypes = {
        "noun": [
            "a place", "a location", "a building", "an object", "a material", "an entity",
            "cathedral", "lobby", "room", "hall", "studio", "forest", "engine", "metal",
            "water", "stone", "glass", "instrument", "machine", "animal", "creature",
            "texture", "timbre", "source", "materiality", "reverb", "space", "environment"
        ],
        "verb": [
            "to act", "to do", "an action", "a movement", "the process of",
            "hitting", "breaking", "moving", "sliding", "exploding", "vibrating",
            "crashing", "flowing", "acting", "striking", "bursting", "splitting"
        ],
        "adjective": [
            "a quality", "a characteristic", "a description", "a feeling", "a state",
            "dark", "bright", "soft", "hard", "gritty", "smooth", "ethereal", "ominous",
            "scary", "peaceful", "tense", "relaxed", "digital", "analog", "metallic",
            "wooden", "organic", "synthetic", "noisy", "quiet"
        ]
    }

    proto_embs = {cat: model.encode(words) for cat, words in prototypes.items()}
    
    # 2. 规则引擎 (优先级最高)
    def rule_based_check(row):
        en = str(row.get('word_en', '')).lower()
        cn = str(row.get('word_cn', '')).lower()
        hint = str(row.get('semantic_hint', '')).lower()
        
        # 常见名词后缀
        noun_indicators = ['room', 'hall', 'space', 'lobby', 'cathedral', 'building', 'studio', 'place', 'field', 'area', 'chamber', 'station', 'park', 'forest', 'cave', 'tunnel']
        # 在这里增加“混响”这类专业名词
        noun_keys = ['reverb', 'echo', 'delay', 'ambience', 'drone', 'pad', 'sub']
        
        # 只要描述中包含这些词，大概率是名词性描述
        combined = f"{en} {cn} {hint}"
        
        if any(x in combined for x in noun_indicators): return 'noun'
        if any(x in en for x in noun_keys): return 'noun'
        
        # 常见形容词后缀 (注意优先级)
        if en.endswith('less') or en.endswith('ous') or en.endswith('ish') or en.endswith('ery'):
            return 'adjective'
            
        return None

    # 3. 执行分类
    master_path = 'master_lexicon_v3.csv'
    df = pd.read_csv(master_path)
    
    print(f"正在分析 {len(df)} 个词汇...")
    word_list = df['word_en'].astype(str).tolist()
    word_embs = model.encode(word_list)

    final_cats = []
    for i, row in df.iterrows():
        # A. 规则优先
        rule_cat = rule_based_check(row)
        if rule_cat:
            final_cats.append(rule_cat)
            continue
            
        # B. 语义投票
        # 计算与每个原型组的平均相似度
        scores = {}
        for cat in ['noun', 'verb', 'adjective']:
            sim = cosine_similarity(word_embs[i].reshape(1, -1), proto_embs[cat])[0]
            scores[cat] = np.max(sim) # 取最大相似度作为参考

        # 针对音效库的微调：如果是 Living (起居室)，虽然 Living 语义偏动词，但最大相似度可能被 Noun 组的 place 吸引
        best_cat = max(scores, key=scores.get)
        final_cats.append(best_cat)

    df['category'] = final_cats

    # 4. 最后兜底：针对用户提到的特定词库结构修正
    # 比如：词库里很多 "Living" 其实对应的是 "Living Room"
    df.to_csv(master_path, index=False, encoding='utf-8-sig')
    print("✨ 分类器优化完成，已更新总词库。")

if __name__ == "__main__":
    refined_categorize()
