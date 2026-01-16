#!/usr/bin/env python3
"""
清理无效的胶囊记录

删除数据库中存在但文件系统中不存在的胶囊记录
"""

import sys
import os
from pathlib import Path
from capsule_db import get_database

def cleanup_orphaned_records():
    """清理孤儿记录"""
    db = get_database()
    capsules = db.get_all_capsules()

    print(f"数据库中共有 {len(capsules)} 个胶囊记录\n")

    orphaned = []
    for cap in capsules:
        capsule_id = cap['id']
        file_path = cap.get('file_path', '')

        # 检查文件夹是否存在
        if file_path:
            full_path = Path(file_path)
            if not full_path.exists():
                print(f"❌ ID {capsule_id}: {cap['name']} - 文件夹不存在")
                print(f"   路径: {file_path}")
                orphaned.append(capsule_id)
            else:
                print(f"✅ ID {capsule_id}: {cap['name']} - 存在")
        else:
            print(f"⚠️  ID {capsule_id}: {cap['name']} - 无文件路径")

    if not orphaned:
        print("\n✅ 所有胶囊记录都有效！")
        return

    print(f"\n发现 {len(orphaned)} 个孤儿记录:")
    print(f"ID: {orphaned}")

    # 询问是否删除
    response = input("\n是否删除这些孤儿记录？(yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("取消删除")
        return

    # 删除孤儿记录
    print("\n正在删除...")
    for capsule_id in orphaned:
        try:
            # TODO: 实现删除功能
            print(f"  - ID {capsule_id}: 删除功能未实现")
        except Exception as e:
            print(f"  - ID {capsule_id}: 删除失败 - {e}")

    print("\n✅ 清理完成！")

def list_all_capsules():
    """列出所有胶囊"""
    db = get_database()
    capsules = db.get_all_capsules()

    print(f"\n数据库中的所有胶囊 ({len(capsules)} 个):")
    print("-" * 80)
    for cap in capsules:
        file_path = cap.get('file_path', 'N/A')
        exists = Path(file_path).exists() if file_path else False
        status = "✅" if exists else "❌"
        print(f"{status} ID {cap['id']:3d} | {cap['name']:40s} | {file_path}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--list':
        list_all_capsules()
    else:
        cleanup_orphaned_records()
