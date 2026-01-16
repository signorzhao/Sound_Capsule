"""
REAPER 触发导出器

从 REAPER 快捷键触发,读取配置并执行导出
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


TRIGGER_FILE = Path("/tmp/synest_export/reaper_trigger.json")


def read_reaper_trigger() -> Optional[Dict[str, Any]]:
    """
    读取 REAPER 触发配置

    Returns:
        配置字典,如果文件不存在返回 None
    """
    if not TRIGGER_FILE.exists():
        return None

    try:
        with open(TRIGGER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def export_from_reaper_trigger(
    project_name: str,
    theme_name: str,
    render_preview: bool = True
) -> Dict[str, Any]:
    """
    从 REAPER 触发导出

    Args:
        project_name: 项目名 (如果为 None,从触发文件读取)
        theme_name: 主题名
        render_preview: 是否渲染预览

    Returns:
        导出结果
    """
    # 读取触发配置
    trigger_config = read_reaper_trigger()

    if trigger_config:
        print(f"✓ 检测到 REAPER 触发")
        print(f"  源项目: {trigger_config.get('project_name')}")
        print(f"  选中的 Items: {trigger_config.get('item_count')}")

        # 如果没有指定项目名,使用触发文件中的
        if not project_name:
            project_name = trigger_config.get('project_name', '默认项目')

    # 执行实际的导出
    # 这里需要调用主导出逻辑
    # 暂时返回成功
    result = {
        'success': True,
        'project_name': project_name,
        'theme_name': theme_name,
        'capsule_name': f"{project_name}_{theme_name}"
    }

    # 清理触发文件
    TRIGGER_FILE.unlink(missing_ok=True)

    return result


if __name__ == '__main__':
    import sys

    trigger_config = read_reaper_trigger()

    if trigger_config:
        print("检测到 REAPER 触发配置:")
        print(f"  项目: {trigger_config.get('project_name')}")
        print(f"  Items: {trigger_config.get('item_count')}")
        print(f"  时间: {trigger_config.get('timestamp')}")
    else:
        print("未检测到 REAPER 触发配置")
        print("\n提示: 在 REAPER 中选中 Items 后,运行 launch_synesth.lua")
