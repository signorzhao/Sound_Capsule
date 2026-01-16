"""
断点续传下载器（Phase B）

功能：
1. HTTP 206 Partial Content 支持
2. 断点续传（Range 请求）
3. 分块下载（1MB chunks）
4. SHA256 完整性校验
5. 自动重试（最多3次）
6. 实时进度更新

使用示例：
    downloader = ResumableDownloader(
        db_path="database/capsules.db",
        task_id=123
    )

    result = downloader.download_with_resume(
        remote_url="https://storage.supabase.co/capsules/1/source.wav",
        local_path="/path/to/local/source.wav"
    )

    if result['success']:
        print(f"下载完成: {result['local_path']}")
"""

import os
import hashlib
import requests
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

from capsule_db import CapsuleDatabase


@dataclass
class DownloadProgress:
    """下载进度数据类"""
    downloaded_bytes: int
    total_bytes: int
    progress_percent: float
    speed: float  # bytes/second
    eta_seconds: Optional[int]


class ResumableDownloader:
    """
    断点续传下载器

    支持从断点继续下载大文件，适用于网络不稳定环境
    """

    def __init__(
        self,
        db_path: str,
        task_id: int,
        chunk_size: int = 1024 * 1024,  # 1MB
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        初始化下载器

        Args:
            db_path: 数据库路径
            task_id: 下载任务 ID
            chunk_size: 分块大小（默认 1MB）
            max_retries: 最大重试次数
            timeout: 请求超时时间（秒）
        """
        self.db = CapsuleDatabase(db_path)
        self.task_id = task_id
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.timeout = timeout

        # 进度回调函数（可选）
        self.progress_callback: Optional[Callable[[DownloadProgress], None]] = None

        # 取消标志
        self._cancelled = False

    def download_with_resume(
        self,
        remote_url: str,
        local_path: str,
        expected_hash: Optional[str] = None,
        expected_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        断点续传下载

        Args:
            remote_url: 远程文件 URL
            local_path: 本地保存路径
            expected_hash: 预期的 SHA256 哈希（用于校验）
            expected_size: 预期的文件大小（用于校验）

        Returns:
            下载结果：
            {
                'success': bool,
                'local_path': str,
                'file_size': int,
                'file_hash': str,
                'downloaded_bytes': int,
                'error': str or None
            }
        """
        print(f"🔶 开始下载: {remote_url}")
        print(f"   保存到: {local_path}")

        # 1. 检查本地文件是否存在（断点）
        downloaded_bytes = 0
        if Path(local_path).exists():
            downloaded_bytes = os.path.getsize(local_path)
            print(f"📦 发现断点: {downloaded_bytes:,} bytes")

        # 2. 获取远程文件信息
        try:
            remote_info = self._get_remote_info(remote_url)

            if remote_info is None:
                return {
                    'success': False,
                    'error': '无法获取远程文件信息'
                }

            total_bytes = remote_info['size']

            # 校验文件大小
            if expected_size and total_bytes != expected_size:
                print(f"⚠️  文件大小不匹配: 预期 {expected_size}, 实际 {total_bytes}")

            # 如果已经下载完成，直接校验
            if downloaded_bytes > 0 and downloaded_bytes == total_bytes:
                print("✅ 文件已完整下载，校验中...")

                if expected_hash:
                    actual_hash = self._calculate_hash(local_path)
                    if actual_hash == expected_hash:
                        print("✅ 校验通过")
                        return {
                            'success': True,
                            'local_path': local_path,
                            'file_size': total_bytes,
                            'file_hash': actual_hash,
                            'downloaded_bytes': downloaded_bytes
                        }
                    else:
                        print("❌ 校验失败，重新下载")
                        os.remove(local_path)
                        downloaded_bytes = 0
                else:
                    return {
                        'success': True,
                        'local_path': local_path,
                        'file_size': total_bytes,
                        'file_hash': None,
                        'downloaded_bytes': downloaded_bytes
                    }

        except Exception as e:
            print(f"❌ 获取远程文件信息失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

        # 3. 开始下载（支持断点续传）
        print(f"📥 开始下载: {total_bytes:,} bytes ({total_bytes / 1024 / 1024:.2f} MB)")

        retry_count = 0
        last_progress_update = time.time()

        while retry_count <= self.max_retries:
            if self._cancelled:
                print("⚠️  下载已取消")
                return {
                    'success': False,
                    'error': '下载已取消',
                    'downloaded_bytes': downloaded_bytes
                }

            try:
                # 设置 Range 请求头
                headers = {}
                if downloaded_bytes > 0:
                    headers['Range'] = f'bytes={downloaded_bytes}-'
                    print(f"🔄 断点续传: from {downloaded_bytes:,}")

                # 发起请求
                response = requests.get(
                    remote_url,
                    headers=headers,
                    stream=True,
                    timeout=self.timeout
                )

                # 检查响应状态
                if response.status_code not in [200, 206]:
                    raise Exception(f"HTTP {response.status_code}: {response.reason}")

                # 打开文件（追加模式）
                mode = 'ab' if downloaded_bytes > 0 else 'wb'
                start_time = time.time()

                with open(local_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if self._cancelled:
                            break

                        if chunk:
                            f.write(chunk)
                            downloaded_bytes += len(chunk)

                            # 更新进度（每秒一次）
                            current_time = time.time()
                            if current_time - last_progress_update >= 1.0:
                                progress = DownloadProgress(
                                    downloaded_bytes=downloaded_bytes,
                                    total_bytes=total_bytes,
                                    progress_percent=(downloaded_bytes / total_bytes) * 100,
                                    speed=downloaded_bytes / (current_time - start_time),
                                    eta_seconds=int((total_bytes - downloaded_bytes) / (downloaded_bytes / (current_time - start_time))) if downloaded_bytes > 0 else None
                                )

                                self._update_progress(progress)
                                last_progress_update = current_time

                # 下载完成
                if not self._cancelled and downloaded_bytes == total_bytes:
                    print(f"✅ 下载完成: {downloaded_bytes:,} bytes")

                    # SHA256 校验
                    file_hash = None
                    if expected_hash:
                        print("🔐 计算 SHA256...")
                        file_hash = self._calculate_hash(local_path)

                        if file_hash != expected_hash:
                            print(f"❌ SHA256 校验失败:")
                            print(f"   预期: {expected_hash}")
                            print(f"   实际: {file_hash}")
                            os.remove(local_path)

                            return {
                                'success': False,
                                'error': 'SHA256 校验失败'
                            }

                        print("✅ SHA256 校验通过")
                    else:
                        # 如果没有提供预期哈希，仍然计算用于记录
                        file_hash = self._calculate_hash(local_path)

                    return {
                        'success': True,
                        'local_path': local_path,
                        'file_size': total_bytes,
                        'file_hash': file_hash,
                        'downloaded_bytes': downloaded_bytes
                    }

                # 如果被取消，返回部分下载
                if self._cancelled:
                    return {
                        'success': False,
                        'error': '下载已取消',
                        'downloaded_bytes': downloaded_bytes
                    }

                # 下载未完成，继续重试
                retry_count += 1
                print(f"⚠️  下载未完成，重试 {retry_count}/{self.max_retries}")

            except requests.exceptions.RequestException as e:
                retry_count += 1
                print(f"❌ 网络错误: {e}")
                print(f"   重试 {retry_count}/{self.max_retries}")

                if retry_count > self.max_retries:
                    return {
                        'success': False,
                        'error': f'网络错误（已重试 {self.max_retries} 次）: {e}',
                        'downloaded_bytes': downloaded_bytes
                    }

                time.sleep(2 ** retry_count)  # 指数退避

            except Exception as e:
                print(f"❌ 下载失败: {e}")
                return {
                    'success': False,
                    'error': str(e),
                    'downloaded_bytes': downloaded_bytes
                }

        return {
            'success': False,
            'error': '达到最大重试次数',
            'downloaded_bytes': downloaded_bytes
        }

    def cancel(self):
        """取消下载"""
        self._cancelled = True
        print("⚠️  正在取消下载...")

    def _get_remote_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        获取远程文件信息（使用 HEAD 请求）

        Args:
            url: 远程文件 URL

        Returns:
            文件信息字典或 None：
            {
                'size': int,
                'etag': str or None,
                'last_modified': str or None
            }
        """
        try:
            response = requests.head(url, timeout=self.timeout)

            if response.status_code != 200:
                return None

            size = int(response.headers.get('Content-Length', 0))
            etag = response.headers.get('ETag')
            last_modified = response.headers.get('Last-Modified')

            return {
                'size': size,
                'etag': etag,
                'last_modified': last_modified
            }

        except Exception as e:
            print(f"⚠️  获取远程文件信息失败: {e}")
            return None

    def _calculate_hash(self, file_path: str) -> str:
        """
        计算文件的 SHA256 哈希

        Args:
            file_path: 文件路径

        Returns:
            SHA256 哈希字符串（十六进制）
        """
        sha256_hash = hashlib.sha256()

        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    def _update_progress(self, progress: DownloadProgress):
        """
        更新下载进度到数据库

        Args:
            progress: 下载进度对象
        """
        try:
            # 更新数据库
            self.db.update_download_task_status(
                task_id=self.task_id,
                status='downloading',
                progress=int(progress.progress_percent),
                downloaded_bytes=progress.downloaded_bytes,
                speed=int(progress.speed),
                eta_seconds=progress.eta_seconds
            )

            # 调用回调函数（如果有）
            if self.progress_callback:
                self.progress_callback(progress)

            # 打印进度
            print(f"   进度: {progress.progress_percent:.1f}% "
                  f"({progress.downloaded_bytes:,} / {progress.total_bytes:,} bytes) "
                  f"速度: {progress.speed / 1024 / 1024:.2f} MB/s", end='')

            if progress.eta_seconds:
                print(f" ETA: {progress.eta_seconds}s")
            else:
                print()

        except Exception as e:
            print(f"⚠️  更新进度失败: {e}")


# 便捷函数
def download_file(
    remote_url: str,
    local_path: str,
    db_path: str,
    task_id: int,
    expected_hash: Optional[str] = None,
    expected_size: Optional[int] = None,
    progress_callback: Optional[Callable[[DownloadProgress], None]] = None
) -> Dict[str, Any]:
    """
    便捷函数：下载文件（支持断点续传）

    Args:
        remote_url: 远程文件 URL
        local_path: 本地保存路径
        db_path: 数据库路径
        task_id: 下载任务 ID
        expected_hash: 预期的 SHA256 哈希
        expected_size: 预期的文件大小
        progress_callback: 进度回调函数

    Returns:
        下载结果字典
    """
    downloader = ResumableDownloader(
        db_path=db_path,
        task_id=task_id
    )

    if progress_callback:
        downloader.progress_callback = progress_callback

    return downloader.download_with_resume(
        remote_url=remote_url,
        local_path=local_path,
        expected_hash=expected_hash,
        expected_size=expected_size
    )


# 测试代码
if __name__ == '__main__':
    import sys

    # 测试断点续传
    if len(sys.argv) < 3:
        print("用法: python resumable_downloader.py <remote_url> <local_path>")
        sys.exit(1)

    remote_url = sys.argv[1]
    local_path = sys.argv[2]

    print("=" * 60)
    print("🧪 断点续传下载测试")
    print("=" * 60)
    print(f"URL: {remote_url}")
    print(f"保存到: {local_path}")
    print()

    result = download_file(
        remote_url=remote_url,
        local_path=local_path,
        db_path="database/capsules.db",
        task_id=1  # 测试任务 ID
    )

    print()
    print("=" * 60)
    if result['success']:
        print("✅ 下载成功!")
        print(f"   文件: {result['local_path']}")
        print(f"   大小: {result['file_size']:,} bytes")
        if result['file_hash']:
            print(f"   SHA256: {result['file_hash']}")
    else:
        print(f"❌ 下载失败: {result['error']}")
        if result['downloaded_bytes']:
            print(f"   已下载: {result['downloaded_bytes']:,} bytes")
    print("=" * 60)
