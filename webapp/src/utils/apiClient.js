/**
 * API 客户端
 *
 * 提供自动处理认证和 token 刷新的 fetch 封装
 * API 基地址可从应用配置 api_base_url 读取（开发/私有部署时连到本机或局域网服务器）
 */

const DEFAULT_API_BASE = 'http://localhost:5002';

/** 从配置注入的基地址（App 启动时从 get_app_config 写入） */
function getApiBaseUrl() {
  return (typeof window !== 'undefined' && window.__API_BASE_URL) || DEFAULT_API_BASE;
}

/** 拼出完整 API URL（如 getApiUrl('/api/prisms/field')） */
export function getApiUrl(path) {
  const base = getApiBaseUrl().replace(/\/$/, '');
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${base}${p}`;
}

/** 供 App 启动时注入配置用 */
export function setApiBaseFromConfig(apiBaseUrl) {
  if (typeof window !== 'undefined') {
    window.__API_BASE_URL = apiBaseUrl && apiBaseUrl.trim() ? apiBaseUrl.trim().replace(/\/$/, '') : DEFAULT_API_BASE;
  }
}

const API_BASE_URL = DEFAULT_API_BASE + '/api';

/**
 * 刷新 access token
 */
async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('refresh_token');

  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  const response = await fetch(getApiUrl('/api/auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Token 刷新失败');
  }

  // 保存新的 access token
  const newAccessToken = data.data.access_token;
  localStorage.setItem('access_token', newAccessToken);

  return newAccessToken;
}

/**
 * 正在刷新 token 的 Promise（防止并发刷新）
let refreshingPromise = null;

/**
 * 带认证的 fetch 封装
 *
 * 自动处理：
 * 1. 添加 Authorization header
 * 2. 捕获 401 错误并刷新 token
 * 3. 使用新 token 重试请求
 *
 * @param {string} url - 请求 URL
 * @param {object} options - fetch 选项
 * @returns {Promise<Response>}
 */
export async function authFetch(url, options = {}) {
  // 获取当前 token
  let accessToken = localStorage.getItem('access_token');
  const refreshToken = localStorage.getItem('refresh_token');

  // 如果没有 access token，但有 refresh token，先尝试刷新
  if (!accessToken && refreshToken) {
    try {
      if (refreshingPromise) {
        await refreshingPromise;
        accessToken = localStorage.getItem('access_token');
      } else {
        refreshingPromise = refreshAccessToken();
        accessToken = await refreshingPromise;
        refreshingPromise = null;
      }
    } catch (error) {
      console.error('Token 刷新失败:', error);
    }
  }

  // 如果仍没有 token，直接发送请求（可能不需要认证）
  if (!accessToken) {
    return fetch(url, options);
  }

  // 添加 Authorization header
  const authOptions = {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`,
    },
  };

  // 发送请求
  let response = await fetch(url, authOptions);

  // 如果遇到 401 错误，尝试刷新 token 并重试
  if (response.status === 401) {
    try {
      // 如果已经在刷新中，等待刷新完成
      if (refreshingPromise) {
        await refreshingPromise;
        accessToken = localStorage.getItem('access_token');
      } else {
        // 开始刷新 token
        refreshingPromise = refreshAccessToken();
        accessToken = await refreshingPromise;
        refreshingPromise = null;
      }

      // 使用新 token 重试请求
      const retryOptions = {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${accessToken}`,
        },
      };

      response = await fetch(url, retryOptions);
    } catch (error) {
      console.error('Token 刷新失败:', error);

      // 刷新失败，清除 tokens 并跳转到登录页
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');

      // 触发登出事件
      window.dispatchEvent(new CustomEvent('auth-failed'));

      throw error;
    }
  }

  return response;
}

/**
 * 导出 base URL 供其他地方使用（注意：优先用 getApiUrl(path) 以尊重配置）
 */
export { API_BASE_URL, getApiBaseUrl, getApiUrl, setApiBaseFromConfig };
