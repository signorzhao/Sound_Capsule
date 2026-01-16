#!/usr/bin/env python3
"""
设置胶囊为所有登录用户可见
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import get_supabase_client

def main():
    print("=" * 60)
    print("设置胶囊为所有登录用户可见")
    print("=" * 60)

    supabase = get_supabase_client()
    if not supabase:
        print("❌ 无法连接云端")
        return

    # SQL 脚本
    sql_statements = [
        # 删除旧策略
        "DROP POLICY IF EXISTS \"Users can view own capsules\" ON cloud_capsules;",
        "DROP POLICY IF EXISTS \"Users can view own tags\" ON cloud_capsule_tags;",
        "DROP POLICY IF EXISTS \"Users can view own coordinates\" ON cloud_capsule_coordinates;",

        # 创建新策略
        """CREATE POLICY "Logged in users can view capsules"
          ON cloud_capsules
          FOR SELECT
          USING (auth.uid() IS NOT NULL);""",

        """CREATE POLICY "Logged in users can view tags"
          ON cloud_capsule_tags
          FOR SELECT
          USING (auth.uid() IS NOT NULL);""",

        """CREATE POLICY "Logged in users can view coordinates"
          ON cloud_capsule_coordinates
          FOR SELECT
          USING (auth.uid() IS NOT NULL);""",
    ]

    try:
        # 执行 SQL（通过 RPC 调用或直接执行）
        # 注意：Supabase Python 客户端不支持直接执行 DDL，需要使用 RPC

        print("\n⚠️ 请手动在 Supabase Dashboard 执行以下 SQL：\n")
        print("访问: https://supabase.com/dashboard/project/mngtddqjbbrdwwfxcvxg/sql")
        print("\n或者执行文件: data-pipeline/set_public_capsules.sql\n")

    except Exception as e:
        print(f"❌ 错误: {e}")

    print("=" * 60)

if __name__ == '__main__':
    main()
