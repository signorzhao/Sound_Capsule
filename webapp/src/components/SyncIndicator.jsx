/**
 * SyncIndicator - 同步状态指示器组件
 *
 * 显示在应用右上角，提供：
 * - 同步状态图标（云图标）
 * - 待同步数量徽章
 * - 手动同步按钮
 * - 同步进度动画
 * - 下拉菜单显示同步详情
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Cloud, CloudOff, RefreshCw, AlertCircle, Clock, X, RotateCw } from 'lucide-react';
import { useSync } from '../contexts/SyncContext';
import './SyncIndicator.css';

export default function SyncIndicator() {
  const { t } = useTranslation();
  const { syncStatus, syncError, sync, fetchSyncStatus } = useSync();
  const [showMenu, setShowMenu] = useState(false);
  const [lastSyncAttempt, setLastSyncAttempt] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  /**
   * 处理云图标点击 - 切换菜单显示
   */
  const handleCloudIconClick = () => {
    setShowMenu(!showMenu);
  };

  /**
   * 手动刷新同步状态
   */
  const handleRefreshStatus = async () => {
    setIsRefreshing(true);
    await fetchSyncStatus();
    setTimeout(() => setIsRefreshing(false), 500); // 添加最小延迟以显示动画
  };

  /**
   * 处理同步按钮点击 - 在菜单中点击同步按钮
   */
  const handleSyncButtonClick = async () => {
    setLastSyncAttempt(new Date());
    // 顶部同步只同步关键词数据
    await sync();
    // 同步完成后保持菜单打开，用户可以看到结果
  };

  /**
   * 格式化最后同步时间
   */
  const formatLastSyncTime = (date) => {
    if (!date) return t('syncIndicator.neverSynced');

    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return t('syncIndicator.justSynced');
    if (diffMins < 60) return t('syncIndicator.minsAgo', { count: diffMins });
    if (diffHours < 24) return t('syncIndicator.hoursAgo', { count: diffHours });
    return t('syncIndicator.daysAgo', { count: diffDays });
  };

  /**
   * 获取同步状态图标
   */
  const getStatusIcon = () => {
    if (syncStatus.isSyncing) {
      return <RefreshCw className="sync-icon spinning" size={18} />;
    }

    if (syncError) {
      return <AlertCircle className="sync-icon error" size={18} />;
    }

    // 优先显示本地待上传（黄色）
    if (syncStatus.pendingCount > 0) {
      return <Cloud className="sync-icon pending" size={18} />;
    }

    // 其次显示云端待下载（蓝色）
    if (syncStatus.remotePending > 0) {
      return <Cloud className="sync-icon remote" size={18} />;
    }

    return <Cloud className="sync-icon synced" size={18} />;
  };

  /**
   * 获取同步状态文本
   */
  const getStatusText = () => {
    if (syncStatus.isSyncing) return t('syncIndicator.syncing');
    if (syncError) return t('syncIndicator.syncFailed');

    if (syncStatus.pendingCount > 0) {
      return t('syncIndicator.pendingUpload', { count: syncStatus.pendingCount });
    }

    if (syncStatus.remotePending > 0) {
      return t('syncIndicator.pendingDownload', { count: syncStatus.remotePending });
    }

    return t('syncIndicator.synced');
  };

  /**
   * 获取同步状态类名
   */
  const getStatusClass = () => {
    if (syncStatus.isSyncing) return 'syncing';
    if (syncError) return 'error';

    // 优先显示本地待上传（黄色）
    if (syncStatus.pendingCount > 0) return 'pending';

    // 其次显示云端待下载（蓝色）
    if (syncStatus.remotePending > 0) return 'remote';

    return 'synced';
  };

  return (
    <div className="sync-indicator-container">
      {/* 刷新状态按钮 */}
      <button
        className="sync-refresh-button"
        onClick={handleRefreshStatus}
        disabled={isRefreshing}
        title={t('syncIndicator.refreshTitle')}
      >
        <RotateCw size={14} className={isRefreshing ? 'spinning' : ''} />
      </button>

      {/* 同步按钮 */}
      <button
        className={`sync-button ${getStatusClass()} ${syncStatus.remotePending > 0 ? 'pulse' : ''}`}
        onClick={handleCloudIconClick}
        title={getStatusText()}
      >
        {getStatusIcon()}

        {/* 待下载数量徽章（蓝色，右上角） */}
        {syncStatus.remotePending > 0 && !syncStatus.isSyncing && (
          <span className="remote-badge animate-bounce">
            {syncStatus.remotePending > 99 ? '99+' : syncStatus.remotePending}
          </span>
        )}

        {/* 待上传数量徽章（黄色，右下角） */}
        {syncStatus.pendingCount > 0 && !syncStatus.isSyncing && (
          <span className="sync-badge">
            {syncStatus.pendingCount > 99 ? '99+' : syncStatus.pendingCount}
          </span>
        )}

        {/* 冲突数量徽章 */}
        {syncStatus.conflictCount > 0 && !syncStatus.isSyncing && (
          <span className="conflict-badge">
            {syncStatus.conflictCount}
          </span>
        )}
      </button>

      {/* 下拉菜单 */}
      {showMenu && (
        <>
          {/* 遮罩层 */}
          <div
            className="sync-menu-overlay"
            onClick={() => setShowMenu(false)}
          />

          {/* 菜单内容 */}
          <div className="sync-menu">
            {/* 关闭按钮 */}
            <button
              className="sync-menu-close"
              onClick={() => setShowMenu(false)}
            >
              <X size={18} />
            </button>

            {/* 标题 */}
            <div className="sync-menu-header">
              <h3>{t('syncIndicator.title')}</h3>
            </div>

            {/* 同步状态 */}
            <div className="sync-status-section">
              <div className="sync-status-item">
                <Clock size={16} />
                <span className="label">{t('syncIndicator.lastSync')}:</span>
                <span className="value">
                  {formatLastSyncTime(syncStatus.lastSyncAt)}
                </span>
              </div>

              <div className="sync-status-item">
                <Cloud size={16} />
                <span className="label">{t('syncIndicator.pendingLabel')}:</span>
                <span className={`value ${syncStatus.pendingCount > 0 ? 'pending' : ''}`}>
                  {t('syncIndicator.items', { count: syncStatus.pendingCount })}
                </span>
              </div>

              {syncStatus.conflictCount > 0 && (
                <div className="sync-status-item conflict">
                  <AlertCircle size={16} />
                  <span className="label">{t('syncIndicator.conflictLabel')}:</span>
                  <span className="value">{t('syncIndicator.items', { count: syncStatus.conflictCount })}</span>
                </div>
              )}

              {syncError && (
                <div className="sync-status-item error">
                  <AlertCircle size={16} />
                  <span className="value">{syncError}</span>
                </div>
              )}
            </div>

            {/* 手动同步按钮及进度条 */}
            <div className="sync-actions">
              {syncStatus.isSyncing && (
                <div className="sync-progress-container">
                  <div className="sync-progress-bar">
                    <div
                      className="sync-progress-fill"
                      style={{ width: `${syncStatus.syncProgress}%` }}
                    />
                  </div>
                  <div className="sync-progress-details">
                    <span className="step-text">{syncStatus.syncStep}</span>
                    <span className="percent-text">{syncStatus.syncProgress}%</span>
                  </div>
                </div>
              )}

              <button
                className="sync-action-button"
                onClick={handleSyncButtonClick}
                disabled={syncStatus.isSyncing}
              >
                {syncStatus.isSyncing ? (
                  <>
                    <RefreshCw className="spinning" size={16} />
                    <span>{t('syncIndicator.syncing')}</span>
                  </>
                ) : (
                  <>
                    <RefreshCw size={16} />
                    <span>{t('syncIndicator.syncNow')}</span>
                  </>
                )}
              </button>
            </div>

            {/* 说明文本 */}
            <div className="sync-menu-footer">
              <p>
                {t('syncIndicator.footer1')}
                <br />
                {t('syncIndicator.footer2')}
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
