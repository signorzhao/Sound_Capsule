"""
REAPER 自动化导出器

通过 Python 脚本自动控制 REAPER 执行导出操作
无需用户手动切换到 REAPER 界面
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


class ReaperAutomation:
    """REAPER 自动化控制类"""

    def __init__(self, reaper_path=None):
        """
        初始化 REAPER 自动化控制器

        Args:
            reaper_path: REAPER 可执行文件路径（可选）
        """
        self.reaper_path = reaper_path or self._find_reaper_path()

    def _find_reaper_path(self) -> Optional[str]:
        """查找 REAPER 可执行文件"""
        # macOS 上的 REAPER 路径
        macos_paths = [
            "/Applications/REAPER.app/Contents/MacOS/REAPER",
            "/Applications/REAPER64.app/Contents/MacOS/REAPER",
        ]

        for path in macos_paths:
            if os.path.exists(path):
                return path

        return None

    def get_active_reaper_project(self) -> Optional[str]:
        """
        获取当前打开的 REAPER 项目路径

        Returns:
            项目路径，如果没有打开项目则返回 None
        """
        try:
            # 方法1: 使用 AppleScript 获取 REAPER 前台项目
            script = '''
            tell application "System Events"
                set isRunning to (name of processes) contains "REAPER"
            end tell

            if isRunning then
                tell application "REAPER"
                    try
                        set projPath to POSIX path of (project path of project 1)
                        return projPath
                    on error
                        return "NO_PROJECT"
                    end try
                end tell
            else
                return "NOT_RUNNING"
            end if
            '''

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                path = result.stdout.strip()
                if path and path not in ["NOT_RUNNING", "NO_PROJECT"] and os.path.exists(path):
                    print(f"通过 AppleScript 找到项目: {path}")
                    return path

            # 方法2: 查找最近修改的 RPP 文件
            print("AppleScript 失败,尝试查找最近修改的 RPP 文件...")

            # 常见的 REAPER 项目目录
            search_paths = [
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Desktop"),
                "/tmp"
            ]

            recent_rpp = None
            recent_time = 0

            for base_path in search_paths:
                if not os.path.exists(base_path):
                    continue

                for root, dirs, files in os.walk(base_path):
                    # 限制搜索深度
                    depth = root.count(os.sep) - base_path.count(os.sep)
                    if depth > 3:
                        continue

                    for file in files:
                        if file.endswith('.RPP'):
                            full_path = os.path.join(root, file)
                            mtime = os.path.getmtime(full_path)

                            # 只考虑最近 1 小时内修改的文件
                            if mtime > recent_time and (time.time() - mtime) < 3600:
                                recent_time = mtime
                                recent_rpp = full_path

            if recent_rpp:
                print(f"找到最近修改的 RPP 文件: {recent_rpp}")
                return recent_rpp

            print("未找到最近修改的 RPP 文件")
            return None

        except Exception as e:
            print(f"获取 REAPER 项目失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def execute_lua_script_via_cli(
        self,
        lua_script_path: str,
        project_path: str = None,
        script_args: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        通过命令行执行 Lua 脚本

        Args:
            lua_script_path: Lua 脚本路径
            project_path: REAPER 项目路径（可选，如果指定会自动加载项目）
            script_args: 传递给脚本的参数

        Returns:
            执行结果字典
        """
        if not os.path.exists(lua_script_path):
            return {
                'success': False,
                'error': f'Lua 脚本不存在: {lua_script_path}'
            }

        try:
            # 构建命令行参数
            cmd = [self.reaper_path]

            # 添加项目路径
            if project_path:
                cmd.extend([project_path])

            # 添加 Lua 脚本
            cmd.extend(["-evalscript", lua_script_path])

            print(f"执行命令: {' '.join(cmd)}")

            # 执行命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 等待完成（最多 60 秒）
            try:
                stdout, stderr = process.communicate(timeout=60)

                if process.returncode == 0:
                    return {
                        'success': True,
                        'output': stdout,
                        'project': project_path
                    }
                else:
                    return {
                        'success': False,
                        'error': stderr or 'REAPER 执行失败',
                        'code': process.returncode
                    }
            except subprocess.TimeoutExpired:
                process.kill()
                return {
                    'success': False,
                    'error': '执行超时 (60秒)'
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def export_capsule(
        self,
        project_name: str,
        theme_name: str,
        render_preview: bool = True,
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        自动导出胶囊

        这个方法会:
        1. 检查是否有打开的 REAPER 项目
        2. 将导出参数写入临时配置文件
        3. 调用 Lua 脚本执行导出
        4. 等待导出完成

        Args:
            project_name: 项目名称
            theme_name: 主题名称
            render_preview: 是否渲染预览
            output_dir: 输出目录（可选）

        Returns:
            导出结果
        """
        # 1. 检查 REAPER 项目
        project_path = self.get_active_reaper_project()

        if not project_path:
            return {
                'success': False,
                'error': '未检测到打开的 REAPER 项目，请先在 REAPER 中打开并保存项目'
            }

        print(f"检测到 REAPER 项目: {project_path}")

        # 2. 准备配置文件
        # 从路径管理器获取路径
        from common import PathManager
        pm = PathManager.get_instance()
        
        temp_dir = Path("/tmp/synest_export")
        temp_dir.mkdir(parents=True, exist_ok=True)

        config_file = temp_dir / "export_config.json"
        config = {
            "project_name": project_name,
            "theme_name": theme_name,
            "render_preview": render_preview,
            "output_dir": output_dir or str(pm.export_dir)
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"配置已写入: {config_file}")

        # 3. 找到导出脚本
        lua_script = pm.get_lua_script("main_export2.lua")

        if not lua_script.exists():
            return {
                'success': False,
                'error': f'导出脚本不存在: {lua_script}'
            }

        # 4. 执行导出
        print("开始自动导出...")
        result = self.execute_lua_script_via_cli(
            str(lua_script),
            project_path,
            config
        )

        if result['success']:
            # 清理临时文件
            config_file.unlink(missing_ok=True)

            result['capsule_name'] = f"{project_name}_{theme_name}"

        return result


# 快捷函数
def export_capsule_from_synesth(
    project_name: str,
    theme_name: str,
    render_preview: bool = True
) -> Dict[str, Any]:
    """
    从 Synesth 导出胶囊

    这是最简单的一键导出接口

    Args:
        project_name: 项目名称
        theme_name: 主题名称
        render_preview: 是否渲染预览

    Returns:
        导出结果
    """
    automation = ReaperAutomation()
    return automation.export_capsule(
        project_name=project_name,
        theme_name=theme_name,
        render_preview=render_preview
    )


if __name__ == '__main__':
    # 测试代码
    import sys

    if len(sys.argv) < 3:
        print("用法: python reaper_automation.py <项目名> <主题名> [渲染预览:1/0]")
        sys.exit(1)

    project = sys.argv[1]
    theme = sys.argv[2]
    preview = len(sys.argv) > 3 and sys.argv[3] == '1'

    print(f"开始自动导出:")
    print(f"  项目: {project}")
    print(f"  主题: {theme}")
    print(f"  预览: {preview}")
    print()

    result = export_capsule_from_synesth(project, theme, preview)

    if result['success']:
        print(f"\n✓ 导出成功!")
        print(f"  胶囊: {result.get('capsule_name')}")
    else:
        print(f"\n✗ 导出失败: {result.get('error')}")
        sys.exit(1)
