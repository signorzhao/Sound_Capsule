#!/usr/bin/env python3
"""
将旧格式 CSV (word_cn, word_en+semantic) 转换为新格式 (word_cn, word_en, semantic_hint)
"""

import re
from pathlib import Path

def convert_csv(input_file, output_file=None):
    """转换 CSV 格式"""
    if output_file is None:
        output_file = input_file
    
    lines = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            
            # 保留注释和空行
            if not line or line.startswith('#'):
                lines.append(line)
                continue
            
            # 处理表头
            if line.startswith('word_cn'):
                lines.append('word_cn,word_en,semantic_hint')
                continue
            
            # 解析数据行
            parts = line.split(',', 1)
            if len(parts) < 2:
                lines.append(line)
                continue
            
            word_cn = parts[0].strip()
            word_en_full = parts[1].strip()
            
            # 分离英文关键词和语义提示
            # 格式: "Keyword-Name semantic hint words"
            # 第一个空格之前是关键词，之后是语义提示
            en_parts = word_en_full.split(' ', 1)
            
            if len(en_parts) == 2:
                word_en = en_parts[0]
                semantic_hint = en_parts[1]
            else:
                word_en = en_parts[0]
                semantic_hint = ''
            
            lines.append(f'{word_cn},{word_en},{semantic_hint}')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    
    print(f'✅ 已转换: {input_file}')
    return len([l for l in lines if l and not l.startswith('#') and not l.startswith('word_')])

if __name__ == '__main__':
    base_dir = Path(__file__).parent
    
    csv_files = [
        'lexicon_texture.csv',
        'lexicon_source.csv', 
        'lexicon_materiality.csv'
    ]
    
    total = 0
    for csv_file in csv_files:
        filepath = base_dir / csv_file
        if filepath.exists():
            count = convert_csv(filepath)
            total += count
            print(f'   {count} 条记录')
    
    print(f'\n总计转换 {total} 条记录')


