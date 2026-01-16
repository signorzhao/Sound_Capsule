"""
依赖追踪器

使用 BFS（广度优先搜索）算法追踪所有相关的轨道
包括父轨道、Send 目标、文件夹结构等

移植自 Lua 脚本的 GetRelatedTracks 函数
"""

from typing import List, Dict, Any, Set, Optional


class DependencyTracker:
    """
    依赖追踪器

    功能：
    1. 追踪父轨道（文件夹结构）
    2. 追踪 Send 目标轨道
    3. 追踪 Receives 源轨道
    4. 使用 BFS 算法确保完整性
    """

    def __init__(self, tracks: List[Dict[str, Any]]):
        """
        初始化追踪器

        Args:
            tracks: 轨道列表（来自 RPPParser）
        """
        self.tracks = tracks
        self.track_map: Dict[int, Dict[str, Any]] = {
            t['index']: t for t in tracks
        }

    def get_related_tracks(self, item: Dict[str, Any]) -> Set[int]:
        """
        获取 Item 相关的所有轨道（BFS 算法）

        Args:
            item: 音频 Item（包含 track 引用）

        Returns:
            需要保留的轨道索引集合
        """
        keep_tracks: Set[int] = set()
        queue: List[Dict[str, Any]] = []
        processed: Set[int] = set()

        # 从 Item 所在的轨道开始
        item_track = item.get('track')
        if not item_track:
            return keep_tracks

        queue.append(item_track)
        keep_tracks.add(item_track['index'])

        # BFS 遍历
        while queue:
            track = queue.pop(0)
            track_idx = track['index']

            if track_idx in processed:
                continue

            processed.add(track_idx)

            # 1. 添加所有父轨道（文件夹结构）
            parent = self._find_parent_track(track)
            while parent:
                parent_idx = parent['index']
                if parent_idx not in keep_tracks:
                    keep_tracks.add(parent_idx)
                    queue.append(parent)
                parent = self._find_parent_track(parent)

            # 2. 添加所有 Send 目标轨道
            for send in track.get('sends', []):
                target_idx = send.get('target_index')
                if target_idx is not None:
                    target_track = self.track_map.get(target_idx)
                    if target_track and target_idx not in keep_tracks:
                        keep_tracks.add(target_idx)
                        queue.append(target_track)

                        # 递归添加目标轨道的父轨道
                        parent = self._find_parent_track(target_track)
                        while parent:
                            parent_idx = parent['index']
                            if parent_idx not in keep_tracks:
                                keep_tracks.add(parent_idx)
                                queue.append(parent)
                            parent = self._find_parent_track(parent)

            # 3. 添加所有 Receives 源轨道
            for receive in track.get('receives', []):
                source_idx = receive.get('source_index')
                if source_idx is not None:
                    source_track = self.track_map.get(source_idx)
                    if source_track and source_idx not in keep_tracks:
                        keep_tracks.add(source_idx)
                        queue.append(source_track)

        return keep_tracks

    def _find_parent_track(self, track: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        查找轨道的父轨道（文件夹）

        Args:
            track: 轨道字典

        Returns:
            父轨道字典或 None
        """
        track_idx = track['index']

        # 在 RPP 文件中，父轨道总是在子轨道之前
        # 向前搜索最近的文件夹轨道
        for i in range(track_idx - 1, -1, -1):
            potential_parent = self.track_map.get(i)
            if potential_parent and potential_parent.get('is_folder', False):
                # 检查是否是真正的父轨道
                # 通过检查轨道索引范围判断
                if self._is_child_of(potential_parent, track):
                    return potential_parent

        return None

    def _is_child_of(self, parent: Dict[str, Any], child: Dict[str, Any]) -> bool:
        """
        判断 child 是否是 parent 的子轨道

        Args:
            parent: 父轨道
            child: 子轨道

        Returns:
            是否是父子关系
        """
        parent_idx = parent['index']
        child_idx = child['index']

        # 父轨道的索引应该小于子轨道
        if parent_idx >= child_idx:
            return False

        # 检查中间是否有同级的文件夹轨道
        # （如果有，则 child 不是 parent 的直接子轨道）
        for i in range(parent_idx + 1, child_idx):
            between_track = self.track_map.get(i)
            if between_track and between_track.get('is_folder', False):
                return False

        return True

    def get_tracks_in_render_order(self, keep_track_indices: Set[int]) -> List[Dict[str, Any]]:
        """
        按渲染顺序获取轨道

        确保父轨道在子轨道之前

        Args:
            keep_track_indices: 要保留的轨道索引集合

        Returns:
            排序后的轨道列表
        """
        tracks = [self.track_map[i] for i in keep_track_indices if i in self.track_map]

        # 按索引排序（这会自动确保父轨道在子轨道之前）
        tracks.sort(key=lambda t: t['index'])

        return tracks

    def get_all_dependencies(self, items: List[Dict[str, Any]]) -> Set[int]:
        """
        获取多个 Item 的所有相关轨道

        Args:
            items: Item 列表

        Returns:
            所有需要保留的轨道索引集合
        """
        all_keep_tracks: Set[int] = set()

        for item in items:
            related = self.get_related_tracks(item)
            all_keep_tracks.update(related)

        return all_keep_tracks

    def analyze_routing_info(self, keep_track_indices: Set[int]) -> Dict[str, Any]:
        """
        分析路由信息

        Args:
            keep_track_indices: 保留的轨道索引

        Returns:
            路由信息字典
        """
        tracks = [self.track_map[i] for i in keep_track_indices if i in self.track_map]

        info = {
            'has_sends': False,
            'has_receives': False,
            'has_folder_bus': False,
            'folder_count': 0,
            'tracks_included': len(tracks),
            'send_count': 0,
            'receive_count': 0
        }

        for track in tracks:
            # 检查 Send
            if track.get('sends'):
                info['has_sends'] = True
                info['send_count'] += len(track['sends'])

            # 检查 Receive
            if track.get('receives'):
                info['has_receives'] = True
                info['receive_count'] += len(track['receives'])

            # 检查文件夹
            if track.get('is_folder'):
                info['has_folder_bus'] = True
                info['folder_count'] += 1

        return info


# 测试代码
if __name__ == '__main__':
    # 测试依赖追踪器
    from rpp_parser import RPPParser
    from pathlib import Path
    import sys

    if len(sys.argv) > 1:
        rpp_file = Path(sys.argv[1])
    else:
        print("用法: python dependency_tracker.py <RPP文件路径>")
        sys.exit(1)

    # 解析 RPP 文件
    parser = RPPParser(rpp_file)
    parser.load()
    tracks = parser.parse_tracks()

    # 创建追踪器
    tracker = DependencyTracker(tracks)

    # 获取选中的 Item
    selected_items = parser.get_selected_items()

    if not selected_items:
        print("⚠️  没有选中的 Item")
        sys.exit(0)

    print(f"选中的 Item: {len(selected_items)}")

    for i, item in enumerate(selected_items, 1):
        print(f"\nItem {i}:")
        print(f"  位置: {item['position']}")
        print(f"  长度: {item['length']}")
        print(f"  轨道: {item['track']['name']}")

        # 追踪依赖
        related = tracker.get_related_tracks(item)
        print(f"  相关轨道: {len(related)}")

        # 按渲染顺序排序
        tracks_in_order = tracker.get_tracks_in_render_order(related)
        print(f"  渲染顺序:")
        for track in tracks_in_order:
            print(f"    - 轨道 {track['index']}: {track['name'] or '(未命名)'}")
            if track.get('is_folder'):
                print(f"      (文件夹)")
            if track.get('sends'):
                print(f"      Send: {len(track['sends'])} 个")

    # 分析路由信息
    all_dependencies = tracker.get_all_dependencies(selected_items)
    routing_info = tracker.analyze_routing_info(all_dependencies)

    print(f"\n路由信息:")
    print(f"  总轨道数: {routing_info['tracks_included']}")
    print(f"  有 Send: {'是' if routing_info['has_sends'] else '否'}")
    print(f"  有 Receive: {'是' if routing_info['has_receives'] else '否'}")
    print(f"  有文件夹总线: {'是' if routing_info['has_folder_bus'] else '否'}")
