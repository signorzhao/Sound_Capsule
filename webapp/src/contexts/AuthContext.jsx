/**
 * 认证上下文
 *
 * 提供用户认证状态和登录/注册/注销功能
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import * as authApi from '../utils/authApi';
import i18n, { configLangToI18n } from '../i18n';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // 初始化：从 localStorage 加载 token
  useEffect(() => {
    const initAuth = async () => {
      const storedAccessToken = localStorage.getItem('access_token');
      const storedRefreshToken = localStorage.getItem('refresh_token');

      if (storedAccessToken && storedRefreshToken) {
        setAccessToken(storedAccessToken);
        try {
          // 优先验证 access token
          const currentUser = await authApi.getCurrentUser(storedAccessToken);
          setUser(currentUser);
        } catch {
          try {
            // access token 过期时，尝试刷新
            const refreshed = await authApi.refreshAccessToken(storedRefreshToken);
            const newAccessToken = refreshed.access_token;
            setAccessToken(newAccessToken);
            localStorage.setItem('access_token', newAccessToken);
            const currentUser = await authApi.getCurrentUser(newAccessToken);
            setUser(currentUser);
          } catch {
            // 刷新失败，清除存储
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            setAccessToken(null);
          }
        } finally {
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  // 当用户信息加载后，若 profile 有 language 则应用
  useEffect(() => {
    if (user?.language) {
      const lang = configLangToI18n(user.language);
      if (i18n.language !== lang) {
        i18n.changeLanguage(lang);
      }
    }
  }, [user?.language]);

  /**
   * 周期性刷新 Token（防止过期）
   */
  useEffect(() => {
    const refreshIntervalMs = 25 * 60 * 1000; // 25 分钟
    let timer = null;

    const scheduleRefresh = () => {
      if (timer) clearInterval(timer);
      timer = setInterval(async () => {
        try {
          await refreshAccessToken();
        } catch (err) {
          console.warn('定时刷新失败:', err?.message || err);
        }
      }, refreshIntervalMs);
    };

    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      scheduleRefresh();
    }

    return () => {
      if (timer) clearInterval(timer);
    };
  }, []);

  /**
   * 用户注册
   */
  const register = async (username, email, password) => {
    setError(null);
    setLoading(true);

    try {
      const result = await authApi.register(username, email, password);

      // 保存 tokens
      setAccessToken(result.tokens.access_token);
      localStorage.setItem('access_token', result.tokens.access_token);
      localStorage.setItem('refresh_token', result.tokens.refresh_token);

      // 保存用户信息
      setUser(result.user);

      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  /**
   * 用户登录
   */
  const login = async (login, password) => {
    setError(null);
    setLoading(true);

    try {
      const result = await authApi.login(login, password);

      // 保存 tokens
      setAccessToken(result.tokens.access_token);
      localStorage.setItem('access_token', result.tokens.access_token);
      localStorage.setItem('refresh_token', result.tokens.refresh_token);

      // 保存用户信息
      setUser(result.user);

      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  /**
   * 用户注销
   */
  const logout = async () => {
    setError(null);
    setLoading(true);

    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      // 无论 API 调用成功与否，都清除本地状态
      setUser(null);
      setAccessToken(null);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setLoading(false);
    }
  };

  /**
   * 刷新 Access Token
   */
  const refreshAccessToken = async () => {
    const refreshToken = localStorage.getItem('refresh_token');

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const result = await authApi.refreshAccessToken(refreshToken);

      const newAccessToken = result.access_token;
      setAccessToken(newAccessToken);
      localStorage.setItem('access_token', newAccessToken);

      return newAccessToken;
    } catch (err) {
      // Token 刷新失败，需要重新登录
      await logout();
      throw err;
    }
  };

  /**
   * 更新用户信息
   */
  const updateUser = async (updates) => {
    setError(null);
    setLoading(true);

    try {
      const updatedUser = await authApi.updateUserProfile(accessToken, updates);
      setUser(updatedUser);
      return updatedUser;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  /**
   * 修改密码
   */
  const changePassword = async (oldPassword, newPassword) => {
    setError(null);
    setLoading(true);

    try {
      await authApi.changePassword(accessToken, oldPassword, newPassword);
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const value = {
    user,
    accessToken,
    loading,
    error,
    isAuthenticated: !!user,
    register,
    login,
    logout,
    refreshAccessToken,
    updateUser,
    changePassword
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
