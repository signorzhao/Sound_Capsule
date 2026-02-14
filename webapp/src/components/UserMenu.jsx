/**
 * 用户菜单组件
 *
 * 显示当前用户信息、设置和注销按钮
 */

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { LogOut, User, ChevronDown, Settings, X, FolderOpen } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { getAppConfig, saveAppConfig } from '../utils/configApi';
import i18n, { configLangToI18n } from '../i18n';
import * as authApi from '../utils/authApi';
import { open } from '@tauri-apps/plugin-dialog';
import { invoke } from '@tauri-apps/api/core';
import './UserMenu.css';

const UserMenu = () => {
  const { t } = useTranslation();
  const { user, logout, accessToken } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [config, setConfig] = useState({
    export_dir: '',
    reaper_path: '',
    language: 'zh-CN'
  });
  const [saving, setSaving] = useState(false);
  const [originalExportDir, setOriginalExportDir] = useState(''); // 用于检测路径变化
  const [showPathChangeModal, setShowPathChangeModal] = useState(false); // 路径变更确认弹窗
  const [pathChangeComplete, setPathChangeComplete] = useState(false); // 路径变更完成状态

  // 加载配置
  const loadConfig = async () => {
    try {
      const saved = await getAppConfig();
      setConfig({
        export_dir: saved.export_dir || '',
        reaper_path: saved.reaper_path || '',
        language: saved.language || 'zh-CN'
      });
      // 保存原始导出目录，用于后续检测变化
      setOriginalExportDir(saved.export_dir || '');
    } catch (err) {
      console.error('加载配置失败:', err);
    }
  };

  // 选择导出目录
  const selectExportDir = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: t('userMenu.selectExportDirTitle')
      });

      if (selected) {
        setConfig(prev => ({ ...prev, export_dir: selected }));
      }
    } catch (err) {
      console.error('选择目录失败:', err);
    }
  };

  // 选择 REAPER 路径
  const selectReaperPath = async () => {
    try {
      const selected = await open({
        directory: false,
        multiple: false,
        title: t('userMenu.selectReaperFile')
      });

      if (selected) {
        setConfig(prev => ({ ...prev, reaper_path: selected }));
      }
    } catch (err) {
      console.error('选择文件失败:', err);
    }
  };

  // Phase G: 保存配置（带路径变更检测和重启）
  const handleSaveConfig = () => {
    // 检查路径是否变化
    const hasPathChanged = originalExportDir && originalExportDir !== config.export_dir;
    
    if (hasPathChanged) {
      // 路径已变更，显示确认 Modal（不执行任何操作）
      setShowPathChangeModal(true);
      return;
    }
    
    // 路径未变更，执行正常保存
    performNormalSave();
  };

  // 正常保存流程（路径未变更）
  const performNormalSave = async () => {
    setSaving(true);
    try {
      // 保存到 Tauri
      await saveAppConfig({
        export_dir: config.export_dir,
        reaper_path: config.reaper_path,
        language: config.language
      });

      // 若已登录，尝试同步语言到云端
      if (user && accessToken && config.language) {
        try {
          await authApi.updateUserProfile(accessToken, { language: config.language });
        } catch (e) {
          console.warn('云端 language 同步失败:', e?.message);
        }
      }
      
      // 同步到 Python 后端
      try {
        await fetch('http://localhost:5002/api/config/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            export_dir: config.export_dir,
            reaper_path: config.reaper_path
          })
        });
      } catch (e) {
        // 忽略错误
      }
      
      // 通知 App 组件
      window.dispatchEvent(new CustomEvent('config-updated', {
        detail: {
          export_dir: config.export_dir,
          reaper_path: config.reaper_path
        }
      }));
      
      setShowSettings(false);
      alert(t('userMenu.configSaved'));
    } catch (err) {
      alert(t('userMenu.saveFailed') + ': ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  // 路径变更确认后的处理（在 Modal 确认按钮中调用）
  const handlePathChangeConfirm = async () => {
    setSaving(true);
    
    try {
      // Step 1: 清空数据库
      console.log('[路径变更] 开始清空数据库...');
      const resetResponse = await fetch('http://localhost:5002/api/config/reset-local-db', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const resetResult = await resetResponse.json();
      
      if (!resetResult.success) {
        throw new Error(resetResult.error || 'Unknown error');
      }
      
      console.log('[路径变更] 数据库已清空');
      
      // Step 2: 保存新配置到 Python 后端
      console.log('[路径变更] 保存配置到 Python 后端...');
      await fetch('http://localhost:5002/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          export_dir: config.export_dir,
          reaper_path: config.reaper_path
        })
      });
      
      console.log('[路径变更] 配置已保存');
      
      // Step 3: 显示完成状态
      // ⚠️ 注意：在开发模式下，保存配置可能触发应用自动重启
      //           在生产模式下，需要用户手动重启
      setPathChangeComplete(true);
      
      console.log('[路径变更] 完成');
    } catch (error) {
      console.error('[路径变更] 失败:', error);
      setPathChangeComplete(true);
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    setLoading(true);
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('注销失败:', error);
      navigate('/login');
    } finally {
      setLoading(false);
      setIsOpen(false);
    }
  };

  const openSettings = () => {
    loadConfig();
    setShowSettings(true);
    setIsOpen(false);
  };

  if (!user) {
    return null;
  }

  return (
    <>
      <div className="user-menu-container">
        <button
          className="user-menu-button"
          onClick={() => setIsOpen(!isOpen)}
          disabled={loading}
        >
          <User className="user-icon" size={18} />
          <span className="user-name">
            {user.display_name || user.username}
          </span>
          <ChevronDown
            className={`chevron ${isOpen ? 'open' : ''}`}
            size={16}
          />
        </button>

        {isOpen && (
          <>
            <div
              className="user-menu-overlay"
              onClick={() => setIsOpen(false)}
            />
            <div className="user-menu-dropdown">
              <div className="user-info">
                <div className="user-avatar">
                  <User size={24} />
                </div>
                <div className="user-details">
                  <div className="user-display-name">
                    {user.display_name || user.username}
                  </div>
                  <div className="user-email">{user.email}</div>
                </div>
              </div>

              <div className="menu-divider" />

              <button
                className="menu-item"
                onClick={openSettings}
              >
                <Settings size={18} />
                <span>{t('userMenu.settings')}</span>
              </button>

              <button
                className="menu-item logout"
                onClick={handleLogout}
                disabled={loading}
              >
                <LogOut size={18} />
                <span>{loading ? t('userMenu.loggingOut') : t('userMenu.logout')}</span>
              </button>
            </div>
          </>
        )}
      </div>

      {/* 设置对话框 - 使用 Portal 渲染到 body 避免被父级 filter/overflow 裁剪 */}
      {showSettings && createPortal(
        <>
          <div className="settings-overlay" onClick={() => setShowSettings(false)} />
          <div className="settings-modal">
            <div className="settings-header">
              <h2>{t('userMenu.settings')}</h2>
              <button
                className="close-btn"
                onClick={() => setShowSettings(false)}
              >
                <X size={20} />
              </button>
            </div>

            <div className="settings-content">
              {/* 导出目录设置 */}
              <div className="setting-item">
                <label className="setting-label">
                  <FolderOpen size={18} />
                  <span>{t('userMenu.exportDir')}</span>
                </label>
                <div className="setting-input-group">
                  <input
                    type="text"
                    className="setting-input"
                    placeholder={t('userMenu.exportDirPlaceholder')}
                    value={config.export_dir}
                    onChange={(e) => setConfig(prev => ({ ...prev, export_dir: e.target.value }))}
                    readOnly
                  />
                  <button
                    className="setting-browse-btn"
                    onClick={selectExportDir}
                  >
                    {t('userMenu.browse')}
                  </button>
                </div>
                <p className="setting-hint">{t('userMenu.exportDirHint')}</p>
              </div>

              {/* REAPER 路径设置 */}
              <div className="setting-item">
                <label className="setting-label">
                  <Settings size={18} />
                  <span>{t('userMenu.reaperPath')}</span>
                </label>
                <div className="setting-input-group">
                  <input
                    type="text"
                    className="setting-input"
                    placeholder={t('userMenu.reaperPathPlaceholder')}
                    value={config.reaper_path}
                    onChange={(e) => setConfig(prev => ({ ...prev, reaper_path: e.target.value }))}
                    readOnly
                  />
                  <button
                    className="setting-browse-btn"
                    onClick={selectReaperPath}
                  >
                    {t('userMenu.browse')}
                  </button>
                </div>
                <p className="setting-hint">{t('userMenu.reaperPathHint')}</p>
              </div>

              {/* 语言设置 - 分段控件，与整体界面风格一致 */}
              <div className="setting-item">
                <label className="setting-label">
                  <span>{t('settings.language')}</span>
                </label>
                <div className="setting-lang-toggle">
                  <button
                    type="button"
                    className={`lang-option ${config.language === 'zh-CN' ? 'active' : ''}`}
                    onClick={() => {
                      setConfig(prev => ({ ...prev, language: 'zh-CN' }));
                      i18n.changeLanguage(configLangToI18n('zh-CN'));
                    }}
                  >
                    {t('settings.languageZh')}
                  </button>
                  <button
                    type="button"
                    className={`lang-option ${config.language === 'en-US' ? 'active' : ''}`}
                    onClick={() => {
                      setConfig(prev => ({ ...prev, language: 'en-US' }));
                      i18n.changeLanguage(configLangToI18n('en-US'));
                    }}
                  >
                    {t('settings.languageEn')}
                  </button>
                </div>
              </div>
            </div>

            <div className="settings-footer">
              <button
                className="cancel-btn"
                onClick={() => setShowSettings(false)}
                disabled={saving}
              >
                {t('common.cancel')}
              </button>
              <button
                className="save-btn"
                onClick={handleSaveConfig}
                disabled={saving}
              >
                {saving ? t('common.saving') : t('common.save')}
              </button>
            </div>
          </div>
        </>,
        document.body
      )}

      {/* 路径变更确认 Modal - 使用 Portal 渲染到 body */}
      {showPathChangeModal && createPortal(
        <>
          <div className="settings-overlay" onClick={() => !pathChangeComplete && setShowPathChangeModal(false)} />
          <div className="path-change-modal">
            {!pathChangeComplete ? (
              // 确认界面
              <>
                <div className="modal-icon warning">⚠️</div>
                <h2 className="modal-title">{t('userMenu.pathChangeWarning')}</h2>
                <div className="modal-content">
                  <p>{t('userMenu.pathChangeDesc')}</p>
                  <ul className="modal-list">
                    <li>{t('userMenu.pathChangeItem1')}</li>
                    <li>{t('userMenu.pathChangeItem2')}</li>
                    <li>{t('userMenu.pathChangeItem3')}</li>
                    <li>{t('userMenu.pathChangeItem4')}</li>
                  </ul>
                  <div className="path-display">
                    <div className="path-label">{t('userMenu.newPath')}</div>
                    <div className="path-value">{config.export_dir}</div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button
                    className="cancel-btn"
                    onClick={() => setShowPathChangeModal(false)}
                    disabled={saving}
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    className="confirm-btn danger"
                    onClick={handlePathChangeConfirm}
                    disabled={saving}
                  >
                    {saving ? t('userMenu.processing') : t('userMenu.confirmChange')}
                  </button>
                </div>
              </>
            ) : (
              // 完成界面
              <>
                <div className="modal-icon success">✅</div>
                <h2 className="modal-title">{t('userMenu.pathChangeComplete')}</h2>
                <div className="modal-content">
                  <div className="success-message">
                    <p><strong>✓ {t('userMenu.pathChangeCompleteDesc')}</strong></p>
                    <p><strong>✓ {t('userMenu.pathChangeConfigSaved')}</strong></p>
                  </div>
                  <div className="path-display">
                    <div className="path-label">{t('userMenu.newPath')}</div>
                    <div className="path-value">{config.export_dir}</div>
                  </div>
                  <div className="restart-instructions">
                    <p><strong>⚠️ {t('userMenu.pathChangeRestartHint')}</strong></p>
                    <div className="info-box">
                      <p>{t('userMenu.pathChangeRestartText')}</p>
                      <p>{t('userMenu.pathChangeSyncText')}</p>
                    </div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button
                    className="confirm-btn success"
                    onClick={() => {
                      setShowPathChangeModal(false);
                      setPathChangeComplete(false);
                      setShowSettings(false);
                    }}
                  >
                    {t('userMenu.gotIt')}
                  </button>
                </div>
              </>
            )}
          </div>
        </>,
        document.body
      )}

      <style>{`
        .settings-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          z-index: 1000;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .settings-modal {
          position: fixed;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          max-height: calc(100vh - 40px);
          overflow-y: auto;
          background: #1e1b4b;
          border: 1px solid #312e81;
          border-radius: 12px;
          padding: 24px;
          width: 90%;
          max-width: 500px;
          z-index: 1001;
          box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
        }

        .settings-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .settings-header h2 {
          margin: 0;
          font-size: 20px;
          font-weight: 600;
          color: #fff;
        }

        .close-btn {
          background: transparent;
          border: none;
          color: #64748b;
          cursor: pointer;
          padding: 4px;
          border-radius: 6px;
          transition: all 0.2s;
        }

        .close-btn:hover {
          background: #312e81;
          color: #fff;
        }

        .settings-content {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .setting-item {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .setting-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 14px;
          font-weight: 500;
          color: #e2e8f0;
        }

        .setting-label svg {
          color: #8b5cf6;
        }

        .setting-input-group {
          display: flex;
          gap: 8px;
        }

        .setting-input {
          flex: 1;
          padding: 10px 12px;
          background: #0f172a;
          border: 1px solid #312e81;
          border-radius: 6px;
          color: #e2e8f0;
          font-size: 14px;
          cursor: pointer;
        }

        .setting-input:focus {
          outline: none;
          border-color: #8b5cf6;
        }

        .setting-input::placeholder {
          color: #475569;
        }

        .setting-browse-btn {
          padding: 10px 16px;
          background: #312e81;
          border: 1px solid #4338ca;
          border-radius: 6px;
          color: #e2e8f0;
          font-size: 14px;
          cursor: pointer;
          transition: all 0.2s;
          white-space: nowrap;
        }

        .setting-browse-btn:hover {
          background: #4338ca;
        }

        .setting-hint {
          margin: 0;
          font-size: 12px;
          color: #64748b;
        }

        .setting-lang-toggle {
          display: flex;
          background: #0f172a;
          padding: 4px;
          border-radius: 8px;
          border: 1px solid #312e81;
          gap: 0;
        }

        .lang-option {
          flex: 1;
          padding: 10px 16px;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          color: #94a3b8;
          background: transparent;
          cursor: pointer;
          transition: all 0.2s;
        }

        .lang-option:hover {
          color: #e2e8f0;
        }

        .lang-option.active {
          background: #312e81;
          color: #fff;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }

        .settings-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          margin-top: 24px;
          padding-top: 24px;
          border-top: 1px solid #312e81;
        }

        .cancel-btn,
        .save-btn {
          padding: 10px 20px;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .cancel-btn {
          background: transparent;
          border: 1px solid #312e81;
          color: #e2e8f0;
        }

        .cancel-btn:hover {
          background: #312e81;
        }

        .save-btn {
          background: #8b5cf6;
          border: 1px solid #7c3aed;
          color: #fff;
        }

        .save-btn:hover:not(:disabled) {
          background: #7c3aed;
        }

        .save-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        /* 路径变更确认 Modal 样式 */
        .path-change-modal {
          position: fixed;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          background: #1e1b4b;
          border: 2px solid #f59e0b;
          border-radius: 12px;
          padding: 32px;
          width: 90%;
          max-width: 480px;
          z-index: 1002;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
        }

        .modal-icon {
          font-size: 48px;
          text-align: center;
          margin-bottom: 16px;
        }

        .modal-icon.warning {
          filter: drop-shadow(0 0 8px rgba(245, 158, 11, 0.5));
        }

        .modal-icon.success {
          filter: drop-shadow(0 0 8px rgba(34, 197, 94, 0.5));
        }

        .modal-title {
          margin: 0 0 20px 0;
          font-size: 20px;
          font-weight: 600;
          color: #fff;
          text-align: center;
        }

        .modal-content {
          color: #e2e8f0;
          font-size: 14px;
          line-height: 1.6;
        }

        .modal-content p {
          margin: 0 0 12px 0;
        }

        .modal-list {
          margin: 12px 0;
          padding-left: 24px;
        }

        .modal-list li {
          margin: 8px 0;
          color: #cbd5e1;
        }

        .path-display {
          margin-top: 16px;
          padding: 12px;
          background: #0f172a;
          border: 1px solid #312e81;
          border-radius: 6px;
        }

        .path-label {
          font-size: 12px;
          color: #94a3b8;
          margin-bottom: 4px;
        }

        .path-value {
          font-size: 13px;
          color: #8b5cf6;
          font-family: monospace;
          word-break: break-all;
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          margin-top: 24px;
        }

        .confirm-btn {
          padding: 10px 20px;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .confirm-btn.danger {
          background: #f59e0b;
          border: 1px solid #d97706;
          color: #fff;
        }

        .confirm-btn.danger:hover:not(:disabled) {
          background: #d97706;
        }

        .confirm-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .confirm-btn.success {
          background: #22c55e;
          border: 1px solid #16a34a;
          color: #fff;
        }

        .confirm-btn.success:hover:not(:disabled) {
          background: #16a34a;
        }

        .success-message {
          margin: 16px 0;
          padding: 16px;
          background: rgba(34, 197, 94, 0.1);
          border: 1px solid rgba(34, 197, 94, 0.3);
          border-radius: 6px;
        }

        .success-message p {
          margin: 8px 0;
          color: #86efac;
        }

        .restart-instructions {
          margin-top: 20px;
          padding: 16px;
          background: rgba(245, 158, 11, 0.1);
          border: 1px solid rgba(245, 158, 11, 0.3);
          border-radius: 6px;
        }

        .restart-instructions p {
          margin: 0 0 12px 0;
          color: #fbbf24;
        }

        .info-box {
          margin: 12px 0;
          padding: 12px;
          background: rgba(59, 130, 246, 0.1);
          border: 1px solid rgba(59, 130, 246, 0.3);
          border-radius: 6px;
        }

        .info-box p {
          margin: 6px 0;
          color: #93c5fd;
        }

        .restart-steps {
          margin: 8px 0;
          padding-left: 24px;
          color: #e2e8f0;
        }

        .restart-steps li {
          margin: 8px 0;
        }

        kbd {
          display: inline-block;
          padding: 2px 6px;
          background: #0f172a;
          border: 1px solid #475569;
          border-radius: 3px;
          font-size: 12px;
          font-family: monospace;
          color: #f1f5f9;
        }

        .code-block {
          margin: 8px 0;
          padding: 12px;
          background: #0f172a;
          border: 1px solid #312e81;
          border-radius: 6px;
          font-family: monospace;
          font-size: 12px;
          color: #8b5cf6;
          word-break: break-all;
          white-space: pre-wrap;
        }
      `}</style>
    </>
  );
};

export default UserMenu;
