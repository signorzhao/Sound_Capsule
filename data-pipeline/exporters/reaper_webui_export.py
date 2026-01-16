"""
REAPER Web UI 远程控制导出器

使用配置文件 + -nonewinst 参数在当前实例中执行脚本
"""

import os
import json
import time
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional


def sanitize_path_for_lua(path: str) -> str:
    """
    将路径转换为 Lua 兼容格式

    Windows: C:\\Users\\xxx -> C:/Users/xxx
    Unix: /home/xxx -> /home/xxx

    Args:
        path: 原始路径

    Returns:
        Lua 兼容的路径字符串
    """
    if not path:
        return ""

    # 确保是绝对路径
    # 注意: pathlib 在非 Windows 系统上无法正确识别 Windows 路径
    # 所以我们需要手动检查 Windows 驱动器字母格式
    is_absolute = Path(path).is_absolute()

    # 如果不是绝对路径，检查是否是 Windows 风格的绝对路径
    if not is_absolute:
        # Windows 路径: C:\ 或 C:/
        if len(path) >= 2 and path[1] == ':':
            is_absolute = True

    if not is_absolute:
        raise ValueError(f"export_dir 必须是绝对路径: {path}")

    # 手动转换为正斜杠（跨平台兼容）
    # 在 Unix 系统上，pathlib 不会转换 Windows 风格的反斜杠
    lua_compatible_path = path.replace('\\', '/')

    return lua_compatible_path


