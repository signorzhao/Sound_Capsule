#!/usr/bin/env python3
"""
生成 Sound Capsule 应用图标

从 SVG 源文件生成各种尺寸的 PNG 图标
"""

import os
import subprocess
from pathlib import Path

# 检查是否安装了必要的工具
def check_dependencies():
    """检查依赖项"""
    print("检查依赖项...")

    # 检查 convert (ImageMagick)
    try:
        result = subprocess.run(['convert', '-version'],
                                capture_output=True,
                                text=True)
        if result.returncode == 0:
            print("✓ ImageMagick 已安装")
            return True
    except FileNotFoundError:
        pass

    print("✗ ImageMagick 未安装")
    print("\n请安装 ImageMagick:")
    print("  brew install imagemagick")
    return False

def generate_icons():
    """生成图标"""
    svg_file = Path(__file__).parent / 'capsule-icon.svg'

    if not svg_file.exists():
        print(f"✗ SVG 文件不存在: {svg_file}")
        return False

    print(f"\n使用 SVG 源文件: {svg_file}")

    # 需要生成的尺寸
    sizes = [
        (16, '16x16.png'),
        (32, '32x32.png'),
        (64, '64x64.png'),
        (128, '128x128.png'),
        (256, '256x256.png'),
        (512, '512x512.png'),
        (1024, '1024x1024.png'),
    ]

    print("\n生成图标...")
    success_count = 0

    for size, filename in sizes:
        output_file = Path(__file__).parent / filename

        try:
            cmd = [
                'convert',
                '-background', 'none',
                '-density', '300',
                str(svg_file),
                '-resize', f'{size}x{size}',
                str(output_file)
            ]

            result = subprocess.run(cmd,
                                    capture_output=True,
                                    text=True)

            if result.returncode == 0:
                print(f"✓ 生成 {filename} ({size}x{size})")
                success_count += 1
            else:
                print(f"✗ 生成 {filename} 失败")
                print(f"  错误: {result.stderr}")

        except Exception as e:
            print(f"✗ 生成 {filename} 出错: {e}")

    print(f"\n成功生成 {success_count}/{len(sizes)} 个图标")

    # 生成 @2x 图标
    print("\n生成 @2x 图标...")
    retina_sizes = [
        (32, '32x32@2x.png'),
        (64, '64x64@2x.png'),
        (128, '128x128@2x.png'),
        (256, '256x256@2x.png'),
    ]

    for size, filename in retina_sizes:
        output_file = Path(__file__).parent / filename

        try:
            cmd = [
                'convert',
                '-background', 'none',
                '-density', '300',
                str(svg_file),
                '-resize', f'{size}x{size}',
                str(output_file)
            ]

            result = subprocess.run(cmd,
                                    capture_output=True,
                                    text=True)

            if result.returncode == 0:
                print(f"✓ 生成 {filename} ({size}x{size})")
            else:
                print(f"✗ 生成 {filename} 失败")

        except Exception as e:
            print(f"✗ 生成 {filename} 出错: {e}")

    # 生成 ICO 文件（Windows）
    print("\n生成 ICO 文件...")
    try:
        cmd = [
            'convert',
            '-background', 'none',
            str(svg_file),
            '-define', 'icon:auto-resize=256,128,64,48,32,16',
            Path(__file__).parent / 'icon.ico'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✓ 生成 icon.ico")
        else:
            print("✗ 生成 icon.ico 失败")

    except Exception as e:
        print(f"✗ 生成 ICO 出错: {e}")

    # 生成 ICNS 文件（macOS）需要 iconutil
    print("\n生成 ICNS 文件...")
    iconset_dir = Path(__file__).parent / 'icon.iconset'

    # 清理旧的 iconset
    if iconset_dir.exists():
        subprocess.run(['rm', '-rf', str(iconset_dir)])

    iconset_dir.mkdir()

    # 复制图标到 iconset
    icon_mappings = [
        ('16x16.png', 'icon_16x16.png'),
        ('32x32.png', 'icon_16x16@2x.png'),
        ('32x32.png', 'icon_32x32.png'),
        ('64x64.png', 'icon_32x32@2x.png'),
        ('128x128.png', 'icon_128x128.png'),
        ('256x256.png', 'icon_128x128@2x.png'),
        ('256x256.png', 'icon_256x256.png'),
        ('512x512.png', 'icon_256x256@2x.png'),
        ('512x512.png', 'icon_512x512.png'),
        ('1024x1024.png', 'icon_512x512@2x.png'),
    ]

    for src, dst in icon_mappings:
        src_path = Path(__file__).parent / src
        dst_path = iconset_dir / dst

        if src_path.exists():
            subprocess.run(['cp', str(src_path), str(dst_path)])

    # 使用 iconutil 生成 ICNS
    try:
        cmd = ['iconutil', '-c', 'icns', str(iconset_dir),
               '-o', Path(__file__).parent / 'icon.icns']

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✓ 生成 icon.icns")
        else:
            print("✗ 生成 icon.icns 失败")
            print(f"  错误: {result.stderr}")

    except Exception as e:
        print(f"✗ 生成 ICNS 出错: {e}")

    print("\n完成！")
    print("\n注意：如果需要重新构建 Tauri 应用，请运行:")
    print("  npm run tauri build")

if __name__ == '__main__':
    print("=" * 60)
    print("Sound Capsule 图标生成器")
    print("=" * 60)

    if check_dependencies():
        generate_icons()
    else:
        print("\n请先安装依赖项")
        exit(1)
