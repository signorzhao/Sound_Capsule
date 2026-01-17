"""
胶囊扫描和导入工具

扫描 output 目录,发现新导出的胶囊并导入到数据库
"""

import os
import sys
import json
from pathlib import Path
from capsule_db import get_database


def get_output_dir():
    """
    获取输出目录（从路径管理器获取）
    
    Returns:
        Path: 导出目录路径
    """
    from common import PathManager
    pm = PathManager.get_instance()
    return pm.export_dir

def scan_output_directory():
    """扫描 output 目录,找到所有胶囊"""
    output_dir = get_output_dir()
    if not output_dir.exists():
        return []

    capsules = []
    for capsule_dir in output_dir.iterdir():
        if not capsule_dir.is_dir():
            continue

        # 检查是否有 metadata.json
        metadata_file = capsule_dir / "metadata.json"
        if not metadata_file.exists():
            continue

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            capsules.append({
                'dir': capsule_dir,
                'name': metadata.get('name'),
                'metadata': metadata
            })
        except Exception as e:
            print(f"读取 {capsule_dir} 失败: {e}")
            continue

    return capsules


def import_capsule_from_output(capsule_info):
    """从 output 目录导入胶囊到数据库"""
    db = get_database()
    metadata = capsule_info['metadata']

    # 从文件夹名提取胶囊类型
    # 格式: {type}_{user}_{timestamp}
    capsule_name = metadata.get('name', '')
    capsule_type = 'magic'  # 默认值
    if '_' in capsule_name:
        type_part = capsule_name.split('_')[0]
        if type_part in ['magic', 'impact', 'atmosphere', 'texture']:
            capsule_type = type_part

    # 准备数据
    # 使用相对于 output_dir 的路径（支持用户自定义目录）
    # capsule_info['dir'] 是完整路径
    output_dir = get_output_dir()
    relative_path = capsule_info['dir'].relative_to(output_dir)

    capsule_data = {
        'uuid': metadata.get('uuid') or metadata.get('id'),
        'name': metadata.get('name'),
        'project_name': metadata.get('project_name'),
        'theme_name': metadata.get('theme_name'),
        'file_path': str(relative_path),  # 使用相对路径
        'preview_audio': metadata.get('preview_audio') or metadata.get('files', {}).get('preview'),
        'rpp_file': metadata.get('rpp_file') or metadata.get('files', {}).get('project'),
        'capsule_type': capsule_type,  # 新增：胶囊类型
        'metadata': {
            'bpm': metadata.get('info', {}).get('bpm'),
            'duration': metadata.get('info', {}).get('length'),
            'sample_rate': metadata.get('info', {}).get('sample_rate'),
            'plugin_count': metadata.get('plugins', {}).get('count'),
            'plugin_list': metadata.get('plugins', {}).get('list', []),
            'has_sends': metadata.get('routing_info', {}).get('has_sends'),
            'has_folder_bus': metadata.get('routing_info', {}).get('has_folder_bus'),
            'tracks_included': metadata.get('routing_info', {}).get('tracks_included')
        }
    }

    # 插入数据库
    capsule_id = db.insert_capsule(capsule_data)

    # 检查本地是否有 Audio 文件夹，修正 asset_status 和 audio_uploaded
    try:
        audio_dir = capsule_info['dir'] / "Audio"
        has_audio_files = False
        if audio_dir.exists() and audio_dir.is_dir():
            has_audio_files = any(
                entry.is_file() and not entry.name.startswith('.')
                for entry in audio_dir.iterdir()
            )

        asset_status = 'local' if has_audio_files else 'cloud_only'
        if capsule_id:
            db.update_asset_status(capsule_id, asset_status)
            # 🔥 如果本地有 Audio 文件，设置 audio_uploaded = 1
            if has_audio_files:
                db.connect()  # 确保连接是打开的
                db.conn.execute("""
                    UPDATE capsules SET audio_uploaded = 1 WHERE id = ?
                """, [capsule_id])
                db.conn.commit()
            status_label = "已下载" if asset_status == 'local' else "仅元数据"
            print(f"✓ 资产状态判定: {capsule_name} -> {status_label}")
    except Exception as e:
        print(f"⚠ 资产状态检测失败: {capsule_name} - {e}")

    # 如果是已存在的胶囊，更新类型
    if capsule_id:
        try:
            db.connect()  # 确保连接是打开的
            db.conn.execute("""
                UPDATE capsules SET capsule_type = ? WHERE id = ?
            """, [capsule_type, capsule_id])
            db.conn.commit()
            print(f"✓ 已更新胶囊类型: {capsule_name} -> {capsule_type}")
        except Exception as e:
            print(f"⚠ 更新胶囊类型失败: {e}")

    return capsule_id


