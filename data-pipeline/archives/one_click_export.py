"""
一键导出功能

通过文件信号触发 REAPER 自动导出
"""

import os
import json
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 临时文件目录
TEMP_DIR = Path("/tmp/synest_export")
SIGNAL_FILE = TEMP_DIR / "trigger.txt"
CONFIG_FILE = TEMP_DIR / "config.json"
RESULT_FILE = TEMP_DIR / "result.json"


def trigger_reaper_export(project_name, theme_name, render_preview=True):
    """
    触发 REAPER 导出

    通过创建信号文件,通知 REAPER 开始导出
    """
    # 创建临时目录
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 准备配置
    config = {
        "project_name": project_name,
        "theme_name": theme_name,
        "render_preview": render_preview,
        "output_dir": str(Path(__file__).parent / "output")
    }

    # 写入配置文件
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    # 创建信号文件 (通知 REAPER)
    with open(SIGNAL_FILE, 'w') as f:
        f.write(str(CONFIG_FILE) + '\n')
        f.write(str(RESULT_FILE) + '\n')

    print(f"✓ 已触发 REAPER 导出")
    print(f"  项目: {project_name}")
    print(f"  主题: {theme_name}")
    print(f"  预览: {render_preview}")
    print(f"\n请在 REAPER 中按以下操作:")
    print(f"  1. 打开 Actions 列表 (Actions → Show action list)")
    print(f"  2. 搜索并运行: one_click_export")
    print(f"  3. 或手动运行: data-pipeline/lua_scripts/one_click_export.lua")

    return {
        'success': True,
        'signal_file': str(SIGNAL_FILE),
        'config_file': str(CONFIG_FILE)
    }


def wait_for_export_result(timeout=60):
    """
    等待 REAPER 导出完成

    监控结果文件,直到 REAPER 写入导出结果
    """
    print(f"\n等待 REAPER 导出完成...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        if RESULT_FILE.exists():
            try:
                with open(RESULT_FILE, 'r', encoding='utf-8') as f:
                    result = json.load(f)

                # 清理临时文件
                SIGNAL_FILE.unlink(missing_ok=True)
                RESULT_FILE.unlink(missing_ok=True)

                return result
            except:
                pass

        time.sleep(1)

    return {
        'success': False,
        'error': f'等待超时 ({timeout}秒)'
    }


def clean_temp_files():
    """清理临时文件"""
    SIGNAL_FILE.unlink(missing_ok=True)
    CONFIG_FILE.unlink(missing_ok=True)
    RESULT_FILE.unlink(missing_ok=True)


if __name__ == '__main__':
    import sys

    try:
        if len(sys.argv) > 1:
            project_name = sys.argv[1]
            theme_name = sys.argv[2] if len(sys.argv) > 2 else "默认主题"
        else:
            project_name = input("项目名: ")
            theme_name = input("主题名: ")

        # 触发导出
        result = trigger_reaper_export(project_name, theme_name)

        if result['success']:
            # 等待完成
            final_result = wait_for_export_result()

            if final_result.get('success'):
                print(f"\n✓ 导出成功!")
                print(f"  胶囊ID: {final_result.get('capsule_id')}")
            else:
                print(f"\n✗ 导出失败: {final_result.get('error')}")

    except KeyboardInterrupt:
        print("\n\n用户取消")
        clean_temp_files()
        sys.exit(1)
    finally:
        clean_temp_files()
