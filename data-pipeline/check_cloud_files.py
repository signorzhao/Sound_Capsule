#!/usr/bin/env python3
"""
详细检查云端存储文件
"""

import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import get_supabase_client

def main():
    print("=" * 60)
    print("详细检查云端存储文件")
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

    bucket_name = 'capsule-files'

    # 列出用户目录下的所有内容（递归）
    print(f"--- 云端存储文件列表 (bucket: {bucket_name}) ---\n")

    try:
        # 列出第一层
        result = supabase.client.storage.from_(bucket_name).list(path=user_id)

        if not result:
            print("(空)")
        else:
            for folder in result:
                folder_name = folder.get('name')
                print(f"📁 {folder_name}/")

                # 列出文件夹内的文件
                folder_path = f"{user_id}/{folder_name}"
                files = supabase.client.storage.from_(bucket_name).list(path=folder_path)

                if files:
                    for file_info in files:
                        file_name = file_info.get('name')
                        file_size = file_info.get('size', 0)
                        updated_at = file_info.get('updated_at', 'N/A')

                        print(f"  📄 {file_name}")
                        print(f"     大小: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
                        print(f"     更新: {updated_at}")

                        # 获取下载URL
                        file_path = f"{user_id}/{folder_name}/{file_name}"
                        file_url = f"{supabase.url}/storage/v1/object/{bucket_name}/{file_path}"
                        print(f"     URL: {file_url}")
                    print()
                else:
                    print(f"  (空文件夹)\n")

        print(f"✓ 列出完成")

    except Exception as e:
        print(f"✗ 列出文件失败: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)

if __name__ == '__main__':
    main()
