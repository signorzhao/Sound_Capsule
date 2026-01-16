from supabase_client import get_supabase_client
import sqlite3

# 获取用户ID
conn = sqlite3.connect('database/capsules.db')
cursor = conn.cursor()
cursor.execute("SELECT supabase_user_id FROM users WHERE is_active = 1 LIMIT 1")
user_id = cursor.fetchone()[0]
conn.close()

# 查询云端表结构
supabase = get_supabase_client()
print("查询 cloud_capsules 表的列...")
print("\n尝试查询一条记录来查看结构：")

try:
    result = supabase.client.table('cloud_capsules').select('*').limit(1).execute()
    if result.data:
        print("云端已有数据，列名：")
        for key in result.data[0].keys():
            print(f"  - {key}")
    else:
        print("云端没有数据，无法查看列结构")
except Exception as e:
    print(f"查询失败: {e}")
