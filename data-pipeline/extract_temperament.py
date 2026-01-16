#!/usr/bin/env python3
"""
从现有词库提取与 Temperament（性情）相关的词汇
四象限定义：
- X轴: Cold (数字/冷静/极简) ← → Hot (模拟/热烈/失真)
- Y轴: Relaxed (松弛/平滑/有序) ← → Tense (紧张/混乱/躁动)
"""

import csv
from pathlib import Path

# 定义四象限的关键词模式
QUADRANTS = {
    'TL': {  # Cold + Relaxed = 数字极简 + 松弛平滑
        'name': 'Digital Minimal',
        'hint': 'cold digital minimal relaxed smooth calm',
        'keywords': [
            'clean', 'pure', 'crystal', 'clear', 'minimal', 'sterile', 'precise',
            'digital', 'electronic', 'synthetic', 'processed', 'clinical',
            'smooth', 'soft', 'gentle', 'quiet', 'subtle', 'delicate', 'light',
            'airy', 'ambient', 'pad', 'drone', 'sustained', 'floating',
            'cold', 'cool', 'icy', 'frozen', 'crisp', 'thin', 'bright'
        ]
    },
    'TR': {  # Hot + Relaxed = 模拟温暖 + 松弛平滑
        'name': 'Analog Warm',
        'hint': 'hot analog warm relaxed mellow vintage',
        'keywords': [
            'warm', 'vintage', 'retro', 'analog', 'tube', 'valve', 'tape',
            'mellow', 'smooth', 'rich', 'full', 'round', 'fat', 'thick',
            'organic', 'natural', 'acoustic', 'wooden', 'earthy',
            'cozy', 'comfortable', 'soft', 'gentle', 'relaxed', 'laid-back',
            'lush', 'saturated', 'colored', 'harmonic'
        ]
    },
    'BL': {  # Cold + Tense = 数字极简 + 紧张躁动
        'name': 'Digital Harsh',
        'hint': 'cold digital tense harsh glitch',
        'keywords': [
            'glitch', 'digital', 'bit', 'pixel', 'data', 'binary', 'code',
            'sharp', 'harsh', 'hard', 'aggressive', 'attack', 'cutting',
            'noise', 'static', 'interference', 'error', 'corrupt', 'broken',
            'tense', 'nervous', 'anxious', 'restless', 'chaotic', 'random',
            'metallic', 'robotic', 'mechanical', 'industrial', 'machine',
            'fast', 'quick', 'rapid', 'stutter', 'glitchy'
        ]
    },
    'BR': {  # Hot + Tense = 模拟热烈 + 紧张躁动
        'name': 'Analog Aggressive',
        'hint': 'hot analog tense aggressive distorted',
        'keywords': [
            'distorted', 'distortion', 'overdrive', 'overdriven', 'saturate',
            'fuzzy', 'fuzz', 'crunchy', 'crunch', 'gritty', 'dirty', 'filthy',
            'aggressive', 'intense', 'powerful', 'loud', 'heavy', 'massive',
            'punchy', 'punching', 'driving', 'energetic', 'explosive',
            'raw', 'rough', 'brutal', 'fierce', 'wild', 'chaotic',
            'growl', 'scream', 'roar', 'rumble', 'thunder'
        ]
    }
}

def load_core_keywords():
    """从 Core High Frequency 加载关键词"""
    filepath = Path(__file__).parent / "Core High Frequency - Ver 1.0.csv"
    words = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            words.append({
                'en': row['English Keyword'],
                'cn': row['Chinese Keyword'],
                'category': row['Category'],
                'subcategory': row['SubCategory']
            })
    
    return words

def load_existing_lexicons():
    """加载现有棱镜词库，避免重复"""
    existing = set()
    base_dir = Path(__file__).parent
    
    for lexicon in ['lexicon_texture.csv', 'lexicon_source.csv', 'lexicon_materiality.csv']:
        filepath = base_dir / lexicon
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip() and not line.startswith('#') and not line.startswith('word_'):
                        parts = line.split(',')
                        if len(parts) >= 2:
                            existing.add(parts[1].strip().lower())
    
    return existing

def classify_word(word_en, word_cn):
    """将词汇分类到四象限"""
    word_lower = word_en.lower()
    
    scores = {'TL': 0, 'TR': 0, 'BL': 0, 'BR': 0}
    
    for quadrant, info in QUADRANTS.items():
        for keyword in info['keywords']:
            if keyword in word_lower or word_lower in keyword:
                scores[quadrant] += 1
    
    # 返回得分最高的象限
    max_score = max(scores.values())
    if max_score == 0:
        return None
    
    for q, s in scores.items():
        if s == max_score:
            return q
    
    return None

