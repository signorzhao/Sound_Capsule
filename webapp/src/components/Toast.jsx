import React, { useState, useEffect, createContext, useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info, Loader2 } from 'lucide-react';

// Toast 上下文
const ToastContext = createContext();

// Toast Provider 组件
export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const scheduleRemove = (id, duration) => {
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  };

  // 添加 Toast
  const addToast = (message, type = 'info', duration = 3000) => {
    const id = Date.now() + Math.random();
    const toast = { id, message, type, duration };

    setToasts(prev => [...prev, toast]);

    // 自动移除
    scheduleRemove(id, duration);

    return id;
  };

  // 更新 Toast
  const updateToast = (id, message, type = 'info', duration = 3000) => {
    setToasts(prev => prev.map(toast => {
      if (toast.id !== id) return toast;
      return { ...toast, message, type, duration };
    }));
    scheduleRemove(id, duration);
  };

  // 移除 Toast
  const removeToast = (id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  // 快捷方法
  const toast = {
    success: (message, duration) => addToast(message, 'success', duration),
    error: (message, duration) => addToast(message, 'error', duration),
    warning: (message, duration) => addToast(message, 'warning', duration),
    info: (message, duration) => addToast(message, 'info', duration),
    loading: (message) => addToast(message, 'loading', 0),
    update: (id, message, type = 'info', duration = 3000) => updateToast(id, message, type, duration),
    dismiss: (id) => removeToast(id),
  };

  return (
    <ToastContext.Provider value={{ toast, addToast, removeToast, updateToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
};

// Toast Hook
export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context.toast;
};

// Toast 容器组件
const ToastContainer = ({ toasts, onRemove }) => {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
      {toasts.map(toast => (
        <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>
  );
};

// Toast 单项组件
const ToastItem = ({ toast, onRemove }) => {
  const { t } = useTranslation();
  const [isExiting, setIsExiting] = useState(false);

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => onRemove(toast.id), 300);
  };

  const icons = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
    loading: Loader2
  };

  const colors = {
    success: 'bg-emerald-500/90 border-emerald-400',
    error: 'bg-red-500/90 border-red-400',
    warning: 'bg-amber-500/90 border-amber-400',
    info: 'bg-blue-500/90 border-blue-400',
    loading: 'bg-blue-500/90 border-blue-400'
  };

  const iconColors = {
    success: 'text-emerald-200',
    error: 'text-red-200',
    warning: 'text-amber-200',
    info: 'text-blue-200',
    loading: 'text-blue-200'
  };

  const Icon = icons[toast.type];

  return (
    <div
      className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg shadow-2xl backdrop-blur-md border min-w-[300px] max-w-md
        ${colors[toast.type]}
        transition-all duration-300
        ${isExiting ? 'opacity-0 translate-y-4' : 'opacity-100 translate-y-0'}
      `}
    >
      {/* 图标 */}
      <Icon size={20} className={`${iconColors[toast.type]} ${toast.type === 'loading' ? 'animate-spin' : ''}`} />

      {/* 消息 */}
      <span className="flex-1 text-white text-sm font-medium">
        {toast.message}
      </span>

      {/* 关闭按钮 */}
      <button
        onClick={handleClose}
        className="text-white/80 hover:text-white hover:bg-white/20 rounded p-1 transition-colors"
        aria-label={t('common.dismiss')}
      >
        <X size={16} />
      </button>

      {/* 进度条（仅在 duration > 0 时显示） */}
      {toast.duration > 0 && (
        <div className="absolute bottom-0 left-0 h-0.5 bg-white/30">
          <div
            className="h-full bg-white/80"
            style={{
              animation: `shrink ${toast.duration}ms linear forwards`
            }}
          />
        </div>
      )}
    </div>
  );
};

// 添加动画关键帧
const style = document.createElement('style');
style.textContent = `
  @keyframes shrink {
    from { width: 100%; }
    to { width: 0%; }
  }
`;
if (!document.head.querySelector('style[data-toast]')) {
  style.setAttribute('data-toast', 'true');
  document.head.appendChild(style);
}

export default ToastProvider;