class ReaperWebUIExporter:
    """REAPER Web UI 远程控制器"""

    def __init__(self, host: str = "localhost", port: int = 9000):
        """
        初始化 Web UI 客户端

        Args:
            host: REAPER Web UI 服务器地址
            port: REAPER Web UI 服务器端口
        """
        self.base_url = f"http://{host}:{port}"
        self.api_base = f"{self.base_url}/api"

    def test_connection(self) -> bool:
        """测试 Web UI 连接"""
        try:
            import requests
            response = requests.get(f"{self.base_url}", timeout=5)
            if response.status_code == 200:
                print(f"✓ REAPER Web UI 已连接: {self.base_url}")
                return True
            else:
                print(f"✗ Web UI 返回状态码: {response.status_code}")
                return False
        except ImportError:
            print(f"⚠ requests 模块未安装,跳过 Web UI 连接测试")
            return False
        except Exception as e:
            print(f"✗ 无法连接到 REAPER Web UI: {self.base_url}")
            print(f"  请确保 REAPER 中的 Web Server 已启动")
            print(f"  错误详情: {e}")
            return False

    def prepare_export_config(self, config: Dict[str, Any]) -> bool:
        """
        准备导出配置文件

        Args:
            config: 配置字典，必须包含 export_dir 字段

        Returns:
            是否成功
        """
        temp_dir = Path("/tmp/synest_export")
        temp_dir.mkdir(parents=True, exist_ok=True)

        config_file = temp_dir / "webui_export_config.json"

        try:
            # 验证并转换 export_dir 为绝对路径
            export_dir = config.get('export_dir')

            if export_dir:
                # 转换为 Lua 兼容的绝对路径
                sanitized_dir = sanitize_path_for_lua(export_dir)
                config['export_dir'] = sanitized_dir

                print(f"✓ 导出目录已验证:")
                print(f"  原始路径: {export_dir}")
                print(f"  转换后: {sanitized_dir}")

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"✓ 配置已准备: {config_file}")
            return True
        except ValueError as e:
            print(f"✗ 路径验证失败: {e}")
            return False
        except Exception as e:
            print(f"✗ 写入配置失败: {e}")
            return False

    def export_via_webui(
        self,
        project_name: str,
        theme_name: str,
        render_preview: bool = True,
        capsule_type: str = 'magic',
        export_dir: str = None
    ) -> Dict[str, Any]:
        """
        通过 REAPER Web UI 执行导出

        流程:
        1. 测试连接
        2. 准备配置文件
        3. 等待用户在 REAPER 中手动执行导出
        4. 读取结果文件

        Args:
            project_name: 项目名
            theme_name: 主题名
            render_preview: 是否渲染预览
            capsule_type: 胶囊类型 (magic/impact/atmosphere)

        Returns:
            导出结果
        """
        # 注意: 我们使用 AppleScript 和 -nonewinst 参数,不需要 REAPER Web UI 运行
        # 但保留 test_connection() 作为可选的诊断信息

        print(f"尝试连接 REAPER Web UI (可选)...")
        connection_ok = self.test_connection()
        if not connection_ok:
            print(f"⚠ REAPER Web UI 未运行,但这不影响导出功能")
            print(f"  导出将通过 AppleScript/-nonewinst 直接执行")

        # 获取系统用户名
        import getpass
        username = getpass.getuser()

        # 0. 清理旧的结果文件（避免读取到旧数据）
        result_file = Path("/tmp/synest_export/export_result.json")
        if result_file.exists():
            print(f"⚠️  发现旧的结果文件，删除: {result_file}")
            result_file.unlink()
            time.sleep(0.1)  # 短暂等待确保删除完成

        # 1. 准备配置
        config = {
            "project_name": project_name,
            "theme_name": theme_name,
            "render_preview": render_preview,
            "capsule_type": capsule_type,
            "username": username,
            "export_dir": export_dir  # 添加导出目录到配置
        }

        if not self.prepare_export_config(config):
            return {
                'success': False,
                'error': '准备配置失败'
            }

        # 3. 调用 REAPER 执行导出脚本
        from common import PathManager
        pm = PathManager.get_instance()
        script_path = pm.get_lua_script("auto_export_from_config.lua")

        if not script_path.exists():
            return {
                'success': False,
                'error': f'Lua 脚本不存在: {script_path}'
            }

        print(f"✓ 准备执行 Lua 脚本: {script_path}")

        try:
            # 方法 1: 尝试使用 AppleScript (macOS)
            print(f"✓ 尝试通过 AppleScript 执行脚本...")

            script_content = f'''tell application "REAPER"
    do Lua script "{script_path}"
end tell'''

            apple_script_cmd = [
                'osascript',
                '-e',
                script_content
            ]

            result = subprocess.run(
                apple_script_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            print(f"✓ AppleScript 命令已发送")
            print(f"  返回码: {result.returncode}")
            print(f"  标准输出: {result.stdout}")
            if result.stderr:
                print(f"  标准错误: {result.stderr}")

            # 如果 AppleScript 失败，回退到命令行方法
            if result.returncode != 0:
                print(f"⚠️  AppleScript 失败，尝试命令行方法...")

                # 查找 REAPER 可执行文件
                import shutil
                reaper_cmd = shutil.which("reaper")
                if not reaper_cmd:
                    # 尝试 macOS 默认路径
                    reaper_cmd = "/Applications/REAPER.app/Contents/MacOS/REAPER"
                    if not Path(reaper_cmd).exists():
                        return {
                            'success': False,
                            'error': '找不到 REAPER 可执行文件'
                        }

                print(f"✓ REAPER 路径: {reaper_cmd}")

                # 使用 -nonewinst 参数在当前实例中执行脚本
                cmd = [reaper_cmd, "-nonewinst", str(script_path)]

                print(f"✓ 执行命令: {' '.join(cmd)}")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5  # 只等待5秒，-nonewinst会立即返回
                )

                print(f"✓ REAPER 命令已发送")
                print(f"  返回码: {result.returncode}")
                print(f"  标准输出: {result.stdout}")
                if result.stderr:
                    print(f"  标准错误: {result.stderr}")

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'REAPER 执行超时 (5秒) - 但这可能正常，继续等待结果文件...'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'执行 REAPER 失败: {e}'
            }

        # 4. 等待结果文件
        result_file = Path("/tmp/synest_export/export_result.json")
        timeout = 180  # 3分钟
        start_time = time.time()
        check_interval = 0.5  # 每0.5秒检查一次
        script_start_time = time.time()  # 记录脚本开始时间

        print(f"等待导出完成... (最长等待 {timeout} 秒)")
        print(f"检查间隔: {check_interval} 秒")

        waited_time = 0
        while time.time() - start_time < timeout:
            if result_file.exists():
                # 检查文件修改时间，确保是新创建的文件
                file_mtime = result_file.stat().st_mtime
                file_age = time.time() - file_mtime

                # 如果文件是脚本启动之前创建的，说明是旧文件
                if file_mtime < script_start_time:
                    print(f"⚠️  检测到旧的结果文件（{file_age:.1f}秒前），跳过...")
                    time.sleep(check_interval)
                    waited_time += check_interval
                    continue

                print(f"✓ 检测到结果文件! (文件年龄: {file_age:.2f}秒)")
                try:
                    # 等待一小段时间确保文件写入完成
                    time.sleep(0.2)

                    with open(result_file, 'r') as f:
                        result_data = json.load(f)

                    # 清理文件
                    result_file.unlink(missing_ok=True)

                    print(f"✓ 结果文件读取成功")
                    print(f"  成功: {result_data.get('success')}")

                    if result_data.get('success'):
                        capsule = result_data.get('capsule_name')
                        print(f"✓ 导出成功: {capsule}")
                        return result_data
                    else:
                        error = result_data.get('error', '导出失败')
                        print(f"✗ 导出失败: {error}")
                        return {
                            'success': False,
                            'error': error
                        }
                except Exception as e:
                    print(f"✗ 读取结果文件失败: {e}")
                    # 继续等待，可能是文件正在写入

            waited_time = time.time() - start_time
            if int(waited_time) % 10 == 0 and waited_time > 0:
                print(f"  等待中... 已等待 {int(waited_time)} 秒")

            time.sleep(check_interval)

        # 超时
        print(f"✗ 等待超时 ({timeout}秒)")
        print(f"  结果文件不存在: {result_file}")

        # 检查临时目录
        temp_dir = Path("/tmp/synest_export")
        if temp_dir.exists():
            print(f"  临时目录内容:")
            for file in temp_dir.iterdir():
                print(f"    - {file.name}")

        return {
            'success': False,
            'error': f'等待超时 ({timeout}秒)。REAPER可能未执行脚本或执行失败'
        }


