/**
 * 登录页面组件
 */

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './LoginPage.css';

const LoginPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    login: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    // 过滤非 ASCII 字符，避免中文输入法干扰（兜底方案）
    let filtered = value;
    if (name === 'login') {
      filtered = value.replace(/[^a-zA-Z0-9@._+-]/g, '');
    } else if (name === 'password') {
      filtered = value.replace(/[^\x20-\x7E]/g, '');
    }
    setFormData(prev => ({ ...prev, [name]: filtered }));
    setError(''); // 清除错误提示
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(formData.login, formData.password);
      // 登录成功，导航到主页
      navigate('/');
    } catch (err) {
      setError(err.message || t('auth.loginFailed'));
    } finally {
      setLoading(false);
    }
  };

  const goToRegister = () => {
    navigate('/register');
  };

  return (
    <div className="auth-container">
      {/* 星空背景 */}
      <div className="starfield" aria-hidden="true" />
      {/* 背景装饰 */}
      <div className="auth-bg-blobs" aria-hidden="true" />
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">SOUND<span className="text-indigo-400">CAPSULE</span></h1>
          <p className="auth-subtitle">{t('auth.loginSubtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && (
            <div className="auth-error">
              {error}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="login">{t('auth.usernameOrEmail')}</label>
            <input
              type="text"
              id="login"
              name="login"
              value={formData.login}
              onChange={handleChange}
              onCompositionStart={(e) => e.preventDefault()}
              required
              autoFocus
              autoComplete="username"
              placeholder={t('auth.usernameOrEmailPlaceholder')}
              lang="en"
              inputMode="latin"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">{t('auth.password')}</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              onCompositionStart={(e) => e.preventDefault()}
              required
              autoComplete="current-password"
              placeholder={t('auth.passwordPlaceholder')}
              lang="en"
              inputMode="latin"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
            />
          </div>

          <button
            type="submit"
            className="auth-button"
            disabled={loading}
          >
            {loading ? t('auth.loggingIn') : t('auth.login')}
          </button>

          <div className="auth-footer">
            <p>
              {t('auth.noAccount')}{' '}
              <button type="button" onClick={goToRegister} className="link-button">
                {t('auth.registerNow')}
              </button>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
