from supabase_client import SupabaseClient
import json

def inspect_cloud_schema():
    client = SupabaseClient()
    
    print("--- cloud_capsule_tags ---")
    tags = client.table('cloud_capsule_tags').select('*').limit(1).execute()
    if tags.data:
        print(json.dumps(tags.data[0], indent=2))
    else:
        print("No tags found")
        
    print("\n--- cloud_capsule_coordinates ---")
    coords = client.table('cloud_capsule_coordinates').select('*').limit(1).execute()
    if coords.data:
        print(json.dumps(coords.data[0], indent=2))
    else:
        print("No coordinates found")

if __name__ == "__main__":
    inspect_cloud_schema()
