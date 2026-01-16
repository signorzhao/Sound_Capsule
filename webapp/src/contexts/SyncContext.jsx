/**
 * Sync Context - 云端同步状态管理
 *
 * 提供同步功能的全局状态管理：
 * - 同步状态（待同步数量、冲突数量、最后同步时间）
 * - 手动/自动同步触发
 * - 同步错误处理
 * - 自动同步调度
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authFetch } from '../utils/apiClient';

// 创建 SyncContext
const SyncContext = createContext(undefined);

// 自定义 Hook
export const useSync = () => {
  const context = useContext(SyncContext);
  if (!context) {
    throw new Error('useSync must be used within SyncProvider');
  }
  return context;
};

// SyncProvider 组件
export const SyncProvider = ({ children }) => {
  // 同步状态
  const [syncStatus, setSyncStatus] = useState({
    lastSyncAt: null,
    pendingCount: 0,
    conflictCount: 0,
    remotePending: 0,  // 云端待下载数量
    isSyncing: false,
    syncProgress: 0,   // 新增：同步进度百分比
    syncStep: '',      // 新增：当前执行步骤描述
  });

  // 同步错误
  const [syncError, setSyncError] = useState(null);

  // 自动同步间隔（毫秒）
  const AUTO_SYNC_INTERVAL = 30 * 1000; // 30秒

  /**
   * 获取同步状态
   */
  const fetchSyncStatus = useCallback(async () => {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      console.log('用户未登录，跳过获取同步状态');
      return null;
    }

    try {
      const response = await authFetch('http://localhost:5002/api/sync/status', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`获取同步状态失败: ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        setSyncStatus(prev => ({
          ...prev,
          lastSyncAt: result.data.last_sync_at ? new Date(result.data.last_sync_at) : null,
          pendingCount: result.data.pending_count || 0,
          conflictCount: result.data.conflict_count || 0,
          remotePending: result.data.remote_pending || 0,  // 云端待下载数量
        }));
      }

      return result.data;
    } catch (error) {
      console.error('获取同步状态失败:', error);
      setSyncError(error.message);
      return null;
    }
  }, []);

  /**
   * 执行同步 - 只同步关键词数据（capsule_tags）
   * 
   * 顶部云图标点击后调用此方法：
   * 1. 上传本地修改过的关键词到云端
   * 2. 下载云端更新的关键词到本地
   */
  const sync = useCallback(async () => {
    // 防止重复同步
    if (syncStatus.isSyncing) {
      console.log('同步正在进行中，跳过');
      return;
    }

    // 检查是否已登录
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      console.log('用户未登录，跳过云端同步');
      setSyncError(null);
      return { success: true, skipped: true, reason: '未登录' };
    }

    setSyncStatus(prev => ({ ...prev, isSyncing: true, syncProgress: 10, syncStep: '正在同步关键词数据...' }));
    setSyncError(null);

    try {
      console.log('🏷️ 开始关键词同步...');

      // 调用后端关键词同步接口
      setSyncStatus(prev => ({ ...prev, syncProgress: 30, syncStep: '正在比对关键词变更...' }));
      
      const response = await authFetch('http://localhost:5002/api/sync/sync-tags', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok && response.status !== 207) {
        throw new Error(`关键词同步失败: ${response.status}`);
      }

      const result = await response.json();
      console.log('🏷️ 关键词同步结果:', result);

      if (!result.success) {
        console.warn('关键词同步警告:', result);
      }

      // 更新同步状态
      setSyncStatus(prev => ({ ...prev, syncProgress: 90, syncStep: '同步数据校验中...' }));
      await fetchSyncStatus();

      setSyncStatus(prev => ({ ...prev, syncProgress: 100, syncStep: '同步完成！' }));
      console.log('✅ 关键词同步完成');

      // 触发同步完成事件（通知其他组件刷新数据）
      window.dispatchEvent(new CustomEvent('sync-completed'));

      return {
        success: true,
        uploaded: result.data?.uploaded || 0,
        downloaded: result.data?.downloaded || 0,
      };
    } catch (error) {
      console.error('❌ 关键词同步失败:', error);
      setSyncError(error.message);

      // 触发同步失败事件
      window.dispatchEvent(new CustomEvent('sync-failed', { detail: { error: error.message } }));

      return {
        success: false,
        error: error.message,
      };
    } finally {
      setSyncStatus(prev => ({ ...prev, isSyncing: false }));
    }
  }, [syncStatus.isSyncing, fetchSyncStatus]);

  /**
   * 仅下载模式（启动同步专用）
   * 只从云端下载数据，不上传本地变更
   */
  const syncDownloadOnly = useCallback(async ({ onProgress } = {}) => {
    // 防止重复同步
    if (syncStatus.isSyncing) {
      console.log('同步正在进行中，跳过');
      return;
    }

    // 检查是否已登录
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      console.log('用户未登录，跳过云端同步');
      setSyncError(null); // 清除之前的错误
      return { success: true, skipped: true, reason: '未登录' };
    }

    setSyncStatus(prev => ({ ...prev, isSyncing: true, syncProgress: 5, syncStep: '正在连接云端...' }));
    onProgress?.({ phase: '正在连接云端...', current: 0, total: 0, percentage: 5 });
    setSyncError(null);

    try {
      console.log('🔄 [BootSync] 开始仅下载同步...');

      // 调用后端的 /api/sync/download-only 端点
      setSyncStatus(prev => ({ ...prev, syncProgress: 10, syncStep: '正在下载全球胶囊元数据...' }));
      onProgress?.({ phase: '正在下载全球胶囊元数据...', current: 0, total: 0, percentage: 10 });

      const response = await authFetch('http://localhost:5002/api/sync/download-only', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          include_previews: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`仅下载同步失败: ${response.status}`);
      }

      const result = await response.json();
      console.log('🔄 [BootSync] 仅下载同步结果:', result);

      if (result.success) {
        setSyncStatus(prev => ({ ...prev, syncProgress: 90, syncStep: '同步数据校验中...' }));
        onProgress?.({ phase: '同步数据校验中...', current: 0, total: 0, percentage: 90 });

        // 更新同步状态
        await fetchSyncStatus();

        setSyncStatus(prev => ({ ...prev, syncProgress: 100, syncStep: '同步完成！' }));
        onProgress?.({ phase: '同步完成！', current: 0, total: 0, percentage: 100 });
        console.log('✅ [BootSync] 仅下载同步完成');

        // 触发同步完成事件（通知其他组件刷新数据）
        window.dispatchEvent(new CustomEvent('sync-completed'));

        return {
          success: true,
          downloaded_count: result.data.downloaded_count,
          preview_downloaded: result.data.preview_downloaded,
        };
      } else {
        throw new Error(result.error || '仅下载同步失败');
      }
    } catch (error) {
      console.error('❌ [BootSync] 仅下载同步失败:', error);
      setSyncError(error.message);

      // 触发同步失败事件
      window.dispatchEvent(new CustomEvent('sync-failed', { detail: { error: error.message } }));

      return {
        success: false,
        error: error.message,
      };
    } finally {
      setSyncStatus(prev => ({ ...prev, isSyncing: false }));
    }
  }, [syncStatus.isSyncing, fetchSyncStatus]);

  /**
   * 标记记录为待同步
   */
  const markForSync = useCallback(async (tableName, recordId, operation = 'update') => {
    try {
      const response = await fetch('http://localhost:5002/api/sync/mark-pending', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          table_name: tableName,
          record_id: recordId,
          operation: operation,
        }),
      });

      if (!response.ok) {
        throw new Error(`标记失败: ${response.status}`);
      }

      const result = await response.json();

      // 更新待同步数量
      await fetchSyncStatus();

      return result.success;
    } catch (error) {
      console.error('标记同步失败:', error);
      return false;
    }
  }, [fetchSyncStatus]);

  /**
   * 获取冲突列表
   */
  const getConflicts = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:5002/api/sync/conflicts', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) {
        throw new Error(`获取冲突失败: ${response.status}`);
      }

      const result = await response.json();
      return result.data.conflicts || [];
    } catch (error) {
      console.error('获取冲突失败:', error);
      return [];
    }
  }, []);

  /**
   * 解决冲突
   */
  const resolveConflict = useCallback(async (conflictId, resolution) => {
    try {
      const response = await fetch('http://localhost:5002/api/sync/resolve-conflict', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          conflict_id: conflictId,
          resolution: resolution, // 'local', 'cloud', or 'merge'
        }),
      });

      if (!response.ok) {
        throw new Error(`解决冲突失败: ${response.status}`);
      }

      const result = await response.json();

      // 更新同步状态
      await fetchSyncStatus();

      return result.success;
    } catch (error) {
      console.error('解决冲突失败:', error);
      return false;
    }
  }, [fetchSyncStatus]);

  /**
   * Phase G2: 启动同步 - 轻量资产完整同步
   *
   * 同步内容：
   * - 元数据（胶囊基本信息、标签、坐标）
   * - OGG 预览音频
   * - RPP 项目文件
   *
   * 不同步：
   * - WAV 源文件（按需下载）
   *
   * @param {Object} options - 同步选项
   * @param {Function} options.onProgress - 进度回调 ({current, total, phase, currentFile, percentage})
   * @returns {Promise<Object>} 同步结果
   */
  const syncLightweightAssets = useCallback(async ({ onProgress } = {}) => {
    // 检查是否已登录
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      console.log('[BootSync] 用户未登录');
      return {
        success: false,
        error: '未登录',
        skipped: true
      };
    }

    try {
      console.log('[BootSync] 开始轻量资产同步...');

      // 调用后端轻量同步端点，它会自动下载所有 OGG 和 RPP 文件
      onProgress?.({
        phase: '正在同步全球胶囊元数据和轻量资产...',
        current: 0,
        total: 0,
        percentage: 10
      });

      const response = await authFetch('http://localhost:5002/api/sync/lightweight', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          include_previews: true,  // 自动下载预览音频
          force: false
        }),
      });

      const result = await response.json();

      // 检查响应是否成功
      // 207 Multi-Status 表示部分成功（有警告但仍同步成功）
      if (!response.ok && response.status !== 207) {
        throw new Error(`轻量同步失败: ${response.status}`);
      }

      // 即使 success 为 false（207 响应），只要 synced_count > 0 就算部分成功
      if (!result.success && (!result.data || result.data.synced_count === 0)) {
        console.error('[BootSync] 同步失败详情:', {
          success: result.success,
          error: result.error,
          data: result.data,
          fullResult: result
        });
        throw new Error(result.error || '轻量同步失败');
      }

      console.log('[BootSync] 轻量同步完成:', result.data);
      if (result.data?.errors?.length > 0) {
        console.warn('[BootSync] 同步过程中的警告:', result.data.errors);
      }

      onProgress?.({
        phase: '同步完成！',
        current: result.data.synced_count || 0,
        total: result.data.synced_count || 0,
        percentage: 100
      });

      // 触发同步完成事件
      window.dispatchEvent(new CustomEvent('sync-completed'));

      return {
        success: true,
        synced_count: result.data.synced_count || 0,
        files_downloaded: result.data.preview_downloaded || 0,
        duration_seconds: result.data.duration_seconds || 0
      };

    } catch (error) {
      console.error('[BootSync] 同步失败:', error);

      return {
        success: false,
        error: error.message
      };
    }
  }, []);

  /**
   * 初始化：获取同步状态
   */
  useEffect(() => {
    fetchSyncStatus();
  }, [fetchSyncStatus]);

  /**
   * 自动同步：数据变更后 30 秒自动同步
   */
  useEffect(() => {
    let autoSyncTimer = null;

    const scheduleAutoSync = () => {
      if (autoSyncTimer) {
        clearTimeout(autoSyncTimer);
      }

      autoSyncTimer = setTimeout(() => {
        console.log('自动同步触发');
        sync();
      }, AUTO_SYNC_INTERVAL);
    };

    // 监听数据变更事件（使用浏览器原生事件）
    const handleDataChanged = () => {
      console.log('检测到数据变更，安排自动同步');
      scheduleAutoSync();
    };

    window.addEventListener('data-changed', handleDataChanged);

    return () => {
      if (autoSyncTimer) {
        clearTimeout(autoSyncTimer);
      }
      window.removeEventListener('data-changed', handleDataChanged);
    };
  }, [sync]);

  /**
   * 网络恢复时自动同步
   */
  useEffect(() => {
    const handleOnline = () => {
      console.log('网络已恢复，触发同步');
      sync();
    };

    window.addEventListener('online', handleOnline);

    return () => {
      window.removeEventListener('online', handleOnline);
    };
  }, [sync]);

  /**
   * 同步完成后刷新同步状态（更新右上角云图标）
   */
  useEffect(() => {
    const handleSyncCompleted = () => {
      fetchSyncStatus();
    };

    window.addEventListener('sync-completed', handleSyncCompleted);
    return () => {
      window.removeEventListener('sync-completed', handleSyncCompleted);
    };
  }, [fetchSyncStatus]);

  // Context 值
  const value = {
    syncStatus,
    syncError,
    sync,
    syncDownloadOnly, // Phase G2: 仅下载模式（启动同步专用）
    syncLightweightAssets, // Phase G2: 启动同步
    markForSync,
    getConflicts,
    resolveConflict,
    fetchSyncStatus,
  };

  return (
    <SyncContext.Provider value={value}>
      {children}
    </SyncContext.Provider>
  );
};
