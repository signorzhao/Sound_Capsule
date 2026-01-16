"""
REAPER OSC 远程触发导出器

通过 OSC 协议远程控制 REAPER 执行导出
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from pythonosc import udp_client
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False


class ReaperOSCExporter:
    """REAPER OSC 远程控制器"""

    def __init__(self, ip: str = "127.0.0.1", port: int = 9000):
        """
        初始化 OSC 客户端

        Args:
            ip: REAPER OSC 服务器 IP
            port: REAPER OSC 服务器端口
        """
        self.ip = ip
        self.port = port
        self.client = None

        if OSC_AVAILABLE:
            self.client = udp_client.SimpleUDPClient(ip, port)
        else:
            print("⚠️  警告: python-osc 未安装")
            print("   请运行: pip install python-osc")

    def test_connection(self) -> bool:
        """测试 OSC 连接"""
        if not self.client:
            return False

        try:
            # 发送一个测试消息
            self.client.send_message("/test", 1)
            print(f"✓ OSC 测试消息已发送到 {self.ip}:{self.port}")
            return True
        except Exception as e:
            print(f"✗ OSC 连接失败: {e}")
            return False

    def trigger_action(self, action_id: int) -> bool:
        """
        触发 REAPER Action

        Args:
            action_id: Action 编号

        Returns:
            是否成功
        """
        if not self.client:
            print("✗ OSC 客户端未初始化")
            return False

        try:
            # OSC 消息格式: /action/<command_id>
            self.client.send_message("/action", action_id)
            print(f"✓ 已触发 Action: {action_id}")
            return True
        except Exception as e:
            print(f"✗ 触发 Action 失败: {e}")
            return False

    def trigger_export_by_name(self, script_name: str) -> bool:
        """
        通过脚本名触发导出

        Args:
            script_name: Lua 脚本名称

        Returns:
            是否成功
        """
        if not self.client:
            return False

        try:
            # 通过 osc.trigger 命令
            self.client.send_message("/osc/trigger", script_name)
            print(f"✓ 已触发脚本: {script_name}")
            return True
        except Exception as e:
            print(f"✗ 触发脚本失败: {e}")
            return False

    def prepare_export_config(self, config: Dict[str, Any]) -> bool:
        """
        准备导出配置文件

        Args:
            config: 配置字典

        Returns:
            是否成功
        """
        temp_dir = Path("/tmp/synest_export")
        temp_dir.mkdir(parents=True, exist_ok=True)

        config_file = temp_dir / "osc_export_config.json"

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"✓ 配置已准备: {config_file}")
            return True
        except Exception as e:
            print(f"✗ 写入配置失败: {e}")
            return False

    def export_with_osc(
        self,
        project_name: str,
        theme_name: str,
        render_preview: bool = True,
        action_id: int = None
    ) -> Dict[str, Any]:
        """
        通过 OSC 触发 REAPER 导出

        流程:
        1. 准备配置文件
        2. 通过 OSC 触发 REAPER 中的导出 Action
        3. 等待 REAPER 完成导出
        4. 读取结果文件

        Args:
            project_name: 项目名
            theme_name: 主题名
            render_preview: 是否渲染预览
            action_id: Action ID (如果为 None,使用默认)

        Returns:
            导出结果
        """
        if not OSC_AVAILABLE:
            return {
                'success': False,
                'error': 'python-osc 未安装,请运行: pip install python-osc'
            }

        # 1. 准备配置
        config = {
            "project_name": project_name,
            "theme_name": theme_name,
            "render_preview": render_preview,
            "capsule_name": f"{project_name}_{theme_name}"
        }

        if not self.prepare_export_config(config):
            return {
                'success': False,
                'error': '准备配置失败'
            }

        # 2. 触发 REAPER 导出
        if action_id:
            success = self.trigger_action(action_id)
        else:
            # 使用默认的导出脚本
            success = self.trigger_export_by_name("auto_export_from_config")

        if not success:
            return {
                'success': False,
                'error': 'OSC 触发失败'
            }

        # 3. 等待结果文件
        result_file = Path("/tmp/synest_export/export_result.json")
        timeout = 60
        start_time = time.time()

        print("等待 REAPER 导出完成...")

        while time.time() - start_time < timeout:
            if result_file.exists():
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)

                    # 清理文件
                    result_file.unlink(missing_ok=True)

                    if result.get('success'):
                        print(f"✓ 导出成功: {result.get('capsule_name')}")
                        return result
                    else:
                        return {
                            'success': False,
                            'error': result.get('error', '导出失败')
                        }
                except:
                    pass

            time.sleep(0.5)

        # 超时
        return {
            'success': False,
            'error': f'等待超时 ({timeout}秒)'
        }


def quick_osc_export(
    project_name: str,
    theme_name: str,
    render_preview: bool = True,
    osc_port: int = 9000
) -> Dict[str, Any]:
    """
    快捷 OSC 导出函数

    Args:
        project_name: 项目名
        theme_name: 主题名
        render_preview: 是否渲染预览
        osc_port: OSC 端口

    Returns:
        导出结果
    """
    exporter = ReaperOSCExporter(port=osc_port)
    return exporter.export_with_osc(project_name, theme_name, render_preview)


if __name__ == '__main__':
    import sys

    if not OSC_AVAILABLE:
        print("错误: python-osc 未安装")
        print("请运行: pip install python-osc")
        sys.exit(1)

    if len(sys.argv) < 3:
        print("用法: python reaper_osc_export.py <项目名> <主题名> [渲染预览:1/0] [OSC端口]")
        sys.exit(1)

    project = sys.argv[1]
    theme = sys.argv[2]
    preview = len(sys.argv) > 2 and sys.argv[3] == '1'
    port = int(sys.argv[4]) if len(sys.argv) > 4 else 9000

    print(f"OSC 远程导出:")
    print(f"  项目: {project}")
    print(f"  主题: {theme}")
    print(f"  预览: {preview}")
    print(f"  OSC 端口: {port}\n")

    result = quick_osc_export(project, theme, preview, port)

    if result['success']:
        print(f"\n✅ 导出成功!")
        print(f"   胶囊: {result.get('capsule_name')}")
    else:
        print(f"\n❌ 导出失败: {result.get('error')}")
        sys.exit(1)
