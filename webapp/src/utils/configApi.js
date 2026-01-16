/**
 * 用户配置管理 API
 * 用于保存和读取应用程序配置
 */

// 检测是否在 Tauri 环境中
// 使用多种检测方法以提高可靠性
const isTauri = typeof window !== 'undefined' && (
  window.__TAURI__ ||
  window.__TAURI_INTERNALS__ ||
  window.__TAURI_METADATA__ ||
  /Tauri/.test(navigator.userAgent)
);

// Tauri invoke 函数（延迟加载）
let tauriInvoke = null;

/**
 * 获取 Tauri invoke 函数
 */
async function getTauriInvoke() {
  if (tauriInvoke) return tauriInvoke;

  if (isTauri) {
    try {
      console.log('[ConfigAPI] 检测到 Tauri 环境，正在加载 API...');
      const tauriModule = await import('@tauri-apps/api/core');
      tauriInvoke = tauriModule.invoke;
      console.log('[ConfigAPI] Tauri API 加载成功');
      return tauriInvoke;
    } catch (error) {
      console.error('[ConfigAPI] Tauri API 加载失败:', error);
      console.error('[ConfigAPI] 错误详情:', error.message, error.stack);
      return null;
    }
  } else {
    console.log('[ConfigAPI] 未检测到 Tauri 环境，使用 Mock 模式');
  }

  return null;
}

/**
 * 调用 Tauri command 或使用 mock
 */
async function invoke(cmd, args) {
  const invokeFn = await getTauriInvoke();

  if (invokeFn) {
    // 在 Tauri 应用中，调用真实的 Rust 后端
    console.log(`[Tauri] 调用命令: ${cmd}`, args);
    return await invokeFn(cmd, args);
  } else {
    // 在浏览器中，使用 mock 实现
    console.log(`[Mock] 调用命令: ${cmd}`, args);

    // 模拟异步延迟
    await new Promise(resolve => setTimeout(resolve, 300));

    if (cmd === 'get_app_config') {
      // 从 localStorage 读取
      const saved = localStorage.getItem('app_config');
      return saved ? JSON.parse(saved) : {
        reaper_path: null,
        reaper_ip: null,
        export_dir: null,
        username: null,
        language: 'zh-CN'
      };
    }

    if (cmd === 'save_app_config') {
      // 保存到 localStorage
      localStorage.setItem('app_config', JSON.stringify(args.config));
      return null;
    }

    if (cmd === 'reset_app_config') {
      // 删除配置
      localStorage.removeItem('app_config');
      return null;
    }

    throw new Error(`未知命令: ${cmd}`);
  }
}

/**
 * 配置结构
 * @typedef {Object} AppConfig
 * @property {string|null} reaper_path - REAPER 安装路径
 * @property {string|null} reaper_ip - REAPER IP 地址
 * @property {string|null} export_dir - 导出目录路径
 * @property {string|null} username - 用户名
 * @property {string|null} language - 语言设置
 */

/**
 * 读取应用配置
 * @returns {Promise<AppConfig>} 配置对象
 */
export async function getAppConfig() {
  try {
    const config = await invoke('get_app_config');
    return config;
  } catch (error) {
    console.error('读取配置失败:', error);
    // 返回默认配置
    return {
      reaper_path: null,
      reaper_ip: null,
      export_dir: null,
      username: null,
      language: 'zh-CN'
    };
  }
}

/**
 * 保存应用配置
 * @param {AppConfig} config - 配置对象
 * @returns {Promise<void>}
 */
export async function saveAppConfig(config) {
  try {
    await invoke('save_app_config', { config });
    console.log('配置保存成功:', config);
  } catch (error) {
    console.error('保存配置失败:', error);
    throw error;
  }
}

/**
 * 重置配置为默认值
 * @returns {Promise<void>}
 */
export async function resetAppConfig() {
  try {
    await invoke('reset_app_config');
    console.log('配置已重置');
  } catch (error) {
    console.error('重置配置失败:', error);
    throw error;
  }
}

/**
 * 获取默认配置
 * @returns {AppConfig} 默认配置对象
 */
export function getDefaultConfig() {
  return {
    reaper_path: null,
    reaper_ip: null,
    export_dir: null,
    username: null,
    language: 'zh-CN'
  };
}

/**
 * 导出环境检测函数，用于调试
 */
export { isTauri };
