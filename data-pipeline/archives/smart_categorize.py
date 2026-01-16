import pandas as pd
import numpy as np
import json
import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

def smart_categorize():
    # 1. 加载模型
    print("正在加载语义模型进行分类...")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # 2. 定义原型词 (Prototypes) - 增加覆盖面
    # 我们用这些词的平均向量作为类别的“北极星”
    prototypes = {
        "noun": [
            "object", "place", "location", "thing", "person", "creature", "material", 
            "room", "building", "instrument", "animal", "weapon", "nature", "vehicle",
            "cathedral", "lobby", "forest", "engine", "metal", "stone", "water", "gear"
        ],
        "verb": [
            "action", "movement", "process", "to do", "to make", "breaking", 
            "hitting", "falling", "sliding", "exploding", "crashing", "rumbling",
            "vibrating", "moving", "flowing", "acting"
        ],
        "adjective": [
            "quality", "feeling", "characteristic", "state", "description",
            "dark", "bright", "scary", "peaceful", "soft", "hard", "gritty",
            "ethereal", "ominous", "happy", "tense", "relaxed", "digital", "analog"
        ]
    }

    print("计算类目原型向量...")
    proto_embs = {}
    for cat, words in prototypes.items():
        embs = model.encode(words)
        proto_embs[cat] = np.mean(embs, axis=0)

    # 3. 读取现有总词库
    master_path = 'master_lexicon_v3.csv'
    if not os.path.exists(master_path):
        print(f"错误: 找不到 {master_path}")
        return

    df = pd.read_csv(master_path)
    
    # 4. 批量计算
    print(f"正在对 {len(df)} 个词汇进行语义分类...")
    word_list = df['word_en'].astype(str).tolist()
    word_embs = model.encode(word_list)

    new_categories = []
    
    # 获取原型矩阵
    proto_matrix = np.array([proto_embs['noun'], proto_embs['verb'], proto_embs['adjective']])
    cats = ['noun', 'verb', 'adjective']

    # 计算相似度
    sims = cosine_similarity(word_embs, proto_matrix)
    
    for i in range(len(word_list)):
        # 寻找契合度最高的类目
        best_cat_idx = np.argmax(sims[i])
        
        # 增加一点点偏置：如果相似度很接近，优先给形容词或名词
        # 因为在音效库中，形容词往往比动词更模糊
        new_categories.append(cats[best_cat_idx])

    df['category'] = new_categories

    # 5. 特殊修正：手动修复用户提到的词
    manual_fixes = {
        "lobby": "noun",
        "cathedral": "noun",
        "room": "noun",
        "reverb": "noun",
        "hall": "noun",
        "concert": "noun",
        "stadium": "noun",
        "studio": "noun",
        "closet": "noun",
        "bathroom": "noun",
        "office": "noun",
        "hospital": "noun",
        "factory": "noun",
        "warehouse": "noun",
        "tunnel": "noun",
        "church": "noun"
    }
    
    def apply_manual(row):
        w = str(row['word_en']).lower()
        for k, v in manual_fixes.items():
            if k in w: return v
        return row['category']

    df['category'] = df.apply(apply_manual, axis=1)

    # 保存
    df.to_csv(master_path, index=False, encoding='utf-8-sig')
    print(f"智能分类完成！结果已存回 {master_path}")

if __name__ == "__main__":
    smart_categorize()
