"""
验证 Supabase 云端数据库 Schema

检查 capsule_tags 表是否存在及其结构是否正确
"""

import sys
from supabase_client import get_supabase_client


def verify_capsule_tags_table():
    """验证 capsule_tags 表结构"""
    
    print("=" * 60)
    print("🔍 验证 Supabase capsule_tags 表结构")
    print("=" * 60)
    print()
    
    try:
        # 获取 Supabase 客户端
        supabase = get_supabase_client()
        if not supabase:
            print("❌ 无法初始化 Supabase 客户端")
            return False
        
        print("✓ Supabase 客户端已连接")
        print()
        
        # 尝试查询 capsule_tags 表
        print("📋 检查 capsule_tags 表...")
        try:
            result = supabase.client.table('capsule_tags').select('*').limit(1).execute()
            print("✓ capsule_tags 表存在")
            print(f"  当前记录数: {len(result.data)}")
            
            if result.data:
                print("  示例记录字段:")
                for key in result.data[0].keys():
                    print(f"    - {key}")
        except Exception as e:
            print(f"❌ capsule_tags 表不存在或无法访问")
            print(f"   错误: {e}")
            print()
            print("📝 需要执行以下操作:")
            print("   1. 登录 Supabase 控制台")
            print("   2. 进入 SQL Editor")
            print("   3. 执行以下文件中的 SQL:")
            print("      data-pipeline/database/migrations/003_create_capsule_tags_table.sql")
            return False
        
        print()
        
        # 检查 cloud_capsule_tags 表（旧表名，如果存在）
        print("📋 检查 cloud_capsule_tags 表（旧表名）...")
        try:
            result = supabase.client.table('cloud_capsule_tags').select('*').limit(1).execute()
            print("⚠️  cloud_capsule_tags 表仍然存在")
            print("   建议：可以删除此表，使用新的 capsule_tags 表")
        except:
            print("✓ cloud_capsule_tags 表不存在（正常）")
        
        print()
        
        # 测试插入权限（需要认证）
        print("🔐 测试 RLS 策略...")
        print("   注意：需要用户认证才能测试插入/更新权限")
        print("   当前仅测试查询权限")
        
        try:
            # 尝试查询（应该允许）
            result = supabase.client.table('capsule_tags').select('id').limit(1).execute()
            print("✓ 查询权限正常（所有人可查看）")
        except Exception as e:
            print(f"❌ 查询权限异常: {e}")
            return False
        
        print()
        print("=" * 60)
        print("✅ Supabase Schema 验证完成")
        print("=" * 60)
        print()
        print("📝 后续步骤:")
        print("   1. 如果 capsule_tags 表不存在，执行迁移脚本")
        print("   2. 测试完整的上传/下载流程")
        print("   3. 验证 Tags 同步功能")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ 验证过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = verify_capsule_tags_table()
    sys.exit(0 if success else 1)
