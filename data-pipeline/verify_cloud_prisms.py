from supabase_client import get_supabase_client
import json

def check_cloud_prisms():
    supabase = get_supabase_client()
    if not supabase:
        print("❌ 无法连接到 Supabase")
        return

    # 获取当前用户的活跃 prisms
    result = supabase.table('cloud_prisms').select('*').execute()
    
    if not result.data:
        print("ℹ️ 云端 prisms 表为空")
        return

    print(f"✅ 发现 {len(result.data)} 个云端棱镜:")
    for p in result.data:
        prism_id = p.get('prism_id')
        version = p.get('version')
        updated_at = p.get('updated_at')
        field_data_len = len(json.loads(p.get('field_data', '[]')))
        anchors_len = len(json.loads(p.get('anchors', '[]')))
        
        print(f"  - [{prism_id}] v{version} | 更新时间: {updated_at}")
        print(f"    锚点数: {anchors_len} | 预计算词库数: {field_data_len}")

if __name__ == "__main__":
    check_cloud_prisms()
