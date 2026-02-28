import React from 'react';
import { useTranslation } from 'react-i18next';
import { Cloud, Upload, Download } from 'lucide-react';

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
    const assetStatus = capsule.asset_status || capsule.cloud_status || '';
    const filesDownloaded = capsule.files_downloaded === true || capsule.files_downloaded === 1;
    const isLightweightOnly = assetStatus === 'cloud_only' || !filesDownloaded;

    // 规则 1：本地只有轻数据 -> 所有人显示下载图标
    if (isLightweightOnly) {
      return {
        icon: Download,
        color: 'text-blue-400',
        bg: 'bg-blue-900/20',
        border: 'border-blue-500/30',
        action: 'download',
        tooltip: t('cloudSync.downloadTooltip', '仅有轻数据，点击下载完整资源')
      };
    }

    // 规则 2：本地有完整数据 + 云端无需动作 -> 不显示图标
    // （后续只在作者且有明确动作时显示）
    if (capsule.is_mine !== true) {
      return null;
    }

    // 规则 3：本地有数据、云端没有 -> 作者显示上传图标
    const hasCloudId = capsule.cloud_id !== null && capsule.cloud_id !== undefined && String(capsule.cloud_id).trim() !== '';
    if (capsule.cloud_exists === false && !hasCloudId) {
      return {
        icon: Upload,
        color: 'text-orange-400',
        bg: 'bg-orange-900/20',
        border: 'border-orange-500/30',
        action: 'upload',
        tooltip: t('cloudSync.localTooltip', '本地有数据，云端不存在，点击上传')
      };
    }

    // 规则 4：本地有数据、云端也有且关键词有更新 -> 作者显示云同步图标
    if (capsule.cloud_exists === true && capsule.cloud_keyword_outdated === true) {
      return {
        icon: Cloud,
        color: 'text-blue-400',
        bg: 'bg-blue-900/20',
        border: 'border-blue-500/30',
        action: 'sync',
        tooltip: t('cloudSync.remoteTooltip', '本地关键词与云端不一致，点击同步更新')
      };
    }

    return null;
  };
  
  const state = getSyncState();
  if (!state) return null;

  const Icon = state.icon;
  
  return (
    <button
      onClick={(e) => {
        e.stopPropagation(); // 防止触发卡片点击
        onClick && onClick(capsule, state.action);
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
