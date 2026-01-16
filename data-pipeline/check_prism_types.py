from supabase_client import get_supabase_client

supabase = get_supabase_client()
print("查询 cloud_prisms 表（棱镜类型）：")

try:
    result = supabase.client.table('cloud_prisms').select('*').limit(5).execute()
    if result.data:
        print("字段名：", list(result.data[0].keys()))
        print("\n数据：")
        for prism in result.data:
            print(f"  {prism}")
    else:
        print("没有棱镜数据")
except Exception as e:
    print(f"查询失败: {e}")
