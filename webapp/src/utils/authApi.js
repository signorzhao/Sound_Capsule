/**
 * 认证相关 API 调用（使用可配置 API 基地址）
 */

import { getApiUrl } from './apiClient';

/**
 * 用户注册
 */
export async function register(username, email, password) {
  const response = await fetch(getApiUrl('/api/auth/register'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password })
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '注册失败');
  }

  return data.data;
}

/**
 * 用户登录
 */
export async function login(login, password) {
  const response = await fetch(getApiUrl('/api/auth/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password })
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '登录失败');
  }

  return data.data;
}

/**
 * 刷新 Token
 */
export async function refreshAccessToken(refreshToken) {
  const response = await fetch(getApiUrl('/api/auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Token 刷新失败');
  }

  return data.data;
}

/**
 * 用户注销
 */
export async function logout(refreshToken) {
  const response = await fetch(getApiUrl('/api/auth/logout'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '注销失败');
  }

  return data;
}

/**
 * 获取当前用户信息
 */
export async function getCurrentUser(accessToken) {
  const response = await fetch(getApiUrl('/api/auth/me'), {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    }
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '获取用户信息失败');
  }

  return data.data.user;
}

/**
 * 更新用户信息
 */
export async function updateUserProfile(accessToken, updates) {
  const response = await fetch(getApiUrl('/api/auth/me'), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    },
    body: JSON.stringify(updates)
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '更新用户信息失败');
  }

  return data.data.user;
}

/**
 * 修改密码
 */
export async function changePassword(accessToken, oldPassword, newPassword) {
  const response = await fetch(getApiUrl('/api/auth/password'), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    },
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword
    })
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '修改密码失败');
  }

  return data;
}
