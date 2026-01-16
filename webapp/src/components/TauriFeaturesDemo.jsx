import React, { useState, useEffect } from 'react';
import { Bell, Download, Save, FolderOpen, Minus, Square, X as XIcon } from 'lucide-react';
import {
  sendNotification,
  requestNotificationPermission,
  saveFile,
  openFile,
  windowControls,
  getAppInfo,
  isTauri
} from '../utils/tauriApi';

/**
 * Tauri 功能演示组件
 * 展示桌面应用的原生功能
 */
function TauriFeaturesDemo() {
  const [appInfo, setAppInfo] = useState(null);
  const [notificationPermission, setNotificationPermission] = useState(false);
  const [isTauriEnv, setIsTauriEnv] = useState(false);

  useEffect(() => {
    // 检测环境
    setIsTauriEnv(isTauri());

    // 获取应用信息
    getAppInfo().then(setAppInfo);

    // 检查通知权限
    checkNotificationPermission();
  }, []);

  const checkNotificationPermission = async () => {
    const hasPermission = await requestNotificationPermission();
    setNotificationPermission(hasPermission);
  };

  // 功能 1: 系统通知
  const handleSendNotification = async () => {
    await sendNotification({
      title: 'Synesth 通知',
      body: '这是一个桌面应用通知测试！'
    });
  };

  // 功能 2: 保存文件
  const handleSaveFile = async () => {
    const data = {
      test: 'data',
      timestamp: new Date().toISOString()
    };

    const filePath = await saveFile({
      defaultPath: 'synesth_export.json',
      filters: [{
        name: 'JSON',
        extensions: ['json']
      }],
      content: JSON.stringify(data, null, 2)
    });

    if (filePath) {
      await sendNotification({
        title: '文件已保存',
        body: `已保存到: ${filePath}`
      });
    }
  };

  // 功能 3: 打开文件
  const handleOpenFile = async () => {
    const files = await openFile({
      filters: [{
        name: 'JSON',
        extensions: ['json']
      }],
      multiple: false
    });

    if (files.length > 0) {
      await sendNotification({
        title: '文件已选择',
        body: files[0]
      });
    }
  };

  // 功能 4: 窗口控制
  const handleMinimize = async () => {
    await windowControls.minimize();
  };

  const handleMaximize = async () => {
    await windowControls.toggleMaximize();
  };

  const handleClose = async () => {
    await windowControls.close();
  };

  const handleSetTitle = async () => {
    await windowControls.setTitle('Synesth - 测试标题');
    await sendNotification({
      title: '标题已更改',
      body: '窗口标题已更新'
    });
  };

  if (!isTauriEnv) {
    return (
      <div className="p-8 bg-zinc-900/50 rounded-2xl border border-zinc-800 max-w-2xl mx-auto">
        <div className="text-center">
          <Bell className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">非桌面环境</h2>
          <p className="text-zinc-400">
            Tauri 功能仅在桌面应用中可用。
            <br />
            请使用 <code className="px-2 py-1 bg-zinc-800 rounded text-purple-400">npm run tauri dev</code> 启动桌面应用。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 bg-zinc-900/50 rounded-2xl border border-zinc-800 max-w-4xl mx-auto">
      {/* 头部 */}
      <div className="mb-8 text-center">
        <h2 className="text-2xl font-bold text-white mb-2">Tauri 桌面应用功能</h2>
        <p className="text-zinc-400">
          {appInfo ? `${appInfo.name} v${appInfo.version} (${appInfo.platform})` : '加载中...'}
        </p>
      </div>

      {/* 功能网格 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* 系统通知 */}
        <div className="p-4 bg-zinc-800/50 rounded-xl border border-zinc-700">
          <div className="flex items-center gap-2 mb-3">
            <Bell className="w-5 h-5 text-purple-400" />
            <h3 className="font-semibold text-white">系统通知</h3>
          </div>
          <p className="text-sm text-zinc-400 mb-3">
            发送原生系统通知
          </p>
          <button
            onClick={handleSendNotification}
            disabled={!notificationPermission}
            className="w-full px-4 py-2 bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-lg hover:bg-purple-500/30 hover:border-purple-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {notificationPermission ? '发送通知' : '无通知权限'}
          </button>
        </div>

        {/* 保存文件 */}
        <div className="p-4 bg-zinc-800/50 rounded-xl border border-zinc-700">
          <div className="flex items-center gap-2 mb-3">
            <Save className="w-5 h-5 text-emerald-400" />
            <h3 className="font-semibold text-white">保存文件</h3>
          </div>
          <p className="text-sm text-zinc-400 mb-3">
            打开原生保存文件对话框
          </p>
          <button
            onClick={handleSaveFile}
            className="w-full px-4 py-2 bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 rounded-lg hover:bg-emerald-500/30 hover:border-emerald-500/50 transition-all"
          >
            保存 JSON 文件
          </button>
        </div>

        {/* 打开文件 */}
        <div className="p-4 bg-zinc-800/50 rounded-xl border border-zinc-700">
          <div className="flex items-center gap-2 mb-3">
            <FolderOpen className="w-5 h-5 text-blue-400" />
            <h3 className="font-semibold text-white">打开文件</h3>
          </div>
          <p className="text-sm text-zinc-400 mb-3">
            打开原生文件选择对话框
          </p>
          <button
            onClick={handleOpenFile}
            className="w-full px-4 py-2 bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-lg hover:bg-blue-500/30 hover:border-blue-500/50 transition-all"
          >
            打开 JSON 文件
          </button>
        </div>

        {/* 窗口控制 */}
        <div className="p-4 bg-zinc-800/50 rounded-xl border border-zinc-700">
          <div className="flex items-center gap-2 mb-3">
            <Minus className="w-5 h-5 text-amber-400" />
            <h3 className="font-semibold text-white">窗口控制</h3>
          </div>
          <p className="text-sm text-zinc-400 mb-3">
            控制桌面应用窗口
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleMinimize}
              className="flex-1 px-3 py-2 bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-lg hover:bg-amber-500/30 transition-all"
              title="最小化"
            >
              <Minus className="w-4 h-4 mx-auto" />
            </button>
            <button
              onClick={handleMaximize}
              className="flex-1 px-3 py-2 bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-lg hover:bg-amber-500/30 transition-all"
              title="最大化"
            >
              <Square className="w-4 h-4 mx-auto" />
            </button>
            <button
              onClick={handleSetTitle}
              className="flex-1 px-3 py-2 bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-lg hover:bg-amber-500/30 transition-all text-xs"
              title="设置标题"
            >
              标题
            </button>
          </div>
        </div>

      </div>

      {/* 底部提示 */}
      <div className="mt-6 p-4 bg-purple-500/10 border border-purple-500/30 rounded-xl">
        <p className="text-sm text-purple-300 text-center">
          💡 提示：所有功能在 Web 环境下会自动降级到替代方案
        </p>
      </div>
    </div>
  );
}

export default TauriFeaturesDemo;
