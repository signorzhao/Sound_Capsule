/**
 * Tauri API 工具函数
 * 封装常用的桌面应用原生功能
 */

// 检测是否在 Tauri 环境中运行
export const isTauri = () => {
  return '__TAURI__' in window;
};

/**
 * 系统通知
 * @param {Object} options - 通知选项
 * @param {string} options.title - 标题
 * @param {string} options.body - 内容
 */
export const sendNotification = async (options) => {
  if (!isTauri()) {
    // Web 环境回退
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(options.title, { body: options.body });
    }
    return;
  }

  try {
    const { notification } = await import('@tauri-apps/plugin-notification');
    await notification.send({
      title: options.title,
      body: options.body,
    });
  } catch (error) {
    console.error('Failed to send notification:', error);
  }
};

/**
 * 文件保存对话框
 * @param {Object} options - 保存选项
 * @param {string} options.defaultPath - 默认文件名
 * @param {Array} options.filters - 文件类型过滤
 * @returns {Promise<string|null>} 文件路径或null
 */
export const saveFile = async (options = {}) => {
  if (!isTauri()) {
    // Web 环境回退：使用 download 属性
    const link = document.createElement('a');
    link.href = options.content || '';
    link.download = options.defaultPath || 'download';
    link.click();
    return null;
  }

  try {
    const { save } = await import('@tauri-apps/plugin-dialog');
    const { writeTextFile } = await import('@tauri-apps/plugin-fs');

    const filePath = await save({
      defaultPath: options.defaultPath || '',
      filters: options.filters || []
    });

    if (filePath && options.content) {
      await writeTextFile(filePath, options.content);
    }

    return filePath;
  } catch (error) {
    console.error('Failed to save file:', error);
    return null;
  }
};

/**
 * 文件打开对话框
 * @param {Object} options - 打开选项
 * @param {Array} options.filters - 文件类型过滤
 * @param {boolean} options.multiple - 是否允许多选
 * @returns {Promise<string[]>} 文件路径数组
 */
export const openFile = async (options = {}) => {
  if (!isTauri()) {
    // Web 环境回退：使用 file input
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.multiple = options.multiple || false;
      input.accept = options.filters?.map(f => `.${f.extensions[0]}`).join(',') || '*.*';
      input.onchange = (e) => {
        const files = Array.from(e.target.files);
        resolve(files.map(f => f.path || f.name));
      };
      input.click();
    });
  }

  try {
    const { open } = await import('@tauri-apps/plugin-dialog');

    const selected = await open({
      multiple: options.multiple || false,
      filters: options.filters || []
    });

    return selected ? [selected] : [];
  } catch (error) {
    console.error('Failed to open file:', error);
    return [];
  }
};

/**
 * 窗口控制
 */
export const windowControls = {
  /**
   * 最小化窗口
   */
  minimize: async () => {
    if (!isTauri()) return;
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      await getCurrentWindow().minimize();
    } catch (error) {
      console.error('Failed to minimize window:', error);
    }
  },

  /**
   * 最大化/还原窗口
   */
  toggleMaximize: async () => {
    if (!isTauri()) return;
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      const window = getCurrentWindow();
      if (await window.isMaximized()) {
        await window.unmaximize();
      } else {
        await window.maximize();
      }
    } catch (error) {
      console.error('Failed to toggle maximize:', error);
    }
  },

  /**
   * 关闭窗口
   */
  close: async () => {
    if (!isTauri()) return;
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      await getCurrentWindow().close();
    } catch (error) {
      console.error('Failed to close window:', error);
    }
  },

  /**
   * 设置窗口标题
   * @param {string} title - 标题
   */
  setTitle: async (title) => {
    if (!isTauri()) {
      document.title = title;
      return;
    }
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      await getCurrentWindow().setTitle(title);
    } catch (error) {
      console.error('Failed to set title:', error);
    }
  },

  /**
   * 设置窗口大小
   * @param {Object} size - 尺寸
   * @param {number} size.width - 宽度
   * @param {number} size.height - 高度
   */
  setSize: async (size) => {
    if (!isTauri()) return;
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      const { LogicalSize } = await import('@tauri-apps/api/dpi');
      await getCurrentWindow().setSize(new LogicalSize(size.width, size.height));
    } catch (error) {
      console.error('Failed to set size:', error);
    }
  }
};

/**
 * 获取应用信息
 * @returns {Promise<Object>} 应用信息
 */
export const getAppInfo = async () => {
  if (!isTauri()) {
    return {
      name: 'Synesth',
      version: '1.0.0',
      platform: 'web'
    };
  }

  try {
    const { getVersion, getName } = await import('@tauri-apps/api/app');

    const appName = await getName().catch(() => 'Synesth');
    const appVersion = await getVersion().catch(() => '1.0.0');

    // 检测平台（简化版本）
    let platform = 'unknown';
    if (navigator.userAgent.includes('Mac')) {
      platform = 'macos';
    } else if (navigator.userAgent.includes('Windows')) {
      platform = 'windows';
    } else if (navigator.userAgent.includes('Linux')) {
      platform = 'linux';
    }

    return {
      name: appName,
      version: appVersion,
      platform
    };
  } catch (error) {
    console.error('Failed to get app info:', error);
    return {
      name: 'Synesth',
      version: '1.0.0',
      platform: 'unknown'
    };
  }
};

/**
 * 请求通知权限
 * @returns {Promise<boolean>} 是否授权
 */
export const requestNotificationPermission = async () => {
  if (!isTauri()) {
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      return permission === 'granted';
    }
    return false;
  }

  try {
    // Tauri 通知通常不需要权限，但这里保留接口
    return true;
  } catch (error) {
    console.error('Failed to request notification permission:', error);
    return false;
  }
};
