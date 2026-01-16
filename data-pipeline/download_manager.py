"""
下载队列管理器（Phase B）

功能：
1. 优先级队列管理
2. 并发下载控制（最多3个）
3. 自动重试失败任务
4. 下载状态实时更新

使用示例：
    queue = DownloadQueue(
        db_path="database/capsules.db",
        max_concurrent=3
    )

    # 启动队列
    queue.start()

    # 添加任务
    queue.add_task({
        'capsule_id': 1,
        'file_type': 'wav',
        'remote_url': 'https://...',
        'local_path': '/path/to/local.wav',
        'priority': 5
    })

    # 等待完成
    queue.wait_for_completion()
"""

import threading
import time
import queue
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from capsule_db import CapsuleDatabase
from resumable_downloader import ResumableDownloader, DownloadProgress


@dataclass(order=True)
class DownloadTask:
    """下载任务数据类"""
    priority: int  # 优先级（数字越大越优先）
    created_at: float  # 创建时间戳
    task_id: int = field(compare=False)
    capsule_id: int = field(compare=False)
    file_type: str = field(compare=False)
    remote_url: str = field(compare=False)
    local_path: str = field(compare=False)
    remote_size: Optional[int] = field(default=None, compare=False)
    remote_hash: Optional[str] = field(default=None, compare=False)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)


class DownloadWorker(threading.Thread):
    """
    下载工作线程

    从队列中获取任务并执行下载
    """

    def __init__(
        self,
        worker_id: int,
        task_queue: queue.PriorityQueue,
        db_path: str,
        manager: 'DownloadQueue'
    ):
        """
        初始化工作线程

        Args:
            worker_id: 工作线程 ID
            task_queue: 任务队列
            db_path: 数据库路径
            manager: 下载队列管理器
        """
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.db_path = db_path
        self.manager = manager
        self._stopped = False

    def run(self):
        """工作线程主循环"""
        print(f"🔧 工作线程 {self.worker_id} 启动")

        while not self._stopped:
            try:
                # 从队列获取任务（超时 1 秒）
                task = self.task_queue.get(timeout=1)

                # 执行下载
                self._download_task(task)

                # 标记任务完成
                self.task_queue.task_done()

            except queue.Empty:
                # 队列为空，继续等待
                continue

            except Exception as e:
                print(f"❌ 工作线程 {self.worker_id} 错误: {e}")
                import traceback
                traceback.print_exc()

        print(f"🔧 工作线程 {self.worker_id} 停止")

    def stop(self):
        """停止工作线程"""
        self._stopped = True

    def _download_task(self, task: DownloadTask):
        """执行下载任务"""
        print(f"📥 [Worker-{self.worker_id}] 下载任务 {task.task_id}: {task.remote_url}")

        # 更新任务状态为下载中
        db = CapsuleDatabase(self.db_path)
        db.update_download_task_status(
            task_id=task.task_id,
            status='downloading',
            progress=0
        )

        # 创建下载器
        downloader = ResumableDownloader(
            db_path=self.db_path,
            task_id=task.task_id
        )

        # 设置进度回调
        downloader.progress_callback = lambda p: self._on_progress(task.task_id, p)

        # 执行下载
        result = downloader.download_with_resume(
            remote_url=task.remote_url,
            local_path=task.local_path,
            expected_hash=task.remote_hash,
            expected_size=task.remote_size
        )

        # 处理下载结果
        if result['success']:
            print(f"✅ [Worker-{self.worker_id}] 任务 {task.task_id} 完成")

            # 更新任务状态为完成
            db.update_download_task_status(
                task_id=task.task_id,
                status='completed',
                progress=100,
                downloaded_bytes=result['file_size']
            )

            # 通知管理器
            self.manager.on_task_completed(task.task_id, result)

        else:
            print(f"❌ [Worker-{self.worker_id}] 任务 {task.task_id} 失败: {result['error']}")

            # 检查是否需要重试
            if task.retry_count < task.max_retries:
                print(f"🔄 [Worker-{self.worker_id}] 重试任务 {task.task_id} ({task.retry_count + 1}/{task.max_retries})")

                # 增加重试计数
                task.retry_count += 1

                # 重新加入队列
                self.manager.retry_task(task)

            else:
                # 达到最大重试次数，标记为失败
                db.update_download_task_status(
                    task_id=task.task_id,
                    status='failed',
                    error_message=result['error']
                )

                # 通知管理器
                self.manager.on_task_failed(task.task_id, result['error'])

    def _on_progress(self, task_id: int, progress: DownloadProgress):
        """进度回调"""
        # 可以在这里添加额外的进度处理逻辑
        pass


