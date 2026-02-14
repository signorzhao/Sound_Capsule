/**
 * 下载进度对话框 (Phase B.3)
 *
 * 功能：
 * 1. 实时显示下载进度
 * 2. 显示下载速度和 ETA
 * 3. 暂停/恢复/取消控制
 * 4. 完成后自动关闭
 */

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Pause, Play, XCircle } from 'lucide-react';

export default function DownloadProgressDialog({
  capsuleId,
  capsuleName,
  taskStatus,
  onComplete,
  onClose
}) {
  const { t } = useTranslation();
  const [progress, setProgress] = useState(0);
  const [downloadedBytes, setDownloadedBytes] = useState(0);
  const [totalBytes, setTotalBytes] = useState(0);
  const [speed, setSpeed] = useState(0);
  const [eta, setEta] = useState(null);
  const [status, setStatus] = useState(taskStatus || 'pending');
  const [error, setError] = useState(null);

  // 轮询下载进度（从后端 API 获取）
  useEffect(() => {
    if (status === 'completed' || status === 'failed' || status === 'cancelled') {
      return;
    }

    const pollInterval = setInterval(async () => {
      try {
        // 使用后端 API 而不是 Tauri 命令
        const response = await fetch(`http://localhost:5002/api/downloads/status/${capsuleId}`);
        const result = await response.json();

        if (result.status === 'not_started') {
          // 下载尚未开始，继续轮询
          return;
        }

        setProgress(result.progress || 0);
        setDownloadedBytes(result.downloaded_bytes || 0);
        setTotalBytes(result.total_bytes || 0);
        setSpeed(result.speed || 0);
        setEta(result.eta_seconds);
        setStatus(result.status);
        setError(result.error_message);

        // 下载完成
        if (result.status === 'completed') {
          clearInterval(pollInterval);
          setTimeout(() => {
            onComplete?.();
          }, 500);
        }

        // 下载失败
        if (result.status === 'failed') {
          clearInterval(pollInterval);
          setError(result.error_message || t('download.downloadFailed'));
        }

      } catch (err) {
        console.error('获取下载进度失败:', err);
        // 不要停止轮询，可能只是暂时的网络问题
      }
    }, 1000);

    return () => clearInterval(pollInterval);
  }, [capsuleId, status, onComplete]);

  // 格式化文件大小
  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) {
      size /= 1024;
      unit++;
    }
    return `${size.toFixed(2)} ${units[unit]}`;
  };

  // 格式化速度
  const formatSpeed = (bytesPerSecond) => {
    if (!bytesPerSecond) return '0 B/s';
    return `${formatSize(bytesPerSecond)}/s`;
  };

  // 格式化时间
  const formatTime = (seconds) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // 暂停下载（使用后端 API）
  const handlePause = async () => {
    try {
      const response = await fetch(`http://localhost:5002/api/capsules/${capsuleId}/pause-download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const result = await response.json();
      if (result.success) {
        setStatus('paused');
      }
    } catch (err) {
      console.error('暂停失败:', err);
    }
  };

  // 恢复下载（使用后端 API）
  const handleResume = async () => {
    try {
      const response = await fetch(`http://localhost:5002/api/capsules/${capsuleId}/resume-download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const result = await response.json();
      if (result.success) {
        setStatus('downloading');
      }
    } catch (err) {
      console.error('恢复失败:', err);
    }
  };

  // 取消下载（使用后端 API）
  const handleCancel = async () => {
    try {
      const response = await fetch(`http://localhost:5002/api/capsules/${capsuleId}/cancel-download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const result = await response.json();
      if (result.success) {
        setStatus('cancelled');
        onClose?.();
      }
    } catch (err) {
      console.error('取消失败:', err);
    }
  };

  const statusConfig = {
    pending: { text: t('download.pending'), color: 'gray', icon: null },
    downloading: { text: t('download.downloading'), color: 'blue', icon: null },
    paused: { text: t('download.paused'), color: 'yellow', icon: null },
    completed: { text: t('download.completed'), color: 'green', icon: '✓' },
    failed: { text: t('download.failed'), color: 'red', icon: '✗' },
    cancelled: { text: t('download.cancelled'), color: 'gray', icon: '✗' }
  };

  const currentStatus = statusConfig[status] || statusConfig.pending;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6 m-4">
        {/* 标题栏 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full bg-${currentStatus.color}-500 animate-pulse`}
                 style={{ backgroundColor: currentStatus.color === 'gray' ? '#9CA3AF' : undefined }} />
            <h3 className="text-lg font-semibold">{t('download.title')}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            disabled={status === 'downloading'}
          >
            <X size={20} />
          </button>
        </div>

        {/* 胶囊名称 */}
        <div className="mb-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('download.capsuleName')}</p>
          <p className="font-medium truncate">{capsuleName}</p>
        </div>

        {/* 进度条 */}
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-500 dark:text-gray-400">{t('download.progress')}</span>
            <span className="font-medium">{progress.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
            <span>{formatSize(downloadedBytes)}</span>
            <span>{formatSize(totalBytes)}</span>
          </div>
        </div>

        {/* 状态信息 */}
        <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
          <div>
            <span className="text-gray-500 dark:text-gray-400">{t('download.status')}</span>
            <span className="ml-2" style={{ color: currentStatus.color }}>
              {currentStatus.icon && <span className="mr-1">{currentStatus.icon}</span>}
              {currentStatus.text}
            </span>
          </div>
          <div>
            <span className="text-gray-500 dark:text-gray-400">{t('download.speed')}</span>
            <span className="ml-2 font-mono">{formatSpeed(speed)}</span>
          </div>
          <div>
            <span className="text-gray-500 dark:text-gray-400">{t('download.remaining')}</span>
            <span className="ml-2 font-mono">{formatTime(eta)}</span>
          </div>
          {error && (
            <div className="col-span-2 text-red-500 text-xs">
              {t('download.error')}: {error}
            </div>
          )}
        </div>

        {/* 控制按钮 */}
        <div className="flex gap-2">
          {status === 'downloading' && (
            <>
              <button
                onClick={handlePause}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-white rounded transition-colors"
              >
                <Pause size={16} />
                {t('download.pause')}
              </button>
              <button
                onClick={handleCancel}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded transition-colors"
              >
                <XCircle size={16} />
                {t('download.cancel')}
              </button>
            </>
          )}

          {status === 'paused' && (
            <>
              <button
                onClick={handleResume}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded transition-colors"
              >
                <Play size={16} />
                {t('download.resume')}
              </button>
              <button
                onClick={handleCancel}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded transition-colors"
              >
                <XCircle size={16} />
                {t('download.cancel')}
              </button>
            </>
          )}

          {(status === 'completed' || status === 'failed' || status === 'cancelled') && (
            <button
              onClick={onClose}
              className="w-full px-4 py-2 bg-gray-500 hover:bg-gray-600 text-white rounded transition-colors"
            >
              {t('download.close')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
