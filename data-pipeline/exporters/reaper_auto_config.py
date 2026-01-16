"""
REAPER 配置文件导出器

创建导出配置文件,用户只需在 REAPER 中运行简化版脚本
"""

import os
import json
from pathlib import Path
from typing import Dict, Any


# 临时文件目录
TEMP_DIR = Path("/tmp/synest_export")
CONFIG_FILE = TEMP_DIR / "auto_export_config.json"


def prepare_export_config(
    project_name: str,
    theme_name: str,
    render_preview: bool = True,
    output_dir: str = None
) -> Dict[str, Any]:
    """
    准备导出配置文件

    Args:
        project_name: 项目名称
        theme_name: 主题名称
        render_preview: 是否渲染预览
        output_dir: 输出目录

    Returns:
        配置字典
    """
    # 创建临时目录
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 从路径管理器获取输出目录
    from common import PathManager
    pm = PathManager.get_instance()
    
    # 准备配置
    config = {
        "project_name": project_name,
        "theme_name": theme_name,
        "render_preview": render_preview,
        "output_dir": output_dir or str(pm.export_dir),
        "capsule_name": f"{project_name}_{theme_name}"
    }

    # 写入配置文件
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✓ 导出配置已准备")
    print(f"  项目: {project_name}")
    print(f"  主题: {theme_name}")
    print(f"  胶囊名: {config['capsule_name']}")
    print(f"  配置文件: {CONFIG_FILE}")

    return config


def read_export_config() -> Dict[str, Any]:
    """
    读取导出配置文件

    Returns:
        配置字典,如果文件不存在返回 None
    """
    if not CONFIG_FILE.exists():
        return None

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def cleanup_export_config():
    """清理配置文件"""
    CONFIG_FILE.unlink(missing_ok=True)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("用法: python reaper_auto_config.py <项目名> <主题名> [渲染预览:1/0]")
        sys.exit(1)

    project = sys.argv[1]
    theme = sys.argv[2]
    preview = len(sys.argv) > 3 and sys.argv[3] == '1'

    prepare_export_config(project, theme, preview)

    print("\n现在请在 REAPER 中运行:")
    print("  data-pipeline/lua_scripts/auto_export_from_config.lua")
    print("\n脚本会自动读取配置并执行导出,无需手动输入任何信息!")
