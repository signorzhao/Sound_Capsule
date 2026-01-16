#!/usr/bin/env python3
"""
检查云端胶囊的 local_id
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import get_supabase_client

def main():
    supabase = get_supabase_client()
    result = supabase.client.table('cloud_capsules').select('id, local_id, name').eq('user_id', '82404db7-ef81-429e-9169-c9d02a6241db').execute()

    print("云端胶囊数据:")
    for capsule in result.data:
        print(f"  ID: {capsule['id']}")
        print(f"  local_id: {capsule.get('local_id')}")
        print(f"  name: {capsule['name']}")

if __name__ == '__main__':
    main()
