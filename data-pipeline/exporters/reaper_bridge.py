"""
REAPER 桥接器

负责调用 Lua 脚本导出胶囊
"""

import subprocess
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional
import time


class ReaperBridge:
    """REAPER 导出桥接器"""

    def __init__(self, reaper_capsule_path: Path, use_headless: bool = True):
        """
        初始化桥接器

        Args:
            reaper_capsule_path: REAPER Sonic Capsule 项目路径
            use_headless: 是否使用无头模式（默认 True）
        """
        self.reaper_capsule_path = Path(reaper_capsule_path)
        self.use_headless = use_headless

        # 根据模式选择 Lua 脚本
        if use_headless:
            script_name = "main_export_headless.lua"
        else:
            script_name = "main_export.lua"

        # 从路径管理器获取 Lua 脚本路径
        from common import PathManager
        pm = PathManager.get_instance()
        self.lua_script = pm.get_lua_script(script_name)
        
        if not self.lua_script.exists():
            raise FileNotFoundError(
                f"Lua 脚本不存在: {self.lua_script}\n"
                f"请确保 Lua 脚本位于: {pm.lua_scripts_dir}"
            )

    def find_reaper_executable(self) -> Optional[Path]:
        """
        查找 REAPER 可执行文件

        Returns:
            Path 或 None
        """
        import platform
        import shutil

        system = platform.system()

        if system == "Darwin":  # macOS
            paths = [
                Path("/Applications/REAPER.app/Contents/MacOS/REAPER"),
                Path("/Applications/REAPER64.app/Contents/MacOS/REAPER"),
                Path.home() / "Applications/REAPER.app/Contents/MacOS/REAPER"
            ]
        elif system == "Windows":
            paths = [
                Path("C:/Program Files/REAPER/reaper.exe"),
                Path("C:/Program Files (x86)/REAPER/reaper.exe"),
                Path.home() / "AppData/Local/Programs/REAPER/reaper.exe"
            ]
        else:  # Linux
            reaper_in_path = shutil.which("reaper")
            if reaper_in_path:
                return Path(reaper_in_path)
            paths = [Path("/usr/bin/reaper")]

        for path in paths:
            if path.exists():
                return path

        return None

    def export_capsule(
        self,
        project_name: str,
        theme_name: str,
        render_preview: bool = True,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        导出胶囊（通过 REAPER + Lua 脚本）

        Args:
            project_name: 项目名称
            theme_name: 主题名称
            render_preview: 是否渲染预览音频
            output_dir: 输出目录（可选）

        Returns:
            导出结果字典
        """
        if not self.use_headless:
            # 交互模式：提示用户手动操作
            return self.export_capsule_with_ui_hints(project_name, theme_name)

        # ===== 无头模式导出 =====
        # 查找 REAPER
        reaper_exe = self.find_reaper_executable()

        if not reaper_exe:
            return {
                'success': False,
                'error': '找不到 REAPER 可执行文件'
            }

        # 检查 Lua 脚本是否存在
        if not self.lua_script.exists():
            return {
                'success': False,
                'error': f'Lua 脚本不存在: {self.lua_script}'
            }

        # 创建临时文件
        temp_dir = Path(tempfile.gettempdir())

        # 1. 创建配置文件
        config_file = temp_dir / "synesth_export_config.json"
        
        # 如果没有提供 output_dir，从路径管理器获取
        if not output_dir:
            from common import PathManager
            pm = PathManager.get_instance()
            output_dir = pm.export_dir
        
        config_data = {
            "project_name": project_name,
            "theme_name": theme_name,
            "render_preview": render_preview,
            "output_dir": str(output_dir)  # 确保使用绝对路径
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        # 2. 创建结果文件路径
        result_file = temp_dir / "synesth_export_result.json"

        # 3. 创建信号文件（通知 Lua 脚本进入无头模式）
        signal_file = temp_dir / "synesth_headless_signal.txt"
        with open(signal_file, 'w') as f:
            f.write(str(config_file) + '\n')
            f.write(str(result_file) + '\n')

        try:
            # 4. 调用 REAPER 执行 Lua 脚本
            # 注意：这里需要 REAPER 已经打开了一个项目
            # 或者我们需要先打开一个项目

            # 使用 macOS 的 osascript 来向 REAPER 发送 AppleScript
            # 这样可以在已有实例中执行脚本
            import platform

            if platform.system() == "Darwin":  # macOS
                # 方法1: 尝试使用 AppleScript 调用 REAPER
                # 但 REAPER 不支持 AppleScript,所以这个方法不可行

                # 方法2: 使用命令行启动 REAPER 并执行脚本
                # REAPER 会在后台运行,执行完脚本后需要手动关闭

                # 创建一个包装脚本来执行并等待结果
                cmd = [
                    str(reaper_exe),
                    f"-reascript",
                    str(self.lua_script)
                ]

                print(f"执行命令: {' '.join(cmd)}")

                # 在后台执行 REAPER,不等待其完成
                # 因为 REAPER 执行完脚本后不会自动退出
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                print(f"REAPER 进程已启动 (PID: {process.pid})")
                print("等待脚本执行完成...")

                # 等待结果文件生成（最多等待 60 秒）
                max_wait = 60
                waited = 0
                while not result_file.exists() and waited < max_wait:
                    time.sleep(1)
                    waited += 1
                    if waited % 5 == 0:  # 每5秒打印一次
                        print(f"  已等待 {waited} 秒...")

            else:
                # Windows/Linux
                cmd = [
                    str(reaper_exe),
                    f"-reascript",
                    str(self.lua_script)
                ]

                print(f"执行命令: {' '.join(cmd)}")

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                print(f"REAPER 进程已启动 (PID: {process.pid})")
                print("等待脚本执行完成...")

                # 等待结果文件生成
                max_wait = 60
                waited = 0
                while not result_file.exists() and waited < max_wait:
                    time.sleep(1)
                    waited += 1
                    if waited % 5 == 0:
                        print(f"  已等待 {waited} 秒...")

            # 读取结果
            if result_file.exists():
                with open(result_file, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)

                print("✓ 收到导出结果")

                # 清理临时文件
                config_file.unlink(missing_ok=True)
                result_file.unlink(missing_ok=True)

                return result_data
            else:
                print(f"✗ 等待超时 ({max_wait}秒)")
                print("\n可能的原因:")
                print("  1. REAPER 没有响应")
                print("  2. Lua 脚本执行失败")
                print("  3. 没有选中音频 Item")
                print("  4. 项目未保存")
                print("\n请检查 REAPER 控制台输出了解详情")

                return {
                    'success': False,
                    'error': f'导出超时（{max_wait}秒），未收到结果'
                }
                # 注意: 信号文件在这里不应该被删除,因为REAPER可能还在尝试读取
                # 信号文件会在下次导出时被覆盖

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'REAPER 执行超时'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'导出失败: {str(e)}'
            }
        # 移除 finally 块,避免过早删除信号文件
        # 信号文件会在成功读取结果后被清理

    def export_capsule_with_ui_hints(self, project_name: str, theme_name: str) -> Dict[str, Any]:
        """
        导出胶囊（通过提示用户）

        这是一个临时的实现方案，在无头模式完成前使用

        Args:
            project_name: 项目名称
            theme_name: 主题名称

        Returns:
            导出结果字典
        """
        print("\n" + "="*60)
        print("🎵 Synesth 胶囊导出")
        print("="*60)
        print(f"\n请按以下步骤操作：\n")
        print(f"1. 在 REAPER 中，选中你想要导出的音频 Item")
        print(f"2. 在 REAPER 中，运行以下脚本：")
        print(f"   → {self.lua_script}")
        print(f"3. 在弹出的对话框中输入：")
        print(f"   胶囊名称: {project_name}_{theme_name}")
        print(f"   导出预览: 是")
        print(f"\n导出完成后，胶囊将保存在 REAPER Sonic Capsule 的 output 目录\n")
        print("="*60 + "\n")

        # 等待用户确认
        input("按 Enter 键继续（在 REAPER 中完成导出后）...")

        # 扫描输出目录查找新导出的胶囊
        output_dir = self.reaper_capsule_path / "output"

        if output_dir.exists():
            # 列出最近修改的文件夹
            capsule_dirs = [
                d for d in output_dir.iterdir()
                if d.is_dir() and (d / "metadata.json").exists()
            ]

            if capsule_dirs:
                # 按修改时间排序
                capsule_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                latest = capsule_dirs[0]

                # 读取元数据
                metadata_file = latest / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)

                    return {
                        'success': True,
                        'capsule_path': str(latest),
                        'metadata': metadata
                    }

        return {
            'success': False,
            'error': '未找到导出的胶囊，请确认已在 REAPER 中完成导出'
        }


# 测试代码
if __name__ == '__main__':
    import sys

    reaper_path = Path("../Reaper_Sonic_Capsule")

    if not reaper_path.exists():
        print(f"错误: REAPER Sonic Capsule 路径不存在: {reaper_path}")
        sys.exit(1)

    bridge = ReaperBridge(reaper_path)

    print("测试 REAPER 桥接器...")
    print(f"REAPER 路径: {reaper_path}")
    print(f"Lua 脚本: {bridge.lua_script}")

    reaper_exe = bridge.find_reaper_executable()
    if reaper_exe:
        print(f"✓ 找到 REAPER: {reaper_exe}")
    else:
        print("✗ 未找到 REAPER")

    # 测试导出（交互模式）
    result = bridge.export_capsule_with_ui_hints("测试项目", "测试主题")
    print(f"\n导出结果: {result}")
