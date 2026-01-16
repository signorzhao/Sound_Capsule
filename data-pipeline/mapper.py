#!/usr/bin/env python3
"""
Project Synesth - 语义向量映射器 v2
====================================
使用 Sentence-BERT 模型将声音形容词映射到二维语义空间。
支持每个透镜使用独立的专属词库。

用法:
    # 使用独立词库（推荐）
    python mapper.py --output sonic_vectors.json
    
    # 使用统一词库（兼容旧版）
    python mapper.py --input lexicon.csv --output sonic_vectors.json

依赖:
    pip install sentence-transformers pandas numpy

作者: Project Synesth
"""

import json
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# ==========================================
# 多透镜锚点定义 (ANCHORS)
# ==========================================

LENS_CONFIG = {
    "texture": {
        "name": "Texture / Timbre (质感)",
        "description": "声音的质感和情绪色彩",
        "lexicon_file": "lexicon_texture.csv",
        # X轴: Dark/Fear ← → Light/Healing
        "axis_x_neg": "dark horror scary fear terror nightmare death blood murder crime violence war destruction pain suffering torture evil demon monster ghost sinister menacing threatening dangerous",
        "axis_x_pos": "light bright beautiful lovely peaceful serene tranquil calm soothing healing therapeutic pure clean fresh gentle soft warm comforting relaxing meditation zen spiritual divine sacred holy angelic heaven",
        # Y轴: Realistic/Serious ← → Playful/Fun
        "axis_y_neg": "realistic serious dramatic cinematic documentary film movie authentic genuine raw organic natural acoustic real professional studio high-fidelity serious tense suspense thriller",
        "axis_y_pos": "playful fun cartoon game arcade toy child kid cute adorable silly goofy funny comic humorous whimsical bouncy springy bubble candy sweet colorful rainbow magical fantasy fairy unicorn nintendo 8-bit retro pixel"
    },
    "source": {
        "name": "Source & Physics (源场)",
        "description": "声音的物理特征与来源属性",
        "lexicon_file": "lexicon_source.csv",
        # X轴: Static/Drone ← → Transient/Impact
        "axis_x_neg": "static drone pad ambient sustained continuous endless loop humming droning steady constant background bed layer texture atmosphere evolving",
        "axis_x_pos": "transient impact hit punch attack burst snap crack pop click bang boom smash crash instant sudden sharp percussive one-shot",
        # Y轴: Organic/Natural ← → Sci-Fi/Synth
        "axis_y_neg": "organic natural real acoustic foley field-recording authentic earthy wooden animal human nature creature wildlife bird insect water wind fire rain forest",
        "axis_y_pos": "synthetic digital electronic sci-fi futuristic robotic mechanical artificial processed cyber tech laser plasma energy beam glitch data computer spaceship robot"
    },
    "materiality": {
        "name": "Materiality / Room (材质)",
        "description": "声音的空间材质与距离特征",
        "lexicon_file": "lexicon_materiality.csv",
        # X轴: Close/Dry(贴耳干涩) ← → Distant/Wet(遥远湿润)
        "axis_x_neg": "close proximity near intimate whisper ear direct dry anechoic booth studio recording isolation upfront present focused tight small-room confined no-reverb dead-room",
        "axis_x_pos": "distant far away reverb reverberation echo long-reverb hall cathedral canyon cave vast spacious open wide diffused atmospheric immersive long-tail large-space stadium arena",
        # Y轴: Cold/Reflective(冷硬反射) ← → Warm/Absorbent(暖软吸音)
        "axis_y_neg": "cold frozen ice metallic metal glass tile ceramic steel concrete stone marble clinical surgical sterile industrial reflective hard bright harsh sharp ringing high-frequency tinny bathroom hospital",
        "axis_y_pos": "warm cozy soft fabric blanket carpet wood wooden cabin forest cloth cotton velvet muffled muted dull dampened absorbed absorptive low-frequency bass underwater mud muddy dark bedroom living-room"
    }
}


def normalize_to_percent(values):
    """将值归一化到 0-100 范围"""
    min_val = np.min(values)
    max_val = np.max(values)
    if max_val - min_val == 0:
        return np.full_like(values, 50.0)
    return ((values - min_val) / (max_val - min_val)) * 100


def compute_axis_score(word_embedding, pos_embedding, neg_embedding):
    """
    计算词汇在某个轴上的得分
    返回值: 正值表示更接近 pos，负值表示更接近 neg
    """
    sim_pos = cosine_similarity(word_embedding.reshape(1, -1), pos_embedding.reshape(1, -1))[0][0]
    sim_neg = cosine_similarity(word_embedding.reshape(1, -1), neg_embedding.reshape(1, -1))[0][0]
    return sim_pos - sim_neg


def load_lexicon(file_path):
    """加载词库文件，跳过注释行"""
    if not file_path.exists():
        return None
    
    # 读取文件，跳过以 # 开头的注释行
    lines = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                lines.append(stripped)
    
    if len(lines) < 2:  # 至少需要表头和一行数据
        return None
    
    # 解析 CSV
    from io import StringIO
    csv_content = '\n'.join(lines)
    df = pd.read_csv(StringIO(csv_content))
    
    # 验证列
    required_cols = ["word_cn", "word_en"]
    for col in required_cols:
        if col not in df.columns:
            print(f"  警告: CSV 缺少必要列 '{col}'")
            return None
    
    # 清洗数据
    df = df.dropna(subset=required_cols)
    df = df.drop_duplicates(subset=["word_en"])
    
    return df


