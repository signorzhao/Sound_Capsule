#!/usr/bin/env python3
"""
检查云端胶囊数据结构
"""

import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import get_supabase_client

def main():
    print("=" * 60)
    print("检查云端胶囊数据结构")
    print("=" * 60)

    # 获取用户ID
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'capsules.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT supabase_user_id FROM users WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()

    if not row or not row[0]:
        print("✗ 未找到用户ID，请先登录")
        return

    user_id = row[0]
    print(f"✓ 用户ID: {user_id}\n")

    conn.close()

    # 连接云端
    supabase = get_supabase_client()
    if not supabase:
        print("✗ 无法连接云端（Supabase 客户端未初始化）")
        return

    # 下载胶囊数据
    capsules = supabase.download_capsules(user_id)

    if not capsules:
        print("⚠ 云端没有胶囊")
        return

    print(f"✓ 云端胶囊数量: {len(capsules)}\n")

    for capsule in capsules:
        print(f"胶囊: {capsule.get('name')}")
        print(f"  - id (云端UUID): {capsule.get('id')}")
        print(f"  - capsule_local_id (本地ID): {capsule.get('capsule_local_id')}")
        print(f"  - file_path: {capsule.get('file_path')}")
        print(f"  - preview_audio: {capsule.get('preview_audio')}")
        print(f"  - rpp_file: {capsule.get('rpp_file')}")
        print(f"  - 元数据: {json.dumps(capsule.get('metadata'), indent=4, ensure_ascii=False)}")
        print()

    print("=" * 60)

if __name__ == '__main__':
    main()