def get_manual_words():
    """手动定义的 Temperament 词汇"""
    return {
        'TL': [  # Cold + Relaxed = 数字极简 + 松弛平滑
            ('纯净', 'Pure'), ('水晶', 'Crystal'), ('极简', 'Minimal'),
            ('精确', 'Precise'), ('临床感', 'Clinical'), ('无菌', 'Sterile'),
            ('空灵', 'Ethereal'), ('飘渺', 'Floating'), ('透明', 'Transparent'),
            ('数字', 'Digital'), ('电子', 'Electronic'), ('合成', 'Synthetic'),
            ('平滑', 'Smooth'), ('丝滑', 'Silky'), ('柔顺', 'Sleek'),
            ('冰冷', 'Icy'), ('冰晶', 'Frozen'), ('清脆', 'Crisp'),
            ('细腻', 'Fine'), ('精致', 'Refined'), ('洁净', 'Clean'),
            ('轻盈', 'Light'), ('稀薄', 'Thin'), ('明亮', 'Bright'),
            ('静谧', 'Serene'), ('宁静', 'Tranquil'), ('安详', 'Peaceful'),
        ],
        'TR': [  # Hot + Relaxed = 模拟温暖 + 松弛平滑
            ('温暖', 'Warm'), ('复古', 'Vintage'), ('怀旧', 'Retro'),
            ('模拟', 'Analog'), ('电子管', 'Tube'), ('磁带', 'Tape'),
            ('柔和', 'Mellow'), ('圆润', 'Round'), ('丰满', 'Full'),
            ('有机', 'Organic'), ('自然', 'Natural'), ('原木', 'Woody'),
            ('舒适', 'Cozy'), ('惬意', 'Comfortable'), ('放松', 'Relaxed'),
            ('饱和', 'Saturated'), ('着色', 'Colored'), ('染色', 'Tinted'),
            ('厚实', 'Thick'), ('肥厚', 'Fat'), ('丰富', 'Rich'),
            ('慵懒', 'Lazy'), ('悠闲', 'Leisurely'), ('闲适', 'Easygoing'),
            ('蜂蜜', 'Honey'), ('奶油', 'Creamy'), ('丝绒', 'Velvet'),
        ],
        'BL': [  # Cold + Tense = 数字极简 + 紧张躁动
            ('故障', 'Glitch'), ('数码', 'Digital'), ('像素', 'Pixel'),
            ('尖锐', 'Sharp'), ('刺耳', 'Harsh'), ('刺激', 'Piercing'),
            ('噪声', 'Noise'), ('静电', 'Static'), ('干扰', 'Interference'),
            ('紧张', 'Tense'), ('焦虑', 'Anxious'), ('躁动', 'Restless'),
            ('机械', 'Mechanical'), ('机器', 'Machine'), ('机器人', 'Robotic'),
            ('快速', 'Fast'), ('急促', 'Rapid'), ('口吃', 'Stutter'),
            ('混乱', 'Chaotic'), ('随机', 'Random'), ('无序', 'Disordered'),
            ('金属', 'Metallic'), ('冷硬', 'Cold-hard'), ('锋利', 'Cutting'),
            ('错误', 'Error'), ('损坏', 'Corrupt'), ('破碎', 'Broken'),
        ],
        'BR': [  # Hot + Tense = 模拟热烈 + 紧张躁动
            ('失真', 'Distorted'), ('过载', 'Overdrive'), ('饱和失真', 'Saturate'),
            ('绒毛', 'Fuzzy'), ('嘎吱', 'Crunchy'), ('粗糙', 'Gritty'),
            ('肮脏', 'Dirty'), ('污浊', 'Filthy'), ('浑浊', 'Muddy'),
            ('激进', 'Aggressive'), ('强烈', 'Intense'), ('强力', 'Powerful'),
            ('重型', 'Heavy'), ('巨大', 'Massive'), ('厚重', 'Weighty'),
            ('原始', 'Raw'), ('粗犷', 'Rough'), ('残暴', 'Brutal'),
            ('咆哮', 'Growl'), ('尖叫', 'Scream'), ('怒吼', 'Roar'),
            ('轰鸣', 'Rumble'), ('雷鸣', 'Thunder'), ('爆炸', 'Explosive'),
            ('狂野', 'Wild'), ('凶猛', 'Fierce'), ('狂暴', 'Furious'),
        ]
    }

def main():
    print("生成 Temperament 词库...\n")
    
    # 使用手动定义的词汇
    manual_words = get_manual_words()
    
    # 分类词汇
    classified = {'TL': [], 'TR': [], 'BL': [], 'BR': []}
    
    for q, words in manual_words.items():
        for cn, en in words:
            classified[q].append({'cn': cn, 'en': en})
    
    # 输出统计
    print("分类结果:")
    for q in ['TL', 'TR', 'BL', 'BR']:
        print(f"  {q} ({QUADRANTS[q]['name']}): {len(classified[q])} 词")
    
    # 生成词库文件
    output_file = Path(__file__).parent / "lexicon_temperament.csv"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("word_cn,word_en,semantic_hint\n")
        f.write("# ========== Temperament / 性情 词库 ==========\n")
        f.write("# X轴: Cold / 数字冷静 <-> Hot / 模拟热烈\n")
        f.write("# Y轴: Relaxed / 松弛平滑 <-> Tense / 紧张躁动\n")
        f.write("\n")
        
        for q in ['TL', 'TR', 'BL', 'BR']:
            f.write(f"# ===== {q} = {QUADRANTS[q]['name']} =====\n")
            for word in classified[q]:
                hint = QUADRANTS[q]['hint']
                f.write(f"{word['cn']},{word['en']},{hint}\n")
            f.write("\n")
    
    total = sum(len(classified[q]) for q in classified)
    print(f"\n✅ 已生成 {output_file}")
    print(f"   共 {total} 个词汇")

if __name__ == '__main__':
    main()

