import json
import sqlite3
import os
from pathlib import Path

def import_vectors():
    base_dir = Path(__file__).parent
    db_path = base_dir / "database" / "capsules.db"
    json_path = base_dir.parent / "webapp" / "public" / "data" / "sonic_vectors.json"
    
    if not json_path.exists():
        print(f"❌ 未找到 {json_path}")
        return
        
    if not db_path.exists():
        print(f"❌ 未找到数据库 {db_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"🔄 正在将 {len(data)} 个棱镜的数据从 JSON 导入数据库...")
    
    for lens_id, lens_data in data.items():
        points = lens_data.get('points', [])
        points_json = json.dumps(points, ensure_ascii=False)
        
        # 检查棱镜是否存在
        cursor.execute("SELECT id FROM prisms WHERE id = ?", (lens_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE prisms 
                SET field_data = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (points_json, lens_id))
            print(f"  ✅ 更新 {lens_id}: {len(points)} 个词汇")
        else:
            print(f"  ⚠️  数据库中未找到棱镜 {lens_id}，跳过")
            
    conn.commit()
    conn.close()
    print("\n🎉 导入完成！现在执行『同步到云端』即可在云端生效。")

if __name__ == "__main__":
    import_vectors()
