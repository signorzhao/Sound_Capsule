#!/usr/bin/env python3
"""
本地缓存扫描脚本（Phase B）

功能：
1. 扫描现有的本地胶囊文件
2. 计算 SHA256 哈希
3. 填充 local_cache 表
4. 更新 capsules 表的 local_wav_* 字段

使用方法：
    python scan_local_cache.py
    python scan_local_cache.py --export-dir /path/to/exports
    python scan_local_cache.py --dry-run  # 仅扫描，不写入数据库
"""

import os
import sys
import hashlib
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from capsule_db import CapsuleDatabase


def calculate_sha256(file_path: str) -> Optional[str]:
    """
    计算文件的 SHA256 哈希

    Args:
        file_path: 文件路径

    Returns:
        SHA256 哈希字符串（十六进制）或 None
    """
    try:
        sha256_hash = hashlib.sha256()

        with open(file_path, 'rb') as f:
            # 分块读取文件（适用于大文件）
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    except Exception as e:
        print(f"  ✗ 计算哈希失败: {e}")
        return None


def find_wav_file(capsule_file_path: str, export_dir: str) -> Optional[str]:
    """
    查找胶囊的 WAV 文件

    Args:
        capsule_file_path: 胶囊的 file_path 字段（相对路径）
        export_dir: 导出目录根路径

    Returns:
        WAV 文件的绝对路径或 None
    """
    # 构建胶囊目录的绝对路径
    capsule_dir = Path(export_dir) / capsule_file_path

    if not capsule_dir.exists():
        return None

    # 查找 Audio 子文件夹
    audio_dir = capsule_dir / "Audio"

    if not audio_dir.exists():
        # 如果没有 Audio 子目录，直接在胶囊目录中查找
        audio_dir = capsule_dir

    # 查找 WAV 文件
    wav_files = list(audio_dir.glob("*.wav"))

    if not wav_files:
        return None

    # 如果有多个 WAV 文件，返回第一个
    # TODO: 未来可能需要更智能的选择逻辑
    return str(wav_files[0].absolute())


