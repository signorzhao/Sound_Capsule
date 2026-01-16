from supabase_client import get_supabase_client
import sqlite3

# 获取用户ID
conn = sqlite3.connect('database/capsules.db')
cursor = conn.cursor()
cursor.execute("SELECT supabase_user_id FROM users WHERE is_active = 1 LIMIT 1")
user_id = cursor.fetchone()[0]
conn.close()

supabase = get_supabase_client()

# 先删除旧的测试胶囊
print("删除旧的测试胶囊...")
capsules = supabase.download_capsules(user_id)
for cap in capsules:
    if cap['name'].startswith('测试胶囊'):
        result = supabase.client.table('cloud_capsules').delete().eq('id', cap['id']).execute()
        print(f"  ✓ 已删除: {cap['name']}")

# 添加新的完整测试胶囊
print("\n添加新的完整测试胶囊...")
test_data = [
    {
        'user_id': user_id,
        'local_id': 1,
        'name': '测试胶囊 #1',
        'description': '这是第1个测试胶囊，用于测试蓝色图标显示',
        'capsule_type_id': None,
        'reaper_project_path': '/test/path/capsule_1.rpp',
        'metadata': {
            'file_path': '/test/capsules/capsule_1',
            'capsule_type': 'magic',
            'bpm': 120,
            'duration': 30.5,
            'plugin_count': 3
        }
    },
    {
        'user_id': user_id,
        'local_id': 2,
        'name': '测试胶囊 #2',
        'description': '这是第2个测试胶囊',
        'capsule_type_id': None,
        'reaper_project_path': '/test/path/capsule_2.rpp',
        'metadata': {
            'file_path': '/test/capsules/capsule_2',
            'capsule_type': 'magic',
            'bpm': 140,
            'duration': 45.2
        }
    },
    {
        'user_id': user_id,
        'local_id': 3,
        'name': '测试胶囊 #3',
        'description': '这是第3个测试胶囊',
        'capsule_type_id': None,
        'reaper_project_path': '/test/path/capsule_3.rpp',
        'metadata': {
            'file_path': '/test/capsules/capsule_3',
            'capsule_type': 'template',
            'bpm': 100
        }
    },
]

for capsule_data in test_data:
    result = supabase.client.table('cloud_capsules').insert(capsule_data).execute()
    print(f"  ✓ 已添加: {capsule_data['name']}")

print("\n验证结果:")
cloud_count = supabase.get_capsule_count(user_id)
print(f"云端胶囊数量: {cloud_count}")
print(f"remotePending = {cloud_count}")
print(f"\n现在在应用中点击刷新按钮，应该能看到蓝色图标！")