def quick_webui_export(
    project_name: str,
    theme_name: str,
    render_preview: bool = True,
    webui_port: int = 9000,
    capsule_type: str = 'magic',
    export_dir: str = None
) -> Dict[str, Any]:
    """
    快捷 Web UI 导出函数

    Args:
        project_name: 项目名
        theme_name: 主题名
        render_preview: 是否渲染预览
        webui_port: Web UI 端口
        capsule_type: 胶囊类型 (magic/impact/atmosphere)
        export_dir: 导出目录路径（可选）

    Returns:
        导出结果
    """
    exporter = ReaperWebUIExporter(port=webui_port)
    return exporter.export_via_webui(project_name, theme_name, render_preview, capsule_type, export_dir)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("用法: python reaper_webui_export.py <项目名> <主题名> [渲染预览:1/0] [WebUI端口]")
        sys.exit(1)

    project = sys.argv[1]
    theme = sys.argv[2]
    preview = len(sys.argv) > 2 and sys.argv[3] == '1'
    port = int(sys.argv[4]) if len(sys.argv) > 4 else 9000

    print(f"REAPER Web UI 远程导出:")
    print(f"  项目: {project}")
    print(f"  主题: {theme}")
    print(f"  预览: {preview}")
    print(f"  WebUI 端口: {port}\n")

    result = quick_webui_export(project, theme, preview, port)

    if result['success']:
        print(f"\n✅ 导出成功!")
        print(f"   胶囊: {result.get('capsule_name')}")
    else:
        print(f"\n❌ 导出失败: {result.get('error')}")
        sys.exit(1)
