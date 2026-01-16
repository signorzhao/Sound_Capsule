from supabase_client import get_supabase_client
import json

def debug_cloud_content():
    supabase = get_supabase_client()
    if not supabase:
        print("❌ 无法连接到 Supabase")
        return

    # 获取 texture 棱镜的完整原始数据
    result = supabase.table('cloud_prisms').select('*').eq('prism_id', 'texture').execute()
    
    if not result.data:
        print("ℹ️ 云端未找到 texture 棱镜")
        return

    print(f"🔍 Texture 棱镜详情 (共 {len(result.data)} 条记录):")
    for i, p in enumerate(result.data):
        field_data_raw = p.get('field_data')
        try:
            field_data = json.loads(field_data_raw) if field_data_raw else []
            count = len(field_data)
        except:
            count = "解析失败"
            
        print(f"记录 #{i+1}:")
        print(f"  - Version: {p.get('version')}")
        print(f"  - Updated At: {p.get('updated_at')}")
        print(f"  - Field Data Length (Raw): {len(field_data_raw) if field_data_raw else 0}")
        print(f"  - Field Data Points Count: {count}")
        if count != "解析失败" and count > 0:
            print(f"  - Sample Point: {field_data[0]}")

if __name__ == "__main__":
    debug_cloud_content()
