#!/usr/bin/env python3
"""
将复合英文词（如 Bone-chilling）拆分：
- 第一个词作为 word_en（如 Bone）
- 其余部分加入 semantic_hint（如 chilling）
"""

from pathlib import Path

def split_compound(input_file, output_file=None):
    """拆分复合词"""
    if output_file is None:
        output_file = input_file
    
    lines = []
    modified_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            
            # 保留注释、空行、表头
            if not line or line.startswith('#') or line.startswith('word_cn'):
                lines.append(line)
                continue
            
            # 解析数据行
            parts = line.split(',')
            if len(parts) < 2:
                lines.append(line)
                continue
            
            word_cn = parts[0].strip()
            word_en = parts[1].strip()
            semantic_hint = parts[2].strip() if len(parts) >= 3 else ''
            
            # 检查是否是复合词（包含 -）
            if '-' in word_en:
                en_parts = word_en.split('-')
                # 第一个词作为 word_en
                new_word_en = en_parts[0]
                # 其余部分加入 semantic_hint
                rest = ' '.join(en_parts[1:])
                if semantic_hint:
                    new_hint = rest + ' ' + semantic_hint
                else:
                    new_hint = rest
                
                lines.append(f'{word_cn},{new_word_en},{new_hint}')
                modified_count += 1
            else:
                lines.append(line)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    
    print(f'✅ 已处理: {input_file}')
    print(f'   修改了 {modified_count} 条复合词')
    return modified_count

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
            count = split_compound(filepath)
            total += count
    
    print(f'\n总计修改 {total} 条复合词')


