#!/usr/bin/env python3
"""
生成 Sound Capsule 应用图标（简化版）

使用 Python 的 cairosvg 或直接绘制来生成图标
"""

import os
from pathlib import Path

def generate_icons_with_svg():
    """使用 cairosvg 转换 SVG 为 PNG"""
    try:
        import cairosvg
    except ImportError:
        print("cairosvg 未安装")
        print("请运行: pip3 install cairosvg")
        return False

    svg_file = Path(__file__).parent / 'capsule-icon.svg'

    if not svg_file.exists():
        print(f"✗ SVG 文件不存在: {svg_file}")
        return False

    print(f"使用 SVG 源文件: {svg_file}\n")

    # 需要生成的尺寸
    sizes = [16, 32, 64, 128, 256, 512, 1024]

    print("生成 PNG 图标...")
    for size in sizes:
        output_file = Path(__file__).parent / f'{size}x{size}.png'

        try:
            cairosvg.svg2png(
                url=str(svg_file),
                write_to=str(output_file),
                output_width=size,
                output_height=size
            )
            print(f"✓ 生成 {size}x{size}.png")
        except Exception as e:
            print(f"✗ 生成 {size}x{size}.png 失败: {e}")

    # 生成 @2x 图标
    print("\n生成 @2x 图标...")
    retina_sizes = [(32, '32x32@2x'), (64, '64x64@2x'),
                    (128, '128x128@2x'), (256, '256x256@2x')]

    for size, name in retina_sizes:
        output_file = Path(__file__).parent / f'{name}.png'

        try:
            cairosvg.svg2png(
                url=str(svg_file),
                write_to=str(output_file),
                output_width=size,
                output_height=size
            )
            print(f"✓ 生成 {name}.png")
        except Exception as e:
            print(f"✗ 生成 {name}.png 失败: {e}")

    return True

def generate_icons_with_pillow():
    """使用 Pillow 直接绘制胶囊图标"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow 未安装")
        print("请运行: pip3 install Pillow")
        return False

    print("使用 Pillow 绘制胶囊图标...\n")

    sizes = [32, 64, 128, 256, 512, 1024]

    for size in sizes:
        # 创建图像
        img_size = size
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 计算胶囊尺寸（旋转后）
        capsule_width = int(size * 0.55)
        capsule_height = int(size * 0.28)

        # 中心点
        center = (size // 2, size // 2)

        # 绘制旋转的胶囊（通过绘制在临时图像上然后旋转）
        # 创建临时图像用于绘制胶囊
        temp_size = int(max(capsule_width, capsule_height) * 1.5)
        temp = Image.new('RGBA', (temp_size, temp_size), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp)

        # 绘制圆角矩形（胶囊主体）
        x0 = (temp_size - capsule_width) // 2
        y0 = (temp_size - capsule_height) // 2
        x1 = x0 + capsule_width
        y1 = y0 + capsule_height

        # 渐变背景（简化为纯色）
        temp_draw.rounded_rectangle(
            [x0, y0, x1, y1],
            radius=capsule_height // 2,
            fill=(139, 92, 246, 255),  # 紫色
            outline=None
        )

        # 绘制高光
        highlight_y = y0 + capsule_height // 4
        temp_draw.ellipse(
            [(x0 + capsule_width // 4, highlight_y),
             (x0 + capsule_width // 2, highlight_y + capsule_height // 4)],
            fill=(255, 255, 255, 50)
        )

        # 旋转临时图像
        rotated = temp.rotate(45, expand=True)

        # 计算粘贴位置（居中）
        paste_x = (img_size - rotated.width) // 2
        paste_y = (img_size - rotated.height) // 2

        # 粘贴到主图像
        img.paste(rotated, (paste_x, paste_y), rotated)

        # 保存
        output_file = Path(__file__).parent / f'{size}x{size}.png'
        img.save(output_file, 'PNG')
        print(f"✓ 生成 {size}x{size}.png")

    # 生成 32x32@2x (64x64)
    img = Image.open(Path(__file__).parent / '64x64.png')
    img.save(Path(__file__).parent / '32x32@2x.png', 'PNG')
    print("✓ 生成 32x32@2x.png")

    # 生成 64x64@2x (128x128)
    img = Image.open(Path(__file__).parent / '128x128.png')
    img.save(Path(__file__).parent / '64x64@2x.png', 'PNG')
    print("✓ 生成 64x64@2x.png")

    # 生成 128x128@2x (256x256)
    img = Image.open(Path(__file__).parent / '256x256.png')
    img.save(Path(__file__).parent / '128x128@2x.png', 'PNG')
    print("✓ 生成 128x128@2x.png")

    # 生成 256x256@2x (512x512)
    img = Image.open(Path(__file__).parent / '512x512.png')
    img.save(Path(__file__).parent / '256x256@2x.png', 'PNG')
    print("✓ 生成 256x256@2x.png")

    return True

def generate_iconset_and_icns():
    """生成 macOS iconset 和 ICNS"""
    print("\n生成 macOS iconset...")

    iconset_dir = Path(__file__).parent / 'icon.iconset'

    # 清理旧的 iconset
    if iconset_dir.exists():
        import shutil
        shutil.rmtree(iconset_dir)

    iconset_dir.mkdir()

    # 图标映射
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
            import shutil
            shutil.copy(src_path, dst_path)
            print(f"✓ 复制 {dst}")
        else:
            print(f"✗ 源文件不存在: {src}")

    # 使用 iconutil 生成 ICNS
    print("\n生成 ICNS 文件...")
    try:
        import subprocess
        cmd = ['iconutil', '-c', 'icns', str(iconset_dir),
               '-o', Path(__file__).parent / 'icon.icns']

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✓ 生成 icon.icns")
        else:
            print("✗ 生成 icon.icns 失败")
            if result.stderr:
                print(f"  错误: {result.stderr}")

    except Exception as e:
        print(f"✗ 生成 ICNS 出错: {e}")

if __name__ == '__main__':
    print("=" * 60)
    print("Sound Capsule 图标生成器")
    print("=" * 60)
    print()

    # 尝试使用 cairosvg（更准确）
    if not generate_icons_with_svg():
        print("\n回退到 Pillow 绘制...")
        if not generate_icons_with_pillow():
            print("\n✗ 无法生成图标")
            exit(1)

    # 生成 macOS 图标
    generate_iconset_and_icns()

    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)
    print("\n如果需要重新构建 Tauri 应用，请运行:")
    print("  cd webapp")
    print("  npm run tauri build")
