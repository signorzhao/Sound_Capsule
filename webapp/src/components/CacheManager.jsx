/**
 * 缓存管理组件 (Phase B.3)
 *
 * 功能：
 * 1. 显示缓存统计信息
 * 2. 清理缓存（LRU 策略）
 * 3. 固定/取消固定缓存
 * 4. 按类型显示缓存占用
 */

import { useState, useEffect } from 'react';
import { HardDrive, Trash2, RefreshCw, AlertTriangle } from 'lucide-react';

export default function CacheManager({ onClose }) {
  const [cacheStats, setCacheStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [purging, setPurging] = useState(false);

  // 加载缓存统计
  const loadCacheStats = async () => {
    try {
      const response = await fetch('http://localhost:5002/api/cache/stats');
      const data = await response.json();

      if (data.success) {
        setCacheStats(data.stats);
      }
    } catch (error) {
      console.error('加载缓存统计失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 组件加载时获取缓存统计
  useEffect(() => {
    loadCacheStats();
  }, []);

  // 清理缓存
  const handlePurgeCache = async () => {
    const confirmed = window.confirm(
      `确定要清理缓存吗？\n\n` +
      `这将删除未固定的缓存文件，释放存储空间。\n\n` +
      `注意：已下载的 WAV 文件将被删除，但可以随时重新下载。`
    );

    if (!confirmed) return;

    setPurging(true);

    try {
      const response = await fetch('http://localhost:5002/api/cache/purge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keep_pinned: true,
          max_size_to_free: null
        })
      });

      const data = await response.json();

      if (data.success) {
        // 重新加载统计
        await loadCacheStats();
        alert(`清理完成！\n\n删除文件: ${data.result.files_deleted}\n释放空间: ${formatSize(data.result.space_freed)}`);
      } else {
        alert('清理失败: ' + data.error);
      }
    } catch (error) {
      console.error('清理缓存失败:', error);
      alert('清理缓存失败');
    } finally {
      setPurging(false);
    }
  };

  // 固定/取消固定缓存
  const handleTogglePin = async (capsuleId, file_type, currentPinned) => {
    try {
      const response = await fetch(`http://localhost:5002/api/capsules/${capsuleId}/cache-pin`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_type: file_type,
          pinned: !currentPinned
        })
      });

      const data = await response.json();

      if (data.success) {
        // 重新加载统计
        await loadCacheStats();
      } else {
        alert('操作失败: ' + data.error);
      }
    } catch (error) {
      console.error('切换固定状态失败:', error);
      alert('操作失败');
    }
  };

  // 格式化文件大小
  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    return `${size.toFixed(2)} ${units[unitIndex]}`;
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6">
          <div className="flex items-center gap-3">
            <RefreshCw className="animate-spin text-indigo-500" size={24} />
            <span className="text-gray-700 dark:text-gray-300">加载缓存统计...</span>
          </div>
        </div>
      </div>
    );
  }

  const stats = cacheStats;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl p-6 m-4">
        {/* 标题栏 */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <HardDrive className="text-indigo-500" size={24} />
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">缓存管理</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            ✕
          </button>
        </div>

        {/* 总体统计 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">总文件数</div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats?.total_cached_files || 0}
            </div>
          </div>

          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">总大小</div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {formatSize(stats?.total_cache_size || 0)}
            </div>
          </div>

          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">使用率</div>
            <div className={`text-2xl font-bold ${
              (stats?.usage_percent || 0) > 90 ? 'text-red-500' :
              (stats?.usage_percent || 0) > 70 ? 'text-yellow-500' :
              'text-green-500'
            }`}>
              {(stats?.usage_percent || 0).toFixed(1)}%
            </div>
          </div>

          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">固定文件</div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats?.pinned_files_count || 0}
            </div>
          </div>
        </div>

        {/* 警告提示 */}
        {(stats?.usage_percent || 0) > 90 && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-3">
              <AlertTriangle className="text-red-500" size={20} />
              <div>
                <div className="font-bold text-red-700 dark:text-red-400">缓存空间不足</div>
                <div className="text-sm text-red-600 dark:text-red-300">
                  当前缓存使用率超过 90%，建议清理缓存以释放空间。
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 按类型统计 */}
        <div className="mb-6">
          <h3 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-3">按类型统计</h3>
          <div className="space-y-2">
            {stats?.by_type && Object.entries(stats.by_type).map(([type, typeStats]) => (
              <div key={type} className="flex items-center justify-between bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    type === 'wav' ? 'bg-indigo-500' :
                    type === 'preview' ? 'bg-green-500' :
                    'bg-gray-500'
                  }`}></div>
                  <span className="font-medium text-gray-900 dark:text-white uppercase">{type}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-gray-600 dark:text-gray-400">
                    {typeStats.count} 个文件
                  </span>
                  <span className="font-mono text-gray-900 dark:text-white">
                    {formatSize(typeStats.size)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3">
          <button
            onClick={handlePurgeCache}
            disabled={purging}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white rounded-lg transition-colors font-medium"
          >
            {purging ? (
              <>
                <RefreshCw className="animate-spin" size={18} />
                清理中...
              </>
            ) : (
              <>
                <Trash2 size={18} />
                清理缓存
              </>
            )}
          </button>

          <button
            onClick={() => {
              loadCacheStats();
            }}
            className="flex items-center justify-center gap-2 px-4 py-3 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg transition-colors font-medium"
          >
            <RefreshCw size={18} />
            刷新
          </button>
        </div>

        {/* 说明文本 */}
        <div className="mt-6 text-xs text-gray-500 dark:text-gray-400">
          <p className="mb-2"><strong>缓存说明：</strong></p>
          <ul className="list-disc list-inside space-y-1">
            <li>LRU（Least Recently Used）清理策略会优先删除最久未使用的文件</li>
            <li>固定的缓存文件不会被自动清理</li>
            <li>清理后，已删除的文件可以在需要时重新下载</li>
            <li>元数据和预览音频不会被清理</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
