#!/usr/bin/env python3
"""
数据库重置脚本
清空所有胶囊数据，保留用户认证信息
"""

import sqlite3
import sys
from pathlib import Path

# 数据库路径
DB_PATH = Path.home() / "Library/Application Support/com.soundcapsule.app/database/capsules.db"

def reset_database():
    """清空数据库中的胶囊数据"""
    
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        return False
    
    print(f"📂 数据库路径: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"📋 找到的表: {', '.join(tables)}")
        print()
        
        # 统计删除前的数据
        stats = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[table] = count
                print(f"   {table}: {count} 条记录")
            except sqlite3.OperationalError as e:
                print(f"   {table}: 查询失败 ({e})")
        
        print()
        print("🗑️  开始清空数据...")
        
        # 清空所有表（保留用户表）
        deleted = {}
        for table in tables:
            if table == 'users':
                print(f"   ⏭️  跳过 users 表（保留用户认证）")
                continue
            
            try:
                cursor.execute(f"DELETE FROM {table}")
                deleted[table] = cursor.rowcount
                print(f"   ✅ {table}: 删除 {cursor.rowcount} 条")
            except sqlite3.OperationalError as e:
                print(f"   ❌ {table}: 删除失败 ({e})")
        
        # 重置自增 ID
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name != 'users'")
            print(f"   ✅ 重置自增 ID")
        except:
            pass
        
        conn.commit()
        conn.close()
        
        print()
        print("✅ 数据库清空完成！")
        print()
        print("📊 删除统计:")
        for table, count in deleted.items():
            print(f"   {table}: {count} 条")
        
        return True
        
    except Exception as e:
        print(f"❌ 清空数据库失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔄 Sound Capsule 数据库重置工具")
    print("=" * 60)
    print()
    
    # 确认操作
    response = input("⚠️  确认要清空所有胶囊数据吗？(输入 yes 继续): ")
    if response.lower() != 'yes':
        print("❌ 操作已取消")
        sys.exit(0)
    
    print()
    success = reset_database()
    
    if success:
        print()
        print("🎉 数据库已重置，可以重新测试同步功能了！")
        print()
        print("📝 下一步:")
        print("   1. 重启 Python 后端")
        print("   2. 刷新前端应用")
        print("   3. 启动同步将重新拉取云端数据")
    else:
        sys.exit(1)
