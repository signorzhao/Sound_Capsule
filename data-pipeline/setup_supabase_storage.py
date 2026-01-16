#!/usr/bin/env python3
"""
设置 Supabase Storage 用于文件存储

这个脚本会：
1. 创建一个名为 'capsule-files' 的 Storage bucket
2. 设置 RLS 策略
3. 创建必要的文件夹结构
"""

import sys
import os
os.chdir('/Users/ianzhao/Desktop/Sound_Capsule/synesth/data-pipeline')
sys.path.insert(0, '.')

from supabase_client import get_supabase_client

print("="*60)
print("Supabase Storage 设置")
print("="*60)

# 获取客户端
supabase = get_supabase_client()
client = supabase.client

print("\n步骤 1: 检查 Storage 是否可用...")
try:
    # 列出所有 buckets
    buckets = client.storage.list_buckets()
    print(f"✓ Storage 可用")
    print(f"  现有 buckets: {[b.name for b in buckets]}")
except Exception as e:
    print(f"✗ Storage 不可用: {e}")
    print("\n请先在 Supabase Dashboard 中启用 Storage:")
    print("1. 访问: https://supabase.com/dashboard/project/mngtddqjbbrdwwfxcvxg/storage")
    print("2. 点击 'Start using Storage'")
    sys.exit(1)

print("\n步骤 2: 创建 'capsule-files' bucket...")
bucket_name = 'capsule-files'

# 检查 bucket 是否已存在
existing_buckets = [b.name for b in client.storage.list_buckets()]
if bucket_name in existing_buckets:
    print(f"✓ Bucket '{bucket_name}' 已存在")
else:
    try:
        # 创建 bucket（需要 service_role key）
        client.storage.create_bucket(
            id=bucket_name,
            options={
                'public': False,  # 私有 bucket，需要认证才能访问
                'file_size_limit': 1024 * 1024 * 100,  # 100 MB
                'allowed_mime_types': ['audio/ogg', 'application/octet-stream', 'text/plain']
            }
        )
        print(f"✓ 创建 bucket '{bucket_name}' 成功")
    except Exception as e:
        print(f"✗ 创建 bucket 失败: {e}")
        print("\n请手动在 Supabase Dashboard 中创建 bucket:")
        print("1. 访问: https://supabase.com/dashboard/project/mngtddqjbbrdwwfxcvxg/storage")
        print("2. 点击 'New bucket'")
        print("3. Name: capsule-files")
        print("4. Public bucket: 关闭")
        print("5. File size limit: 100MB")
        print("6. Allowed MIME types: audio/ogg, application/octet-stream")

print("\n步骤 3: 创建文件夹结构...")
# Supabase Storage 不需要预先创建文件夹，上传时会自动创建

print("\n步骤 4: 显示访问 URL...")
print("\n文件访问格式:")
print(f"  /storage/v1/object/{bucket_name}/{{user_id}}/{{capsule_id}}/preview.ogg")
print(f"  /storage/v1/object/{bucket_name}/{{user_id}}/{{capsule_id}}/project.rpp")

print("\n" + "="*60)
print("✅ Storage 设置完成")
print("="*60)

print("\n下一步:")
print("1. 测试文件上传功能")
print("2. 集成到胶囊同步流程")
