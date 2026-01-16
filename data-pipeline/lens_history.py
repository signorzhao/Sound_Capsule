#!/usr/bin/env python3
"""
棱镜历史版本管理模块 - Lens History Manager
============================================
功能：
1. 自动保存棱镜配置快照
2. 查看历史版本列表
3. 回滚到指定历史版本
4. 自动清理旧快照（保留最近N个）
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 路径配置
BASE_DIR = Path(__file__).parent
HISTORY_DIR = BASE_DIR / "lens_history"
MAX_SNAPSHOTS = 20  # 每个棱镜保留的快照数量


def ensure_history_dir():
    """确保历史目录存在"""
    HISTORY_DIR.mkdir(exist_ok=True)


def save_lens_snapshot(lens: str, config: Dict, action: str = "save", description: str = "") -> str:
    """
    保存棱镜快照

    Args:
        lens: 棱镜ID
        config: 棱镜完整配置
        action: 操作类型 (save/update/delete/restore)
        description: 操作描述

    Returns:
        快照文件路径
    """
    ensure_history_dir()

    timestamp = datetime.now().isoformat()
    # 替换时间戳中的冒号，避免文件名问题
    filename = f"{lens}_{timestamp.replace(':', '-')}.json"
    filepath = HISTORY_DIR / filename

    snapshot = {
        'lens': lens,
        'action': action,
        'description': description,
        'timestamp': timestamp,
        'config': config
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # 清理旧快照
    cleanup_old_snapshots(lens, keep=MAX_SNAPSHOTS)

    return str(filepath)


def get_lens_history(lens: str, limit: int = 20) -> List[Dict]:
    """
    获取棱镜的历史版本列表

    Args:
        lens: 棱镜ID
        limit: 返回的最大版本数

    Returns:
        历史版本列表，按时间倒序
    """
    ensure_history_dir()

    # 查找所有匹配的快照文件
    snapshots = sorted(
        HISTORY_DIR.glob(f"{lens}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:limit]

    history = []
    for snapshot_path in snapshots:
        try:
            with open(snapshot_path, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
                history.append({
                    'filename': snapshot_path.name,
                    'timestamp': snapshot['timestamp'],
                    'action': snapshot.get('action', 'save'),
                    'description': snapshot.get('description', ''),
                    'lens': snapshot['lens']
                })
        except Exception as e:
            print(f"Warning: Failed to read snapshot {snapshot_path}: {e}")
            continue

    return history


def restore_lens_snapshot(lens: str, filename: str) -> Dict:
    """
    回滚到指定历史版本

    Args:
        lens: 棱镜ID
        filename: 快照文件名

    Returns:
        操作结果 {"success": bool, "message": str}
    """
    ensure_history_dir()

    snapshot_path = HISTORY_DIR / filename

    if not snapshot_path.exists():
        return {"success": False, "message": f"快照文件不存在: {filename}"}

    try:
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)

        config = snapshot['config']

        # 导入 anchor_editor_v2 来访问保存函数
        # 避免循环导入，延迟导入
        import anchor_editor_v2

        # 加载当前配置
        current_config = anchor_editor_v2.load_config_v2()

        # 保存当前状态（回滚前）
        save_lens_snapshot(lens, current_config.get(lens, {}),
                          action="before_restore",
                          description=f"回滚前的状态（将回滚到 {snapshot['timestamp']}）")

        # 更新配置
        current_config[lens] = config
        anchor_editor_v2.save_config_v2(current_config)

        # 记录回滚操作
        restore_timestamp = datetime.now().isoformat()
        save_lens_snapshot(lens, config,
                          action="restore",
                          description=f"已回滚到 {snapshot['timestamp']}")

        return {
            "success": True,
            "message": f"成功回滚到 {snapshot['timestamp']}",
            "restored_from": snapshot['timestamp']
        }

    except Exception as e:
        return {"success": False, "message": f"回滚失败: {str(e)}"}


def cleanup_old_snapshots(lens: str, keep: int = 20):
    """
    清理旧快照，保留最近的N个
    
    Args:
        lens: 棱镜ID
        keep: 保留的快照数量
    """
    ensure_history_dir()

    snapshots = sorted(
        HISTORY_DIR.glob(f"{lens}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    # 删除超出保留数量的旧快照
    for old_snapshot in snapshots[keep:]:
        try:
            old_snapshot.unlink()
            print(f"Cleaned up old snapshot: {old_snapshot.name}")
        except Exception as e:
            print(f"Warning: Failed to delete old snapshot {old_snapshot}: {e}")


def delete_all_lens_history(lens: str) -> Dict:
    """
    删除棱镜的所有历史版本

    Args:
        lens: 棱镜ID

    Returns:
        操作结果 {"success": bool, "deleted_count": int}
    """
    ensure_history_dir()

    snapshots = list(HISTORY_DIR.glob(f"{lens}_*.json"))
    deleted_count = 0

    for snapshot in snapshots:
        try:
            snapshot.unlink()
            deleted_count += 1
        except Exception as e:
            print(f"Warning: Failed to delete snapshot {snapshot}: {e}")

    return {
        "success": True,
        "deleted_count": deleted_count
    }


def get_all_lens_history_summaries() -> Dict[str, int]:
    """
    获取所有棱镜的历史版本摘要

    Returns:
        字典 {lens: snapshot_count}
    """
    ensure_history_dir()

    if not HISTORY_DIR.exists():
        return {}

    summaries = {}
    for snapshot_file in HISTORY_DIR.glob("*.json"):
        try:
            lens = snapshot_file.name.split('_')[0]
            summaries[lens] = summaries.get(lens, 0) + 1
        except Exception:
            continue

    return summaries


if __name__ == '__main__':
    # 测试代码
    print("Lens History Module Test")
    print("=" * 50)

    ensure_history_dir()

    # 测试保存快照
    test_config = {
        "name": "Test Lens",
        "description": "测试棱镜",
        "anchors": [
            {"word": "test", "x": 50, "y": 50}
        ]
    }

    filepath = save_lens_snapshot("test", test_config, action="test", description="测试快照")
    print(f"Saved snapshot to: {filepath}")

    # 测试获取历史
    history = get_lens_history("test")
    print(f"\nHistory for 'test': {len(history)} snapshots")
    for h in history:
        print(f"  - {h['timestamp']}: {h['action']}")

    # 测试获取摘要
    summaries = get_all_lens_history_summaries()
    print(f"\nAll lens summaries: {summaries}")
