"""
REAPER 无头模式导出器

使用 REAPER 命令行在后台执行导出,无需打开新窗口
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


class ReaperHeadlessExporter:
    """REAPER 无头模式导出器"""

    def __init__(self):
        self.reaper_path = self._find_reaper()

    def _find_reaper(self) -> Optional[str]:
        """查找 REAPER"""
        paths = [
            "/Applications/REAPER.app/Contents/MacOS/REAPER",
            "/Applications/REAPER64.app/Contents/MacOS/REAPER",
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def get_current_project(self) -> Optional[str]:
        """
        获取当前 REAPER 打开的项目路径

        方法1: 通过 lsof 查找 REAPER 进程打开的 .RPP 文件
        方法2: 查找最近修改的 .RPP 文件
        """
        # 方法1: 使用 lsof
        try:
            result = subprocess.run(
                ["lsof", "-c", "REAPER", "-F", "n"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # 解析输出,找到 .RPP 文件
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line.endswith('.RPP') or line.endswith('.rpp'):
                        if os.path.exists(line):
                            print(f"✓ 通过 lsof 找到项目: {line}")
                            return line
        except Exception as e:
            print(f"lsof 查找失败: {e}")

        # 方法2: 查找最近修改的 .RPP 文件
        print("lsof 未找到,尝试查找最近修改的 .RPP 文件...")

        # 常见的项目目录
        search_paths = [
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Music"),
            os.path.expanduser("~/"),
            "/tmp"
        ]

        recent_rpp = None
        recent_time = 0

        for base_path in search_paths:
            if not os.path.exists(base_path):
                continue

            try:
                for root, dirs, files in os.walk(base_path):
                    # 限制搜索深度
                    depth = root.count(os.sep) - base_path.count(os.sep)
                    if depth > 3:
                        dirs[:] = []  # 不继续深入
                        continue

                    for file in files:
                        if file.endswith('.RPP') or file.endswith('.rpp'):
                            full_path = os.path.join(root, file)
                            try:
                                mtime = os.path.getmtime(full_path)

                                # 只考虑最近 1 小时内修改的文件
                                if mtime > recent_time and (time.time() - mtime) < 3600:
                                    recent_time = mtime
                                    recent_rpp = full_path
                            except:
                                pass
            except Exception as e:
                continue

        if recent_rpp:
            print(f"✓ 找到最近修改的 .RPP 文件: {recent_rpp}")
            return recent_rpp

        print("✗ 未找到 REAPER 项目")
        print("\n提示:")
        print("  1. 确保 REAPER 正在运行")
        print("  2. 确保已打开一个项目")
        print("  3. 项目必须已保存 (.RPP 文件)")

        return None

    def export_with_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用配置文件导出

        流程:
        1. 保存配置到临时文件
        2. 启动 REAPER (加载当前项目) + 执行 Lua 脚本
        3. Lua 脚本读取配置并导出
        4. 等待结果文件
        5. 清理临时文件

        Args:
            config: 导出配置字典

        Returns:
            导出结果
        """
        # 1. 获取当前项目
        project_path = self.get_current_project()

        if not project_path:
            return {
                'success': False,
                'error': '未找到 REAPER 打开的项目。请确保 REAPER 正在运行且已打开项目。'
            }

        print(f"✓ 项目: {project_path}")

        # 2. 保存配置
        temp_dir = Path("/tmp/synest_export")
        temp_dir.mkdir(parents=True, exist_ok=True)

        config_file = temp_dir / "export_config.json"
        result_file = temp_dir / "export_result.json"

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"✓ 配置已保存: {config_file}")

        # 3. 准备 Lua 脚本路径
        from common import PathManager
        pm = PathManager.get_instance()
        lua_script = pm.get_lua_script("auto_export_from_config.lua")

        if not lua_script.exists():
            return {
                'success': False,
                'error': f'Lua 脚本不存在: {lua_script}'
            }

        print(f"✓ Lua 脚本: {lua_script}")

        # 4. 启动 REAPER 并执行脚本
        # 关键: 使用 -splashdisable 隐藏启动画面
        cmd = [
            self.reaper_path,
            project_path,
            "-splashdisable",
            "-evalscript", str(lua_script)
        ]

        print(f"\n执行命令:")
        print(f"  {self.reaper_path}")
        print(f"  {project_path}")
        print(f"  -splashdisable")
        print(f"  -evalscript {lua_script}")
        print()

        try:
            # 启动 REAPER (后台运行)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 5. 等待结果文件 (最多 60 秒)
            print("等待导出完成...")

            timeout = 60
            start_time = time.time()

            while time.time() - start_time < timeout:
                if result_file.exists():
                    print("✓ 检测到结果文件")

                    # 读取结果
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)

                    # 清理临时文件
                    config_file.unlink(missing_ok=True)
                    result_file.unlink(missing_ok=True)

                    if result.get('success'):
                        print(f"✓ 导出成功: {result.get('capsule_name')}")
                        return result
                    else:
                        return {
                            'success': False,
                            'error': result.get('error', '导出失败')
                        }

                time.sleep(0.5)

            # 超时
            print(f"✗ 等待超时 ({timeout}秒)")
            return {
                'success': False,
                'error': f'导出超时 ({timeout}秒),请检查 REAPER 是否有弹窗需要确认'
            }

        except Exception as e:
            print(f"✗ 执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }


def quick_export(project_name: str, theme_name: str, render_preview: bool = True) -> Dict[str, Any]:
    """
    快捷导出函数

    Args:
        project_name: 项目名
        theme_name: 主题名
        render_preview: 是否渲染预览

    Returns:
        导出结果
    """
    exporter = ReaperHeadlessExporter()

    config = {
        "project_name": project_name,
        "theme_name": theme_name,
        "render_preview": render_preview,
        "capsule_name": f"{project_name}_{theme_name}"
    }

    return exporter.export_with_config(config)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python reaper_headless_export.py <项目名> <主题名> [渲染预览:1/0]")
        sys.exit(1)

    project = sys.argv[1]
    theme = sys.argv[2]
    preview = len(sys.argv) > 3 and sys.argv[3] == '1'

    print(f"开始导出: {project}_{theme}")
    print(f"预览: {preview}\n")

    result = quick_export(project, theme, preview)

    if result['success']:
        print(f"\n✅ 导出成功!")
        print(f"   胶囊: {result.get('capsule_name')}")
    else:
        print(f"\n❌ 导出失败: {result.get('error')}")
        sys.exit(1)
