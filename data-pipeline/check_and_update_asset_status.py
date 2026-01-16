#!/usr/bin/env python3
"""
检查并更新胶囊的 asset_status

根据实际文件存在情况更新状态：
- 如果 audio/WAV 存在 → asset_status = 'local'
- 如果只有 OGG 和 RPP → asset_status = 'cloud_only'
"""

import sqlite3
import os
from pathlib import Path

# 数据库路径
DB_PATH = "data-pipeline/database/capsules.db"

# 导出目录（从配置获取，这里先硬编码）
EXPORT_DIR = Path("/Users/ianzhao/Documents/t111")

def check_capsule_files(capsule_id, capsule_name):
    """检查胶囊的文件是否存在"""
    capsule_dir = EXPORT_DIR / capsule_name

    if not capsule_dir.exists():
        return {
            'has_wav': False,
            'has_ogg': False,
            'has_rpp': False,
            'has_audio_folder': False
        }

    # 检查文件
    wav_files = list(capsule_dir.glob("*.wav")) + list((capsule_dir / "audio").glob("*.wav")) if (capsule_dir / "audio").exists() else []
    ogg_files = list(capsule_dir.glob("*.ogg"))
    rpp_files = list(capsule_dir.glob("*.rpp"))

    return {
        'has_wav': len(wav_files) > 0,
        'has_ogg': len(ogg_files) > 0,
        'has_rpp': len(rpp_files) > 0,
        'has_audio_folder': (capsule_dir / "audio").exists(),
        'wav_count': len(wav_files),
        'ogg_count': len(ogg_files),
        'rpp_count': len(rpp_files)
    }

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取所有胶囊
    cursor.execute("SELECT id, name, file_path FROM capsules")
    capsules = cursor.fetchall()

    print(f"检查 {len(capsules)} 个胶囊的文件状态...\n")

    for capsule_id, name, file_path in capsules:
        files = check_capsule_files(capsule_id, file_path or name)

        # 判断正确的 asset_status
        if files['has_wav']:
            correct_status = 'local'
        elif files['has_ogg'] and files['has_rpp']:
            correct_status = 'cloud_only'  # 有预览但无完整资源
        else:
            correct_status = 'cloud_only'

        # 获取当前状态
        cursor.execute("SELECT asset_status FROM capsules WHERE id = ?", (capsule_id,))
        row = cursor.fetchone()
        current_status = row[0] if row else None

        # 显示状态
        status_match = "✅" if current_status == correct_status else "❌"
        print(f"{status_match} ID={capsule_id} | {file_path or name}")
        print(f"   当前状态: {current_status}")
        print(f"   正确状态: {correct_status}")
        print(f"   文件检查: WAV={files['wav_count']}, OGG={files['ogg_count']}, RPP={files['rpp_count']}, audio文件夹={files['has_audio_folder']}")

        # 如果状态不匹配，更新
        if current_status != correct_status:
            print(f"   📝 更新状态: {current_status} → {correct_status}")
            cursor.execute(
                "UPDATE capsules SET asset_status = ? WHERE id = ?",
                (correct_status, capsule_id)
            )
            conn.commit()
        else:
            print(f"   ✓ 状态正确")

        print()

    conn.close()
    print("✅ 检查完成！")

if __name__ == "__main__":
    main()
