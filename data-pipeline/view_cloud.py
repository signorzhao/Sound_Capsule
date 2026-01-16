#!/usr/bin/env python3
"""
临时脚本：查看云端胶囊数据
用于调试 remotePending 计算问题
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import get_supabase_client

def main():
    print("=" * 60)
    print("云端胶囊数据查看工具")
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
        print(f"✓ 本地胶囊数量: {local_count}")

        conn.close()

        # 连接云端
        supabase = get_supabase_client()
        if not supabase:
            print("✗ 无法连接云端（Supabase 客户端未初始化）")
            return

        # 查询云端胶囊数量
        cloud_count = supabase.get_capsule_count(user_id)
        print(f"✓ 云端胶囊数量: {cloud_count if cloud_count is not None else 0}")

        # 计算 remotePending
        if cloud_count is not None:
            remote_pending = max(0, cloud_count - local_count)
            print(f"\n--- 计算结果 ---")
            print(f"remotePending = max(0, {cloud_count} - {local_count}) = {remote_pending}")

            if remote_pending > 0:
                print(f"⚠️  应该显示蓝色图标，待下载 {remote_pending} 个胶囊")
            else:
                print(f"✓ 显示绿色图标（已同步或云端为空）")

        # 查询云端胶囊详情（前5个）
        print(f"\n--- 云端胶囊详情（前5个）---")
        try:
            result = supabase.client.table('cloud_capsules') \
                .select('id, name, created_at') \
                .eq('user_id', user_id) \
                .limit(5) \
                .execute()

            if result.data:
                for capsule in result.data:
                    print(f"  - [{capsule['id']}] {capsule.get('name', '(未命名)')} - {capsule.get('created_at', '')}")
                print(f"  ... 共 {len(result.data)} 个胶囊显示")
            else:
                print("  (云端没有胶囊)")
        except Exception as e:
            print(f"✗ 查询云端胶囊详情失败: {e}")

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)

if __name__ == '__main__':
    main()
