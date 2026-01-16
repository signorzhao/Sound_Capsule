# -*- mode: python ; coding: utf-8 -*-
"""
Sound Capsule API - PyInstaller 配置文件

用于将 capsule_api.py 打包为独立的可执行文件
"""

import sys
import os
from pathlib import Path

# 获取当前目录（使用当前工作目录）
block_cipher = None
current_dir = Path.cwd()

# 收集所有需要包含的文件
datas = [
    # Lua 脚本
    (str(current_dir / 'lua_scripts'), 'lua_scripts'),
    
    # 数据库 schema（Phase G: 使用完整 schema）
    (str(current_dir / 'database' / 'capsule_schema_complete.sql'), 'database'),
    (str(current_dir / 'database' / 'sync_schema.sql'), 'database'),

    # 静态数据文件
    (str(current_dir / 'master_lexicon_v3.csv'), '.'),
]

# 隐藏导入（PyInstaller 可能无法自动检测的模块）
hiddenimports = [
    'sentence_transformers',
    'flask',
    'flask_cors',
    'torch',
    'transformers',
    'numpy',
    'pandas',
    'sklearn',
    'dotenv',
]

# 分析配置
a = Analysis(
    ['capsule_api.py'],
    pathex=[str(current_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型模块以减小体积
        'matplotlib',
        'pytest',
        'IPython',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 过滤不需要的文件
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 可执行文件配置
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='capsules_api',  # 输出文件名（不带扩展名）
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 使用 UPX 压缩（如果可用）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 显示控制台（调试时有用，生产环境可设为 False）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # macOS 特定配置
    icon=None,  # 可以添加 .icns 图标文件路径
)
