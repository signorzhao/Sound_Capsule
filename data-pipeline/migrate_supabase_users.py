#!/usr/bin/env python3
"""
为现有用户生成 Supabase UUID
"""

import sys
import sqlite3
import uuid

DB_PATH = "database/capsules.db"

print("=" * 60)
print("为现有用户生成 Supabase UUID")
print("=" * 60)

# 连接数据库
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 查询所有没有 supabase_user_id 的用户
cursor.execute("SELECT id, username, email FROM users WHERE supabase_user_id IS NULL")
users = cursor.fetchall()

print(f"\n找到 {len(users)} 个需要更新的用户\n")

for user_id, username, email in users:
    # 生成 UUID
    supabase_uuid = str(uuid.uuid4())

    # 更新数据库
    cursor.execute(
        "UPDATE users SET supabase_user_id = ? WHERE id = ?",
        (supabase_uuid, user_id)
    )

    print(f"✓ 用户 {username} (ID: {user_id}) -> {supabase_uuid}")

# 提交更改
conn.commit()

print(f"\n✓ 成功更新 {len(users)} 个用户")
print("=" * 60)

# 验证
cursor.execute("SELECT id, username, supabase_user_id FROM users")
print("\n当前用户列表:")
for row in cursor.fetchall():
    print(f"  ID: {row[0]}, 用户名: {row[1]}, Supabase ID: {row[2]}")

conn.close()
