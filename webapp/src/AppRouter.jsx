/**
 * AppRouter - 主路由配置
 *
 * 集成 React Router 和认证系统
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { SyncProvider } from './contexts/SyncContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import App from './App';

/**
 * 主路由组件
 *
 * 路由结构:
 * - /login - 登录页面（公开）
 * - /register - 注册页面（公开）
 * - / - 主应用（需要认证）
 * - * - 其他路由重定向到首页或登录页
 */
function AppRouter() {
  return (
    <AuthProvider>
      <SyncProvider>
        <Routes>
          {/* 公开路由 - 登录和注册 */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* 受保护的路由 - 需要登录 */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <App />
              </ProtectedRoute>
            }
          />

          {/* 其他路由重定向 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </SyncProvider>
    </AuthProvider>
  );
}

export default AppRouter;
