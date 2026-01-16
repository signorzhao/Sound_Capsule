"""
旧胶囊 Tags 迁移脚本

将 metadata.json 文件中的 Tags 迁移到本地数据库
用于处理在动静分离架构之前创建的胶囊
"""

import sys
import json
from pathlib import Path
from capsule_db import get_database
from tags_service import get_tags_service
from common import PathManager


def migrate_all_capsules():
    """迁移所有胶囊的 Tags"""
    
    print("=" * 60)
    print("🔄 开始迁移旧胶囊 Tags 到数据库")
    print("=" * 60)
    print()
    
    try:
        # 获取路径管理器
        pm = PathManager.get_instance()
        export_dir = pm.export_dir
        
        print(f"📁 导出目录: {export_dir}")
        print()
        
        # 获取数据库和 Tags 服务
        db = get_database()
        tags_service = get_tags_service()
        
        # 获取所有胶囊
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, name, file_path FROM capsules")
        capsules = cursor.fetchall()
        db.close()
        
        if not capsules:
            print("ℹ️  数据库中没有胶囊")
            return
        
        print(f"📊 找到 {len(capsules)} 个胶囊")
        print()
        
        migrated_count = 0
        skipped_count = 0
        failed_count = 0
        
        for capsule in capsules:
            capsule_id = capsule[0]
            capsule_name = capsule[1]
            file_path = capsule[2]
            
            print(f"🔍 检查胶囊: {capsule_name}")
            
            # 检查是否已有 Tags
            db.connect()
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM capsule_tags WHERE capsule_id = ?", (capsule_id,))
            existing_tags_count = cursor.fetchone()[0]
            db.close()
            
            if existing_tags_count > 0:
                print(f"   ✓ 已有 {existing_tags_count} 个 Tags，跳过")
                skipped_count += 1
                continue
            
            # 查找 metadata.json 文件
            capsule_dir = export_dir / file_path
            metadata_path = capsule_dir / "metadata.json"
            
            if not metadata_path.exists():
                print(f"   ⚠️  metadata.json 不存在，跳过")
                skipped_count += 1
                continue
            
            # 读取 metadata.json
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    tags = metadata.get('tags', [])
                
                if not tags:
                    print(f"   ℹ️  metadata.json 中无 Tags，跳过")
                    skipped_count += 1
                    continue
                
                # 迁移 Tags
                print(f"   → 迁移 {len(tags)} 个 Tags...")
                success = tags_service.merge_tags_from_metadata(capsule_id, metadata_path)
                
                if success:
                    print(f"   ✓ 迁移成功")
                    migrated_count += 1
                else:
                    print(f"   ✗ 迁移失败")
                    failed_count += 1
                    
            except Exception as e:
                print(f"   ✗ 迁移异常: {e}")
                failed_count += 1
            
            print()
        
        # 打印总结
        print("=" * 60)
        print("📊 迁移完成")
        print("=" * 60)
        print(f"总胶囊数: {len(capsules)}")
        print(f"迁移成功: {migrated_count}")
        print(f"跳过: {skipped_count}")
        print(f"失败: {failed_count}")
        print("=" * 60)
        print()
        
        if migrated_count > 0:
            print("✅ Tags 迁移完成！")
            print()
            print("📝 后续步骤:")
            print("   1. 重启前端应用")
            print("   2. 验证胶囊的 Tags 显示正常")
            print("   3. 测试 Tags 编辑和同步功能")
            print()
        
        return migrated_count > 0
        
    except Exception as e:
        print(f"❌ 迁移过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def migrate_single_capsule(capsule_id: int):
    """迁移单个胶囊的 Tags"""
    
    print(f"🔄 迁移胶囊 {capsule_id} 的 Tags...")
    
    try:
        # 获取路径管理器
        pm = PathManager.get_instance()
        export_dir = pm.export_dir
        
        # 获取数据库和 Tags 服务
        db = get_database()
        tags_service = get_tags_service()
        
        # 获取胶囊信息
        capsule = db.get_capsule(capsule_id)
        if not capsule:
            print(f"❌ 胶囊不存在: {capsule_id}")
            return False
        
        # 查找 metadata.json
        capsule_dir = export_dir / capsule['file_path']
        metadata_path = capsule_dir / "metadata.json"
        
        if not metadata_path.exists():
            print(f"❌ metadata.json 不存在: {metadata_path}")
            return False
        
        # 迁移 Tags
        success = tags_service.merge_tags_from_metadata(capsule_id, metadata_path)
        
        if success:
            print(f"✅ 迁移成功")
        else:
            print(f"❌ 迁移失败")
        
        return success
        
    except Exception as e:
        print(f"❌ 迁移异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='迁移旧胶囊 Tags 到数据库')
    parser.add_argument('--capsule-id', type=int, help='迁移指定胶囊 ID')
    parser.add_argument('--all', action='store_true', help='迁移所有胶囊')
    parser.add_argument('--config-dir', type=str, help='配置目录路径（可选，默认使用标准路径）')
    parser.add_argument('--export-dir', type=str, help='导出目录路径（可选，默认使用标准路径）')
    
    args = parser.parse_args()
    
    # 初始化 PathManager
    try:
        from pathlib import Path
        import os
        
        # 确定配置目录
        if args.config_dir:
            config_dir = args.config_dir
        else:
            # 使用标准路径
            config_dir = str(Path.home() / 'Library' / 'Application Support' / 'com.soundcapsule.app')
        
        # 确定导出目录
        if args.export_dir:
            export_dir = args.export_dir
        else:
            # 尝试从配置文件读取
            config_file = Path(config_dir) / 'config.json'
            if config_file.exists():
                import json
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    export_dir = config.get('export_dir', str(Path.home() / 'Documents' / 'soundcapsule_syncfolder'))
            else:
                export_dir = str(Path.home() / 'Documents' / 'soundcapsule_syncfolder')
        
        # 资源目录（脚本所在目录）
        resource_dir = str(Path(__file__).parent)
        
        print(f"📁 配置目录: {config_dir}")
        print(f"📁 导出目录: {export_dir}")
        print(f"📁 资源目录: {resource_dir}")
        print()
        
        # 初始化 PathManager
        PathManager.initialize(
            config_dir=config_dir,
            export_dir=export_dir,
            resource_dir=resource_dir
        )
        
        print("✓ PathManager 已初始化")
        print()
        
    except Exception as e:
        print(f"❌ PathManager 初始化失败: {e}")
        sys.exit(1)
    
    # 执行迁移
    if args.capsule_id:
        success = migrate_single_capsule(args.capsule_id)
    elif args.all:
        success = migrate_all_capsules()
    else:
        print("请指定 --capsule-id <ID> 或 --all")
        print()
        print("示例:")
        print("  python migrate_tags_to_database.py --all")
        print("  python migrate_tags_to_database.py --capsule-id 123")
        print("  python migrate_tags_to_database.py --all --export-dir /path/to/export")
        sys.exit(1)
    
    sys.exit(0 if success else 1)
