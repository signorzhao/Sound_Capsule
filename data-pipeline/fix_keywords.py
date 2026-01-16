#!/usr/bin/env python3
"""
手动修复胶囊关键词聚合问题

1. 为现有胶囊聚合 keywords 字段
2. 检查前端发送的数据格式
"""

import sqlite3
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from capsule_db import CapsuleDatabase

DB_PATH = "database/capsules.db"

def fix_existing_capsules():
    """为所有现有胶囊聚合关键词"""
    db = CapsuleDatabase(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取所有有标签但没有 keywords 的胶囊
    cursor.execute("""
        SELECT DISTINCT c.id, c.name, c.keywords
        FROM capsules c
        INNER JOIN capsule_tags ct ON c.id = ct.capsule_id
        WHERE c.keywords IS NULL OR c.keywords = ''
    """)

    capsules = cursor.fetchall()
    print(f"找到 {len(capsules)} 个需要修复的胶囊\n")

    for capsule_id, name, keywords in capsules:
        print(f"处理胶囊 {capsule_id}: {name}")
        print(f"  当前 keywords: {keywords}")

        # 调用聚合函数
        success = db.aggregate_and_update_keywords(capsule_id)

        if success:
            # 验证修复结果
            cursor.execute("SELECT keywords FROM capsules WHERE id = ?", (capsule_id,))
            new_keywords = cursor.fetchone()[0]
            print(f"  ✅ 修复后 keywords: {new_keywords}")
        else:
            print(f"  ❌ 修复失败")
        print()

    conn.close()
    print("修复完成！")

def check_tags_data():
    """检查标签数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查胶囊 92 的标签数据
    cursor.execute("""
        SELECT lens, word_id, word_cn, word_en
        FROM capsule_tags
        WHERE capsule_id = 92
    """)

    tags = cursor.fetchall()
    print(f"\n胶囊 92 的标签数据 ({len(tags)} 条):")
    for lens, word_id, word_cn, word_en in tags:
        print(f"  {lens}: word_id={word_id}, word_cn={word_cn}, word_en={word_en}")

    conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("胶囊关键词修复工具")
    print("=" * 60)

    check_tags_data()
    print("\n" + "=" * 60)
    fix_existing_capsules()
