#!/usr/bin/env python3
"""
检查云端存储内容
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import get_supabase_client

def main():
    print("=" * 60)
    print("检查云端存储内容")
    print("=" * 60)

    try:
        # 读取本地用户ID
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), 'database', 'capsules.db')

        if not os.path.exists(db_path):
            print(f"✗ 本地数据库不存在: {db_path}")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 查询用户ID（从users表）
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

        # 列出存储桶中的文件
        try:
            bucket_name = 'capsule-files'

            # 列出用户目录下的所有文件
            result = supabase.client.storage.from_(bucket_name).list(path=user_id)

            print(f"--- 云端存储文件列表 (bucket: {bucket_name}) ---")
            if result:
                for file_info in result:
                    print(f"\n📄 {file_info.get('name')}")
                    print(f"   大小: {file_info.get('size', 0):,} bytes")
                    print(f"   更新时间: {file_info.get('updated_at', 'N/A')}")

                    # 获取下载URL
                    file_path = f"{user_id}/{file_info.get('name')}"
                    file_url = f"{supabase.url}/storage/v1/object/{bucket_name}/{file_path}"
                    print(f"   URL: {file_url}")

                print(f"\n✓ 共 {len(result)} 个文件/文件夹")
            else:
                print("(空)")

        except Exception as e:
            print(f"✗ 列出文件失败: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)

if __name__ == '__main__':
    main()
