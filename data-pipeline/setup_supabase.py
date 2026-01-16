#!/usr/bin/env python3
"""
Supabase 初始化脚本
创建数据表并测试连接
"""

import sys
from supabase import create_client

# 配置
SUPABASE_URL = "https://mngtddqjbbrdwwfxcvxg.supabase.co"
SUPABASE_KEY = "sb_publishable_IXJZMBYmusLOEuKoydTbMg_42F5XVSu"

print("="*60)
print("Supabase 初始化")
print("="*60)
print(f"URL: {SUPABASE_URL}")
print(f"Key: {SUPABASE_KEY[:20]}...")
print()

# 创建客户端
client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✓ 客户端创建成功\n")

# 测试连接
try:
    # 尝试查询表（应该返回空，因为表还不存在）
    result = client.table('cloud_capsules').select('*').limit(1).execute()
    print("✓ 数据库连接成功")
    print(f"  当前胶囊数量: {len(result.data)}\n")
except Exception as e:
    print(f"⚠ 表可能还不存在: {e}\n")

print("="*60)
print("下一步：在 Supabase SQL Editor 中执行脚本")
print("="*60)
print("""
1. 打开 Supabase Dashboard
2. 点击左侧 "SQL Editor"
3. 点击 "New Query"
4. 复制并粘贴 supabase_schema.sql 的内容
5. 点击 "Run" 执行

完成后，我们就可以开始同步数据了！
""")
