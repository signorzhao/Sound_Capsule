import pandas as pd
import os
import glob
from pathlib import Path

def categorize_word(word_en):
    # 简单的启发式分类 (这是一个起点，后面可以用更强大的模型优化)
    # 动词通常具有动作感
    verbs = ['hit', 'strike', 'impact', 'smash', 'crash', 'burst', 'snap', 'crack', 'pop', 'click', 'rumble', 'vibrate', 'shake', 'flow', 'rush', 'sweep']
    # 名词通常是物体或地点
    nouns = ['wood', 'metal', 'water', 'stone', 'glass', 'forest', 'cave', 'stadium', 'room', 'zombie', 'demon', 'engine', 'machine', 'bird', 'animal']
    # 形容词通常是状态或感官
    adjectives = ['dark', 'bright', 'warm', 'cold', 'soft', 'hard', 'gritty', 'smooth', 'heavy', 'light', 'ethereal', 'ominous', 'peaceful']

    w = word_en.lower()
    if any(v in w for v in verbs): return 'verb'
    if any(n in w for n in nouns): return 'noun'
    if any(a in w for a in adjectives): return 'adjective'
    
    # 默认分类补丁
    return 'adjective' # 默认先给形容词，因为目前用户最在意质感

def process_lexicons():
    all_data = []
    lexicon_files = glob.glob('lexicon_*.csv')
    
    print(f"发现 {len(lexicon_files)} 个词库文件")
    
    for f in lexicon_files:
        if 'test' in f: continue
        try:
            df = pd.read_csv(f, on_bad_lines='skip', comment='#')
            # 确保列名统一
            df.columns = [c.strip() for c in df.columns]
            all_data.append(df)
        except Exception as e:
            print(f"跳过文件 {f}: {e}")

    if not all_data:
        print("未找到有效数据")
        return

    master_df = pd.concat(all_data).drop_duplicates(subset=['word_en'])
    
    # 自动打标签
    print("正在进行语义分类...")
    master_df['category'] = master_df['word_en'].apply(categorize_word)
    
    # 保存总表
    output_path = 'master_lexicon_v3.csv'
    master_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"已生成总词库: {output_path} (共 {len(master_df)} 词)")

if __name__ == "__main__":
    process_lexicons()
