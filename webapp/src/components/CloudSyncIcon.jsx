import React from 'react';
import { useTranslation } from 'react-i18next';
import { Cloud, Upload, Download, Check } from 'lucide-react';

/**
 * CloudSyncIcon - 云同步状态图标
 * 
 * 根据胶囊的云端状态显示不同的图标和操作
 * 
 * @param {Object} props
 * @param {Object} props.capsule - 胶囊对象，包含 cloud_status 字段
 * @param {Function} props.onClick - 点击回调函数
 * @param {string} props.className - 额外的 CSS 类名
 */
const CloudSyncIcon = ({ capsule, onClick, className = '' }) => {
  const { t } = useTranslation();

  const getSyncState = () => {
    // 状态 1: 需上传 (Dirty)
    // 条件: cloud_status === 'local' 表示仅存在本地，未上传
    if (capsule.cloud_status === 'local') {
      return {
        icon: Upload,
        color: 'text-orange-400',
        bg: 'bg-orange-900/20',
        border: 'border-orange-500/30',
        tooltip: t('cloudSync.localTooltip')
      };
    }

    if (capsule.cloud_status === 'remote') {
      return {
        icon: Download,
        color: 'text-blue-400',
        bg: 'bg-blue-900/20',
        border: 'border-blue-500/30',
        tooltip: t('cloudSync.remoteTooltip')
      };
    }

    if (capsule.asset_status === 'local' && !capsule.audio_uploaded) {
      return {
        icon: Upload,
        color: 'text-orange-400',
        bg: 'bg-orange-900/20',
        border: 'border-orange-500/30',
        tooltip: t('cloudSync.audioNotUploadedTooltip')
      };
    }

    if (capsule.cloud_status === 'synced') {
      return {
        icon: Check,
        color: 'text-green-400',
        bg: 'bg-green-900/20',
        border: 'border-green-500/30',
        tooltip: t('cloudSync.syncedTooltip')
      };
    }

    return {
      icon: Cloud,
      color: 'text-gray-400',
      bg: 'bg-gray-900/20',
      border: 'border-gray-500/30',
      tooltip: t('cloudSync.unknownTooltip')
    };
  };
  
  const state = getSyncState();
  const Icon = state.icon;
  
  return (
    <button
      onClick={(e) => {
        e.stopPropagation(); // 防止触发卡片点击
        onClick && onClick(capsule);
      }}
      title={state.tooltip}
      className={`
        flex items-center gap-1 px-2 py-1 rounded-full border transition-all
        ${state.color} ${state.bg} ${state.border}
        hover:scale-110 active:scale-95
        ${className}
      `}
    >
      <Icon size={14} />
    </button>
  );
};

export default CloudSyncIcon;
