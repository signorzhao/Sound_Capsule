"""
RPP 文件解析器

解析 REAPER 项目文件（.RPP），提取轨道、Item、插件等信息
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional


class RPPParser:
    """REAPER 项目文件解析器"""

    def __init__(self, rpp_path: Path):
        """
        初始化解析器

        Args:
            rpp_path: RPP 文件路径
        """
        self.rpp_path = Path(rpp_path)
        self.content: str = ""
        self.lines: List[str] = []
        self.tracks: List[Dict[str, Any]] = []

    def load(self) -> None:
        """加载 RPP 文件"""
        if not self.rpp_path.exists():
            raise FileNotFoundError(f"RPP 文件不存在: {self.rpp_path}")

        # RPP 文件使用 UTF-8 编码
        with open(self.rpp_path, 'r', encoding='utf-8', errors='ignore') as f:
            self.content = f.read()
            self.lines = self.content.splitlines()

    def parse_project_info(self) -> Dict[str, Any]:
        """
        解析项目信息

        Returns:
            项目信息字典（BPM、采样率等）
        """
        info = {
            'bpm': 120.0,
            'sample_rate': 48000,
            'project_name': self.rpp_path.stem
        }

        for line in self.lines:
            # 查找 BPM
            if 'BPM' in line or 'TEMPO' in line:
                match = re.search(r'(\d+\.?\d*)\s*[BPM]*', line, re.IGNORECASE)
                if match:
                    info['bpm'] = float(match.group(1))

            # 查找采样率
            if 'SAMPLERATE' in line or 'SRATE' in line:
                match = re.search(r'(\d+)\s*HZ', line, re.IGNORECASE)
                if match:
                    info['sample_rate'] = int(match.group(1))

        return info

    def parse_tracks(self) -> List[Dict[str, Any]]:
        """
        解析所有轨道

        Returns:
            轨道列表
        """
        self.tracks = []
        current_track: Optional[Dict[str, Any]] = None
        current_item: Optional[Dict[str, Any]] = None
        depth = 0
        track_index = 0

        for line_num, line in enumerate(self.lines):
            # 轨道开始
            if '<TRACK' in line or '<TRACK ' in line:
                current_track = {
                    'index': track_index,
                    'line_start': line_num,
                    'items': [],
                    'sends': [],
                    'receives': [],
                    'plugins': [],
                    'is_folder': False,
                    'folder_depth': 0,
                    'parent_index': None,
                    'name': '',
                    'flags': 0,
                    'muted': False,
                    'solo': False,
                    'volume': 1.0,
                    'pan': 0.0,
                    'height': 0
                }
                depth = 1
                track_index += 1

            elif current_track is not None and depth > 0:
                # 轨道名称
                if 'NAME' in line and current_track['name'] == '':
                    match = re.search(r'NAME\s+"([^"]*)"', line)
                    if match:
                        current_track['name'] = match.group(1)

                # 轨道标志位（包含是否为文件夹）
                elif 'TRACKHEIGHT' in line or 'FOLDER' in line:
                    match = re.search(r'(\d+)', line)
                    if match:
                        flags = int(match.group(1))
                        current_track['flags'] = flags
                        # 检查是否是文件夹（位标志）
                        current_track['is_folder'] = (flags & 1) != 0

                # 音量
                elif 'VOLPAN' in line or 'VOLUME' in line:
                    match = re.search(r'([\d.-]+)', line)
                    if match:
                        try:
                            current_track['volume'] = float(match.group(1))
                        except:
                            pass

                # 静音/独奏
                elif 'MUTE' in line or 'MUTED' in line:
                    if '1' in line or 'true' in line.lower():
                        current_track['muted'] = True
                elif 'SOLO' in line or 'SOLOED' in line:
                    if '1' in line or 'true' in line.lower():
                        current_track['solo'] = True

                # Item 开始
                elif '<ITEM' in line:
                    current_item = {
                        'track_index': current_track['index'],
                        'line_start': line_num,
                        'selected': False,
                        'position': 0.0,
                        'length': 0.0,
                        'offset': 0.0,
                        'source_file': '',
                        'take_count': 0,
                        'plugins': []
                    }

                    # 检查是否选中
                    if 'SEL' in line:
                        current_item['selected'] = True

                # Item 内容
                elif current_item is not None:
                    # Item 位置
                    if 'POSITION' in line:
                        match = re.search(r'POSITION\s+([\d.-]+)', line)
                        if match:
                            current_item['position'] = float(match.group(1))

                    # Item 长度
                    elif 'LENGTH' in line or 'DURATION' in line:
                        match = re.search(r'(?:LENGTH|DURATION)\s+([\d.-]+)', line)
                        if match:
                            current_item['length'] = float(match.group(1))

                    # Item 偏移
                    elif 'OFFSET' in line or 'SOFF' in line:
                        match = re.search(r'(?:OFFSET|SOFF)\s+([\d.-]+)', line)
                        if match:
                            current_item['offset'] = float(match.group(1))

                    # 音频源文件
                    elif '<SOURCE' in line or 'SOURCE FILE' in line:
                        match = re.search(r'FILE\s+"([^"]*)"', line)
                        if match:
                            current_item['source_file'] = match.group(1)
                        else:
                            # 尝试其他格式
                            match = re.search(r'"([^"]*\.(?:wav|WAV|ogg|OGG|mp3|MP3|flac|FLAC)[^"]*)"', line)
                            if match:
                                current_item['source_file'] = match.group(1)

                    # Take（音频片段）
                    elif '<TAKE' in line:
                        current_item['take_count'] = current_item.get('take_count', 0) + 1

                    # 插件
                    elif '<FXCHAIN' in line or '<VST' in line or '<AU' in line:
                        plugin_name = self._extract_plugin_name(line)
                        if plugin_name:
                            current_item['plugins'].append(plugin_name)

                    # Item 结束
                    elif '</ITEM>' in line:
                        if current_item['selected']:
                            current_track['items'].append(current_item)
                        current_item = None

                # Send 效果
                elif '<AUXRENDER' in line or 'AUXSEND' in line or 'SEND' in line:
                    send_info = self._parse_send(line, line_num)
                    if send_info:
                        current_track['sends'].append(send_info)

                # 接收效果
                elif '<RECEIVE' in line or 'Rcv' in line:
                    receive_info = self._parse_receive(line, line_num)
                    if receive_info:
                        current_track['receives'].append(receive_info)

                # 轨道结束
                elif '</TRACK>' in line:
                    depth -= 1
                    if depth == 0:
                        self.tracks.append(current_track)
                        current_track = None

        return self.tracks

    def get_selected_items(self) -> List[Dict[str, Any]]:
        """
        获取所有选中的 Item

        Returns:
            选中的 Item 列表
        """
        if not self.tracks:
            self.parse_tracks()

        selected_items = []
        for track in self.tracks:
            for item in track['items']:
                if item.get('selected', False):
                    item['track'] = track
                    selected_items.append(item)

        return selected_items

    def _parse_send(self, line: str, line_num: int) -> Optional[Dict[str, Any]]:
        """解析 Send 效果"""
        # 提取目标轨道索引
        match = re.search(r'SEND\s+(\d+)', line, re.IGNORECASE)
        if match:
            target_index = int(match.group(1))
            return {
                'target_index': target_index,
                'type': 'send',
                'line': line_num
            }
        return None

    def _parse_receive(self, line: str, line_num: int) -> Optional[Dict[str, Any]]:
        """解析 Receive 效果"""
        match = re.search(r'RECEIVE\s+(\d+)', line, re.IGNORECASE)
        if match:
            source_index = int(match.group(1))
            return {
                'source_index': source_index,
                'type': 'receive',
                'line': line_num
            }
        return None

    def _extract_plugin_name(self, line: str) -> Optional[str]:
        """从行中提取插件名称"""
        # 尝试匹配常见格式
        patterns = [
            r'VST\s+"([^"]*)"',
            r'AU\s+"([^"]*)"',
            r'VST3\s+"([^"]*)"',
            r'<JS\s+"([^"]*)"',
            r'NAME\s+"([^"]*)"'
        ]

        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def get_track_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """
        根据索引获取轨道

        Args:
            index: 轨道索引

        Returns:
            轨道字典或 None
        """
        if not self.tracks:
            self.parse_tracks()

        for track in self.tracks:
            if track['index'] == index:
                return track

        return None

    def get_folder_structure(self) -> Dict[int, List[int]]:
        """
        获取文件夹结构（父子轨道关系）

        Returns:
            字典：{父轨道索引: [子轨道索引列表]}
        """
        if not self.tracks:
            self.parse_tracks()

        folder_structure = {}

        for i, track in enumerate(self.tracks):
            if track.get('is_folder', False):
                # 查找子轨道（直到下一个同级的文件夹）
                children = []
                for j in range(i + 1, len(self.tracks)):
                    child_track = self.tracks[j]
                    # 简单的判断：子轨道在父轨道之后
                    # 实际应该根据 RPP 的缩进判断
                    if child_track['index'] > track['index']:
                        children.append(child_track['index'])
                    else:
                        break

                if children:
                    folder_structure[track['index']] = children

        return folder_structure


# 测试代码
if __name__ == '__main__':
    # 测试解析器
    import sys

    if len(sys.argv) > 1:
        rpp_file = Path(sys.argv[1])
    else:
        print("用法: python rpp_parser.py <RPP文件路径>")
        sys.exit(1)

    parser = RPPParser(rpp_file)
    parser.load()

    print(f"✓ 成功加载 RPP 文件: {rpp_file.name}")
    print(f"  文件行数: {len(parser.lines)}")

    # 解析项目信息
    info = parser.parse_project_info()
    print(f"\n项目信息:")
    print(f"  BPM: {info['bpm']}")
    print(f"  采样率: {info['sample_rate']} Hz")

    # 解析轨道
    tracks = parser.parse_tracks()
    print(f"\n轨道数量: {len(tracks)}")

    for track in tracks:
        print(f"\n轨道 {track['index']}: {track['name'] or '(未命名)'}")
        print(f"  文件夹: {'是' if track['is_folder'] else '否'}")
        print(f"  选中的 Item: {len(track['items'])}")
        print(f"  Send 效果: {len(track['sends'])}")

        for item in track['items']:
            print(f"    Item: 位置={item['position']}, 长度={item['length']}")
            if item['source_file']:
                print(f"      源文件: {item['source_file']}")

    # 获取选中的 Item
    selected = parser.get_selected_items()
    print(f"\n总共选中的 Item: {len(selected)}")
