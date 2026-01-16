#!/usr/bin/env python3
"""
删除指定的胶囊记录

使用方法: python3 delete_capsule.py <capsule_id>
"""

import sys
from capsule_db import get_database

def delete_capsule(capsule_id):
    """删除指定的胶囊记录"""
    db = get_database()

    # 检查胶囊是否存在
    capsule = db.get_capsule(capsule_id)
    if not capsule:
        print(f"❌ 胶囊 ID {capsule_id} 不存在")
        return False

    print(f"\n删除胶囊: {capsule['name']}")
    print(f"ID: {capsule['id']}")
    print(f"路径: {capsule.get('file_path', 'N/A')}")

    # 确认删除
    response = input("\n确认删除？(yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("取消删除")
        return False

    try:
        # 执行 SQL 删除
        import sqlite3
        conn = sqlite3.connect('database/capsules.db')
        cursor = conn.cursor()

        # 删除标签
        cursor.execute('DELETE FROM capsule_tags WHERE capsule_id = ?', (capsule_id,))
        tags_deleted = cursor.rowcount

        # 删除坐标
        cursor.execute('DELETE FROM capsule_coordinates WHERE capsule_id = ?', (capsule_id,))
        coords_deleted = cursor.rowcount

        # 删除元数据
        cursor.execute('DELETE FROM capsule_metadata WHERE capsule_id = ?', (capsule_id,))
        metadata_deleted = cursor.rowcount

        # 删除胶囊
        cursor.execute('DELETE FROM capsules WHERE id = ?', (capsule_id,))
        capsule_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        print(f"\n✅ 删除成功！")
        print(f"   - 删除了 {tags_deleted} 条标签记录")
        print(f"   - 删除了 {coords_deleted} 条坐标记录")
        print(f"   - 删除了 {metadata_deleted} 条元数据记录")
        print(f"   - 删除了 {capsule_deleted} 条胶囊记录")

        return True

    except Exception as e:
        print(f"\n❌ 删除失败: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python3 delete_capsule.py <capsule_id>")
        print("示例: python3 delete_capsule.py 51")
        sys.exit(1)

    try:
        capsule_id = int(sys.argv[1])
        delete_capsule(capsule_id)
    except ValueError:
        print(f"❌ 无效的胶囊 ID: {sys.argv[1]}")
        sys.exit(1)
