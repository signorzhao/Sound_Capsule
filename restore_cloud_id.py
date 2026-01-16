import os
import sys
from pathlib import Path

# Add data-pipeline to path
sys.path.append(os.path.join(os.getcwd(), 'data-pipeline'))

from supabase_client import get_supabase_client
from capsule_db import get_database

def find_and_restore_cloud_identity():
    print("--- 🔍 Searching for Cloud Data ---")
    
    supabase = get_supabase_client()
    if not supabase:
        print("Error: Supabase client not available")
        return

    try:
        # 1. Get all distinct user_ids from cloud_capsules
        # Note: We can't do distinct on the column easily with the python client depending on version, 
        # but we can fetch all and aggregate locally for this one-off script.
        # Ideally we'd use a raw rpc call if available, but let's try a simple fetch.
        
        print("Fetching cloud records...")
        response = supabase.client.table('cloud_capsules').select('user_id').execute()
        
        if not response.data:
            print("No data found in cloud_capsules table.")
            return

        # Aggregate counts
        user_counts = {}
        for row in response.data:
            uid = row['user_id']
            user_counts[uid] = user_counts.get(uid, 0) + 1
            
        print(f"\nFound {len(user_counts)} unique user identities in cloud:")
        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        
        for i, (uid, count) in enumerate(sorted_users):
            print(f"[{i+1}] User ID: {uid} | Capsules: {count}")
            
        if not sorted_users:
            return

        # 2. Get current local user
        conn = get_database().connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, supabase_user_id FROM users WHERE is_active = 1")
        current_user = cursor.fetchone()
        
        if not current_user:
            print("\n❌ No active local user found. Please log in first.")
            return
            
        print(f"\n--- 👤 Current Local User ---")
        print(f"Username: {current_user['username']}")
        print(f"Current Identity: {current_user['supabase_user_id']} (Capsules: 0)") # Assuming 0 since verified
        
        # 3. Auto-restore logic (Pick the top one if it has data)
        best_candidate_id = sorted_users[0][0]
        best_candidate_count = sorted_users[0][1]
        
        if best_candidate_count > 0:
            print(f"\n✨ Restoring link to Cloud Identity: {best_candidate_id} ({best_candidate_count} capsules)")
            
            cursor.execute("UPDATE users SET supabase_user_id = ? WHERE id = ?", (best_candidate_id, current_user['id']))
            conn.commit()
            print("✅ Restore successful! Please refresh your capsule library page.")
        else:
            print("No significant cloud data found to restore.")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_and_restore_cloud_identity()
