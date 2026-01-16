#!/usr/bin/env python3
import struct

def create_simple_png(filename, width, height, color=(147, 51, 234)):
    """创建一个简单的纯色 PNG 文件"""
    
    def png_chunk(chunk_type, data):
        """创建 PNG chunk"""
        import zlib
        chunk_data = chunk_type + data
        crc = zlib.crc32(chunk_data) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk_data + struct.pack('>I', crc)
    
    # PNG signature
    signature = b'\x89PNG\r\n\x1a\n'
    
    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    ihdr = png_chunk(b'IHDR', ihdr_data)
    
    # IDAT chunk (image data)
    import zlib
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # filter type 0 (None)
        for x in range(width):
            r, g, b = color
            a = 255  # 完全不透明
            raw_data += bytes([r, g, b, a])
    
    compressed = zlib.compress(raw_data)
    idat = png_chunk(b'IDAT', compressed)
    
    # IEND chunk
    iend = png_chunk(b'IEND', b'')
    
    # 写入文件
    with open(filename, 'wb') as f:
        f.write(signature + ihdr + idat + iend)
    
    print(f'Created {filename} ({width}x{height})')

# 创建图标
create_simple_png('32x32.png', 32, 32)
create_simple_png('128x128.png', 128, 128)
create_simple_png('128x128@2x.png', 256, 256)

print('All icons created!')
