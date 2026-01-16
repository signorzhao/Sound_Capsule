#!/usr/bin/env python3
"""
词库合并工具 - 从 Core High Frequency 数据库补充词汇到各棱镜词库
"""

import csv
from pathlib import Path
from collections import defaultdict

# 定义棱镜分配规则
LENS_MAPPING = {
    # Texture (质感) - 情绪/质感/氛围相关
    "texture": {
        "categories": [
            "Texture", "Modifier/Mood", "Modifier/Sonic_Character", 
            "Horror/General", "Horror/Ambience", "Cinematic/Element",
            "Abstract/Design", "Sound_Word/Electronic", "Sound_Word/Friction_Break",
            "Audio_Process/Design"
        ],
        "exclude_words": set()  # 已存在的词
    },
    # Source (源场) - 物理来源/动作/物体相关
    "source": {
        "categories": [
            "Impact", "Movement", "Nature", "Creature", "Weapons", 
            "Vehicles", "Industrial", "Foley", "Sports", "Tools",
            "Action", "Leisure", "Domestic/Kitchen", "Domestic/Bathroom",
            "Domestic/Utility", "Sound_Word/Impact_Dull", "Sound_Word/Metal_Glass",
            "Sound_Word/Liquid_Wet", "Sound_Word/Air_Wind"
        ],
        "exclude_words": set()
    },
    # Materiality (材质) - 空间/距离/材质相关
    "materiality": {
        "categories": [
            "Modifier/Perspective", "Modifier/Scale", "Ambience/Public",
            "Urban", "Office", "Domestic/LivingRoom", "Domestic/Office"
        ],
        "exclude_words": set()
    }
}

def load_existing_words(filepath):
    """加载现有词库中的英文词汇"""
    words = set()
    if not filepath.exists():
        return words
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('word_'):
                continue
            parts = line.split(',', 1)
            if len(parts) >= 2:
                # 提取英文词根（去除描述性后缀）
                en_word = parts[1].strip().split('-')[0].lower()
                words.add(en_word)
    return words

def load_core_hf(filepath):
    """加载 Core High Frequency 数据库"""
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = f"{row['Category']}/{row['SubCategory']}" if row['SubCategory'] != 'General' else row['Category']
            entries.append({
                'category': category,
                'en': row['English Keyword'].strip(),
                'cn': row['Chinese Keyword'].strip(),
                'full_category': f"{row['Category']}/{row['SubCategory']}"
            })
    return entries

def categorize_word(entry, lens_mapping):
    """判断一个词应该属于哪个棱镜"""
    category = entry['category']
    full_cat = entry['full_category']
    
    for lens, config in lens_mapping.items():
        for cat_pattern in config['categories']:
            if category.startswith(cat_pattern) or full_cat.startswith(cat_pattern):
                return lens
    return None

def main():
    base_path = Path(__file__).parent
    
    # 加载现有词库
    print("加载现有词库...")
    for lens in LENS_MAPPING:
        filepath = base_path / f"lexicon_{lens}.csv"
        existing = load_existing_words(filepath)
        LENS_MAPPING[lens]['exclude_words'] = existing
        print(f"  {lens}: {len(existing)} 个现有词汇")
    
    # 加载 Core HF
    print("\n加载 Core High Frequency 数据库...")
    core_hf = load_core_hf(base_path / "Core High Frequency - Ver 1.0.csv")
    print(f"  共 {len(core_hf)} 个词条")
    
    # 分类统计
    new_words = defaultdict(list)
    skipped = 0
    
    for entry in core_hf:
        lens = categorize_word(entry, LENS_MAPPING)
        if lens is None:
            continue
        
        # 检查是否已存在
        en_word_lower = entry['en'].lower().replace(' ', '-')
        if en_word_lower in LENS_MAPPING[lens]['exclude_words']:
            skipped += 1
            continue
        
        new_words[lens].append(entry)
    
    # 输出统计
    print(f"\n=== 可补充词汇统计 ===")
    print(f"跳过已存在: {skipped} 个")
    for lens, words in new_words.items():
        print(f"{lens}: {len(words)} 个新词")
    
    # 按类别分组输出
    print(f"\n=== 详细分类 ===")
    for lens, words in new_words.items():
        print(f"\n--- {lens.upper()} ---")
        by_category = defaultdict(list)
        for w in words:
            by_category[w['full_category']].append(w)
        
        for cat in sorted(by_category.keys()):
            items = by_category[cat]
            print(f"  {cat}: {len(items)} 词")
            # 显示前5个
            for item in items[:3]:
                print(f"    - {item['cn']} ({item['en']})")
            if len(items) > 3:
                print(f"    ... 还有 {len(items)-3} 词")
    
    # 生成补充内容
    print(f"\n=== 生成补充文件 ===")
    for lens, words in new_words.items():
        output_file = base_path / f"supplement_{lens}.csv"
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            f.write("word_cn,word_en\n")
            
            by_category = defaultdict(list)
            for w in words:
                by_category[w['full_category']].append(w)
            
            for cat in sorted(by_category.keys()):
                f.write(f"# === {cat} ===\n")
                for item in by_category[cat]:
                    # 处理英文：替换空格为连字符
                    en = item['en'].replace(' ', '-')
                    cn = item['cn'].split('/')[0]  # 取第一个中文词
                    f.write(f"{cn},{en}\n")
        
        print(f"  已生成: {output_file.name} ({len(words)} 词)")

if __name__ == "__main__":
    main()


