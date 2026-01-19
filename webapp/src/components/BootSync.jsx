import React, { useState, useEffect, useRef } from 'react';
import { Cloud, Download, Check, AlertCircle, Sparkles } from 'lucide-react';
import { useSync } from '../contexts/SyncContext';

/**
 * BootSync - 启动同步组件
 *
 * Phase G2: 启动同步逻辑（仅下载模式）
 *
 * 功能：
 * - 在用户登录后、进入 App 前执行仅下载同步
 * - 不上传本地数据，避免每次启动都上传
 * - 显示同步进度和状态
 * - 支持跳过（30秒后）
 */
export default function BootSync({ onComplete, onError }) {
  const { syncDownloadOnly } = useSync();

  const [status, setStatus] = useState('initializing'); // 'initializing' | 'syncing' | 'completed' | 'error'
  const [canSkip, setCanSkip] = useState(false);
  const hasStartedRef = useRef(false); // 使用 useRef 避免触发 useEffect 重新执行
  const onCompleteRef = useRef(onComplete); // 保持回调引用稳定
  const onErrorRef = useRef(onError); // 保持回调引用稳定
  const [error, setError] = useState(null);
  const [progressInfo, setProgressInfo] = useState({ phase: '', current: 0, total: 0, currentFile: '', percentage: 0 });

  // 更新回调引用
  useEffect(() => {
    onCompleteRef.current = onComplete;
    onErrorRef.current = onError;
  }, [onComplete, onError]);

  // 30秒后允许跳过
  useEffect(() => {
    let timeoutId;
    let mounted = true;

    timeoutId = setTimeout(() => {
      if (mounted && status === 'syncing') {
        setCanSkip(true);
      }
    }, 30000);

    return () => {
      mounted = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [status]);

  // 执行启动同步（只执行一次）
  useEffect(() => {
    console.log('[BootSync] 组件挂载', Date.now());
    let mounted = true;

    async function performBootSync() {
      // 防止重复执行
      if (hasStartedRef.current) {
        console.log('[BootSync] 已经启动过，跳过');
        return;
      }
      hasStartedRef.current = true;
      console.log('[BootSync] 标记为已启动');

      try {
        console.log('🚀 [BootSync] 开始启动同步...');

        setStatus('syncing');

        // 启动同步：仅下载（不上传）
        const result = await syncDownloadOnly({
          onProgress: (progress) => {
            if (!mounted) return;
            setProgressInfo(progress);
          }
        });

        if (!mounted) return;

        if (result.success) {
          console.log('✅ [BootSync] 同步完成', result);
          setStatus('completed');

          // 1秒后自动进入 App
          setTimeout(() => {
            if (mounted && onCompleteRef.current) {
              onCompleteRef.current({ success: true, ...result });
            }
          }, 1000);
        } else if (!result.skipped) {
          // 如果不是跳过，则视为错误
          throw new Error(result.error || '同步失败');
        }

      } catch (err) {
        console.error('❌ [BootSync] 同步失败:', err);
        if (!mounted) return;

        setStatus('error');
        setError(err.message || '未知错误');

        if (onErrorRef.current) onErrorRef.current(err);
      }
    }

    // 延迟执行，确保 token 已加载
    const timeoutId = setTimeout(() => {
      performBootSync();
    }, 100);

    return () => {
      mounted = false;
      clearTimeout(timeoutId);
    };
  }, []); // 空依赖数组，确保只执行一次

  const handleSkip = () => {
    console.log('⏭️ [BootSync] 用户跳过同步');
    if (onCompleteRef.current) {
      onCompleteRef.current({ skipped: true });
    }
  };

  // 计算进度条颜色
  const getProgressColor = () => {
    if (status === 'error') return 'from-red-500 to-red-600';
    if (status === 'completed') return 'from-green-500 to-green-600';
    return 'from-purple-500 to-pink-500';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 backdrop-blur-xl">
      <div className="max-w-2xl w-full mx-4">
        {/* Logo 和标题 */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 mb-6">
            <Sparkles className="w-10 h-10 text-purple-400" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-3">Sound Capsule</h1>
          <p className="text-zinc-400">全球声音资产协作网络</p>
        </div>

        {/* 同步卡片 */}
        <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl border border-zinc-800 p-8 shadow-2xl">

          {/* 状态图标 */}
          <div className="flex justify-center mb-6">
            {status === 'initializing' && (
              <Cloud className="w-12 h-12 text-blue-400 animate-pulse" />
            )}
            {status === 'syncing' && (
              <Download className="w-12 h-12 text-purple-400 animate-bounce" />
            )}
            {status === 'completed' && (
              <Check className="w-12 h-12 text-green-400" />
            )}
            {status === 'error' && (
              <AlertCircle className="w-12 h-12 text-red-400" />
            )}
          </div>

          {/* 状态文本 */}
          <div className="text-center mb-8">
            <h2 className="text-xl font-semibold text-white mb-2">
              {status === 'initializing' && '初始化同步...'}
              {status === 'syncing' && '正在下载全球资产...'}
              {status === 'completed' && '下载完成'}
              {status === 'error' && '同步失败'}
            </h2>
            <p className="text-zinc-400 text-sm">
              {progressInfo.phase || '准备中...'}
            </p>
            {progressInfo.currentFile && (
              <p className="text-zinc-500 text-xs mt-1">
                当前: {progressInfo.currentFile} ({progressInfo.current}/{progressInfo.total})
              </p>
            )}
          </div>

          {/* 进度条 */}
          {status === 'syncing' && (
            <div className="mb-6">
              {/* 进度条轨道 */}
              <div className="h-2 bg-zinc-800 rounded-full overflow-hidden mb-4">
                <div
                  className={`h-full bg-gradient-to-r ${getProgressColor()} transition-all duration-300 ease-out`}
                  style={{ width: `${progressInfo.percentage || 0}%` }}
                />
              </div>

              {/* 进度信息 */}
              <div className="flex justify-between text-sm text-zinc-500">
                <span>下载进度</span>
                <span>{Math.round(progressInfo.percentage || 0)}%</span>
              </div>
            </div>
          )}

          {/* 统计信息 */}
          {status === 'completed' && (
            <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 mb-6">
              <div className="text-center text-green-400 text-sm">
                <Check className="w-5 h-5 inline-block mr-2" />
                全球资产下载完成，可以开始使用
              </div>
            </div>
          )}

          {/* 错误信息 */}
          {status === 'error' && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6">
              <div className="text-red-400 text-sm">
                <AlertCircle className="w-5 h-5 inline-block mr-2" />
                {error || '同步过程中发生错误'}
              </div>
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex justify-center gap-4">
            {status === 'error' && (
              <>
                <button
                  onClick={() => {
                    // 重置状态并重新执行同步
                    hasStartedRef.current = false;
                    setStatus('initializing');
                    setError(null);
                    // window.location.reload();
                    console.error("🛑 [DEBUG] 拦截到重启请求（BootSync 重试按钮）");
                    alert("调试模式：拦截到 BootSync 重试重启请求");
                  }}
                  className="px-6 py-3 bg-purple-500 hover:bg-purple-600 text-white rounded-xl font-medium transition-colors"
                >
                  重试
                </button>
                <button
                  onClick={handleSkip}
                  className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl font-medium transition-colors"
                >
                  跳过
                </button>
              </>
            )}
            {canSkip && status === 'syncing' && (
              <button
                onClick={handleSkip}
                className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl font-medium transition-colors"
              >
                跳过（稍后同步）
              </button>
            )}
            {status === 'completed' && onCompleteRef.current && (
              <button
                onClick={() => onCompleteRef.current({ completed: true })}
                className="px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-xl font-medium transition-all"
              >
                开始使用
              </button>
            )}
          </div>
        </div>

        {/* 提示信息 */}
        <div className="mt-6 text-center text-xs text-zinc-600">
          <p>仅下载云端数据，不会上传本地修改</p>
          <p className="mt-1">如需上传本地胶囊，请在胶囊库中点击胶囊的上传按钮</p>
        </div>
      </div>
    </div>
  );
}