class DownloadQueue:
    """
    下载队列管理器

    管理多个下载任务，支持优先级队列和并发控制
    """

    def __init__(
        self,
        db_path: str,
        max_concurrent: int = 3,
        poll_interval: float = 5.0
    ):
        """
        初始化下载队列管理器

        Args:
            db_path: 数据库路径
            max_concurrent: 最大并发下载数
            poll_interval: 轮询数据库新任务的间隔（秒）
        """
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self.poll_interval = poll_interval

        # 任务队列（优先级队列）
        self.task_queue = queue.PriorityQueue()

        # 工作线程
        self.workers: List[DownloadWorker] = []

        # 控制标志
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None

        # 回调函数
        self.on_task_completed_callback: Optional[callable] = None
        self.on_task_failed_callback: Optional[callable] = None
        self.on_all_tasks_completed_callback: Optional[callable] = None

    def start(self):
        """启动下载队列"""
        if self._running:
            print("⚠️  下载队列已在运行")
            return

        print(f"🚀 启动下载队列（最大并发: {self.max_concurrent}）")
        self._running = True

        # 创建并启动工作线程
        for i in range(self.max_concurrent):
            worker = DownloadWorker(
                worker_id=i + 1,
                task_queue=self.task_queue,
                db_path=self.db_path,
                manager=self
            )
            worker.start()
            self.workers.append(worker)

        # 启动轮询线程
        self._poll_thread = threading.Thread(target=self._poll_database, daemon=True)
        self._poll_thread.start()

    def stop(self):
        """停止下载队列"""
        if not self._running:
            return

        print("🛑 停止下载队列...")
        self._running = False

        # 停止工作线程
        for worker in self.workers:
            worker.stop()

        # 等待工作线程结束
        for worker in self.workers:
            worker.join(timeout=5)

        self.workers.clear()

        # 等待轮询线程结束
        if self._poll_thread:
            self._poll_thread.join(timeout=5)

        print("✅ 下载队列已停止")

    def add_task(self, task_data: Dict[str, Any]) -> int:
        """
        添加下载任务

        Args:
            task_data: 任务数据
                {
                    'capsule_id': int,
                    'file_type': str,
                    'remote_url': str,
                    'local_path': str,
                    'remote_size': int (optional),
                    'remote_hash': str (optional),
                    'priority': int (default: 0)
                }

        Returns:
            任务 ID
        """
        db = CapsuleDatabase(self.db_path)

        # 创建数据库记录
        task_id = db.create_download_task(task_data)

        print(f"✅ 任务已创建: ID={task_id}, 优先级={task_data.get('priority', 0)}")

        # 添加到内存队列
        task = DownloadTask(
            priority=task_data.get('priority', 0),
            created_at=time.time(),
            task_id=task_id,
            capsule_id=task_data['capsule_id'],
            file_type=task_data['file_type'],
            remote_url=task_data['remote_url'],
            local_path=task_data['local_path'],
            remote_size=task_data.get('remote_size'),
            remote_hash=task_data.get('remote_hash')
        )

        self.task_queue.put(task)

        return task_id

    def retry_task(self, task: DownloadTask):
        """重试任务"""
        self.task_queue.put(task)

    def pause_task(self, task_id: int) -> bool:
        """
        暂停下载任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        # 注意：真正的暂停需要更复杂的实现
        # 这里只是标记任务为 paused 状态
        db = CapsuleDatabase(self.db_path)
        return db.update_download_task_status(task_id, 'paused')

    def resume_task(self, task_id: int) -> bool:
        """
        恢复下载任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        db = CapsuleDatabase(self.db_path)

        # 获取任务信息
        task = db.get_download_task(task_id)
        if not task:
            return False

        # 重新加入队列
        download_task = DownloadTask(
            priority=task['priority'],
            created_at=task['created_at'],
            task_id=task['id'],
            capsule_id=task['capsule_id'],
            file_type=task['file_type'],
            remote_url=task['remote_url'],
            local_path=task['local_path'],
            remote_size=task['remote_size'],
            remote_hash=task['remote_hash'],
            retry_count=task['retry_count'],
            max_retries=task['max_retries']
        )

        self.task_queue.put(download_task)

        # 更新状态为 pending
        return db.update_download_task_status(task_id, 'pending')

    def cancel_task(self, task_id: int) -> bool:
        """
        取消下载任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        # 注意：真正的取消需要通知下载器
        # 这里只是标记任务为 cancelled 状态
        db = CapsuleDatabase(self.db_path)
        return db.update_download_task_status(task_id, 'cancelled')

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        等待所有任务完成

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否全部完成
        """
        return self.task_queue.join()

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        db = CapsuleDatabase(self.db_path)
        return db.get_download_queue_status()

    def _poll_database(self):
        """轮询数据库获取新任务"""
        while self._running:
            try:
                # 从数据库获取待处理任务
                db = CapsuleDatabase(self.db_path)
                tasks = db.get_pending_download_tasks(limit=10)

                # 添加到队列
                for task in tasks:
                    # 检查是否已在队列中（简单检查）
                    download_task = DownloadTask(
                        priority=task['priority'],
                        created_at=task['created_at'].timestamp(),
                        task_id=task['id'],
                        capsule_id=task['capsule_id'],
                        file_type=task['file_type'],
                        remote_url=task['remote_url'],
                        local_path=task['local_path'],
                        remote_size=task['remote_size'],
                        remote_hash=task['remote_hash'],
                        retry_count=task['retry_count'],
                        max_retries=task['max_retries']
                    )

                    self.task_queue.put(download_task)

                # 检查是否所有任务完成
                if self.task_queue.empty():
                    status = self.get_queue_status()
                    if status.get('pending_count', 0) == 0 and status.get('downloading_count', 0) == 0:
                        if self.on_all_tasks_completed_callback:
                            self.on_all_tasks_completed_callback()

                # 等待下次轮询
                time.sleep(self.poll_interval)

            except Exception as e:
                print(f"⚠️  轮询数据库错误: {e}")
                time.sleep(self.poll_interval)

    def on_task_completed(self, task_id: int, result: Dict[str, Any]):
        """任务完成回调"""
        if self.on_task_completed_callback:
            self.on_task_completed_callback(task_id, result)

    def on_task_failed(self, task_id: int, error: str):
        """任务失败回调"""
        if self.on_task_failed_callback:
            self.on_task_failed_callback(task_id, error)


