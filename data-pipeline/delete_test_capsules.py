#!/usr/bin/env python3
"""
删除测试胶囊脚本
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import get_supabase_client

def main():
    print("=" * 60)
    print("删除测试胶囊")
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
        print(f"✓ 用户ID: {user_id}")

        # 查询本地胶囊数量
        cursor.execute("SELECT COUNT(*) FROM capsules")
        local_count = cursor.fetchone()[0]
        print(f"✓ 本地胶囊数量（删除前）: {local_count}")

        # 删除本地所有胶囊
        cursor.execute("DELETE FROM capsules")
        cursor.execute("DELETE FROM capsule_tags")
        cursor.execute("DELETE FROM capsule_coordinates")
        cursor.execute("DELETE FROM capsule_metadata")
        cursor.execute("DELETE FROM sync_status")
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM capsules")
        local_count_after = cursor.fetchone()[0]
        print(f"✓ 本地胶囊数量（删除后）: {local_count_after}")

        conn.close()

        # 连接云端
        supabase = get_supabase_client()
        if not supabase:
            print("✗ 无法连接云端（Supabase 客户端未初始化）")
            return

        # 查询云端胶囊数量
        cloud_count = supabase.get_capsule_count(user_id)
        print(f"✓ 云端胶囊数量（删除前）: {cloud_count if cloud_count is not None else 0}")

        # 删除云端所有胶囊
        try:
            result = supabase.client.table('cloud_capsules') \
                .delete() \
                .eq('user_id', user_id) \
                .execute()

            deleted_count = len(result.data) if result.data else 0
            print(f"✓ 已删除 {deleted_count} 个云端胶囊")

        except Exception as e:
            print(f"✗ 删除云端胶囊失败: {e}")

        # 再次查询云端胶囊数量
        cloud_count_after = supabase.get_capsule_count(user_id)
        print(f"✓ 云端胶囊数量（删除后）: {cloud_count_after if cloud_count_after is not None else 0}")

        print("\n✅ 清理完成！现在你可以重新上传胶囊进行测试。")

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)

if __name__ == '__main__':
    main()
