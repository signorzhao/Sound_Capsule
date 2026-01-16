#!/usr/bin/env python3
"""
检查同步状态
"""

import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import get_supabase_client

def main():
    print("=" * 60)
    print("检查同步状态")
    print("=" * 60)

    # 获取当前激活用户
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'capsules.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT supabase_user_id FROM users WHERE is_active = 1')
    user_row = cursor.fetchone()

    if not user_row:
        print('❌ 没有激活的用户')
        return

    user_id = user_row[0]
    print(f'✓ 当前用户ID: {user_id}')

    # 获取本地胶囊数量
    cursor.execute('SELECT COUNT(*) FROM capsules')
    local_count = cursor.fetchone()[0]
    print(f'✓ 本地胶囊数量: {local_count}')

    # 获取本地胶囊ID列表
    cursor.execute('SELECT id, name FROM capsules')
    local_capsules = cursor.fetchall()
    if local_capsules:
        print(f'  本地胶囊:')
        for capsule_id, name in local_capsules:
            print(f'    - ID {capsule_id}: {name}')

    # 获取 sync_status
    cursor.execute('SELECT remote_pending FROM sync_status WHERE table_name = "capsules"')
    sync_row = cursor.fetchone()
    if sync_row:
        print(f'\n✓ remote_pending (数据库): {sync_row[0]}')
    else:
        print('\n⚠ sync_status 中没有 capsules 记录')

    # 检查云端数据
    supabase = get_supabase_client()
    if not supabase:
        print('❌ Supabase 客户端未初始化')
        return

    cloud_capsules = supabase.client.table('capsules').select('id, capsule_local_id, name').eq('user_id', user_id).execute()

    if cloud_capsules.data:
        print(f'\n✓ 云端胶囊数量: {len(cloud_capsules.data)}')
        for capsule in cloud_capsules.data:
            print(f'  - {capsule["name"]} (本地ID: {capsule["capsule_local_id"]})')
    else:
        print(f'\n⚠ 云端胶囊数量: 0')

    # 计算 remote_pending
    local_ids = set()
    cursor.execute('SELECT id FROM capsules')
    for row in cursor.fetchall():
        local_ids.add(row[0])

    cloud_ids = set()
    for capsule in cloud_capsules.data:
        cloud_ids.add(capsule['capsule_local_id'])

    # 云端有但本地没有的 = 需要下载的
    remote_pending_calc = len(cloud_ids - local_ids)
    print(f'\n✓ 计算得出 remote_pending: {remote_pending_calc}')

    if remote_pending_calc > 0:
        print(f'\n🔵 应该显示蓝色图标，待下载 {remote_pending_calc} 个胶囊')
    else:
        print(f'\n🟢 应该显示绿色图标（无需下载）')

    conn.close()

    print("=" * 60)

if __name__ == '__main__':
    main()
