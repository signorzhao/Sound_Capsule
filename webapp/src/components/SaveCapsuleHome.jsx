import React, { useState, useEffect } from 'react';
import { Package, Sparkles, Flame, Music, Activity, Settings, X } from 'lucide-react';
import CapsuleCard from './CapsuleCard';
import CapsuleTypeManager from './CapsuleTypeManager';
import UserMenu from './UserMenu';

/**
 * 保存胶囊首页组件 - 重新设计版
 *
 * 使用精美的3D胶囊卡片设计
 * 移除渲染预览开关（默认都渲染）
 * 支持编辑模式管理胶囊类型
 */

function SaveCapsuleHome({ onSave, saveStatus, saveProgress, onShowLibrary }) {
  const [selectedCapsule, setSelectedCapsule] = useState(null);
  const [openCapsuleId, setOpenCapsuleId] = useState(null);
  const [capsuleTypes, setCapsuleTypes] = useState([]);
  const [isEditMode, setIsEditMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isShowManager, setIsShowManager] = useState(false);

  // 从API加载胶囊类型
  const loadCapsuleTypes = async () => {
    try {
      const response = await fetch('http://localhost:5002/api/capsule-types');
      const data = await response.json();

      if (data.success) {
        // 转换为CapsuleCard需要的格式
        const types = data.types.map(t => ({
          id: t.id,
          type: t.id,
          name: t.name,
          nameCn: t.name_cn,
          description: t.description,
          icon: t.icon,
          color: t.color,
          gradient: t.gradient,
          priorityLens: t.priority_lens
        }));
        setCapsuleTypes(types);
      } else {
        console.error('加载胶囊类型失败:', data.error);
        // 使用默认类型
        setCapsuleTypes([
          { id: 'magic', type: 'magic', name: 'MAGIC', nameCn: '魔法', description: '神秘、梦幻、超自然' },
          { id: 'impact', type: 'impact', name: 'IMPACT', nameCn: '打击', description: '强力、冲击、震撼' },
          { id: 'atmosphere', type: 'atmosphere', name: 'ATMOSPHERE', nameCn: '环境', description: '空间、氛围、场景' }
        ]);
      }
    } catch (error) {
      console.error('加载胶囊类型失败:', error);
      // 使用默认类型
      setCapsuleTypes([
        { id: 'magic', type: 'magic', name: 'MAGIC', nameCn: '魔法', description: '神秘、梦幻、超自然' },
        { id: 'impact', type: 'impact', name: 'IMPACT', nameCn: '打击', description: '强力、冲击、震撼' },
        { id: 'atmosphere', type: 'atmosphere', name: 'ATMOSPHERE', nameCn: '环境', description: '空间、氛围、场景' }
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCapsuleTypes();
  }, []);

  const handleCapsuleClick = (id) => {
    // 编辑模式下不允许选择胶囊
    if (isEditMode) return;

    // 切换打开/关闭状态
    setOpenCapsuleId(openCapsuleId === id ? null : id);

    // 选中胶囊
    if (openCapsuleId !== id) {
      const capsule = capsuleTypes.find(c => c.id === id);
      setSelectedCapsule(capsule);
    }
  };

  const handleSave = () => {
    if (!selectedCapsule) {
      alert('请先选择一个胶囊');
      return;
    }

    // 只发送必要的字段
    // 后端会根据 capsule_type 自动生成项目名和主题名
    onSave({
      capsule_type: selectedCapsule.type,
      render_preview: true,
      webui_port: 9000
    });
  };

  const isChecking = saveStatus === 'checking';
  const isSaving = saveStatus === 'saving';
  const isSuccess = saveStatus === 'success';
  const isBusy = isChecking || isSaving;

  // 获取当前选中胶囊的颜色（用于进度条）
  const getCapsuleColors = () => {
    if (!selectedCapsule) return { top: '#8b5cf6', bottom: '#c4b5fd', Icon: Sparkles };

    const colorMap = {
      magic: { top: '#8b5cf6', bottom: '#c4b5fd', Icon: Sparkles },
      impact: { top: '#ef4444', bottom: '#fca5a5', Icon: Flame },
      atmosphere: { top: '#3b82f6', bottom: '#93c5fd', Icon: Music },
      texture: { top: '#10b981', bottom: '#6ee7b7', Icon: Activity }
    };

    return colorMap[selectedCapsule.type] || colorMap.magic;
  };

  const { top: topColor, bottom: bottomColor, Icon: CapsuleIcon } = getCapsuleColors();

  return (
    <div className="relative min-h-screen w-full bg-black flex items-center justify-center p-8 overflow-hidden font-sans">
      {/* 星空背景 */}
      <div className="fixed inset-0 bg-[radial-gradient(2px_2px_at_20px_30px,#eee,rgba(0,0,0,0)),radial-gradient(2px_2px_at_40px_70px,#fff,rgba(0,0,0,0)),radial-gradient(2px_2px_at_50px_160px,#ddd,rgba(0,0,0,0)),radial-gradient(2px_2px_at_90px_40px,#fff,rgba(0,0,0,0)),radial-gradient(2px_2px_at_130px_80px,#fff,rgba(0,0,0,0))] bg-[length:200px_200px] animate-[twinkle_8s_infinite] opacity-30 z-0"></div>

      {/* 背景装饰层 */}
      <div className="absolute inset-0 pointer-events-none z-0">
        <div className="absolute top-[-20%] left-[10%] w-[600px] h-[600px] bg-indigo-900/20 blur-[120px] rounded-full mix-blend-screen"></div>
        <div className="absolute bottom-[-20%] right-[10%] w-[600px] h-[600px] bg-blue-900/20 blur-[120px] rounded-full mix-blend-screen"></div>
      </div>

      {/* 主内容 */}
      <div className="relative z-10 w-full max-w-6xl">
        {/* 头部 */}
        <header className="text-center mb-16">
          <div className="flex items-center justify-between mb-4">
            <div className="flex-1 flex justify-start">
              {/* 编辑模式切换按钮 */}
              <button
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isEditMode
                    ? 'bg-red-500/15 border border-red-500/30 text-red-400 hover:bg-red-500/25 hover:border-red-500/50'
                    : 'bg-blue-500/15 border border-blue-500/30 text-blue-400 hover:bg-blue-500/25 hover:border-blue-500/50'
                }`}
                onClick={() => setIsEditMode(!isEditMode)}
              >
                <Settings className="w-4 h-4 flex-shrink-0" />
                <span>{isEditMode ? '退出编辑' : '管理类型'}</span>
              </button>
            </div>
            <h1 className="text-3xl font-bold text-white tracking-[0.1em] uppercase flex-1 text-center">
              {isEditMode ? '胶囊类型管理' : '选择胶囊类型'}
            </h1>
            <div className="flex-1 flex justify-end gap-3 items-center">
              <UserMenu />
              {!isEditMode && (
                <button
                  className="flex items-center gap-2 px-5 py-2.5 bg-purple-500/15 border border-purple-500/30 rounded-xl text-purple-400 text-sm font-medium hover:bg-purple-500/25 hover:border-purple-500/50 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-purple-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
                  onClick={onShowLibrary}
                  disabled={isBusy}
                >
                  <Package className="w-4 h-4 flex-shrink-0" />
                  <span>查看胶囊库</span>
                </button>
              )}
            </div>
          </div>
          <p className="text-sm text-zinc-600 tracking-[0.05em]">
            {isEditMode ? '编辑模式下可以对胶囊类型进行增加、修改、删除操作' : '点击胶囊打开，选择类型后点击"SAVE"保存'}
          </p>
        </header>

        {/* 胶囊选择区域 */}
        {!isEditMode ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-16 justify-items-center items-center">
            {capsuleTypes.map((capsule) => (
              <CapsuleCard
                key={capsule.id}
                capsule={capsule}
                isOpen={openCapsuleId === capsule.id}
                onClick={handleCapsuleClick}
                onSave={handleSave}
              />
            ))}

            {/* 空位占位符 */}
            <div className="hidden lg:flex flex-col items-center justify-center opacity-30 group cursor-default transition-all duration-300 hover:opacity-50">
              <div className="w-40 h-80 rounded-full border border-dashed border-zinc-700 flex flex-col items-center justify-center gap-4">
                <div className="w-[1px] h-12 bg-zinc-800"></div>
                <div className="w-12 h-[1px] bg-zinc-800 absolute"></div>
              </div>
              <h3 className="mt-4 text-[10px] text-zinc-700 tracking-[0.3em] uppercase font-bold">EMPTY</h3>
            </div>
          </div>
        ) : (
          /* 编辑模式：显示管理按钮 */
          <div className="mt-8">
            <button
              className="w-full py-6 bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-xl font-bold text-lg shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5"
              onClick={() => setIsShowManager(true)}
            >
              <Settings className="inline w-5 h-5 mr-2 mb-1" />
              打开胶囊类型管理器
            </button>
          </div>
        )}

        {/* 检查状态提示 */}
        {isChecking && (
          <div className="fixed bottom-0 left-0 right-0 z-50 bg-black/90 backdrop-blur-xl border-t border-zinc-800">
            <div className="max-w-7xl mx-auto px-6 py-4">
              <div className="flex items-center gap-4">
                <div className="relative w-12 h-12 flex-shrink-0">
                  <div className="absolute inset-0 rounded-full border-2 border-zinc-700"></div>
                  <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-purple-500 animate-spin"></div>
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-white">正在检查 REAPER 选中状态...</h3>
                  <p className="text-xs text-zinc-500 mt-1">请稍候，正在验证是否有选中的音频 Items</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 进度提示 */}
        {isSaving && (
          <div className="fixed bottom-0 left-0 right-0 z-50 bg-black/90 backdrop-blur-xl border-t border-zinc-800">
            <div className="max-w-7xl mx-auto px-6 py-4">
              <div className="flex items-center gap-4">
                {/* 加载动画图标 */}
                <div className="relative w-12 h-12 flex-shrink-0">
                  <div className="absolute inset-0 rounded-full border-2 border-zinc-700"></div>
                  <div
                    className="absolute inset-0 rounded-full border-2 border-transparent border-t-purple-500 animate-spin"
                    style={{
                      borderTopColor: topColor
                    }}
                  ></div>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <CapsuleIcon size={16} style={{ color: topColor }} />
                  </div>
                </div>

                {/* 进度信息 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-white">正在保存胶囊...</h3>
                    <span className="text-sm font-bold text-zinc-300">{saveProgress}%</span>
                  </div>
                  <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300 relative overflow-hidden"
                      style={{
                        width: `${saveProgress}%`,
                        background: `linear-gradient(to right, ${topColor}, ${bottomColor})`
                      }}
                    >
                      {/* 闪光动画效果 */}
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-[shimmer_1.5s_infinite]"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 成功提示 */}
        {isSuccess && (
          <div className="fixed bottom-0 left-0 right-0 z-50 bg-black/90 backdrop-blur-xl border-t border-zinc-800">
            <div className="max-w-7xl mx-auto px-6 py-4">
              <div className="flex items-center gap-4">
                {/* 成功图标 */}
                <div className="relative w-12 h-12 flex-shrink-0">
                  <div className="absolute inset-0 rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/20 blur-sm"></div>
                  <div className="absolute inset-0 rounded-full border border-purple-500/30 flex items-center justify-center">
                    <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>

                {/* 成功信息 */}
                <div className="flex-1">
                  <h3 className="text-sm font-bold tracking-wide text-white uppercase">Capsule Saved</h3>
                  <p className="text-xs text-zinc-500 tracking-wider mt-0.5">Redirecting to semantic tags...</p>
                </div>

                {/* 进度指示器 */}
                <div className="flex gap-1.5">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse"
                      style={{
                        animationDelay: `${i * 0.15}s`,
                        backgroundColor: i === 0 ? topColor : undefined
                      }}
                    ></div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 胶囊类型管理器 */}
        {isShowManager && (
          <CapsuleTypeManager
            onClose={() => {
              setIsShowManager(false);
              loadCapsuleTypes(); // 重新加载类型
            }}
          />
        )}
      </div>
    </div>
  );
}

export default SaveCapsuleHome;