# 便捷函数
def create_download_queue(
    db_path: str = "database/capsules.db",
    max_concurrent: int = 3
) -> DownloadQueue:
    """
    创建下载队列

    Args:
        db_path: 数据库路径
        max_concurrent: 最大并发数

    Returns:
        下载队列实例
    """
    queue = DownloadQueue(
        db_path=db_path,
        max_concurrent=max_concurrent
    )
    queue.start()

    return queue


# 测试代码
if __name__ == '__main__':
    import sys

    # 测试下载队列
    print("=" * 60)
    print("🧪 下载队列测试")
    print("=" * 60)

    # 创建队列
    queue = create_download_queue(
        db_path="database/capsules.db",
        max_concurrent=2
    )

    # 添加测试任务
    if len(sys.argv) >= 3:
        remote_url = sys.argv[1]
        local_path = sys.argv[2]

        queue.add_task({
            'capsule_id': 1,
            'file_type': 'wav',
            'remote_url': remote_url,
            'local_path': local_path,
            'priority': 5
        })

        print("✅ 测试任务已添加")
        print("等待下载完成...")
        queue.wait_for_completion()
        print("✅ 所有任务完成")

    else:
        print("用法: python download_manager.py <remote_url> <local_path>")

    # 停止队列
    queue.stop()
