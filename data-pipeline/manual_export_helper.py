"""
REAPER 导出辅助脚本

工作流程:
1. 用户在 REAPER 中手动运行 Lua 脚本导出胶囊
2. 本脚本监控输出目录,检测新导出的胶囊
3. 自动将胶囊导入数据库
"""

import os
import sys
import json
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from capsule_db import get_database
from capsule_scanner import get_output_dir


class CapsuleExportHandler(FileSystemEventHandler):
    """处理新导出的胶囊"""

    def __init__(self, output_dir: Path, auto_import: bool = True):
        super().__init__()
        self.output_dir = output_dir
        self.auto_import = auto_import
        self.db = get_database()
        print(f"✓ 监控目录: {output_dir}")

    def on_created(self, event):
        """当新文件/目录创建时"""
        if event.is_directory:
            self.check_new_capsule(Path(event.src_path))

    def check_new_capsule(self, capsule_dir: Path):
        """检查是否是新导出的胶囊"""
        # 检查是否有 metadata.json
        metadata_file = capsule_dir / "metadata.json"
        if not metadata_file.exists():
            return

        print(f"\n{'='*60}")
        print(f"🎉 检测到新导出的胶囊: {capsule_dir.name}")
        print(f"{'='*60}")

        # 读取元数据
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        print(f"  项目名: {metadata.get('project_name', 'N/A')}")
        print(f"  主题名: {metadata.get('theme_name', 'N/A')}")
        print(f"  胶囊名: {metadata.get('name', 'N/A')}")

        # 检查必需文件
        required_files = [
            metadata.get('files', {}).get('preview'),
            metadata.get('files', {}).get('project')
        ]

        missing = [f for f in required_files if f and not (capsule_dir / f).exists()]
        if missing:
            print(f"\n⚠️  警告: 缺少文件: {missing}")
            if not self.auto_import:
                return

        # 询问是否导入
        if not self.auto_import:
            response = input("\n是否导入到数据库? (y/n): ").strip().lower()
            if response != 'y':
                print("✗ 跳过导入")
                return

        # 导入到数据库
        self.import_capsule(capsule_dir, metadata)

    def import_capsule(self, capsule_dir: Path, metadata: dict):
        """将胶囊导入数据库"""
        try:
            print("\n导入到数据库...")

            # 准备数据
            # 使用相对于 OUTPUT_DIR 的路径（支持用户自定义目录）
            capsule_data = {
                'uuid': metadata.get('id'),
                'name': metadata.get('name'),
                'project_name': metadata.get('project_name'),
                'theme_name': metadata.get('theme_name'),
                'file_path': str(capsule_dir.relative_to(get_output_dir())),
                'preview_audio': metadata.get('files', {}).get('preview'),
                'rpp_file': metadata.get('files', {}).get('project'),
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
            capsule_id = self.db.insert_capsule(capsule_data)

            print(f"✓ 导入成功!")
            print(f"  胶囊 ID: {capsule_id}")
            print(f"  API 访问: http://localhost:5002/api/capsules/{capsule_id}")

        except Exception as e:
            print(f"✗ 导入失败: {e}")


def find_reaper_output_dir():
    """查找 REAPER 导出目录"""
    # 可能的输出目录
    possible_dirs = [
        Path("../Reaper_Sonic_Capsule/output"),
        Path("output"),
        Path("capsules"),
    ]

    for dir_path in possible_dirs:
        if dir_path.exists():
            return dir_path

    # 如果都不存在,使用默认的
    default_dir = Path("output")
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir


def scan_existing_capsules(output_dir: Path):
    """扫描已存在的胶囊"""
    print("\n扫描已有胶囊...")

    if not output_dir.exists():
        print(f"  输出目录不存在: {output_dir}")
        return

    capsule_dirs = [
        d for d in output_dir.iterdir()
        if d.is_dir() and (d / "metadata.json").exists()
    ]

    if not capsule_dirs:
        print("  未找到已有胶囊")
        return

    print(f"  找到 {len(capsule_dirs)} 个已有胶囊:")
    for capsule_dir in capsule_dirs:
        print(f"    - {capsule_dir.name}")

    response = input("\n是否导入已有胶囊? (y/n/all): ").strip().lower()

    if response == 'all':
        # 导入所有
        for capsule_dir in capsule_dirs:
            metadata_file = capsule_dir / "metadata.json"
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            handler = CapsuleExportHandler(output_dir, auto_import=True)
            handler.import_capsule(capsule_dir, metadata)
    elif response == 'y':
        # 选择性导入
        for i, capsule_dir in enumerate(capsule_dirs, 1):
            print(f"\n[{i}/{len(capsule_dirs)}] {capsule_dir.name}")
            metadata_file = capsule_dir / "metadata.json"
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            resp = input("  导入这个胶囊? (y/n): ").strip().lower()
            if resp == 'y':
                handler = CapsuleExportHandler(output_dir, auto_import=True)
                handler.import_capsule(capsule_dir, metadata)


def main():
    """主函数"""
    print("\n" + "="*60)
    print("🎵 REAPER 胶囊导出辅助工具")
    print("="*60)

    # 查找输出目录
    output_dir = find_reaper_output_dir()
    print(f"\nREAPER 导出目录: {output_dir}")

    # 扫描已有胶囊
    scan_existing_capsules(output_dir)

    # 开始监控
    print("\n" + "="*60)
    print("开始监控新导出的胶囊...")
    print("="*60)
    print("\n使用说明:")
    print("  1. 在 REAPER 中选中要导出的音频 Item")
    print("  2. 运行 Lua 脚本: data-pipeline/lua_scripts/main_export.lua")
    print("  3. 脚本导出后,本工具会自动检测并导入到数据库")
    print("\n按 Ctrl+C 停止监控\n")

    event_handler = CapsuleExportHandler(output_dir, auto_import=True)
    observer = Observer()
    observer.schedule(event_handler, output_dir, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n停止监控")
        observer.stop()

    observer.join()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
