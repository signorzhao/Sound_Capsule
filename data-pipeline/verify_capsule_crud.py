import requests
import json
import time

API_BASE = "http://localhost:5002"

print("\n" + "=" * 60)
print("💊 Capsule API CRUD Test")
print("=" * 60)

# Test Data
new_capsule = {
    "title": "Test Capsule",
    "description": "Created by automated verification script",
    "duration": 12.5,
    "tags": ["test", "verification"],
    "lens_data": {
        "mechanics": {"x": 50, "y": 50},
        "texture": {"x": 20, "y": 80}
    }
}

capsule_id = None

# 1. Create Capsule
print("\n1️⃣ Creating Capsule...")
try:
    response = requests.post(f"{API_BASE}/api/capsules", json=new_capsule, timeout=5)
    if response.status_code in [200, 201]:
        data = response.json()
        print(f"   ✅ Created successfully. Data: {data}")
        # Extract ID
        if 'capsule' in data and 'id' in data['capsule']:
             capsule_id = data['capsule']['id']
        elif 'data' in data and 'id' in data['data']:
             capsule_id = data['data']['id']
        elif 'id' in data:
             capsule_id = data['id']
        
        print(f"   Captured ID: {capsule_id}")
    else:
        print(f"   ❌ Creation failed: {response.status_code} {response.text}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

if not capsule_id:
    print("   ⚠️ Cannot proceed without ID. Attempting to list capsules explicitly.")
    try:
        response = requests.get(f"{API_BASE}/api/capsules?limit=1", timeout=5)
        data = response.json()
        if data.get('capsules'):
            capsule_id = data['capsules'][0]['id']
            print(f"   Using existing capsule ID: {capsule_id}")
    except:
        pass

if not capsule_id:
    print("   ❌ No capsule ID available for further tests.")
    exit(1)

# 2. Get Capsule
print("\n2️⃣ Getting Capsule...")
try:
    response = requests.get(f"{API_BASE}/api/capsules/{capsule_id}", timeout=5)
    if response.status_code == 200:
        print("   ✅ Get successful")
    else:
        print(f"   ❌ Get failed: {response.status_code}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

# 3. Delete Capsule
print("\n3️⃣ Deleting Capsule...")
try:
    response = requests.delete(f"{API_BASE}/api/capsules/{capsule_id}", timeout=5)
    if response.status_code == 200:
            print("   ✅ Delete successful")
    else:
            print(f"   ❌ Delete failed: {response.status_code}")
except Exception as e:
    print(f"   ❌ Exception: {e}")
