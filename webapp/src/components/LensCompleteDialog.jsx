import React from 'react';
import { CheckCircle, Circle } from 'lucide-react';

const LensCompleteDialog = ({
  isOpen,
  lensName,
  lensConfig, // 新增：接收完整的棱镜配置
  selectedTags,
  completedLenses,
  onContinue,
  onFinish
}) => {
  if (!isOpen) return null;

  // 从 lensConfig 动态获取棱镜名称映射
  const lensNames = {};
  Object.keys(lensConfig).forEach(lensId => {
    lensNames[lensId] = lensConfig[lensId].nameCn || lensConfig[lensId].name || lensId;
  });

  // 动态获取可用的棱镜（未完成的）
  const availableLenses = Object.keys(lensConfig)
    .filter(lens => !completedLenses.includes(lens));

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      {/* 背景遮罩 */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.3s_ease]"></div>

      {/* 对话框容器 */}
      <div className="relative bg-zinc-900/95 backdrop-blur-xl border border-zinc-800 rounded-3xl p-8 max-w-[500px] w-full shadow-2xl animate-[slideUp_0.3s_ease]">
        {/* 头部 */}
        <div className="mb-6 text-center">
          <div className="flex items-center justify-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-purple-400" />
            </div>
            <h2 className="text-xl font-bold text-white tracking-wide">
              完成{lensNames[lensName] || ''}棱镜
            </h2>
          </div>
          <div className="w-16 h-0.5 bg-gradient-to-r from-transparent via-purple-500/50 to-transparent mx-auto rounded-full"></div>
        </div>

        {/* 主体 */}
        <div className="mb-6 space-y-4">
          {/* 已选标签摘要 */}
          <div className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-4">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-purple-400" />
              已选择的标签 ({selectedTags.length})
            </h3>
            <div className="flex flex-wrap gap-2">
              {selectedTags.map((tag, index) => (
                <span
                  key={index}
                  className="inline-flex items-center px-3 py-1.5 bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-500/30 text-white text-sm rounded-full"
                >
                  {tag.zh || tag.word || tag.cn}
                </span>
              ))}
            </div>
          </div>

          {availableLenses.length > 0 ? (
            <div className="bg-zinc-800/30 rounded-2xl p-5 border border-zinc-800">
              <p className="text-zinc-400 text-sm text-center leading-relaxed mb-4">
                你已经完成了当前棱镜的标签选择。
                <br />
                是否继续在其他棱镜中选择标签？
              </p>

              <div className="bg-zinc-900/50 rounded-xl p-4">
                <p className="text-xs font-semibold text-purple-400 mb-3 uppercase tracking-wider">
                  其他可选棱镜:
                </p>
                <div className="flex flex-wrap gap-2">
                  {availableLenses.map(lens => (
                    <span
                      key={lens}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm rounded-full font-medium shadow-lg"
                    >
                      <Circle className="w-3 h-3" />
                      {lensNames[lens]}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-2xl p-6 text-center">
              <div className="flex items-center justify-center gap-2 mb-3">
                <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 text-emerald-400" />
                </div>
                <p className="text-zinc-200 text-base font-semibold">
                  所有棱镜已完成
                </p>
              </div>
              <p className="text-zinc-400 text-sm">
                准备好保存了吗？
              </p>
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="flex gap-3 justify-center">
          {availableLenses.length > 0 ? (
            <>
              <button
                className="px-6 py-3 bg-zinc-800 text-white rounded-xl font-semibold border border-zinc-700 hover:bg-zinc-700 hover:border-zinc-600 transition-all hover:-translate-y-0.5"
                onClick={onFinish}
              >
                完成标签
              </button>
              <button
                className="px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-xl font-semibold shadow-lg shadow-purple-500/30 hover:shadow-purple-500/50 transition-all hover:-translate-y-0.5"
                onClick={onContinue}
              >
                继续选择
              </button>
            </>
          ) : (
            <button
              className="w-full px-8 py-4 bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-xl font-semibold shadow-lg shadow-emerald-500/30 hover:shadow-emerald-500/50 transition-all hover:-translate-y-0.5 text-lg"
              onClick={onFinish}
            >
              完成并保存所有标签
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default LensCompleteDialog;
