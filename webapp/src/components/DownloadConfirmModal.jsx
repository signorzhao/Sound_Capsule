import React from 'react';
import { Download, FileText, X } from 'lucide-react';

/**
 * DownloadConfirmModal - JIT 决策弹窗组件
 *
 * 让用户在需要时选择下载策略：
 * - 下载完整资源并打开（推荐）
 * - 仅打开工程文件（媒体离线）
 *
 * @param {Object} props
 * @param {string} props.capsuleName - 胶囊名称
 * @param {Function} props.onConfirm - 用户选择"下载并打开"的回调
 * @param {Function} props.onOfflineOpen - 用户选择"仅打开 RPP"的回调
 * @param {Function} props.onClose - 用户取消的回调
 */
export default function DownloadConfirmModal({
  capsuleName = '',
  onConfirm = () => {},
  onOfflineOpen = () => {},
  onClose = () => {}
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl p-6 max-w-md w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 关闭按钮 */}
        <button onClick={onClose} className="absolute top-4 right-4 text-zinc-500 hover:text-white">
          <X size={20} />
        </button>

        {/* 标题和描述 */}
        <h3 className="text-lg font-bold text-white mb-2">资源未就绪</h3>
        <p className="text-zinc-400 text-sm mb-6">
          胶囊 <span className="text-purple-400 font-mono">{capsuleName}</span> 的音频文件尚未下载到本地。您希望如何处理？
        </p>

        {/* 操作按钮 */}
        <div className="space-y-3">
          {/* 选项 A: 推荐 */}
          <button
            onClick={onConfirm}
            className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 text-white py-3 rounded-lg font-medium transition-colors"
          >
            <Download size={18} />
            下载完整资源并打开 (推荐)
          </button>

          {/* 选项 B: 降级 */}
          <button
            onClick={onOfflineOpen}
            className="w-full flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 py-3 rounded-lg font-medium border border-zinc-700 transition-colors"
          >
            <FileText size={18} />
            仅打开工程文件 (媒体离线)
          </button>
        </div>
      </div>
    </div>
  );
}
