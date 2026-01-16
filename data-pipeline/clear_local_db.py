#!/usr/bin/env python3
"""
清空本地数据库脚本
用于测试下载功能
"""

import sys
import os
import sqlite3

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

def main():
    print("=" * 60)
    print("清空本地数据库")
    print("=" * 60)

    try:
        db_path = os.path.join(os.path.dirname(__file__), 'database', 'capsules.db')

        if not os.path.exists(db_path):
            print(f"✗ 本地数据库不存在: {db_path}")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 查询当前数据
        cursor.execute("SELECT COUNT(*) FROM capsules")
        capsule_count = cursor.fetchone()[0]
        print(f"✓ 本地胶囊数量（删除前）: {capsule_count}")

        cursor.execute("SELECT COUNT(*) FROM sync_status")
        sync_count = cursor.fetchone()[0]
        print(f"✓ 同步状态记录（删除前）: {sync_count}")

        # 清空所有表
        print("\n正在清空数据...")
        cursor.execute("DELETE FROM capsules")
        cursor.execute("DELETE FROM capsule_tags")
        cursor.execute("DELETE FROM capsule_coordinates")
        cursor.execute("DELETE FROM capsule_metadata")
        cursor.execute("DELETE FROM sync_status")

        conn.commit()

        # 验证删除结果
        cursor.execute("SELECT COUNT(*) FROM capsules")
        capsule_count_after = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sync_status")
        sync_count_after = cursor.fetchone()[0]

        print(f"✓ 本地胶囊数量（删除后）: {capsule_count_after}")
        print(f"✓ 同步状态记录（删除后）: {sync_count_after}")

        conn.close()

        print("\n✅ 本地数据库已清空！")
        print("现在点击同步按钮，应该会从云端下载胶囊。")

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)

if __name__ == '__main__':
    main()