def scan_local_cache(
    db_path: str,
    export_dir: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    扫描本地文件并填充缓存表

    Args:
        db_path: 数据库文件路径
        export_dir: 导出目录路径
        dry_run: 是否仅测试（不写入数据库）

    Returns:
        扫描结果统计：
        {
            'total_capsules': int,
            'scanned_capsules': int,
            'found_wav_files': int,
            'failed_wav_files': int,
            'cache_entries': int
        }
    """
    print("=" * 60)
    print("🔍 本地缓存扫描工具（Phase B）")
    print("=" * 60)
    print(f"数据库: {db_path}")
    print(f"导出目录: {export_dir}")
    if dry_run:
        print("⚠️  干运行模式：不会写入数据库")
    print()

    # 初始化数据库
    db = CapsuleDatabase(db_path)
    db.connect()

    # 获取所有 asset_status = 'local' 的胶囊
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, name, file_path, asset_status
        FROM capsules
        WHERE asset_status = 'local'
        ORDER BY created_at DESC
    """)

    capsules = cursor.fetchall()

    if not capsules:
        print("⚠️  没有找到本地胶囊（asset_status = 'local'）")
        return {
            'total_capsules': 0,
            'scanned_capsules': 0,
            'found_wav_files': 0,
            'failed_wav_files': 0,
            'cache_entries': 0
        }

    print(f"📦 找到 {len(capsules)} 个本地胶囊")
    print()

    stats = {
        'total_capsules': len(capsules),
        'scanned_capsules': 0,
        'found_wav_files': 0,
        'failed_wav_files': 0,
        'cache_entries': 0
    }

    # 遍历每个胶囊
    for capsule in capsules:
        capsule_id = capsule[0]
        capsule_name = capsule[1]
        capsule_file_path = capsule[2]

        stats['scanned_capsules'] += 1

        print(f"[{stats['scanned_capsules']}/{len(capsules)}] 扫描: {capsule_name}")

        # 查找 WAV 文件
        wav_path = find_wav_file(capsule_file_path, export_dir)

        if not wav_path:
            print(f"  ⚠️  未找到 WAV 文件")
            stats['failed_wav_files'] += 1
            continue

        # 获取文件信息
        try:
            file_size = os.path.getsize(wav_path)
        except Exception as e:
            print(f"  ✗ 获取文件大小失败: {e}")
            stats['failed_wav_files'] += 1
            continue

        # 计算 SHA256
        print(f"  📄 文件: {Path(wav_path).name}")
        print(f"  📦 大小: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)", end="")

        file_hash = calculate_sha256(wav_path)

        if not file_hash:
            stats['failed_wav_files'] += 1
            continue

        print(f" ✓")

        # 检查缓存表是否已有记录
        cursor.execute("""
            SELECT id FROM local_cache
            WHERE capsule_id = ? AND file_type = 'wav'
        """, (capsule_id,))

        existing = cursor.fetchone()

        if existing:
            print(f"  ℹ️  缓存记录已存在，跳过")
            continue

        if dry_run:
            print(f"  [DRY RUN] 将创建缓存记录")
            stats['cache_entries'] += 1
            stats['found_wav_files'] += 1
            continue

        # 写入数据库
        try:
            # 1. 更新 capsules 表
            cursor.execute("""
                UPDATE capsules
                SET local_wav_path = ?,
                    local_wav_size = ?,
                    local_wav_hash = ?
                WHERE id = ?
            """, (wav_path, file_size, file_hash, capsule_id))

            # 2. 插入 local_cache 表
            cursor.execute("""
                INSERT INTO local_cache
                (capsule_id, file_type, file_path, file_size, file_hash,
                 last_accessed_at, access_count, is_pinned, cache_priority,
                 created_at, updated_at)
                VALUES (?, 'wav', ?, ?, ?, CURRENT_TIMESTAMP, 1, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (capsule_id, wav_path, file_size, file_hash))

            db.conn.commit()

            print(f"  ✅ 缓存记录已创建")
            stats['found_wav_files'] += 1
            stats['cache_entries'] += 1

        except Exception as e:
            db.conn.rollback()
            print(f"  ✗ 写入数据库失败: {e}")
            stats['failed_wav_files'] += 1

        print()

    db.close()

    return stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='本地缓存扫描工具（Phase B）'
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default=None,
        help='数据库文件路径（默认: data-pipeline/database/capsules.db）'
    )

    parser.add_argument(
        '--export-dir',
        type=str,
        default=None,
        help='导出目录路径（默认: ~/Documents/testout）'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='干运行模式：仅扫描，不写入数据库'
    )

    args = parser.parse_args()

    # 默认路径
    if args.db_path is None:
        current_dir = Path(__file__).parent
        args.db_path = str(current_dir / "database" / "capsules.db")

    if args.export_dir is None:
        args.export_dir = str(Path.home() / "Documents" / "testout")

    # 验证路径
    if not Path(args.db_path).exists():
        print(f"❌ 数据库文件不存在: {args.db_path}")
        sys.exit(1)

    if not Path(args.export_dir).exists():
        print(f"❌ 导出目录不存在: {args.export_dir}")
        sys.exit(1)

    # 执行扫描
    try:
        stats = scan_local_cache(
            db_path=args.db_path,
            export_dir=args.export_dir,
            dry_run=args.dry_run
        )

        # 打印统计
        print()
        print("=" * 60)
        print("📊 扫描完成统计")
        print("=" * 60)
        print(f"总胶囊数:       {stats['total_capsules']}")
        print(f"已扫描胶囊:     {stats['scanned_capsules']}")
        print(f"找到 WAV 文件:  {stats['found_wav_files']}")
        print(f"失败文件:       {stats['failed_wav_files']}")
        print(f"创建缓存记录:   {stats['cache_entries']}")
        print()

        if args.dry_run:
            print("⚠️  干运行模式：数据库未修改")
        else:
            print("✅ 数据库已更新")

        print("=" * 60)

    except Exception as e:
        print(f"❌ 扫描失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
