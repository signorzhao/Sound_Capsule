import React from 'react';
import i18n from '../i18n';
import {
  Sparkles, Flame, Zap, Wind, Music, Activity, Box,
  Radio, Headphones, Guitar, Piano, Mic, Volume2, Bell,
  Signal, Heart, Timer, Clock, Target, Star, Sun, Moon, Snowflake
} from 'lucide-react';

// 图标组件映射表
const ICON_COMPONENTS = {
  Sparkles, Flame, Music, Activity, Box,
  Zap, Radio, Headphones, Guitar,
  Piano, Mic, Volume2, Bell,
  Wind, Signal, Heart, Timer, Clock,
  Target, Star, Sun, Moon, Snowflake
};

const CapsuleCard = ({ capsule, isOpen, onClick, onSave }) => {
  const { type, name, nameCn, icon, color, gradient, id } = capsule;
  const isEn = i18n.language === 'en' || i18n.language?.startsWith('en');
  const displayName = isEn ? (name || nameCn) : (nameCn || name);

  // 从 gradient 中提取颜色
  let colorTop = color;
  let colorBottom = color;

  if (gradient) {
    const colorMatch = gradient.match(/#[A-Fa-f0-9]{6}/g);
    if (colorMatch && colorMatch.length >= 2) {
      colorTop = colorMatch[0];
      colorBottom = colorMatch[1];
    }
  }

  // 如果没有颜色，使用默认紫色
  if (!colorTop) colorTop = '#8b5cf6';
  if (!colorBottom) colorBottom = '#3b82f6';

  // 获取图标组件
  const Icon = ICON_COMPONENTS[icon] || ICON_COMPONENTS.Sparkles;

  // 处理按钮点击（保存）
  const handleSaveClick = (e) => {
    e.stopPropagation(); // 阻止事件冒泡到胶囊容器
    if (onSave) {
      onSave(capsule);
    }
  };

  return (
    <div
      className="group relative flex flex-col items-center justify-center cursor-pointer z-20 hover:z-40 transition-all duration-300"
      style={{ perspective: '1000px' }}
      onClick={() => onClick(id)}
    >
      {/* 胶囊主容器 */}
      <div className="relative w-40 h-80 transition-transform duration-500 ease-out group-hover:scale-105">
        {/* 底部悬浮光：移到胶囊底部，小点+柔和阴影，避免明显椭圆形 */}
        <div
          className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full opacity-50 transition-all duration-700 group-hover:opacity-70 pointer-events-none"
          style={{
            boxShadow: `0 0 36px 18px ${colorTop}40`,
          }}
        ></div>
        {/* 上半部分 (The Cap) */}
        <div
          className={`absolute left-0 right-0 mx-auto top-0 w-full h-[52%] rounded-t-full rounded-b-sm z-30 overflow-hidden transition-all duration-700 ${
            isOpen ? 'translate-y-[-70px] -rotate-5' : ''
          }`}
          style={{
            backgroundColor: colorTop,
            transformOrigin: '50% 100%',
            boxShadow: isOpen
              ? '0 25px 35px -5px rgba(0,0,0,0.8), inset 0 -2px 5px rgba(0,0,0,0.5)'
              : '0 4px 15px rgba(0,0,0,0.8)'
          }}
        >
          {/* 体积感阴影层 */}
          <div className="absolute inset-0 bg-gradient-to-r from-black/40 via-transparent to-black/30 pointer-events-none"></div>

          {/* 高光层 */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent opacity-50 pointer-events-none" style={{ backgroundSize: '200% 100%', backgroundPosition: '30% 0' }}></div>

          {/* 边缘轮廓光 */}
          <div className="absolute inset-0 rounded-t-full border-[1px] border-white/20 pointer-events-none"></div>
          <div className="absolute top-10 right-3 w-[1px] h-[60%] bg-white/60 blur-[2px]"></div>
          <div className="absolute top-10 left-3 w-[2px] h-[60%] bg-black/50 blur-[2px]"></div>

          {/* 顶部强高光 */}
          <div className="absolute top-6 left-5 w-[30%] h-[40%] bg-gradient-to-b from-white/80 to-transparent rounded-full blur-[6px]"></div>
        </div>

        {/* 内部机械结构 */}
        <div className={`absolute left-0 right-0 top-[30%] bottom-[30%] z-10 flex flex-col items-center justify-center transition-all duration-500 delay-75 ${
          isOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-75'
        }`}>
          {/* 连接杆 */}
          <div className="w-2 h-[140%] bg-zinc-800 absolute"></div>

          {/* 按钮 */}
          <div
            className="relative bg-black border border-zinc-700 px-6 py-3 rounded-xl shadow-[0_0_30px_rgba(255,255,255,0.15)] flex items-center gap-3 transform hover:scale-110 active:scale-95 transition-all cursor-pointer group/btn z-20"
            onClick={handleSaveClick}
          >
            <div className="absolute inset-0 bg-white/10 rounded-xl opacity-0 group-hover/btn:opacity-100 transition-opacity"></div>
            <Icon size={18} style={{ color: colorTop }} className="animate-pulse" />
            <span className="text-white font-bold tracking-widest text-sm whitespace-nowrap uppercase">SAVE {name}</span>
          </div>
        </div>

        {/* 下半部分 (The Body) */}
        <div
          className={`absolute left-0 right-0 mx-auto bottom-0 w-[92%] h-[50%] rounded-b-full rounded-t-lg z-20 overflow-hidden transition-all duration-700 ${
            isOpen ? 'translate-y-[70px] rotate-5' : ''
          }`}
          style={{
            backgroundColor: colorBottom,
            transformOrigin: '50% 0%',
            boxShadow: isOpen
              ? '0 -25px 35px -5px rgba(0,0,0,0.8), inset 0 2px 5px rgba(255,255,255,0.1)'
              : 'inset 0 10px 20px rgba(0,0,0,0.8)'
          }}
        >
          {/* 体积感阴影层 */}
          <div className="absolute inset-0 bg-gradient-to-r from-black/40 via-transparent to-black/30 pointer-events-none"></div>

          {/* 顶部遮挡阴影 */}
          {!isOpen && (
            <div className="absolute top-0 w-full h-8 bg-gradient-to-b from-black/70 to-transparent z-10"></div>
          )}

          {/* 底部强烈反光 */}
          <div className="absolute bottom-6 right-6 w-[40%] h-[30%] bg-white/10 rounded-full blur-[8px]"></div>
          <div className="absolute inset-0 rounded-b-full border-b border-r border-white/10 pointer-events-none"></div>
        </div>
      </div>

      {/* 标签文字 */}
      <div className={`mt-12 flex flex-col items-center transition-all duration-500 ${
        isOpen ? 'opacity-0 translate-y-8' : 'opacity-100'
      }`}>
        <span className="text-[10px] text-zinc-600 font-bold tracking-[0.5em] mb-1 opacity-80 uppercase">CAPSULE</span>
        <h3 className="text-lg font-bold text-zinc-300 tracking-[0.2em] uppercase drop-shadow-md">{displayName}</h3>
      </div>
    </div>
  );
};

export default CapsuleCard;
