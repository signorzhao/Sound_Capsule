/**
 * 注册页面组件
 */

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './LoginPage.css';

const RegisterPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { register } = useAuth();

  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    // 过滤非 ASCII 字符，避免中文输入法干扰（兜底方案）
    let filtered = value;
    if (name === 'username') {
      filtered = value.replace(/[^a-zA-Z0-9_]/g, '');
    } else if (name === 'email') {
      filtered = value.replace(/[^a-zA-Z0-9@._+-]/g, '');
    } else if (name === 'password' || name === 'confirmPassword') {
      filtered = value.replace(/[^\x20-\x7E]/g, '');
    }
    setFormData(prev => ({ ...prev, [name]: filtered }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // 验证密码
    if (formData.password !== formData.confirmPassword) {
      setError(t('auth.passwordMismatch'));
      return;
    }

    // 验证密码强度
    if (formData.password.length < 8) {
      setError(t('auth.passwordTooShort'));
      return;
    }

    const hasLetter = /[a-zA-Z]/.test(formData.password);
    const hasDigit = /[0-9]/.test(formData.password);
    if (!hasLetter || !hasDigit) {
      setError(t('auth.passwordRequirements'));
      return;
    }

    setLoading(true);

    try {
      await register(formData.username, formData.email, formData.password);
      // 注册成功，导航到主页
      navigate('/');
    } catch (err) {
      setError(err.message || t('auth.registerFailed'));
    } finally {
      setLoading(false);
    }
  };

  const goToLogin = () => {
    navigate('/login');
  };

  return (
    <div className="auth-container">
      <div className="starfield" aria-hidden="true" />
      <div className="auth-bg-blobs" aria-hidden="true" />
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">SOUND<span className="text-indigo-400">CAPSULE</span></h1>
          <p className="auth-subtitle">{t('auth.registerSubtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && (
            <div className="auth-error">
              {error}
            </div>
          )}

          <div className="form-hints">
            <h4>{t('auth.passwordRequirementsTitle')}</h4>
            <ul>
              <li>{t('auth.passwordReq1')}</li>
              <li>{t('auth.passwordReq2')}</li>
            </ul>
          </div>

          <div className="form-group">
            <label htmlFor="username">{t('auth.username')}</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              onCompositionStart={(e) => e.preventDefault()}
              required
              autoFocus
              autoComplete="username"
              placeholder={t('auth.usernamePlaceholder')}
              pattern="[a-zA-Z0-9_]{3,30}"
              lang="en"
              inputMode="latin"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">{t('auth.email')}</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              onCompositionStart={(e) => e.preventDefault()}
              required
              autoComplete="email"
              placeholder={t('auth.emailPlaceholder')}
              lang="en"
              inputMode="email"
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
              autoComplete="new-password"
              placeholder={t('auth.passwordPlaceholderRegister')}
              minLength={8}
              lang="en"
              inputMode="latin"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">{t('auth.confirmPassword')}</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              onCompositionStart={(e) => e.preventDefault()}
              required
              autoComplete="new-password"
              placeholder={t('auth.confirmPasswordPlaceholder')}
              minLength={8}
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
            {loading ? t('auth.registering') : t('auth.register')}
          </button>

          <div className="auth-footer">
            <p>
              {t('auth.hasAccount')}{' '}
              <button type="button" onClick={goToLogin} className="link-button">
                {t('auth.loginNow')}
              </button>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default RegisterPage;
