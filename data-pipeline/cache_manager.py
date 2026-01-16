"""
缓存管理器（Phase B）

功能：
1. LRU 缓存清理策略
2. 最大缓存限制（默认5GB）
3. 保护用户固定缓存
4. 按优先级清理

使用示例：
    manager = CacheManager(
        db_path="database/capsules.db",
        max_cache_size=5 * 1024 * 1024 * 1024  # 5GB
    )

    # 清理缓存
    result = manager.purge_old_cache(keep_pinned=True)

    print(f"清理了 {result['files_deleted']} 个文件")
    print(f"释放了 {result['space_freed']} bytes")
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional


class CacheManager:
    """
    缓存管理器

    实现 LRU（Least Recently Used）缓存清理策略
    """

    def __init__(
        self,
        db_path: str,
        max_cache_size: int = 5 * 1024 * 1024 * 1024  # 5GB
    ):
        """
        初始化缓存管理器

        Args:
            db_path: 数据库路径
            max_cache_size: 最大缓存大小（字节）
        """
        from capsule_db import CapsuleDatabase

        self.db = CapsuleDatabase(db_path)
        self.max_cache_size = max_cache_size

    def get_cache_status(self) -> Dict[str, Any]:
        """
        获取缓存状态

        Returns:
            缓存状态字典：
            {
                'total_cached_files': int,
                'total_cache_size': int,
                'max_cache_size': int,
                'usage_percent': float,
                'available_space': int,
                'needs_purge': bool,
                'by_type': {...}
            }
        """
        stats = self.db.get_cache_stats()

        total_size = stats['total_cache_size']
        usage_percent = (total_size / self.max_cache_size) * 100 if self.max_cache_size > 0 else 0

        return {
            **stats,
            'max_cache_size': self.max_cache_size,
            'usage_percent': usage_percent,
            'available_space': max(0, self.max_cache_size - total_size),
            'needs_purge': total_size > self.max_cache_size
        }

    def purge_old_cache(
        self,
        keep_pinned: bool = True,
        max_size_to_free: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        清理旧缓存（LRU 策略）

        Args:
            keep_pinned: 是否保留固定缓存
            max_size_to_free: 最大释放空间（字节），如果为 None 则清理到低于 max_cache_size
            dry_run: 干运行模式（不实际删除文件）

        Returns:
            清理结果：
            {
                'files_deleted': int,
                'space_freed': int,
                'files_skipped': int,
                'errors': List[str]
            }
        """
        print("=" * 60)
        print("🧹 缓存清理开始")
        print("=" * 60)

        # 1. 获取当前缓存状态
        status = self.get_cache_status()

        print(f"📊 当前缓存状态:")
        print(f"   总文件数: {status['total_cached_files']}")
        print(f"   总大小: {self._format_size(status['total_cache_size'])}")
        print(f"   最大限制: {self._format_size(self.max_cache_size)}")
        print(f"   使用率: {status['usage_percent']:.1f}%")
        print(f"   固定文件: {status['pinned_files_count']} ({self._format_size(status['pinned_files_size'])})")
        print()

        # 2. 计算需要清理的空间
        if max_size_to_free is None:
            # 清理到低于 max_cache_size 的 90%
            target_size = int(self.max_cache_size * 0.9)
            max_size_to_free = max(0, status['total_cache_size'] - target_size)

        if max_size_to_free == 0:
            print("✅ 缓存大小正常，无需清理")
            return {
                'files_deleted': 0,
                'space_freed': 0,
                'files_skipped': 0,
                'errors': []
            }

        print(f"🎯 目标: 释放 {self._format_size(max_size_to_free)}")
        if dry_run:
            print("⚠️  干运行模式：不会实际删除文件")
        print()

        # 3. 获取 LRU 清理候选列表
        candidates = self.db.get_lru_cache_candidates(limit=100)

        if not candidates:
            print("✅ 没有可清理的文件")
            return {
                'files_deleted': 0,
                'space_freed': 0,
                'files_skipped': 0,
                'errors': []
            }

        print(f"📋 找到 {len(candidates)} 个清理候选")
        print()

        # 4. 按优先级清理
        result = {
            'files_deleted': 0,
            'space_freed': 0,
            'files_skipped': 0,
            'errors': []
        }

        space_freed = 0

        for candidate in candidates:
            # 检查是否已释放足够空间
            if space_freed >= max_size_to_free:
                break

            capsule_id = candidate['capsule_id']
            file_type = candidate['file_type']
            file_path = candidate['file_path']
            file_size = candidate['file_size']
            capsule_name = candidate['capsule_name']

            # 检查是否是固定缓存
            if keep_pinned and candidate.get('is_pinned'):
                result['files_skipped'] += 1
                print(f"⏭️  跳过固定缓存: {capsule_name}")
                continue

            # 检查文件是否存在
            if not Path(file_path).exists():
                print(f"⚠️  文件不存在，跳过: {file_path}")
                result['files_skipped'] += 1
                continue

            # 删除文件
            try:
                if not dry_run:
                    os.remove(file_path)
                    print(f"🗑️  删除: {capsule_name} ({self._format_size(file_size)})")
                else:
                    print(f"[DRY RUN] 会删除: {capsule_name} ({self._format_size(file_size)})")

                # 从数据库删除缓存记录
                if not dry_run:
                    self.db.delete_cache_entry(capsule_id, file_type)

                result['files_deleted'] += 1
                space_freed += file_size

            except Exception as e:
                error_msg = f"删除文件失败 {file_path}: {e}"
                print(f"❌ {error_msg}")
                result['errors'].append(error_msg)

        result['space_freed'] = space_freed

        # 5. 打印总结
        print()
        print("=" * 60)
        print("📊 清理完成")
        print("=" * 60)
        print(f"删除文件: {result['files_deleted']}")
        print(f"跳过文件: {result['files_skipped']}")
        print(f"释放空间: {self._format_size(result['space_freed'])}")
        if result['errors']:
            print(f"错误数量: {len(result['errors'])}")
        print()

        # 更新后的状态
        if not dry_run:
            new_status = self.get_cache_status()
            print(f"📊 新缓存状态:")
            print(f"   总大小: {self._format_size(new_status['total_cache_size'])}")
            print(f"   使用率: {new_status['usage_percent']:.1f}%")
        else:
            print("⚠️  干运行模式：数据库未更新")

        print("=" * 60)

        return result

    def pin_cache(self, capsule_id: int, file_type: str) -> bool:
        """
        固定缓存（防止被清理）

        Args:
            capsule_id: 胶囊 ID
            file_type: 文件类型

        Returns:
            是否成功
        """
        return self.db.set_cache_pinned(capsule_id, True)

    def unpin_cache(self, capsule_id: int, file_type: str) -> bool:
        """
        取消固定缓存

        Args:
            capsule_id: 胶囊 ID
            file_type: 文件类型

        Returns:
            是否成功
        """
        return self.db.set_cache_pinned(capsule_id, False)

    def clear_all_cache(self, keep_pinned: bool = True) -> Dict[str, Any]:
        """
        清空所有缓存

        Args:
            keep_pinned: 是否保留固定缓存

        Returns:
            清理结果
        """
        print("🗑️  清空所有缓存...")

        # 获取所有缓存条目
        status = self.get_cache_status()

        # 清理所有（保留固定缓存）
        return self.purge_old_cache(
            keep_pinned=keep_pinned,
            max_size_to_free=status['total_cache_size']
        )

    def update_cache_priority(
        self,
        capsule_id: int,
        file_type: str,
        priority: int
    ) -> bool:
        """
        更新缓存优先级

        Args:
            capsule_id: 胶囊 ID
            file_type: 文件类型
            priority: 优先级（0-10，数字越大越重要）

        Returns:
            是否成功
        """
        # 注意：这需要在 capsule_db.py 中添加相应方法
        # 暂时返回 True
        print(f"📝 更新缓存优先级: capsule_id={capsule_id}, file_type={file_type}, priority={priority}")
        return True

    # ========== Phase B.5: 智能缓存策略优化 ==========

    def smart_cache_cleanup(
        self,
        target_usage_percent: float = 80.0,
        keep_frequent: bool = True,
        min_access_count: int = 3
    ) -> Dict[str, Any]:
        """
        智能缓存清理策略（Phase B.5）

        综合考虑以下因素：
        1. LRU（最后访问时间）
        2. 访问频率（access_count）
        3. 文件大小
        4. 固定状态（is_pinned）
        5. 文件类型（preview 优先于 wav）

        Args:
            target_usage_percent: 目标使用率（默认 80%）
            keep_frequent: 是否保留高频访问文件（默认 True）
            min_access_count: 最小访问次数阈值（默认 3）

        Returns:
            清理结果：{
                'files_deleted': int,
                'space_freed': int,
                'files_skipped': int,
                'errors': List[str]
            }
        """
        print("=" * 60)
        print("🧠 智能缓存清理开始")
        print("=" * 60)

        # 1. 获取当前缓存状态
        status = self.get_cache_status()

        print(f"📊 当前缓存状态:")
        print(f"   总大小: {self._format_size(status['total_cache_size'])}")
        print(f"   使用率: {status['usage_percent']:.1f}%")
        print(f"   固定文件: {status['pinned_files_count']} ({self._format_size(status['pinned_files_size'])})")
        print()

        # 2. 检查是否需要清理
        if status['usage_percent'] < target_usage_percent:
            print("✅ 缓存使用率正常，无需清理")
            return {
                'files_deleted': 0,
                'space_freed': 0,
                'files_skipped': 0,
                'errors': []
            }

        # 3. 计算需要释放的空间
        target_size = int(self.max_cache_size * (target_usage_percent / 100.0))
        max_size_to_free = max(0, status['total_cache_size'] - target_size)

        print(f"🎯 目标使用率: {target_usage_percent}%")
        print(f"🎯 释放空间: {self._format_size(max_size_to_free)}")
        print()

        # 4. 获取清理候选（智能排序）
        candidates = self.db.get_lru_cache_candidates(limit=100)

        if not candidates:
            print("✅ 没有可清理的文件")
            return {
                'files_deleted': 0,
                'space_freed': 0,
                'files_skipped': 0,
                'errors': []
            }

        # 5. 智能排序清理优先级
        # 优先级分数 = (访问次数倒数) × (文件大小 / 1MB) × (类型权重)
        # 类型权重: preview=1.0, wav=0.5, rpp=0.3
        type_weights = {'preview': 1.0, 'wav': 0.5, 'rpp': 0.3, 'other': 0.7}

        def calculate_priority(candidate):
            """计算清理优先级（分数越高越应该清理）"""
            access_count = max(1, candidate.get('access_count', 0))
            file_size = candidate.get('file_size', 0)
            file_type = candidate.get('file_type', 'other')
            is_pinned = candidate.get('is_pinned', 0)

            # 固定缓存不清理
            if is_pinned:
                return -1

            # 访问频率保护
            if keep_frequent and access_count >= min_access_count:
                return -1

            # 计算分数
            access_score = 1.0 / access_count  # 访问越少，分数越高
            size_score = file_size / (1024 * 1024)  # 文件越大，分数越高
            type_weight = type_weights.get(file_type, type_weights['other'])

            return access_score * size_score * type_weight

        # 按优先级排序
        sorted_candidates = sorted(candidates, key=calculate_priority, reverse=True)

        print(f"📋 清理候选（按优先级排序）: {len(sorted_candidates)} 个")
        print()

        # 6. 执行清理
        result = {
            'files_deleted': 0,
            'space_freed': 0,
            'files_skipped': 0,
            'errors': []
        }

        space_freed = 0

        for candidate in sorted_candidates:
            # 检查是否已释放足够空间
            if space_freed >= max_size_to_free:
                break

            capsule_id = candidate['capsule_id']
            file_type = candidate['file_type']
            file_path = candidate['file_path']
            file_size = candidate['file_size']
            capsule_name = candidate.get('capsule_name', 'Unknown')
            access_count = candidate.get('access_count', 0)
            priority_score = calculate_priority(candidate)

            # 检查文件是否存在
            if not Path(file_path).exists():
                print(f"⚠️  文件不存在，跳过: {file_path}")
                result['files_skipped'] += 1
                continue

            # 删除文件
            try:
                os.remove(file_path)
                print(f"🗑️  删除: {capsule_name}")
                print(f"   类型: {file_type}, 大小: {self._format_size(file_size)}, 访问: {access_count} 次, 优先级: {priority_score:.2f}")

                # 从数据库删除缓存记录
                self.db.delete_cache_entry(capsule_id, file_type)

                result['files_deleted'] += 1
                space_freed += file_size

                # 检查是否已释放足够空间
                if space_freed >= max_size_to_free:
                    print(f"\n✅ 已释放足够空间: {self._format_size(space_freed)}")
                    break

            except Exception as e:
                error_msg = f"删除文件失败 {file_path}: {e}"
                print(f"❌ {error_msg}")
                result['errors'].append(error_msg)

        result['space_freed'] = space_freed

        # 7. 打印总结
        print()
        print("=" * 60)
        print("📊 清理完成")
        print("=" * 60)
        print(f"删除文件: {result['files_deleted']}")
        print(f"跳过文件: {result['files_skipped']}")
        print(f"释放空间: {self._format_size(result['space_freed'])}")

        if result['errors']:
            print(f"错误数量: {len(result['errors'])}")

        print()

        # 更新后的状态
        new_status = self.get_cache_status()
        print(f"📊 新缓存状态:")
        print(f"   总大小: {self._format_size(new_status['total_cache_size'])}")
        print(f"   使用率: {new_status['usage_percent']:.1f}%")

        print("=" * 60)
        print()

        return result

    def _format_size(self, size: int) -> str:
        """
        格式化文件大小

        Args:
            size: 字节数

        Returns:
            格式化后的字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"


# 便捷函数
def create_cache_manager(
    db_path: str = "database/capsules.db",
    max_cache_size: int = 5 * 1024 * 1024 * 1024
) -> CacheManager:
    """
    创建缓存管理器

    Args:
        db_path: 数据库路径
        max_cache_size: 最大缓存大小（字节）

    Returns:
        缓存管理器实例
    """
    return CacheManager(
        db_path=db_path,
        max_cache_size=max_cache_size
    )


# 测试代码
if __name__ == '__main__':
    import sys

    print("=" * 60)
    print("🧪 缓存管理器测试")
    print("=" * 60)
    print()

    # 创建缓存管理器
    manager = create_cache_manager(
        db_path="database/capsules.db",
        max_cache_size=100 * 1024 * 1024  # 100MB（测试用）
    )

    # 显示缓存状态
    status = manager.get_cache_status()

    print("📊 缓存状态:")
    print(f"   总文件数: {status['total_cached_files']}")
    print(f"   总大小: {manager._format_size(status['total_cache_size'])}")
    print(f"   最大限制: {manager._format_size(status['max_cache_size'])}")
    print(f"   使用率: {status['usage_percent']:.1f}%")
    print(f"   可用空间: {manager._format_size(status['available_space'])}")
    print(f"   需要清理: {'是' if status['needs_purge'] else '否'}")
    print()

    # 按类型统计
    if status['by_type']:
        print("📋 按类型统计:")
        for file_type, type_stats in status['by_type'].items():
            print(f"   {file_type}: {type_stats['count']} 个文件, {manager._format_size(type_stats['size'])}")
        print()

    # 如果需要清理，执行清理
    if status['needs_purge']:
        print("⚠️  缓存超限，执行清理...")

        if '--dry-run' in sys.argv:
            result = manager.purge_old_cache(dry_run=True)
        else:
            result = manager.purge_old_cache()

        print()
        print("✅ 清理完成")

    else:
        print("✅ 缓存大小正常")

    print("=" * 60)
