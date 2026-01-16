import React from 'react';
import { Sparkles, Flame, Music } from 'lucide-react';

/**
 * 胶囊类型选择卡片组件
 *
 * 显示三种预设胶囊类型，用户点击选择保存类型
 *
 * Props:
 * - type: 胶囊类型 ('magic' | 'impact' | 'atmosphere')
 * - selected: 是否选中
 * - onClick: 点击回调函数
 */

const CAPSULE_TYPES = {
  magic: {
    id: 'magic',
    name: '魔法胶囊',
    icon: Sparkles,
    description: '保存纹理型、抽象素材',
    examples: ['粒子合成', '调制噪声', '演变音色'],
    color: '#8B5CF6',
    gradient: 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)'
  },
  impact: {
    id: 'impact',
    name: '打击胶囊',
    icon: Flame,
    description: '保存瞬态感强的素材',
    examples: ['鼓点', '打击乐', '贝斯拨奏'],
    color: '#EF4444',
    gradient: 'linear-gradient(135deg, #EF4444 0%, #F59E0B 100%)'
  },
  atmosphere: {
    id: 'atmosphere',
    name: '环境胶囊',
    icon: Music,
    description: '保存氛围型、长线条素材',
    examples: ['Pad', '氛围纹理', '音景'],
    color: '#10B981',
    gradient: 'linear-gradient(135deg, #10B981 0%, #06B6D4 100%)'
  }
};

function CapsuleTypeCard({ type, selected, onClick }) {
  const config = CAPSULE_TYPES[type];
  const IconComponent = config.icon;

  return (
    <div
      className={`capsule-card ${selected ? 'selected' : ''}`}
      onClick={onClick}
      style={{ '--capsule-color': config.color }}
    >
      {/* 背景渐变 */}
      <div className="capsule-card-background" style={{ background: config.gradient }} />

      {/* 胶囊图标 */}
      <div className="capsule-icon" style={{ filter: `drop-shadow(0 0 20px ${config.color})` }}>
        <IconComponent size={48} />
      </div>

      {/* 胶囊名称 */}
      <div className="capsule-name">{config.name}</div>

      {/* 胶囊描述 */}
      <div className="capsule-description">{config.description}</div>

      {/* 示例标签 */}
      <div className="capsule-examples">
        {config.examples.map((example, index) => (
          <span key={index} className="example-tag">
            {example}
          </span>
        ))}
      </div>
    </div>
  );
}

export default CapsuleTypeCard;
