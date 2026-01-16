#!/usr/bin/env python3
"""
批量删除孤儿记录（数据库中有但文件系统中不存在的胶囊）
使用方法: python3 bulk_delete_orphans.py
"""

import sys
from pathlib import Path
from capsule_db import get_database

def find_orphaned_records():
    """找出所有孤儿记录"""
    db = get_database()
    capsules = db.get_all_capsules()

    orphaned = []
    for cap in capsules:
        capsule_id = cap['id']
        file_path = cap.get('file_path', '')

        if file_path:
            full_path = Path(file_path)
            if not full_path.exists():
                orphaned.append(capsule_id)

    return orphaned

def delete_capsule(capsule_id):
    """删除指定的胶囊记录"""
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

    return {
        'tags': tags_deleted,
        'coords': coords_deleted,
        'metadata': metadata_deleted,
        'capsule': capsule_deleted
    }

def bulk_delete_orphans(auto_confirm=False):
    """批量删除孤儿记录"""
    orphaned_ids = find_orphaned_records()

    if not orphaned_ids:
        print("✅ 没有发现孤儿记录")
        return

    print(f"发现 {len(orphaned_ids)} 个孤儿记录:")
    print(f"ID: {orphaned_ids}")
    print()

    if not auto_confirm:
        try:
            response = input("确认批量删除这些记录？(yes/no): ").strip().lower()
        except EOFError:
            print("\n检测到非交互模式，使用 --yes 参数自动确认")
            response = 'yes'
    else:
        response = 'yes'

    if response not in ['yes', 'y']:
        print("取消删除")
        return

    print("\n开始批量删除...\n")

    total_tags = 0
    total_coords = 0
    total_metadata = 0
    total_capsules = 0
    failed = []

    for capsule_id in orphaned_ids:
        try:
            result = delete_capsule(capsule_id)
            total_tags += result['tags']
            total_coords += result['coords']
            total_metadata += result['metadata']
            total_capsules += result['capsule']
            print(f"✅ ID {capsule_id}: 删除成功")
        except Exception as e:
            print(f"❌ ID {capsule_id}: 删除失败 - {e}")
            failed.append(capsule_id)

    print(f"\n{'='*60}")
    print(f"批量删除完成！")
    print(f"{'='*60}")
    print(f"总计:")
    print(f"   - 删除了 {total_capsules} 条胶囊记录")
    print(f"   - 删除了 {total_tags} 条标签记录")
    print(f"   - 删除了 {total_coords} 条坐标记录")
    print(f"   - 删除了 {total_metadata} 条元数据记录")

    if failed:
        print(f"\n❌ 失败的 ID: {failed}")

if __name__ == '__main__':
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    bulk_delete_orphans(auto_confirm=auto_confirm)
