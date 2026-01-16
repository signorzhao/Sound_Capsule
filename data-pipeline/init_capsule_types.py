#!/usr/bin/env python3
"""
初始化胶囊类型表

创建 capsule_types 表并插入默认数据
"""

import sqlite3
import json

def init_capsule_types():
    conn = sqlite3.connect('database/capsules.db')
    cursor = conn.cursor()

    # 创建胶囊类型表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS capsule_types (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_cn TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            color TEXT NOT NULL,
            gradient TEXT NOT NULL,
            examples TEXT,
            priority_lens TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 插入默认胶囊类型
    default_types = [
        {
            'id': 'magic',
            'name': 'MAGIC',
            'name_cn': '魔法',
            'description': '神秘、梦幻、超自然',
            'icon': 'Sparkles',
            'color': '#8B5CF6',
            'gradient': 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)',
            'examples': json.dumps(['粒子合成', '调制噪声', '演变音色'], ensure_ascii=False),
            'priority_lens': 'texture',
            'sort_order': 1
        },
        {
            'id': 'impact',
            'name': 'IMPACT',
            'name_cn': '打击',
            'description': '强力、冲击、震撼',
            'icon': 'Flame',
            'color': '#EF4444',
            'gradient': 'linear-gradient(135deg, #EF4444 0%, #F59E0B 100%)',
            'examples': json.dumps(['鼓点', '打击乐', '贝斯拨奏'], ensure_ascii=False),
            'priority_lens': 'texture',
            'sort_order': 2
        },
        {
            'id': 'atmosphere',
            'name': 'ATMOSPHERE',
            'name_cn': '环境',
            'description': '空间、氛围、场景',
            'icon': 'Music',
            'color': '#10B981',
            'gradient': 'linear-gradient(135deg, #10B981 0%, #06B6D4 100%)',
            'examples': json.dumps(['Pad', '氛围纹理', '音景'], ensure_ascii=False),
            'priority_lens': 'atmosphere',
            'sort_order': 3
        }
    ]

    for capsule_type in default_types:
        cursor.execute('''
            INSERT OR REPLACE INTO capsule_types
            (id, name, name_cn, description, icon, color, gradient, examples, priority_lens, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            capsule_type['id'],
            capsule_type['name'],
            capsule_type['name_cn'],
            capsule_type['description'],
            capsule_type['icon'],
            capsule_type['color'],
            capsule_type['gradient'],
            capsule_type['examples'],
            capsule_type['priority_lens'],
            capsule_type['sort_order']
        ))

    conn.commit()
    conn.close()

    print("✅ 胶囊类型表初始化完成")
    print(f"   插入了 {len(default_types)} 个默认胶囊类型")

if __name__ == '__main__':
    init_capsule_types()