def process_lens(model, lens_key, lens_config, words_df):
    """处理单个透镜的所有词汇"""
    print(f"\n{'='*50}")
    print(f"处理透镜: {lens_config['name']}")
    print(f"词汇数量: {len(words_df)}")
    print(f"{'='*50}")
    
    # 编码锚点
    print("  编码锚点句子...")
    emb_x_neg = model.encode(lens_config["axis_x_neg"])
    emb_x_pos = model.encode(lens_config["axis_x_pos"])
    emb_y_neg = model.encode(lens_config["axis_y_neg"])
    emb_y_pos = model.encode(lens_config["axis_y_pos"])
    
    points = []
    raw_x_scores = []
    raw_y_scores = []
    
    # 处理每个词汇
    total = len(words_df)
    for idx, row in words_df.iterrows():
        word_en = row['word_en']
        word_cn = row['word_cn']
        
        # 编码词汇 (使用英文)
        word_emb = model.encode(word_en)
        
        # 计算轴得分
        x_score = compute_axis_score(word_emb, emb_x_pos, emb_x_neg)
        y_score = compute_axis_score(word_emb, emb_y_pos, emb_y_neg)
        
        raw_x_scores.append(x_score)
        raw_y_scores.append(y_score)
        
        points.append({
            "word": word_en,
            "zh": word_cn,
            "raw_x": float(x_score),
            "raw_y": float(y_score)
        })
        
        if (idx + 1) % 50 == 0 or idx + 1 == total:
            print(f"  进度: {idx + 1}/{total}")
    
    # 归一化到 0-100
    print("  归一化坐标...")
    x_normalized = normalize_to_percent(np.array(raw_x_scores))
    y_normalized = normalize_to_percent(np.array(raw_y_scores))
    
    for i, point in enumerate(points):
        point["x"] = round(float(x_normalized[i]), 1)
        point["y"] = round(float(y_normalized[i]), 1)
        del point["raw_x"]
        del point["raw_y"]
    
    print(f"  ✅ 完成!")
    
    return {
        "name": lens_config["name"],
        "description": lens_config["description"],
        "axes": {
            "x_neg": lens_config["axis_x_neg"].split()[0].title(),
            "x_pos": lens_config["axis_x_pos"].split()[0].title(),
            "y_neg": lens_config["axis_y_neg"].split()[0].title(),
            "y_pos": lens_config["axis_y_pos"].split()[0].title()
        },
        "points": points
    }


def main():
    parser = argparse.ArgumentParser(
        description="Project Synesth - 语义向量映射器 v2"
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="统一词库 CSV 文件路径 (可选，不指定则使用各透镜独立词库)"
    )
    parser.add_argument(
        "--output", "-o",
        default="sonic_vectors.json",
        help="输出 JSON 文件路径 (默认: sonic_vectors.json)"
    )
    parser.add_argument(
        "--model", "-m",
        default="paraphrase-multilingual-MiniLM-L12-v2",
        help="Sentence-BERT 模型名称"
    )
    parser.add_argument(
        "--lenses", "-l",
        nargs="+",
        default=["texture", "source", "materiality"],
        help="要处理的透镜 (默认: texture source materiality)"
    )
    
    args = parser.parse_args()
    
    # 确定词库模式
    use_unified_lexicon = args.input is not None
    
    if use_unified_lexicon:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"错误: 找不到输入文件 '{input_path}'")
            return 1
        print(f"模式: 统一词库")
        print(f"读取词库: {input_path}")
        unified_df = load_lexicon(input_path)
        if unified_df is None:
            print("错误: 无法加载词库")
            return 1
        print(f"词库包含 {len(unified_df)} 个有效词汇")
    else:
        print("模式: 独立词库 (每个透镜使用专属词库)")
    
    # 加载模型
    print(f"\n加载模型: {args.model}")
    model = SentenceTransformer(args.model)
    print("模型加载完成!")
    
    # 处理每个透镜
    output_data = {}
    total_words = 0
    
    for lens_key in args.lenses:
        if lens_key not in LENS_CONFIG:
            print(f"警告: 未知透镜 '{lens_key}'，跳过")
            continue
        
        lens_config = LENS_CONFIG[lens_key]
        
        # 获取词库
        if use_unified_lexicon:
            df = unified_df
        else:
            lexicon_path = Path(lens_config["lexicon_file"])
            df = load_lexicon(lexicon_path)
            if df is None:
                print(f"警告: 找不到透镜 '{lens_key}' 的词库文件 '{lexicon_path}'，跳过")
                continue
        
        # 处理透镜
        lens_result = process_lens(model, lens_key, lens_config, df)
        output_data[lens_key] = lens_result
        total_words += len(lens_result["points"])
    
    # 保存结果
    output_path = Path(args.output)
    print(f"\n保存结果到: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*50)
    print("✅ 处理完成!")
    print(f"   输出文件: {output_path}")
    print(f"   透镜数量: {len(output_data)}")
    print(f"   总词汇数: {total_words}")
    for lens_key, lens_data in output_data.items():
        print(f"     - {lens_key}: {len(lens_data['points'])} 词")
    print("="*50)
    
    return 0


if __name__ == "__main__":
    exit(main())
