import React from 'react';
import { useTranslation } from 'react-i18next';
import { Cloud, Upload, Check } from 'lucide-react';

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
    // 非作者：不显示云状态图标
    if (capsule.is_mine !== true) {
      return null;
    }

    // 作者 + 云端无数据：显示上传按钮
    if (capsule.cloud_exists === false) {
      return {
        icon: Upload,
        color: 'text-orange-400',
        bg: 'bg-orange-900/20',
        border: 'border-orange-500/30',
        tooltip: t('cloudSync.localTooltip', '本地有数据，云端不存在，点击上传')
      };
    }

    // 作者 + 云端有数据且关键词不一致：显示云同步按钮
    if (capsule.cloud_exists === true && capsule.cloud_keyword_outdated === true) {
      return {
        icon: Cloud,
        color: 'text-blue-400',
        bg: 'bg-blue-900/20',
        border: 'border-blue-500/30',
        tooltip: t('cloudSync.remoteTooltip', '本地关键词与云端不一致，点击同步更新')
      };
    }

    // 作者 + 云端一致：显示已同步
    if (capsule.cloud_exists === true && capsule.cloud_keyword_outdated === false) {
      return {
        icon: Check,
        color: 'text-green-400',
        bg: 'bg-green-900/20',
        border: 'border-green-500/30',
        tooltip: t('cloudSync.syncedTooltip', '云端与本地一致')
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
  if (!state) return null;

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
