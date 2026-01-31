#!/usr/bin/env python3
"""
私有化 Supabase 执行 4 个 SQL 后的检查脚本

从 data-pipeline/.env.supabase 读取 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY，
检查表是否创建成功、Storage bucket 是否存在。不依赖本地数据库或登录。
"""

import os
import sys
from pathlib import Path

# 确保能加载同目录的 supabase_client（会读 .env.supabase）
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 表名（与 4 个 SQL 一致）
TABLES = [
    "cloud_capsules",
    "cloud_capsule_tags",
    "cloud_capsule_coordinates",
    "sync_log_cloud",
    "cloud_prisms",
]
BUCKET_NAME = "capsule-files"


def main():
    print("=" * 60)
    print("私有化 Supabase 检查（4 个 SQL 执行后）")
    print("=" * 60)

    env_file = Path(__file__).parent / ".env.supabase"
    if not env_file.exists():
        print(f"\n✗ 未找到 {env_file.name}")
        print("  请在该文件中配置 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY 后重试。")
        return 1

    url = os.getenv("SUPABASE_URL")
    if not url:
        # 再读一次（可能脚本直接运行未经过 supabase_client）
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "SUPABASE_URL":
                        url = v.strip()
                        break
    if not url:
        print("\n✗ .env.supabase 中未设置 SUPABASE_URL")
        return 1

    print(f"\n连接: {url}\n")

    try:
        from supabase_client import get_supabase_client
    except Exception as e:
        print(f"✗ 导入 supabase_client 失败: {e}")
        print("  请确认已安装: pip install supabase")
        return 1

    supabase = get_supabase_client()
    if not supabase:
        print("✗ 无法初始化 Supabase 客户端（检查 .env.supabase 中的 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY）")
        return 1

    ok = True

    # 1. 检查表是否存在并可查询
    print("1. 表结构检查")
    print("-" * 40)
    for table in TABLES:
        try:
            r = supabase.client.table(table).select("*").limit(0).execute()
            print(f"   ✓ {table}")
        except Exception as e:
            print(f"   ✗ {table}: {e}")
            ok = False
    print()

    # 2. 检查 cloud_prisms 是否有 is_active、field_data 列（004 迁移）
    print("2. cloud_prisms 列检查（004 迁移）")
    print("-" * 40)
    try:
        r = supabase.client.table("cloud_prisms").select("id, is_active, field_data").limit(0).execute()
        print("   ✓ cloud_prisms 含 is_active, field_data")
    except Exception as e:
        if "is_active" in str(e) or "field_data" in str(e):
            print(f"   ✗ 请执行: database/supabase_migrations/004_cloud_prisms_add_is_active_and_field_data.sql")
        print(f"   ✗ {e}")
        ok = False
    print()

    # 3. Storage bucket
    print("3. Storage bucket 检查")
    print("-" * 40)
    try:
        buckets = supabase.client.storage.list_buckets()
        names = [b.name for b in buckets] if buckets else []
        if BUCKET_NAME in names:
            print(f"   ✓ bucket '{BUCKET_NAME}' 已存在")
        else:
            print(f"   ✗ bucket '{BUCKET_NAME}' 不存在，请在 Dashboard → Storage 中创建")
            ok = False
    except Exception as e:
        print(f"   ✗ 列出 bucket 失败: {e}")
        ok = False
    print()

    # 4. 可选：RLS 策略（仅提示，不阻断）
    print("4. 说明")
    print("-" * 40)
    print("   RLS 策略已由 001_add_global_read_policies.sql 配置，无需在此验证。")
    print("   若需测试登录与同步，请启动应用后登录并执行一次「同步到云端」。")
    print()

    print("=" * 60)
    if ok:
        print("✅ 检查通过，私有化 Supabase 可正常使用。")
    else:
        print("❌ 存在未通过项，请按上述提示修复后重试。")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
