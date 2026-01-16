from supabase_client import get_supabase_client
import sqlite3

conn = sqlite3.connect('database/capsules.db')
cursor = conn.cursor()
cursor.execute("SELECT supabase_user_id FROM users WHERE is_active = 1 LIMIT 1")
user_id = cursor.fetchone()[0]
conn.close()

supabase = get_supabase_client()
capsules = supabase.download_capsules(user_id)

for cap in capsules:
    print(f"\n胶囊: {cap['name']}")
    print(f"  - id: {cap['id']}")
    print(f"  - local_id: {cap.get('local_id')}")
    print(f"  - reaper_project_path: {cap.get('reaper_project_path')}")
    print(f"  - metadata: {cap.get('metadata')}")
    print(f"  - description: {cap.get('description')}")
