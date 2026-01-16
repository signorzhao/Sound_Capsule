"""
路径工具函数

处理开发环境和生产环境的资源路径差异
"""

import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """
    获取资源文件路径

    开发环境: 使用相对路径
    生产环境: 使用 sys._MEIPASS (PyInstaller)

    Args:
        relative_path: 相对路径，如 "lua_scripts", "master_lexicon_v3.csv"

    Returns:
        Path: 资源文件的完整路径
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境：使用脚本所在目录
        base_path = Path(__file__).parent

    return base_path / relative_path


def get_lua_scripts_dir() -> Path:
    """获取 Lua 脚本目录"""
    return get_resource_path("lua_scripts")


def get_lexicon_path() -> Path:
    """获取词典文件路径"""
    return get_resource_path("master_lexicon_v3.csv")


def get_exporters_dir() -> Path:
    """获取导出器目录"""
    return get_resource_path("exporters")
