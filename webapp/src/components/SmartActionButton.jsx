import React from 'react';
import { useTranslation } from 'react-i18next';
import { Cloud, Check, Loader2, AlertTriangle, Play } from 'lucide-react';

/**
 * SmartActionButton - JIT 智能按钮组件
 *
 * 根据胶囊的资源状态动态显示不同的按钮样式和行为
 *
 * @param {Object} props
 * @param {string} props.status - 胶囊状态 ('cloud_only' | 'downloading' | 'synced' | 'partial')
 * @param {Function} props.onClick - 点击回调
 * @param {string} props.className - 额外的 CSS 类名
 */
const SmartActionButton = ({ status, onClick, className = '' }) => {
  const { t } = useTranslation();

  const config = {
    cloud_only: {
      icon: Cloud,
      text: t('smartAction.fetch'),
      style: 'bg-blue-500/20 text-blue-400 border-blue-500/30 hover:bg-blue-500/30',
      tooltip: t('smartAction.cloudOnlyTooltip')
    },
    downloading: {
      icon: Loader2,
      text: t('smartAction.downloading'),
      style: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30 cursor-wait',
      animate: true,
      tooltip: t('smartAction.downloadingTooltip')
    },
    synced: {
      icon: Play,
      text: t('smartAction.open'),
      style: 'bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/30',
      tooltip: t('smartAction.openTooltip')
    },
    local: {
      icon: Play,
      text: t('smartAction.open'),
      style: 'bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/30',
      tooltip: t('smartAction.openTooltip')
    },
    full: {
      icon: Play,
      text: t('smartAction.open'),
      style: 'bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/30',
      tooltip: t('smartAction.openTooltip')
    },
    partial: {
      icon: AlertTriangle,
      text: t('smartAction.fix'),
      style: 'bg-orange-500/20 text-orange-400 border-orange-500/30 hover:bg-orange-500/30',
      tooltip: t('smartAction.partialTooltip')
    }
  };

  // 默认使用 cloud_only，防止未知状态报错
  const current = config[status] || config.cloud_only;
  const Icon = current.icon;

  return (
    <button
      onClick={(e) => {
        e.stopPropagation(); // 防止触发卡片点击
        onClick();
      }}
      title={current.tooltip}
      className={`
        flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-all
        ${current.style} ${className}
      `}
    >
      <Icon size={14} className={current.animate ? 'animate-spin' : ''} />
      <span>{current.text}</span>
    </button>
  );
};

export default SmartActionButton;