def scan_and_import_all():
    """扫描并导入所有胶囊"""
    output_dir = get_output_dir()
    print(f"扫描目录: {output_dir}")

    if not output_dir.exists():
        print(f"✗ 目录不存在: {output_dir}")
        return []

    capsules = scan_output_directory()
    print(f"找到 {len(capsules)} 个胶囊")

    if not capsules:
        return []

    db = get_database()
    imported = []

    for capsule in capsules:
        # 检查是否已存在
        existing = db.get_capsule_by_name(capsule['name'])
        if existing:
            print(f"  跳过(已存在): {capsule['name']}")
            continue

        try:
            capsule_id = import_capsule_from_output(capsule)
            print(f"  ✓ 导入成功: {capsule['name']} (ID: {capsule_id})")

            # 获取完整的胶囊数据
            full_capsule = db.get_capsule(capsule_id)
            if full_capsule:
                imported.append(full_capsule)
            else:
                # Fallback: 如果获取失败，至少返回 id 和 name
                imported.append({
                    'id': capsule_id,
                    'name': capsule['name']
                })
        except Exception as e:
            print(f"  ✗ 导入失败: {capsule['name']} - {e}")

    return imported


def import_specific_capsule(capsule_name):
    """
    导入指定名称的胶囊

    Args:
        capsule_name: 要导入的胶囊名称

    Returns:
        完整的胶囊数据，如果失败则返回 None
    """
    print(f"🎯 尝试导入指定胶囊: {capsule_name}")

    # 检查胶囊目录是否存在
    output_dir = get_output_dir()
    capsule_dir = output_dir / capsule_name
    if not capsule_dir.exists():
        print(f"  ❌ 胶囊目录不存在: {capsule_dir}")
        return None

    # 检查 metadata.json 是否存在
    metadata_file = capsule_dir / 'metadata.json'
    if not metadata_file.exists():
        print(f"  ❌ metadata.json 不存在: {metadata_file}")
        return None

    # 读取 metadata
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"  ❌ 读取 metadata.json 失败: {e}")
        return None

    # 检查数据库中是否已存在
    db = get_database()
    existing = db.get_capsule_by_name(capsule_name)
    if existing:
        print(f"  ⚠️ 胶囊已存在于数据库 (ID: {existing.get('id')})")
        # 返回已存在的胶囊数据
        return existing

    # 导入胶囊
    try:
        capsule_info = {
            'dir': capsule_dir,
            'name': capsule_name,
            'metadata': metadata
        }

        capsule_id = import_capsule_from_output(capsule_info)
        print(f"  ✓ 导入成功: {capsule_name} (ID: {capsule_id})")

        # 获取完整的胶囊数据
        full_capsule = db.get_capsule(capsule_id)
        if full_capsule:
            return full_capsule
        else:
            # Fallback
            return {
                'id': capsule_id,
                'name': capsule_name
            }
    except Exception as e:
        print(f"  ❌ 导入失败: {e}")
        return None


if __name__ == '__main__':
    import sys

    try:
        imported = scan_and_import_all()

        if imported:
            print(f"\n成功导入 {len(imported)} 个新胶囊:")
            for cap in imported:
                print(f"  - ID {cap['id']}: {cap['name']}")
        else:
            print("\n没有新胶囊需要导入")

        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
